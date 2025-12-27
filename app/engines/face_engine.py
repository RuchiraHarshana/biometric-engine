import cv2
import numpy as np
import onnxruntime as ort


class FaceEngineONNX:
    """
    Stable Face Recognition Engine (University-ready)

    - Haar Cascade face detection
    - ArcFace ONNX embedding model
    - Cosine similarity matching
    """

    def __init__(self, model_path: str):
        self.model_path = model_path

        # Load ArcFace ONNX model
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self.input = self.session.get_inputs()[0]
        self.output = self.session.get_outputs()[0]

        self.input_name = self.input.name
        self.output_name = self.output.name

        # Expected input size (usually 112x112)
        shape = self.input.shape
        self.input_h = int(shape[2]) if isinstance(shape[2], int) else 112
        self.input_w = int(shape[3]) if isinstance(shape[3], int) else 112

        # Haar face detector
        self.detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def read_image(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image file.")
        return img

    def detect_face(self, img_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )

        if len(faces) == 0:
            raise ValueError("No face detected.")

        # Select largest face
        x, y, w, h = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]

        # Padding improves recognition robustness
        pad = int(0.15 * max(w, h))
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_bgr.shape[1], x + w + pad)
        y2 = min(img_bgr.shape[0], y + h + pad)

        face = img_bgr[y1:y2, x1:x2]
        if face.size == 0:
            raise ValueError("Face crop failed.")

        return face

    def preprocess(self, face_bgr: np.ndarray) -> np.ndarray:
        face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        face_resized = cv2.resize(face_rgb, (self.input_w, self.input_h))

        img = face_resized.astype(np.float32)
        img = (img - 127.5) / 128.0

        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        return img

    def get_embedding(self, img_bgr: np.ndarray) -> np.ndarray:
        face = self.detect_face(img_bgr)
        inp = self.preprocess(face)

        out = self.session.run(
            [self.output_name],
            {self.input_name: inp}
        )[0]

        emb = out.flatten().astype(np.float32)

        norm = np.linalg.norm(emb)
        if norm == 0:
            raise ValueError("Invalid embedding vector.")
        return emb / norm

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))
