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

    def quality_score(self, img: np.ndarray) -> float:
        """
        Heuristic quality score in [0, 1] combining edge density and sharpness.
        """
        proc = self.preprocess(img)
        h, w = proc.shape
        if h == 0 or w == 0:
            return 0.0

        edges = cv2.Canny(proc, 45, 140)
        edge_density = float(np.sum(edges > 0)) / float(h * w)
        lap_var = float(cv2.Laplacian(proc, cv2.CV_32F).var())

        score_edge = min(1.0, max(0.0, edge_density / 0.25))
        score_sharp = min(1.0, lap_var / 300.0)
        score = 0.55 * score_edge + 0.45 * score_sharp
        return float(max(0.0, min(1.0, score)))

    def extract_template(self, img_gray: np.ndarray) -> dict:
        proc = self.preprocess(img_gray)
        kps, des = self.detector.detectAndCompute(proc, None)
        if des is None or len(kps) < 6:
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
