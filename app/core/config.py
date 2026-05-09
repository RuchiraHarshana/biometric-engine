import os
from dotenv import load_dotenv

load_dotenv()


def _clean_env(value: str | None, default: str = "") -> str:
	if value is None:
		return default
	# Secret Manager values can occasionally include BOM or null bytes.
	return value.replace("\x00", "").lstrip("\ufeff").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./biometric.db")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))
FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", "app/models/arcface.onnx")
SCRFD_MODEL_PATH = os.getenv("SCRFD_MODEL_PATH", "app/models/scrfd_person_2.5g.onnx")
SCRFD_DET_SIZE = int(os.getenv("SCRFD_DET_SIZE", "640"))
SCRFD_THRESH = float(os.getenv("SCRFD_THRESH", "0.5"))
SCRFD_NMS = float(os.getenv("SCRFD_NMS", "0.4"))
FINGERPRINT_THRESHOLD = float(os.getenv("FINGERPRINT_THRESHOLD", "0.85"))
FINGERPRINT_FP_SCORE_THRESHOLD = float(os.getenv("FINGERPRINT_FP_SCORE_THRESHOLD", "0.85"))
FINGERPRINT_FP_HIGH = float(os.getenv("FINGERPRINT_FP_HIGH", "0.90"))
FINGERPRINT_FP_LOW = float(os.getenv("FINGERPRINT_FP_LOW", "0.65"))
FINGERPRINT_REVIEW_SIMILARITY = float(os.getenv("FINGERPRINT_REVIEW_SIMILARITY", "0.40"))

# Fingerprint V2 thresholds (anti-diagram gates)
def _env_float_floor(name: str, default: float, floor: float) -> float:
	raw = os.getenv(name)
	try:
		v = float(raw) if raw is not None else float(default)
	except Exception:
		v = float(default)
	return max(v, floor)

def _env_int_floor(name: str, default: int, floor: int) -> int:
	raw = os.getenv(name)
	try:
		v = int(raw) if raw is not None else int(default)
	except Exception:
		v = int(default)
	return max(v, floor)

def _env_float_ceil(name: str, default: float, ceil: float) -> float:
	raw = os.getenv(name)
	try:
		v = float(raw) if raw is not None else float(default)
	except Exception:
		v = float(default)
	return min(v, ceil)

FINGERPRINT_V2_THRESHOLD = float(os.getenv("FINGERPRINT_V2_THRESHOLD", "0.40"))
FINGERPRINT_V2_QUALITY_THRESHOLD = _env_float_floor("FINGERPRINT_V2_QUALITY_THRESHOLD", 0.28, 0.10)
FINGERPRINT_V2_FP_SCORE_THRESHOLD = float(os.getenv("FINGERPRINT_V2_FP_SCORE_THRESHOLD", "0.20"))
FINGERPRINT_V2_LIKENESS_THRESHOLD = _env_float_floor("FINGERPRINT_V2_LIKENESS_THRESHOLD", 0.50, 0.15)
FINGERPRINT_V2_MIN_COVERAGE = _env_float_floor("FINGERPRINT_V2_MIN_COVERAGE", 0.14, 0.08)
FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY = _env_float_floor("FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY", 0.58, 0.40)
FINGERPRINT_V2_MIN_KP_COUNT = _env_int_floor("FINGERPRINT_V2_MIN_KP_COUNT", 35, 20)
FINGERPRINT_V2_MIN_KP_SPREAD = _env_float_floor("FINGERPRINT_V2_MIN_KP_SPREAD", 0.12, 0.06)
FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO", 0.28, 0.15)
FINGERPRINT_V2_MAX_TILE_COVERAGE_STD = _env_float_ceil("FINGERPRINT_V2_MAX_TILE_COVERAGE_STD", 0.24, 0.24)
FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT = _env_int_floor("FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT", 45, 25)
FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO = _env_float_ceil("FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO", 0.32, 0.32)
FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO", 0.20, 0.08)
FINGERPRINT_V2_MIN_MEAN_PERIODICITY = _env_float_floor("FINGERPRINT_V2_MIN_MEAN_PERIODICITY", 4.5, 2.0)
FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO", 0.12, 0.06)
MODEL_SERVICE_URL = _clean_env(os.getenv("MODEL_SERVICE_URL"), "http://localhost:8001")
MODEL_SERVICE_TIMEOUT = float(os.getenv("MODEL_SERVICE_TIMEOUT", "30"))
SUPABASE_URL = _clean_env(os.getenv("SUPABASE_URL"), "")
SUPABASE_SERVICE_KEY = _clean_env(os.getenv("SUPABASE_SERVICE_KEY"), "")
SUPABASE_BUCKET = _clean_env(os.getenv("SUPABASE_BUCKET"), "faces")

# Auth
JWT_SECRET = _clean_env(os.getenv("JWT_SECRET"), "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
ADMIN_EMAIL = _clean_env(os.getenv("ADMIN_EMAIL"), "admin@biosecuregate.com")
SKIP_2FA = os.getenv("SKIP_2FA", "true").lower() in ("1", "true", "yes")

# SMTP for OTP/email
SMTP_HOST = _clean_env(os.getenv("SMTP_HOST"), "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = _clean_env(os.getenv("SMTP_USER"), "")
SMTP_PASS = _clean_env(os.getenv("SMTP_PASS"), "")
SMTP_FROM = _clean_env(os.getenv("SMTP_FROM"), ADMIN_EMAIL)
