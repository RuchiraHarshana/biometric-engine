import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./biometric.db")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))
FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", "app/models/arcface.onnx")
SCRFD_MODEL_PATH = os.getenv("SCRFD_MODEL_PATH", "app/models/scrfd_person_2.5g.onnx")
SCRFD_DET_SIZE = int(os.getenv("SCRFD_DET_SIZE", "640"))
SCRFD_THRESH = float(os.getenv("SCRFD_THRESH", "0.5"))
SCRFD_NMS = float(os.getenv("SCRFD_NMS", "0.4"))
FINGERPRINT_THRESHOLD = float(os.getenv("FINGERPRINT_THRESHOLD", "0.45"))
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://localhost:8001")
MODEL_SERVICE_TIMEOUT = float(os.getenv("MODEL_SERVICE_TIMEOUT", "30"))
