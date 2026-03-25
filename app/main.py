from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.auth_routes import router_auth
from app.api.admin_routes import router_admin

app = FastAPI(title="BioSecureGate - Biometric Engine")

# ✅ CORS (fixes browser preflight OPTIONS requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],   # allows OPTIONS, GET, POST, etc.
    allow_headers=["*"],
)

app.include_router(router_auth, prefix="/api")
app.include_router(router_admin, prefix="/api")
app.include_router(router, prefix="/api")

# Serve frontend static files (fingerprint capture UI)
import os
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
            "verify": "/api/verify",
            "persons": "/api/persons",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}
