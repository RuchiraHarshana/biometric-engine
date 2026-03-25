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
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "faces")

# Auth
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@biosecuregate.com")
SKIP_2FA = os.getenv("SKIP_2FA", "true").lower() in ("1", "true", "yes")

# SMTP for OTP/email
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("ADMIN_EMAIL", "admin@biosecuregate.com"))
