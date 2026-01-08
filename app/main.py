from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.session import Base, engine

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

# create tables
Base.metadata.create_all(bind=engine)

app.include_router(router, prefix="/api")

@app.get("/")
def home():
    return {
        "message": "BioSecureGate Biometric Engine running",
        "health": "/health",
        "docs": "/docs",
        "endpoints": {
            "enroll_face": "/api/enroll/face",
            "match_face": "/api/match/face",
            "enroll_fingerprint": "/api/enroll/fingerprint",
            "match_fingerprint": "/api/match/fingerprint",
            "persons": "/api/persons",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}
