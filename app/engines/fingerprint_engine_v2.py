"""Minutiae-based fingerprint engine â€” replaces AKAZE pipeline.

Algorithm (single pass via analyze()):
  1. Resize to 400Ã—500 px (standard size for consistent minutiae counts)
  2. CLAHE contrast enhancement
  3. Gabor ridge enhancement â€” 8 orientations tuned to fingerprint ridge frequency
  4. Variance-based segmentation mask (foreground = ridge area)
  5. Adaptive binarization
  6. Zhang-Suen skeletonization via scikit-image (OpenCV fallback if unavailable)
  7. Vectorised crossing-number minutiae detection (ridge endings + bifurcations)
  8. Deduplication of spurious nearby minutiae
  9. Alignment-based matching (rotation-tolerant by design â€” no multi-angle variants needed)

Why this beats AKAZE:
  - Non-fingerprint images (faces, diagrams) produce 0-8 minutiae â†’ score â‰ˆ 0 â†’ auto-rejected
  - False-positive rate is controlled by biological structure, not generic keypoint density
  - Rotation is handled internally in the matcher via rigid alignment on anchor pairs
  - Backward-compatible: old AKAZE templates matched via _akaze_match() fallback
"""
import math

import cv2
import numpy as np

try:
    from skimage.morphology import skeletonize as _skel_fn
    _SKIMAGE_OK = True
except ImportError:
    _SKIMAGE_OK = False

# â”€â”€ Tuning constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_W, _H        = 400, 500      # standard processing size (pixels)
_N_ORI        = 8             # Gabor filter orientations
_BLOCK        = 16            # segmentation / local-variance block size
_BORDER       = 14            # ignore minutiae within this many pixels of edge
_MIN_MINUTIAE = 15            # below this â†’ not a fingerprint
_N_ANCHORS    = 8             # how many anchor pairs to try per match
_POS_THRESH   = 20.0          # px â€” position tolerance for minutia match
_ANG_THRESH   = 25.0          # deg â€” angle tolerance for minutia match
_MIN_DIST     = 8.0           # px â€” deduplicate minutiae closer than this


