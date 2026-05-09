from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import router
from app.api.auth_routes import router_auth
from app.api.admin_routes import router_admin

app = FastAPI(title="BioSecureGate - Biometric Engine")


def _build_cors_origins() -> list[str]:
    # Supports comma-separated custom origins via env while keeping sensible local defaults.
    defaults = {
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "https://127.0.0.1:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "https://127.0.0.1:3001",
        "https://localhost:3001",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://127.0.0.1:5173",
        "https://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "https://127.0.0.1:5174",
        "https://localhost:5174",
    }

    env_value = os.getenv("CORS_ALLOW_ORIGINS", "")
    env_origins = {origin.strip() for origin in env_value.split(",") if origin.strip()}
    return sorted(defaults | env_origins)


cors_origins = _build_cors_origins()
cors_allow_all = os.getenv("CORS_ALLOW_ALL", "true").lower() in ("1", "true", "yes")
cors_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"https?://.*")

# ✅ CORS (fixes browser preflight OPTIONS requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_allow_all else cors_origins,
    allow_origin_regex=cors_origin_regex if not cors_allow_all else None,
    # With wildcard origins, credentials must be disabled by spec.
    allow_credentials=not cors_allow_all,
    allow_methods=["*"],   # allows OPTIONS, GET, POST, etc.
    allow_headers=["*"],
)

app.include_router(router_auth, prefix="/api")
app.include_router(router_admin, prefix="/api")
app.include_router(router, prefix="/api")

# Serve frontend static files (fingerprint capture UI)
_static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir, html=True), name="static")

@app.get("/")
def home():
    return {
        "message": "BioSecureGate Biometric Engine running",
        "health": "/health",
        "docs": "/docs",
        "endpoints": {
            "login": "/api/auth/login",
            "2fa_setup": "/api/auth/2fa/setup",
            "2fa_verify": "/api/auth/2fa/verify",
            "admin_officers": "/api/admin/officers",
            "enroll_face": "/api/enroll/face",
            "match_face": "/api/match/face",
            "enroll_fingerprint": "/api/enroll/fingerprint",
            "match_fingerprint": "/api/match/fingerprint",
            "enroll_fingerprint_v2": "/api/experimental/enroll/fingerprint",
            "match_fingerprint_v2": "/api/experimental/match/fingerprint",
            "verify": "/api/verify",
            "persons": "/api/persons",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}
