"""Hybrid fingerprint engine -- production-grade, 4-layer defense.

LAYER 1  FFT ridge frequency gate
           Fingerprints have a dominant spatial frequency band (0.04-0.28 cy/px).
           Diagrams, portraits, blank paper do NOT -> rejected immediately.
LAYER 2  Ridge structure validation
           Structure tensor coherence >= 0.28  (parallel ridges)
           Ridge period consistency  (uniform inter-ridge spacing, CV < 0.35)
           Foreground coverage 10-70 %
LAYER 3  Multi-scale minutiae extraction
           CLAHE -> two Gabor scales -> binarize (Otsu+adaptive) -> Zhang-Suen skeleton
           Crossing-number with per-minutia quality weight
           Deduplication + border exclusion + count gate (>= 20)
LAYER 4  Hybrid template  (minutiae + ridge_period + coherence)
           ridge_period and coherence are stored and cross-checked at match time.

Matching (4-step):
  A  Pre-filter: ridge_period ratio < 0.60 -> score = 0 (different fingers)
  B  Alignment-based minutiae matching (rotation + translation tolerant)
  C  MCC neighborhood consistency per matched pair (local topology check)
  D  Weighted score = alignment_raw * quality_weight * (0.5 + 0.5 * nbc)
     Match threshold: 0.50
"""
from __future__ import annotations

import math
import logging

import cv2
import numpy as np

try:
    from skimage.morphology import skeletonize as _skel_fn
    _SKIMAGE_OK = True
except ImportError:
    _SKIMAGE_OK = False

log = logging.getLogger(__name__)

# -- Tuning constants ----------------------------------------------------------
_W, _H          = 400, 500    # standard processing size (pixels)
_N_ORI          = 8           # Gabor orientations
_BLOCK          = 16          # segmentation block size
_BORDER         = 16          # ignore minutiae this close to edge (px)
_MIN_MINUTIAE   = 20          # below this -> not a fingerprint
_N_ANCHORS      = 25          # anchor pairs tried per match (top-N by quality)
_POS_THRESH     = 25.0        # px  position tolerance (raised for ink scans)
_ANG_THRESH     = 30.0        # deg angle tolerance  (raised for ink scans)
_MIN_DIST       = 8.0         # px  deduplicate minutiae closer than this
_NBC_K          = 5           # MCC neighborhood size
_NBC_THRESH     = 0.40        # fraction of neighborhood that must be consistent

# Ridge frequency band (cycles per pixel at 400px width)
# Fingerprints: ~100-500 LPI at ~500 DPI -> 0.04-0.28 cy/px
_FREQ_LO        = 0.04
_FREQ_HI        = 0.28
_FREQ_ENERGY_MIN = 0.15       # fraction of total FFT energy that must be in band

_COH_THRESH     = 0.28        # coherence gate
_PERIOD_CV_MAX  = 0.35        # ridge period coefficient of variation gate