class FingerprintEngineV2:
    """Minutiae-based fingerprint engine (v2)."""

    def __init__(self):
        self._gabor = self._build_gabor_bank()

    # â”€â”€ Setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_gabor_bank(self) -> list:
        kernels = []
        for i in range(_N_ORI):
            theta = i * math.pi / _N_ORI
            k = cv2.getGaborKernel(
                ksize=(17, 17), sigma=3.5, theta=theta,
                lambd=9.0, gamma=0.5, psi=0, ktype=cv2.CV_32F,
            )
            kernels.append(k)
        return kernels

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def read_image(self, img_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Cannot decode image bytes")
        return img

    def _ridge_coherence(self, enhanced, mask):
        """Mean local orientation coherence in foreground mask.

        Fingerprint ridges are locally parallel  -> coherence ~0.45-0.85.
        Diagrams / photos have mixed directions  -> coherence ~0.05-0.25.
        """
        if mask.sum() < 200:
            return 0.0
        f   = enhanced.astype(np.float32)
        gx  = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy  = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        Gxx = cv2.GaussianBlur(gx * gx, (11, 11), 2.0)
        Gyy = cv2.GaussianBlur(gy * gy, (11, 11), 2.0)
        Gxy = cv2.GaussianBlur(gx * gy, (11, 11), 2.0)
        numer = np.sqrt((Gxx - Gyy) ** 2 + 4.0 * Gxy ** 2)
        denom = Gxx + Gyy + 1e-6
        coh   = numer / denom
        return float(coh[mask].mean())

    def analyze(self, img: np.ndarray) -> dict:
        """Single-pass full pipeline. Returns template + quality + likeness."""
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        enhanced, mask = self._enhance_and_segment(gray)
        ridge_ratio = float(mask.sum()) / max(1, mask.size)

        def _reject(likeness_val: float) -> dict:
            return {
                "template":       {"minutiae": [], "width": _W, "height": _H, "count": 0, "algorithm": "minutiae_v1"},
                "quality":        0.0,
                "likeness":       float(max(0.0, min(0.39, likeness_val))),
                "minutiae_count": 0,
                "ridge_ratio":    ridge_ratio,
            }

        # Gate 1: mask coverage.
        # Fingerprints fill 15-70% of image. Diagram on white paper fills <10%.
        if ridge_ratio < 0.10:
            return _reject(ridge_ratio * 0.5)

        # Gate 2: ridge orientation coherence.
        # Real fingerprints have parallel flowing ridges (coherence 0.45-0.85).
        # Diagrams (boxes, text, arrows) have mixed directions (0.05-0.25).
        # Face/skin photos have isotropic texture (0.10-0.30).
        coherence = self._ridge_coherence(enhanced, mask)
        if coherence < 0.30:
            return _reject(coherence * 0.95)

        # Passed structural gates - run full minutiae pipeline
        binary   = self._binarize(enhanced, mask)
        skeleton = self._thin(binary)
        orient   = self._orientation_map(enhanced)
        minutiae = self._extract_minutiae(skeleton, mask, orient)
        minutiae = self._deduplicate(minutiae)
        count    = len(minutiae)

        # Gate 3: minimum minutiae count.
        if count < _MIN_MINUTIAE:
            likeness = count / _MIN_MINUTIAE * 0.44
            quality  = count / _MIN_MINUTIAE * 0.30
            return {
                "template":       {"minutiae": minutiae, "width": _W, "height": _H, "count": count, "algorithm": "minutiae_v1"},
                "quality":        float(quality),
                "likeness":       float(likeness),
                "minutiae_count": count,
                "ridge_ratio":    ridge_ratio,
            }

        # All gates passed - compute final scores.
        # Likeness blends coherence (structure) and minutiae richness (biology).
        likeness = float(min(1.0, 0.5 * coherence + 0.5 * min(1.0, count / 50.0)))
        likeness = max(0.44, likeness)   # floor: if we got here it IS a fingerprint
        quality  = float(0.65 * min(1.0, count / 50.0) + 0.35 * min(1.0, ridge_ratio / 0.22))

        template = {
            "minutiae": minutiae,
            "width":    _W,
            "height":   _H,
            "count":    count,
            "algorithm": "minutiae_v1",
        }
        return {
            "template":       template,
            "quality":        quality,
            "likeness":       likeness,
            "minutiae_count": count,
            "ridge_ratio":    ridge_ratio,
        }

    # Legacy wrappers kept for compatibility with model_service and old route code
    def fingerprint_likeness_components(self, img: np.ndarray) -> dict:
        r = self.analyze(img)
        return {
            "score":             r["likeness"],
            "minutiae_count":    r["minutiae_count"],
            "ridge_block_ratio": r["ridge_ratio"],
            "kp_count":          r["minutiae_count"],
            "coverage":          r["ridge_ratio"],
        }

    def quality_score(self, img: np.ndarray) -> float:
        return self.analyze(img)["quality"]

    def extract_template(self, img: np.ndarray) -> dict:
        return self.analyze(img)["template"]

    # â”€â”€ Pipeline steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _enhance_and_segment(self, gray: np.ndarray):
        """CLAHE + Gabor enhancement, plus variance-based segmentation mask."""
        resized  = cv2.resize(gray, (_W, _H), interpolation=cv2.INTER_AREA)
        clahe    = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        equalized = clahe.apply(resized)

        # Gabor bank: take max response across all orientations
        resp = np.zeros((_H, _W), dtype=np.float32)
        eq_f = equalized.astype(np.float32)
        for k in self._gabor:
            r = cv2.filter2D(eq_f, cv2.CV_32F, k)
            np.maximum(resp, r, out=resp)

        # Normalise to uint8
        r_min, r_max = float(resp.min()), float(resp.max())
        if r_max > r_min:
            enhanced = ((resp - r_min) / (r_max - r_min) * 255.0).astype(np.uint8)
        else:
            enhanced = equalized

        # Segmentation: local std-dev via blur trick (fully vectorised)
        f2  = enhanced.astype(np.float32)
        mu  = cv2.blur(f2, (_BLOCK, _BLOCK))
        mu2 = cv2.blur(f2 * f2, (_BLOCK, _BLOCK))
        std = np.sqrt(np.maximum(0.0, mu2 - mu * mu))
        mask_u8 = (std > 8.0).astype(np.uint8) * 255
        kern    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_BLOCK, _BLOCK))
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kern)

        return enhanced, mask_u8 > 0

    def _binarize(self, enhanced: np.ndarray, mask: np.ndarray) -> np.ndarray:
        binary = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,
            blockSize=15, C=4,
        )
        binary[~mask] = 0
        return binary

    def _thin(self, binary: np.ndarray) -> np.ndarray:
        """Skeletonise ridges to 1-pixel width (Zhang-Suen via scikit-image)."""
        if _SKIMAGE_OK:
            return (_skel_fn(binary > 0).astype(np.uint8)) * 255
        # Pure-OpenCV iterative fallback
        skel = np.zeros_like(binary)
        el   = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        tmp  = binary.copy()
        while True:
            er  = cv2.erode(tmp, el)
            op  = cv2.dilate(er, el)
            skel = cv2.bitwise_or(skel, cv2.subtract(tmp, op))
            tmp  = er
            if cv2.countNonZero(tmp) == 0:
                break
        return skel

    def _orientation_map(self, enhanced: np.ndarray) -> np.ndarray:
        """Ridge orientation at every pixel using structure tensor (0-180 deg)."""
        f   = enhanced.astype(np.float32)
        gx  = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy  = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        Gxx = cv2.GaussianBlur(gx * gx, (5, 5), 1.0)
        Gyy = cv2.GaussianBlur(gy * gy, (5, 5), 1.0)
        Gxy = cv2.GaussianBlur(gx * gy, (5, 5), 1.0)
        angle = 0.5 * np.degrees(np.arctan2(2.0 * Gxy, Gxx - Gyy)) + 90.0
        return angle % 180.0

    def _extract_minutiae(
        self, skeleton: np.ndarray, mask: np.ndarray, orient: np.ndarray
    ) -> list:
        """Vectorised crossing-number minutiae detection."""
        sk = (skeleton > 0).astype(np.int32)
        h, w = sk.shape

        # 8-connectivity neighbour count (fully vectorised)
        nb = np.zeros((h, w), dtype=np.int32)
        nb[1:-1, 1:-1] = (
            sk[:-2, :-2] + sk[:-2, 1:-1] + sk[:-2, 2:] +
            sk[1:-1, :-2] +               sk[1:-1, 2:] +
            sk[2:, :-2]  + sk[2:, 1:-1]  + sk[2:, 2:]
        )

        in_border = np.zeros((h, w), dtype=bool)
        in_border[_BORDER:h - _BORDER, _BORDER:w - _BORDER] = True
        valid = (sk > 0) & mask & in_border

        endings = valid & (nb == 1)   # ridge ending
        bifurcs = valid & (nb >= 3)   # bifurcation

        minutiae = []
        for y, x in zip(*np.where(endings)):
            minutiae.append([int(x), int(y), float(orient[y, x]), 0])
        for y, x in zip(*np.where(bifurcs)):
            minutiae.append([int(x), int(y), float(orient[y, x]), 1])

        # Cap to avoid very noisy templates
        if len(minutiae) > 100:
            minutiae = minutiae[:100]
        return minutiae

    def _deduplicate(self, minutiae: list, min_dist: float = _MIN_DIST) -> list:
        if len(minutiae) < 2:
            return minutiae
        xy   = np.array([[m[0], m[1]] for m in minutiae], dtype=np.float32)
        keep = []
        used = np.zeros(len(minutiae), dtype=bool)
        for i in range(len(minutiae)):
            if used[i]:
                continue
            keep.append(minutiae[i])
            dists = np.hypot(xy[i, 0] - xy[:, 0], xy[i, 1] - xy[:, 1])
            used |= (dists < min_dist) & (dists > 0)
        return keep

    # â”€â”€ Matching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def match_score(self, tpl_a: dict, tpl_b: dict) -> float:
        """Match two templates. Handles minutiae_v1 and legacy AKAZE formats."""
        # Legacy AKAZE: both templates must have 'des' key
        if "des" in tpl_a and "des" in tpl_b:
            return self._akaze_match(tpl_a, tpl_b)
        # Mixed formats (one minutiae, one AKAZE) â†’ cannot compare meaningfully
        if "minutiae" not in tpl_a or "minutiae" not in tpl_b:
            return 0.0
        m_a = tpl_a["minutiae"]
        m_b = tpl_b["minutiae"]
        if len(m_a) < 3 or len(m_b) < 3:
            return 0.0
        return self._minutiae_match(m_a, m_b)

    def _minutiae_match(self, m_a: list, m_b: list) -> float:
        """Alignment-based minutiae matching (rotation + translation tolerant)."""
        arr_a = np.array([[m[0], m[1], m[2]] for m in m_a], dtype=np.float64)
        arr_b = np.array([[m[0], m[1], m[2]] for m in m_b], dtype=np.float64)
        na, nb = len(arr_a), len(arr_b)

        best    = 0
        n_a = min(_N_ANCHORS, na)
        n_b = min(_N_ANCHORS, nb)
        for i in range(n_a):
            for j in range(n_b):
                c = self._aligned_count(arr_a, arr_b, i, j)
                if c > best:
                    best = c

        return float(min(1.0, best / math.sqrt(max(1, na) * max(1, nb))))

    def _aligned_count(
        self, arr_a: np.ndarray, arr_b: np.ndarray, ai: int, bi: int
    ) -> int:
        """Rigid-align arr_a onto arr_b using anchor pair (ai, bi); count inliers."""
        ax, ay, aa = arr_a[ai]
        bx, by, ba = arr_b[bi]
        rot_rad = math.radians(float(ba - aa))
        cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)

        # Transform all of arr_a into arr_b frame (vectorised)
        dx = arr_a[:, 0] - ax
        dy = arr_a[:, 1] - ay
        tx = cos_r * dx - sin_r * dy + bx
        ty = sin_r * dx + cos_r * dy + by
        ta = (arr_a[:, 2] + math.degrees(rot_rad)) % 180.0

        matched = 0
        used    = set()
        for k in range(len(tx)):
            diff_x = arr_b[:, 0] - tx[k]
            diff_y = arr_b[:, 1] - ty[k]
            dists  = np.hypot(diff_x, diff_y)
            ang_d  = np.abs(((arr_b[:, 2] - ta[k]) + 90.0) % 180.0 - 90.0)
            cands  = np.where((dists < _POS_THRESH) & (ang_d < _ANG_THRESH))[0]
            cands  = [int(c) for c in cands if int(c) not in used]
            if cands:
                best_j = int(cands[int(np.argmin(dists[[c for c in cands]]))])
                matched += 1
                used.add(best_j)
        return matched

    def _akaze_match(self, tpl_a: dict, tpl_b: dict) -> float:
        """Backward-compat AKAZE matching for templates enrolled before the minutiae engine."""
        try:
            da = np.array(tpl_a["des"], dtype=np.uint8)
            db = np.array(tpl_b["des"], dtype=np.uint8)
            if da.ndim != 2 or db.ndim != 2:
                return 0.0
            bf      = cv2.BFMatcher(cv2.NORM_HAMMING)
            matches = bf.knnMatch(da, db, k=2)
            good    = [m for m, n in matches if m.distance < 0.75 * n.distance]
            return float(len(good)) / max(1, min(len(da), len(db)))
        except Exception:
            return 0.0

    # â”€â”€ Preprocess (legacy compat â€” not used by minutiae pipeline) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def preprocess(self, img: np.ndarray) -> np.ndarray:
        """Legacy preprocessing kept for model_service backward compat."""
        norm  = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        eq    = clahe.apply(norm)
        return cv2.bilateralFilter(eq, 5, 45, 45)
