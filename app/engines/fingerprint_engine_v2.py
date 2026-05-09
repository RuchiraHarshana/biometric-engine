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
        self.max_template_keypoints = 200

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
                "periodic_tile_ratio": 0.0,
                "mean_periodicity": 0.0,
                "ridge_block_ratio": 0.0,
                "line_count": 0,
                "circle_count": 0,
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

        theta = (np.arctan2(gy, gx) + np.pi) % np.pi

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

        # Fingerprints exhibit repeated ridge spacing in many local tiles.
        # Diagrams/photos can have edges, but usually not consistent mid-frequency periodicity.
        tile_size = 32
        periodic_hits = 0
        periodic_scores = []
        ridge_blocks = 0
        total_blocks = 0
        for y0 in range(0, max(1, h - tile_size + 1), tile_size):
            for x0 in range(0, max(1, w - tile_size + 1), tile_size):
                tile = arr[y0:y0 + tile_size, x0:x0 + tile_size]
                if tile.shape[0] != tile_size or tile.shape[1] != tile_size:
                    continue
                total_blocks += 1
                tile = tile - float(np.mean(tile))
                if float(np.std(tile)) < 10.0:
                    continue

                gx_t = gx[y0:y0 + tile_size, x0:x0 + tile_size]
                gy_t = gy[y0:y0 + tile_size, x0:x0 + tile_size]
                grad_t = np.sqrt(gx_t * gx_t + gy_t * gy_t)
                informative_t = grad_t > 12.0
                tile_cov = float(np.mean(informative_t)) if informative_t.size else 0.0

                theta_t = theta[y0:y0 + tile_size, x0:x0 + tile_size]
                theta_vals = theta_t[informative_t]
                if theta_vals.size >= 24:
                    vcos = np.cos(2.0 * theta_vals)
                    vsin = np.sin(2.0 * theta_vals)
                    tile_coh = float(np.sqrt(np.sum(vcos) ** 2 + np.sum(vsin) ** 2) / max(1.0, theta_vals.size))
                else:
                    tile_coh = 0.0

                window = np.outer(np.hanning(tile_size), np.hanning(tile_size)).astype(np.float32)
                f = np.fft.fftshift(np.fft.fft2(tile * window))
                mag = np.abs(f)
                yy, xx = np.indices((tile_size, tile_size))
                cy = cx = tile_size // 2
                rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
                # Mid-frequency annulus where fingerprint ridge spacing usually lives.
                band = mag[(rr >= 3.0) & (rr <= 10.0)]
                if band.size < 8:
                    continue
                peak = float(np.max(band))
                med = float(np.median(band))
                periodicity = peak / (med + 1e-6)
                periodic_scores.append(periodicity)
                if periodicity >= 6.0:
                    periodic_hits += 1
                if tile_cov >= 0.10 and tile_coh >= 0.55 and periodicity >= 6.0:
                    ridge_blocks += 1

        periodic_tile_ratio = float(periodic_hits) / float(max(1, len(periodic_scores)))
        mean_periodicity = float(np.mean(periodic_scores)) if periodic_scores else 0.0
        ridge_block_ratio = float(ridge_blocks) / float(max(1, total_blocks))
        score_periodic_tiles = self._range_score(periodic_tile_ratio, 0.22, 0.55)
        score_periodicity = self._range_score(mean_periodicity, 4.0, 10.0)
        score_ridge_blocks = self._range_score(ridge_block_ratio, 0.12, 0.35)

        # Fingerprints have varied local ridge directions (loops/whorls/arcs),
        # while simple drawings often have only a few dominant directions.
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

        # Geometric primitive detector (center crop): diagrams often contain long straight
        # lines and circles; real fingerprints rarely contain those primitives in the core area.
        ch, cw = proc.shape[:2]
        y0 = int(0.08 * ch)
        y1 = int(0.92 * ch)
        x0 = int(0.08 * cw)
        x1 = int(0.92 * cw)
        core = proc[y0:y1, x0:x1] if (y1 > y0 and x1 > x0) else proc
        core_edges = cv2.Canny(core, 55, 160)
        min_len = int(0.30 * min(core.shape[0], core.shape[1]))
        lines = cv2.HoughLinesP(core_edges, 1, np.pi / 180.0, threshold=60, minLineLength=max(16, min_len), maxLineGap=6)
        line_count = int(len(lines)) if lines is not None else 0

        circles = cv2.HoughCircles(
            cv2.GaussianBlur(core, (5, 5), 1.2),
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(20, int(0.12 * min(core.shape[:2]))),
            param1=120,
            param2=24,
            minRadius=max(8, int(0.06 * min(core.shape[:2]))),
            maxRadius=max(20, int(0.45 * min(core.shape[:2]))),
        )
        circle_count = int(circles.shape[1]) if circles is not None else 0

        score = (
            0.16 * score_coverage
            + 0.14 * score_entropy
            + 0.10 * score_density
            + 0.08 * score_spread
            + 0.12 * score_tile_active
            + 0.08 * score_tile_uniform
            + 0.10 * score_components
            + 0.06 * score_largest_ratio
            + 0.10 * score_periodic_tiles
            + 0.06 * score_periodicity
            + 0.08 * score_ridge_blocks
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
            "periodic_tile_ratio": float(periodic_tile_ratio),
            "mean_periodicity": float(mean_periodicity),
            "ridge_block_ratio": float(ridge_block_ratio),
            "line_count": int(line_count),
            "circle_count": int(circle_count),
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

        # Cap template size to keep API/database payloads stable in production.
        if len(kps) > self.max_template_keypoints:
            idx = np.argsort([-float(k.response) for k in kps])[: self.max_template_keypoints]
            des = des[idx]
            kps = [kps[int(i)] for i in idx]

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

            # Reward descriptor agreement directly so same-finger partial captures
            # are not over-penalized by a fragile global homography fit.
            score_matches = float(min(1.0, num_good / 28.0))
            mean_distance = float(np.mean([m.distance for m in good]))
            score_distance = float(max(0.0, min(1.0, 1.0 - (mean_distance / 80.0))))

            if q_kps is not None and d_kps is not None and num_good >= 6:
                pts_q = np.float32([q_kps[m.queryIdx] for m in good]).reshape(-1, 2)
                pts_d = np.float32([d_kps[m.trainIdx] for m in good]).reshape(-1, 2)
                _, mask = cv2.findHomography(pts_q, pts_d, cv2.RANSAC, 6.0)  # more tolerant RANSAC
                inliers = int(np.sum(mask)) if mask is not None else 0
                inlier_ratio = inliers / float(max(1, num_good))
                score = 0.45 * inlier_ratio + 0.35 * score_matches + 0.20 * score_distance
                return float(max(0.0, min(1.0, score)))

            score = 0.70 * score_matches + 0.30 * score_distance
            return float(max(0.0, min(1.0, score)))
        except Exception:
            return 0.0