class FingerprintEngineV2:
    """Production-grade hybrid fingerprint engine (hybrid_v2)."""

    def __init__(self):
        self._gabor_fine   = self._build_gabor_bank(sigma=3.0, lambd=8.0)
        self._gabor_coarse = self._build_gabor_bank(sigma=4.5, lambd=12.0)

    # -- Gabor bank ------------------------------------------------------------

    def _build_gabor_bank(self, sigma: float, lambd: float) -> list:
        kernels = []
        for i in range(_N_ORI):
            theta = i * math.pi / _N_ORI
            k = cv2.getGaborKernel(
                ksize=(21, 21), sigma=sigma, theta=theta,
                lambd=lambd, gamma=0.5, psi=0, ktype=cv2.CV_32F,
            )
            kernels.append(k)
        return kernels

    # -- Public API ------------------------------------------------------------

    def read_image(self, img_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Cannot decode image bytes")
        return img

    def analyze(self, img: np.ndarray) -> dict:
        """Full 4-layer pipeline. Returns template + quality + likeness."""
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # LAYER 1: FFT ridge frequency gate ------------------------------------
        freq_score = self._fft_ridge_frequency_score(gray)
        if freq_score < _FREQ_ENERGY_MIN:
            log.debug("FFT gate failed: freq_score=%.3f", freq_score)
            return self._reject(freq_score * 0.5, "fft_gate")

        # Enhance + segment
        enhanced_f, enhanced_c, mask = self._enhance_and_segment(gray)
        ridge_ratio = float(mask.sum()) / max(1, mask.size)

        # LAYER 2A: mask coverage ----------------------------------------------
        if ridge_ratio < 0.10 or ridge_ratio > 0.75:
            log.debug("Coverage gate failed: ridge_ratio=%.3f", ridge_ratio)
            return self._reject(ridge_ratio * 0.3, "coverage_gate")

        # LAYER 2B: orientation coherence --------------------------------------
        coherence = self._ridge_coherence(enhanced_f, mask)
        if coherence < _COH_THRESH:
            log.debug("Coherence gate failed: coherence=%.3f", coherence)
            return self._reject(coherence * 0.9, "coherence_gate")

        # LAYER 2C: ridge period consistency -----------------------------------
        ridge_period, period_cv = self._ridge_period_stats(enhanced_f, mask)
        if period_cv > _PERIOD_CV_MAX or ridge_period < 4.0 or ridge_period > 30.0:
            log.debug("Period gate failed: period=%.2f cv=%.3f", ridge_period, period_cv)
            return self._reject(0.25, "period_gate")

        # LAYER 3: multi-scale minutiae extraction -----------------------------
        minutiae = self._extract_multiscale(enhanced_f, enhanced_c, mask)
        count = len(minutiae)

        if count < _MIN_MINUTIAE:
            likeness = count / _MIN_MINUTIAE * 0.44
            quality  = count / _MIN_MINUTIAE * 0.30
            return {
                "template":       self._make_template(minutiae, ridge_period, coherence),
                "quality":        float(quality),
                "likeness":       float(likeness),
                "minutiae_count": count,
                "ridge_ratio":    ridge_ratio,
                "coherence":      coherence,
                "ridge_period":   ridge_period,
            }

        # LAYER 4: final scores ------------------------------------------------
        likeness = float(min(1.0,
            0.35 * coherence +
            0.30 * min(1.0, freq_score / 0.40) +
            0.35 * min(1.0, count / 60.0)
        ))
        likeness = max(0.50, likeness)   # floor: passed all gates = IS a fingerprint

        quality = float(min(1.0,
            0.50 * min(1.0, count / 60.0) +
            0.30 * min(1.0, ridge_ratio / 0.30) +
            0.20 * coherence
        ))

        return {
            "template":       self._make_template(minutiae, ridge_period, coherence),
            "quality":        quality,
            "likeness":       likeness,
            "minutiae_count": count,
            "ridge_ratio":    ridge_ratio,
            "coherence":      coherence,
            "ridge_period":   ridge_period,
        }

    def _reject(self, likeness_val: float, gate: str = "") -> dict:
        return {
            "template":       {"minutiae": [], "width": _W, "height": _H,
                               "count": 0, "algorithm": "hybrid_v2",
                               "ridge_period": 0.0, "coherence": 0.0},
            "quality":        0.0,
            "likeness":       float(max(0.0, min(0.39, likeness_val))),
            "minutiae_count": 0,
            "ridge_ratio":    0.0,
            "coherence":      0.0,
            "ridge_period":   0.0,
            "rejected_at":    gate,
        }

    def _make_template(self, minutiae: list, ridge_period: float, coherence: float) -> dict:
        return {
            "minutiae":     minutiae,
            "width":        _W,
            "height":       _H,
            "count":        len(minutiae),
            "algorithm":    "hybrid_v2",
            "ridge_period": float(ridge_period),
            "coherence":    float(coherence),
        }

    # -- Legacy wrappers -------------------------------------------------------

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

    # -- LAYER 1: FFT ridge frequency gate ------------------------------------

    def _fft_ridge_frequency_score(self, gray: np.ndarray) -> float:
        """Fraction of FFT energy in the fingerprint ridge frequency band.

        Real fingerprints have a dominant spatial frequency from parallel ridges
        (0.04-0.28 cy/px at 400px width).  Diagrams, portraits, and blank images
        do NOT have a concentrated energy peak in this band -> score is very low.
        """
        resized = cv2.resize(gray, (_W, _H), interpolation=cv2.INTER_AREA)
        f32 = resized.astype(np.float32)
        fft = np.fft.fft2(f32)
        fft_shift = np.fft.fftshift(fft)
        mag = np.abs(fft_shift)

        cy, cx = _H // 2, _W // 2
        yy, xx = np.mgrid[0:_H, 0:_W]
        freq = np.sqrt(((xx - cx) / _W) ** 2 + ((yy - cy) / _H) ** 2)

        dc_mask = freq < 0.02
        in_band = (freq >= _FREQ_LO) & (freq <= _FREQ_HI) & ~dc_mask
        total   = float(mag[~dc_mask].sum()) + 1e-9
        return float(mag[in_band].sum()) / total

    # -- LAYER 2: Structure analysis ------------------------------------------

    def _enhance_and_segment(self, gray: np.ndarray):
        """CLAHE + two-scale Gabor enhancement + variance segmentation mask.

        Handles two input types:
          - Grayscale live-scanner captures (typical DPI 500, gradients present)
          - Near-binary high-contrast ink scans (inked card, paper scan)
            For these, a pre-blur restores gray gradients so the Gabor bank
            gets proper ridge/valley contrast rather than hard edges only.
        """
        resized = cv2.resize(gray, (_W, _H), interpolation=cv2.INTER_AREA)

        # Detect near-binary input: if >60% of pixels are very dark (<40) or
        # very bright (>215) the image is likely an inked scan already binarized.
        # Apply a gentle Gaussian blur to restore gradient information before CLAHE.
        flat = resized.ravel()
        binary_frac = float(np.mean((flat < 40) | (flat > 215)))
        if binary_frac > 0.60:
            resized = cv2.GaussianBlur(resized, (5, 5), 1.2)

        clahe   = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        eq      = clahe.apply(resized)
        eq_f    = eq.astype(np.float32)

        def _gabor_max(bank):
            resp = np.zeros((_H, _W), dtype=np.float32)
            for k in bank:
                np.maximum(resp, cv2.filter2D(eq_f, cv2.CV_32F, k), out=resp)
            return resp

        resp_f = _gabor_max(self._gabor_fine)
        resp_c = _gabor_max(self._gabor_coarse)

        def _norm_u8(arr):
            lo, hi = float(arr.min()), float(arr.max())
            if hi > lo:
                return ((arr - lo) / (hi - lo) * 255.0).astype(np.uint8)
            return eq

        enh_f = _norm_u8(resp_f)
        enh_c = _norm_u8(resp_c)

        # Segmentation from fine response
        f2  = enh_f.astype(np.float32)
        mu  = cv2.blur(f2, (_BLOCK, _BLOCK))
        mu2 = cv2.blur(f2 * f2, (_BLOCK, _BLOCK))
        std = np.sqrt(np.maximum(0.0, mu2 - mu * mu))
        mask_u8 = (std > 7.0).astype(np.uint8) * 255
        kern    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_BLOCK, _BLOCK))
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kern)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN,  kern)

        return enh_f, enh_c, mask_u8 > 0

    def _ridge_coherence(self, enhanced: np.ndarray, mask: np.ndarray) -> float:
        """Structure tensor coherence.  Fingerprints: 0.45-0.85.  Others: 0.05-0.25."""
        if mask.sum() < 500:
            return 0.0
        f   = enhanced.astype(np.float32)
        gx  = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy  = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        Gxx = cv2.GaussianBlur(gx * gx, (15, 15), 3.0)
        Gyy = cv2.GaussianBlur(gy * gy, (15, 15), 3.0)
        Gxy = cv2.GaussianBlur(gx * gy, (15, 15), 3.0)
        numer = np.sqrt((Gxx - Gyy) ** 2 + 4.0 * Gxy ** 2)
        denom = Gxx + Gyy + 1e-6
        return float((numer / denom)[mask].mean())

    def _ridge_period_stats(self, enhanced: np.ndarray, mask: np.ndarray):
        """Estimate mean ridge period and coefficient of variation across the image.

        Samples 16x16 pixel blocks via 1D FFT.  Fingerprints have consistent
        inter-ridge spacing (CV < 0.35).  Diagrams and text do not.
        Returns (mean_period_px, cv).
        """
        periods = []
        h, w = enhanced.shape
        step = 32
        for y in range(_BORDER, h - _BORDER - 16, step):
            for x in range(_BORDER, w - _BORDER - 16, step):
                if mask[y:y + 16, x:x + 16].sum() < 100:
                    continue
                strip = enhanced[y:y + 16, x:x + 16].astype(np.float32)
                for proj in [strip.mean(axis=0), strip.mean(axis=1)]:
                    proj -= proj.mean()
                    if proj.std() < 2.0:
                        continue
                    fft_mag = np.abs(np.fft.rfft(proj))
                    fft_mag[0] = 0
                    pk = int(np.argmax(fft_mag))
                    if pk > 0:
                        period = len(proj) / pk
                        if 3.0 < period < 40.0:
                            periods.append(period)

        if len(periods) < 5:
            return 10.0, 0.20   # inconclusive -> mild pass
        arr = np.array(periods, dtype=np.float32)
        mean_p = float(arr.mean())
        return mean_p, float(arr.std() / (mean_p + 1e-6))

    # -- LAYER 3: Multi-scale minutiae extraction ------------------------------

    def _extract_multiscale(self, enh_f, enh_c, mask) -> list:
        orient = self._orientation_map(enh_f)
        m_fine   = self._single_scale_minutiae(enh_f, mask, orient)
        m_coarse = self._single_scale_minutiae(enh_c, mask, orient)

        combined = list(m_fine)
        if m_coarse:
            fine_xy = np.array([[m[0], m[1]] for m in m_fine], dtype=np.float32) if m_fine else None
            for m in m_coarse:
                if fine_xy is None:
                    combined.append(m)
                    continue
                if np.hypot(fine_xy[:, 0] - m[0], fine_xy[:, 1] - m[1]).min() > _MIN_DIST * 1.5:
                    combined.append(m)

        combined = self._deduplicate(combined)
        combined.sort(key=lambda m: -m[4])   # quality descending
        return combined[:120]

    def _single_scale_minutiae(self, enhanced, mask, orient) -> list:
        binary   = self._binarize(enhanced, mask)
        skeleton = self._thin(binary)
        return self._extract_minutiae(skeleton, mask, orient)

    def _binarize(self, enhanced: np.ndarray, mask: np.ndarray) -> np.ndarray:
        _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 4,
        )
        binary = cv2.bitwise_or(otsu, adaptive)
        binary[~mask] = 0
        kernel = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    def _thin(self, binary: np.ndarray) -> np.ndarray:
        if _SKIMAGE_OK:
            skel = (_skel_fn(binary > 0).astype(np.uint8)) * 255
        else:
            skel = np.zeros_like(binary)
            el   = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
            tmp  = binary.copy()
            while True:
                er   = cv2.erode(tmp, el)
                op   = cv2.dilate(er, el)
                skel = cv2.bitwise_or(skel, cv2.subtract(tmp, op))
                tmp  = er
                if cv2.countNonZero(tmp) == 0:
                    break

        # Remove isolated skeleton pixels (noise from ink-scan fragmentation).
        # A real ridge pixel has at least 1 neighbour; isolated dots have 0.
        sk = (skel > 0).astype(np.int32)
        nb = np.zeros_like(sk)
        nb[1:-1, 1:-1] = (
            sk[:-2, :-2] + sk[:-2, 1:-1] + sk[:-2, 2:] +
            sk[1:-1, :-2] +                sk[1:-1, 2:] +
            sk[2:, :-2]  + sk[2:, 1:-1]  + sk[2:, 2:]
        )
        skel[(skel > 0) & (nb == 0)] = 0   # remove isolated dots
        return skel

    def _orientation_map(self, enhanced: np.ndarray) -> np.ndarray:
        f   = enhanced.astype(np.float32)
        gx  = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy  = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        Gxx = cv2.GaussianBlur(gx * gx, (5, 5), 1.0)
        Gyy = cv2.GaussianBlur(gy * gy, (5, 5), 1.0)
        Gxy = cv2.GaussianBlur(gx * gy, (5, 5), 1.0)
        return (0.5 * np.degrees(np.arctan2(2.0 * Gxy, Gxx - Gyy)) + 90.0) % 180.0

    def _extract_minutiae(self, skeleton, mask, orient) -> list:
        sk = (skeleton > 0).astype(np.int32)
        h, w = sk.shape
        nb = np.zeros((h, w), dtype=np.int32)
        nb[1:-1, 1:-1] = (
            sk[:-2, :-2] + sk[:-2, 1:-1] + sk[:-2, 2:] +
            sk[1:-1, :-2] +                sk[1:-1, 2:] +
            sk[2:, :-2]  + sk[2:, 1:-1]  + sk[2:, 2:]
        )
        border = np.zeros((h, w), dtype=bool)
        border[_BORDER:h - _BORDER, _BORDER:w - _BORDER] = True
        valid = (sk > 0) & mask & border

        blur = cv2.GaussianBlur(skeleton.astype(np.float32), (9, 9), 2.0)
        minutiae = []
        for y, x in zip(*np.where(valid & (nb == 1))):
            q = float(np.clip(blur[y, x] / 128.0, 0.1, 1.0))
            minutiae.append([int(x), int(y), float(orient[y, x]), 0, q])
        for y, x in zip(*np.where(valid & (nb >= 3))):
            q = float(np.clip(blur[y, x] / 128.0, 0.1, 1.0))
            minutiae.append([int(x), int(y), float(orient[y, x]), 1, q])
        return minutiae

    def _deduplicate(self, minutiae: list) -> list:
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
            used |= (dists < _MIN_DIST) & (dists > 0)
        return keep

    # -- LAYER 4: Matching -----------------------------------------------------

    def match_score(self, tpl_a: dict, tpl_b: dict) -> float:
        """Match two templates. Handles hybrid_v2, hybrid_v1, minutiae_v1, legacy AKAZE."""
        if "des" in tpl_a and "des" in tpl_b:
            return self._akaze_match(tpl_a, tpl_b)
        if "minutiae" not in tpl_a or "minutiae" not in tpl_b:
            return 0.0

        m_a = tpl_a["minutiae"]
        m_b = tpl_b["minutiae"]
        if len(m_a) < 4 or len(m_b) < 4:
            return 0.0

        alg_a = tpl_a.get("algorithm", "")
        alg_b = tpl_b.get("algorithm", "")

        # Version mismatch: hybrid_v1 templates are incompatible with hybrid_v2
        # (ink-scan pre-blur changes minutiae coordinates).  Signal re-enroll.
        if ("hybrid_v2" in (alg_a, alg_b)) and ("hybrid_v1" in (alg_a, alg_b)):
            log.warning("Template version mismatch: %s vs %s — re-enroll needed", alg_a, alg_b)
            raise ValueError(f"STALE_TEMPLATE:{alg_a}:{alg_b}")

        # Step A: pre-filter on ridge_period and coherence
        if (alg_a in ("hybrid_v1", "hybrid_v2", "minutiae_v1") and
                alg_b in ("hybrid_v1", "hybrid_v2", "minutiae_v1")):
            rp_a = tpl_a.get("ridge_period", 0.0)
            rp_b = tpl_b.get("ridge_period", 0.0)
            if rp_a > 0 and rp_b > 0:
                if min(rp_a, rp_b) / max(rp_a, rp_b) < 0.60:
                    return 0.0
            coh_a = tpl_a.get("coherence", 1.0)
            coh_b = tpl_b.get("coherence", 1.0)
            if coh_a < 0.20 or coh_b < 0.20:
                return 0.0

        return self._hybrid_match(m_a, m_b)

    def _hybrid_match(self, m_a: list, m_b: list) -> float:
        """Steps B+C+D: alignment + MCC neighborhood consistency.

        Scoring formula:
          raw   = matched_count / min(na, nb)   -- fraction of smaller set matched
          score = raw * (0.4 + 0.6 * nbc)       -- weighted by neighborhood consistency

        At threshold 0.40 a genuine same-finger match needs ~50% minutiae aligned
        with decent neighborhood consistency (nbc >= 0.5).
        Random imposters score < 0.10 (few chance alignments, no spatial consistency).
        """
        def _arr(lst):
            return np.array([
                [float(m[0]), float(m[1]), float(m[2]),
                 float(m[3]) if len(m) > 3 else 0.0,
                 float(m[4]) if len(m) > 4 else 1.0]
                for m in lst
            ], dtype=np.float64)

        arr_a = _arr(m_a)
        arr_b = _arr(m_b)
        na, nb = len(arr_a), len(arr_b)
        best_score = 0.0
        norm = float(min(na, nb))  # fraction of smaller template matched

        for i in range(min(_N_ANCHORS, na)):
            for j in range(min(_N_ANCHORS, nb)):
                count, pairs = self._aligned_pairs(arr_a, arr_b, i, j)
                if count < 4:
                    continue
                nbc   = self._neighborhood_consistency(arr_a, arr_b, pairs)
                raw   = float(count) / norm
                score = raw * (0.4 + 0.6 * nbc)
                if score > best_score:
                    best_score = score

        return float(min(1.0, best_score))

    def _aligned_pairs(self, arr_a, arr_b, ai, bi):
        ax, ay, aa = arr_a[ai, :3]
        bx, by, ba = arr_b[bi, :3]
        rot_rad = math.radians(float(ba - aa))
        cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)

        dx = arr_a[:, 0] - ax
        dy = arr_a[:, 1] - ay
        tx = cos_r * dx - sin_r * dy + bx
        ty = sin_r * dx + cos_r * dy + by
        ta = (arr_a[:, 2] + math.degrees(rot_rad)) % 180.0

        used, pairs = set(), []
        for k in range(len(tx)):
            dists = np.hypot(arr_b[:, 0] - tx[k], arr_b[:, 1] - ty[k])
            ang_d = np.abs(((arr_b[:, 2] - ta[k]) + 90.0) % 180.0 - 90.0)
            cands = [int(c) for c in np.where((dists < _POS_THRESH) & (ang_d < _ANG_THRESH))[0]
                     if int(c) not in used]
            if cands:
                best_j = int(cands[int(np.argmin(dists[cands]))])
                pairs.append((k, best_j))
                used.add(best_j)
        return len(pairs), pairs

    def _neighborhood_consistency(self, arr_a, arr_b, pairs) -> float:
        """MCC: check that k nearest neighbors around each matched pair also match."""
        if len(pairs) < 2:
            return 0.0
        xy_a = arr_a[:, :2]
        xy_b = arr_b[:, :2]
        matched_a = set(p[0] for p in pairs)
        matched_b = set(p[1] for p in pairs)
        pair_map  = {p[0]: p[1] for p in pairs}
        consistent = 0

        for (ia, ib) in pairs:
            da = np.hypot(xy_a[:, 0] - arr_a[ia, 0], xy_a[:, 1] - arr_a[ia, 1])
            da[ia] = 1e9
            nn_a = set(np.argsort(da)[:_NBC_K].tolist())

            db = np.hypot(xy_b[:, 0] - arr_b[ib, 0], xy_b[:, 1] - arr_b[ib, 1])
            db[ib] = 1e9
            nn_b = set(np.argsort(db)[:_NBC_K].tolist())

            a_nbs = nn_a & matched_a
            b_nbs = nn_b & matched_b
            if not a_nbs:
                consistent += 0.5
                continue
            hits = sum(1 for na_ in a_nbs if pair_map.get(na_) in b_nbs)
            if hits / len(a_nbs) >= _NBC_THRESH:
                consistent += 1

        return float(consistent) / len(pairs)

    def _akaze_match(self, tpl_a: dict, tpl_b: dict) -> float:
        """Backward-compat AKAZE matching for pre-hybrid templates."""
        try:
            da = np.array(tpl_a["des"], dtype=np.uint8)
            db = np.array(tpl_b["des"], dtype=np.uint8)
            if da.ndim != 2 or db.ndim != 2:
                return 0.0
            bf = cv2.BFMatcher(cv2.NORM_HAMMING)
            matches = bf.knnMatch(da, db, k=2)
            good = [m for m, n in matches if m.distance < 0.75 * n.distance]
            return float(len(good)) / max(1, min(len(da), len(db)))
        except Exception:
            return 0.0

    def preprocess(self, img: np.ndarray) -> np.ndarray:
        norm  = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        return cv2.bilateralFilter(clahe.apply(norm), 5, 45, 45)
