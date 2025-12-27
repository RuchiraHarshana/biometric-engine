from fastapi import FastAPI
from app.api.routes import router
from app.db.session import Base, engine

app = FastAPI(title="BioSecureGate - Biometric Engine")

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
        },
    }

@app.get("/health")
def health():
    return {"status": "ok"}
