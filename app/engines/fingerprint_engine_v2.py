import cv2
import numpy as np


class FingerprintEngineV2:
    """
    Experimental fingerprint engine using AKAZE descriptors.
    Kept separate from the current ORB engine to allow safe A/B testing.
    """

    def __init__(self):
        self.detector = cv2.AKAZE_create()
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def _channel_quality(self, ch: np.ndarray) -> float:
        edges = cv2.Canny(ch, 45, 140)
        edge_density = float(np.sum(edges > 0)) / float(max(1, ch.shape[0] * ch.shape[1]))
        lap_var = float(cv2.Laplacian(ch, cv2.CV_32F).var())
        # Balance structure presence and sharpness.
        return edge_density * min(1.0, lap_var / 300.0)

    def read_image(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, np.uint8)
        raw = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError("Invalid fingerprint image.")

        # If already grayscale, keep as-is.
        if len(raw.shape) == 2:
            return raw

        # Convert edited/recolored images to a stable monochrome signal by
        # selecting the channel with strongest ridge-like structure.
        if raw.shape[2] == 4:
            bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        else:
            bgr = raw

        b, g, r = cv2.split(bgr)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        hsv_v = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 2]
        lab_l = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[:, :, 0]

        candidates = [gray, b, g, r, hsv_v, lab_l]
        best = max(candidates, key=self._channel_quality)
        return best

    def preprocess(self, img: np.ndarray) -> np.ndarray:
        # Improve color-edit invariance by normalizing dynamic range first.
        norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        eq = clahe.apply(norm)
        den = cv2.bilateralFilter(eq, 5, 45, 45)
        return den

    @staticmethod
    def _clamp01(x: float) -> float:
        return float(max(0.0, min(1.0, x)))

    @staticmethod
    def _range_score(x: float, lo: float, hi: float) -> float:
        if hi <= lo:
            return 0.0
        return float(max(0.0, min(1.0, (x - lo) / (hi - lo))))

    def fingerprint_likeness_components(self, img: np.ndarray) -> dict:
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return {
                "score": 0.0,
                "coverage": 0.0,
                "orientation_entropy": 0.0,
                "kp_count": 0,
                "kp_density": 0.0,
                "kp_spread": 0.0,
                "tile_active_ratio": 0.0,
                "tile_coverage_std": 0.0,
                "edge_component_count": 0,
                "largest_edge_component_ratio": 1.0,
            }

        raw_norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        arr = raw_norm.astype(np.float32)
        gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx * gx + gy * gy)

        # Real fingerprints usually have ridge texture over a large fraction of the image.
        informative = grad_mag > 12.0
        coverage = float(np.mean(informative))
        score_coverage = self._range_score(coverage, 0.12, 0.35)

        # Spatial distribution check: fingerprints spread ridge texture over many regions,
        # while drawings often occupy only a few tiles.
        grid_n = 6
        active_tiles = 0
        tile_covs = []
        for gy_i in range(grid_n):
            y0 = int(gy_i * h / grid_n)
            y1 = int((gy_i + 1) * h / grid_n)
            for gx_i in range(grid_n):
                x0 = int(gx_i * w / grid_n)
                x1 = int((gx_i + 1) * w / grid_n)
                tile = informative[y0:y1, x0:x1]
                if tile.size == 0:
                    tile_cov = 0.0
                else:
                    tile_cov = float(np.mean(tile))
                tile_covs.append(tile_cov)
                if tile_cov >= 0.08:
                    active_tiles += 1
        tile_active_ratio = float(active_tiles) / float(grid_n * grid_n)
        tile_coverage_std = float(np.std(np.array(tile_covs, dtype=np.float32))) if tile_covs else 0.0
        score_tile_active = self._range_score(tile_active_ratio, 0.28, 0.70)
        score_tile_uniform = 1.0 - self._range_score(tile_coverage_std, 0.20, 0.45)

        # Fingerprints have varied local ridge directions (loops/whorls/arcs),
        # while simple drawings often have only a few dominant directions.
        theta = (np.arctan2(gy, gx) + np.pi) % np.pi
        informative_theta = theta[informative]
        if informative_theta.size >= 32:
            hist, _ = np.histogram(informative_theta, bins=12, range=(0.0, np.pi))
            p = hist.astype(np.float64)
            p_sum = float(p.sum())
            if p_sum > 0:
                p = p / p_sum
                p = p[p > 0]
                entropy = float(-(p * np.log(p)).sum())
                entropy_norm = entropy / np.log(12.0)
            else:
                entropy_norm = 0.0
        else:
            entropy_norm = 0.0
        score_entropy = self._range_score(entropy_norm, 0.45, 0.90)

        proc = self.preprocess(img)
        kps, _ = self.detector.detectAndCompute(proc, None)
        kp_count = int(len(kps)) if kps is not None else 0
        kp_density = float(kp_count) / float(max(1, h * w))
        score_density = self._range_score(kp_density, 0.00008, 0.00050)

        if kp_count >= 2:
            pts = np.array([[kp.pt[0], kp.pt[1]] for kp in kps], dtype=np.float32)
            sx = float(np.std(pts[:, 0])) / float(max(1.0, w))
            sy = float(np.std(pts[:, 1])) / float(max(1.0, h))
            kp_spread = 0.5 * (sx + sy)
        else:
            kp_spread = 0.0
        score_spread = self._range_score(kp_spread, 0.08, 0.22)

        # Connected-component structure on edge map.
        # Fingerprints usually produce many distributed ridge fragments,
        # while drawings have fewer components dominated by one/few strokes.
        edges = cv2.Canny(proc, 45, 140)
        bin_edges = (edges > 0).astype(np.uint8)
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(bin_edges, connectivity=8)
        component_areas = []
        for i in range(1, num_labels):
            a = int(stats[i, cv2.CC_STAT_AREA])
            if a >= 8:
                component_areas.append(a)
        edge_component_count = int(len(component_areas))
        sum_area = float(sum(component_areas))
        largest_ratio = (float(max(component_areas)) / sum_area) if sum_area > 0 else 1.0
        score_components = self._range_score(float(edge_component_count), 45.0, 180.0)
        score_largest_ratio = 1.0 - self._range_score(largest_ratio, 0.22, 0.65)

        score = (
            0.22 * score_coverage
            + 0.18 * score_entropy
            + 0.12 * score_density
            + 0.10 * score_spread
            + 0.14 * score_tile_active
            + 0.08 * score_tile_uniform
            + 0.10 * score_components
            + 0.06 * score_largest_ratio
        )

        return {
            "score": self._clamp01(score),
            "coverage": float(coverage),
            "orientation_entropy": float(entropy_norm),
            "kp_count": int(kp_count),
            "kp_density": float(kp_density),
            "kp_spread": float(kp_spread),
            "tile_active_ratio": float(tile_active_ratio),
            "tile_coverage_std": float(tile_coverage_std),
            "edge_component_count": int(edge_component_count),
            "largest_edge_component_ratio": float(largest_ratio),
        }

    def quality_score(self, img: np.ndarray) -> float:
        """
        Heuristic quality score in [0, 1].

        Three components:
        - coverage  (weight 0.65): fraction of pixels with non-trivial gradient,
                measured on the RAW image before CLAHE. CLAHE amplifies noise on
                blank white areas, creating fake gradients and inflating coverage.
                Fingerprints have ridges across the whole image (coverage >0.25).
                Diagrams on white paper have only a few lines (coverage <0.04).
        - edge_density (0.20): Canny edge fraction on preprocessed image.
        - sharpness   (0.15): Laplacian variance on preprocessed image.
        """
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return 0.0

        # Coverage on the raw normalized image — before CLAHE so blank-area noise
        # isn't amplified into fake ridges.
        raw_norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        gx_r = cv2.Sobel(raw_norm.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        gy_r = cv2.Sobel(raw_norm.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx_r * gx_r + gy_r * gy_r)
        coverage = float(np.sum(grad_mag > 12.0)) / float(h * w)
        score_coverage = min(1.0, coverage / 0.25)  # 0.25 coverage -> full score

        proc = self.preprocess(img)
        edges = cv2.Canny(proc, 45, 140)
        edge_density = float(np.sum(edges > 0)) / float(h * w)
        score_edge = min(1.0, max(0.0, edge_density / 0.25))

        lap_var = float(cv2.Laplacian(proc, cv2.CV_32F).var())
        score_sharp = min(1.0, lap_var / 300.0)

        score = 0.65 * score_coverage + 0.20 * score_edge + 0.15 * score_sharp
        return float(max(0.0, min(1.0, score)))

    def extract_template(self, img_gray: np.ndarray) -> dict:
        proc = self.preprocess(img_gray)
        kps, des = self.detector.detectAndCompute(proc, None)
        if des is None or len(kps) < 30:
            raise ValueError("Fingerprint features not found. Use a clearer image.")

        kp_coords = [[float(p.pt[0]), float(p.pt[1])] for p in kps]
        return {
            "algo": "akaze_v2",
            "des": des.tolist(),
            "shape": list(des.shape),
            "kps": kp_coords,
        }

    def deserialize_template(self, tpl: dict):
        if "des" not in tpl or "shape" not in tpl:
            return None, None
        des = np.array(tpl["des"], dtype=np.uint8).reshape(tpl["shape"][0], tpl["shape"][1])
        kps = None
        if "kps" in tpl:
            kps = np.array(tpl["kps"], dtype=np.float32)
        return des, kps

    def match_score(self, query_tpl: dict, db_tpl: dict) -> float:
        q_des, q_kps = self.deserialize_template(query_tpl)
        d_des, d_kps = self.deserialize_template(db_tpl)
        if q_des is None or d_des is None:
            return 0.0

        try:
            knn = self.bf.knnMatch(q_des, d_des, k=2)
            good = []
            for pair in knn:
                if len(pair) < 2:
                    continue
                m, n = pair
                if m.distance < 0.82 * n.distance:  # more permissive ratio test
                    good.append(m)

            num_good = len(good)
            if num_good == 0:
                return 0.0

            if q_kps is not None and d_kps is not None and num_good >= 6:
                pts_q = np.float32([q_kps[m.queryIdx] for m in good]).reshape(-1, 2)
                pts_d = np.float32([d_kps[m.trainIdx] for m in good]).reshape(-1, 2)
                _, mask = cv2.findHomography(pts_q, pts_d, cv2.RANSAC, 6.0)  # more tolerant RANSAC
                inliers = int(np.sum(mask)) if mask is not None else 0
                inlier_ratio = inliers / float(max(1, num_good))
                score = 0.75 * inlier_ratio + 0.25 * min(1.0, num_good / 40.0)  # 40 good = full score
                return float(max(0.0, min(1.0, score)))

            return float(min(1.0, num_good / 40.0))
        except Exception:
            return 0.0
