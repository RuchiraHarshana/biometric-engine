import cv2
import numpy as np

class FingerprintEngine:
    def __init__(self, nfeatures: int = 1000):
        self.orb = cv2.ORB_create(nfeatures=nfeatures)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def read_image(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Invalid fingerprint image.")
        return img

    def preprocess(self, img: np.ndarray) -> np.ndarray:
        img = cv2.equalizeHist(img)
        img = cv2.GaussianBlur(img, (3, 3), 0)
        _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return img

    def is_fingerprint(self, img: np.ndarray) -> bool:
        """
        Heuristic check to detect fingerprint-like ridge-frequency patterns.
        Uses the 2D FFT magnitude: fingerprints tend to have mid-frequency
        peaks due to periodic ridge/valley structure. Returns True when a
        clear mid-frequency peak is present.
        """
        try:
            score = self.fingerprint_score(img)
            return score > 0.5
        except Exception:
            return False

    def fingerprint_score(self, img: np.ndarray) -> float:
        # Keep compatibility: compute components and return overall score
        comps = self.fingerprint_score_components(img)
        return float(comps.get("score", 0.0))

    def fingerprint_score_components(self, img: np.ndarray) -> dict:
        """
        Return detailed components of the fingerprint-likeness score for tuning.
        Returns a dict with keys: score, score_coh, score_fft, score_edge, score_grad
        """
        arr = img.astype(np.float32)

        # FFT metric
        f = np.fft.fft2(arr)
        fshift = np.fft.fftshift(f)
        mag = np.abs(fshift)
        h, w = mag.shape
        cy, cx = h // 2, w // 2
        cz = max(4, min(h, w) // 32)
        mag_out = mag.copy()
        mag_out[cy - cz: cy + cz + 1, cx - cz: cx + cz + 1] = 0
        max_out = float(np.max(mag_out))
        med_out = float(np.median(mag_out))
        if med_out <= 0:
            score_fft = 0.0
        else:
            ratio = max_out / (med_out + 1e-9)
            score_fft = float(min(1.0, np.log1p(ratio) / np.log1p(100.0)))

        # Edge density (Canny)
        try:
            edges = cv2.Canny(img, 50, 150)
            edge_density = float(np.sum(edges > 0)) / (h * w)
            score_edge = min(1.0, max(0.0, (edge_density - 0.01) / 0.2))
        except Exception:
            score_edge = 0.0

        # Gradient magnitude mean
        try:
            gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
            grad_mean = float(np.mean(np.sqrt(gx * gx + gy * gy)))
            score_grad = min(1.0, grad_mean / 50.0)
        except Exception:
            score_grad = 0.0

        # Orientation coherence
        try:
            block = 16
            theta = np.arctan2(gy, gx)
            grad_mag_map = np.sqrt(gx * gx + gy * gy)
            hblocks = max(1, h // block)
            wblocks = max(1, w // block)
            weighted_coh_sum = 0.0
            weight_sum = 0.0
            for by in range(hblocks):
                for bx in range(wblocks):
                    y0 = by * block
                    x0 = bx * block
                    patch = theta[y0:y0 + block, x0:x0 + block]
                    mag_patch = grad_mag_map[y0:y0 + block, x0:x0 + block]
                    if patch.size == 0:
                        continue
                    # Weight by mean gradient magnitude so blank blocks (arctan2(0,0)=0 -> coh=1)
                    # don't inflate the score. A white diagram is ~80% blank blocks that
                    # previously each contributed coherence=1.0 to the mean.
                    block_weight = float(np.mean(mag_patch))
                    if block_weight < 2.0:
                        continue
                    vcos = np.cos(2.0 * patch)
                    vsin = np.sin(2.0 * patch)
                    sumx = float(np.sum(vcos))
                    sumy = float(np.sum(vsin))
                    norm = np.sqrt(sumx * sumx + sumy * sumy)
                    coherence = norm / (patch.size + 1e-9)
                    weighted_coh_sum += coherence * block_weight
                    weight_sum += block_weight
            score_coh = float(weighted_coh_sum / (weight_sum + 1e-9)) if weight_sum > 0 else 0.0
            score_coh = min(1.0, max(0.0, score_coh))
        except Exception:
            score_coh = 0.0

        # Weighted combination
        score = 0.7 * score_coh + 0.2 * score_fft + 0.08 * score_edge + 0.02 * score_grad
        score = float(max(0.0, min(1.0, score)))

        return {
            "score": score,
            "score_coh": float(score_coh),
            "score_fft": float(score_fft),
            "score_edge": float(score_edge),
            "score_grad": float(score_grad),
        }

    def extract_template(self, img_gray: np.ndarray) -> dict:
        img = self.preprocess(img_gray)

        # Quick fingerprint-likeness check to reject non-fingerprint images
        if not self.is_fingerprint(img):
            raise ValueError("Image does not appear to be a fingerprint.")

        kp, des = self.orb.detectAndCompute(img, None)
        if des is None or len(kp) < 8:
            raise ValueError("Fingerprint features not found. Use a clearer fingerprint image.")

        # Save descriptors and keypoint coordinates for geometric verification
        kp_coords = [[float(p.pt[0]), float(p.pt[1])] for p in kp]
        return {
            "des": des.tolist(),
            "shape": list(des.shape),
            "kps": kp_coords,
        }

    def deserialize_template(self, tpl: dict):
        """Return (des, kps) where kps may be None if not present."""
        des = None
        kps = None
        if "des" in tpl:
            des = np.array(tpl["des"], dtype=np.uint8).reshape(tpl["shape"][0], tpl["shape"][1])
        if "kps" in tpl:
            kps = np.array(tpl["kps"], dtype=np.float32)
        return des, kps

    def match_score(self, a, b) -> float:
        """
        Accept either raw descriptor arrays or template dicts (des,kps tuple).
        Returns a normalized similarity in 0..1.
        Uses ratio-test + homography inlier ratio when keypoint coords available.
        """
        # Normalize inputs to (des, kps)
        if isinstance(a, dict):
            des1, kps1 = self.deserialize_template(a)
        elif isinstance(a, tuple) or isinstance(a, list):
            des1, kps1 = a
        else:
            des1, kps1 = a, None

        if isinstance(b, dict):
            des2, kps2 = self.deserialize_template(b)
        elif isinstance(b, tuple) or isinstance(b, list):
            des2, kps2 = b
        else:
            des2, kps2 = b, None

        if des1 is None or des2 is None:
            return 0.0

        # If keypoints available, run ratio-test and geometric check
        try:
            # use KNN matching for ratio test
            matches = self.bf.knnMatch(des1, des2, k=2)
            good = []
            for m_n in matches:
                if len(m_n) < 2:
                    continue
                m, n = m_n
                if m.distance < 0.75 * n.distance:
                    good.append(m)
            num_good = len(good)
            if num_good == 0:
                # fallback to distance-based avg
                all_matches = self.bf.match(des1, des2)
                if not all_matches:
                    return 0.0
                dists = np.array([m.distance for m in all_matches], dtype=np.float32)
                avg = float(np.mean(np.sort(dists)[: min(60, len(dists))]))
                return max(0.0, 1.0 - (avg / 100.0))

            # If keypoint coordinates exist, check geometric consistency
            if kps1 is not None and kps2 is not None and num_good >= 8:
                pts1 = np.float32([kps1[m.queryIdx] for m in good]).reshape(-1, 2)
                pts2 = np.float32([kps2[m.trainIdx] for m in good]).reshape(-1, 2)
                H, mask = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
                if mask is None:
                    inliers = 0
                else:
                    inliers = int(np.sum(mask))
                inlier_ratio = inliers / float(max(1, num_good))
                # Combine inlier ratio and good-match count
                score = 0.7 * inlier_ratio + 0.3 * min(1.0, num_good / 50.0)
                return float(max(0.0, min(1.0, score)))

            # Otherwise, use proportion of good matches
            score = min(1.0, num_good / 60.0)
            return float(score)
        except Exception:
            # conservative fallback
            try:
                all_matches = self.bf.match(des1, des2)
                if not all_matches:
                    return 0.0
                dists = np.array([m.distance for m in all_matches], dtype=np.float32)
                avg = float(np.mean(np.sort(dists)[: min(60, len(dists))]))
                return max(0.0, 1.0 - (avg / 100.0))
            except Exception:
                return 0.0

    def deserialize_des(self, tpl: dict) -> np.ndarray:
        des = np.array(tpl["des"], dtype=np.uint8).reshape(tpl["shape"][0], tpl["shape"][1])
        return des
