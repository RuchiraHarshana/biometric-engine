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

    def extract_template(self, img_gray: np.ndarray) -> dict:
        img = self.preprocess(img_gray)
        kp, des = self.orb.detectAndCompute(img, None)
        if des is None or len(kp) < 10:
            raise ValueError("Fingerprint features not found. Use a clearer fingerprint image.")

        # Save descriptors only (enough for baseline)
        return {
            "des": des.tolist(),
            "shape": list(des.shape),
        }

    def match_score(self, des1: np.ndarray, des2: np.ndarray) -> float:
        if des1 is None or des2 is None:
            return 0.0
        matches = self.bf.match(des1, des2)
        if len(matches) == 0:
            return 0.0

        matches = sorted(matches, key=lambda m: m.distance)
        top = matches[: min(60, len(matches))]
        avg_dist = float(np.mean([m.distance for m in top]))

        # Convert distance -> similarity (0..1)
        sim = max(0.0, 1.0 - (avg_dist / 100.0))
        return sim

    def deserialize_des(self, tpl: dict) -> np.ndarray:
        des = np.array(tpl["des"], dtype=np.uint8).reshape(tpl["shape"][0], tpl["shape"][1])
        return des
