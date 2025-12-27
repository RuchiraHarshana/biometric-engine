import json
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import PersonBiometric
from app.engines.face_engine import FaceEngineONNX
from app.schemas.biometric import EnrollResponse, MatchResponse
from app.core.config import SIMILARITY_THRESHOLD, FACE_MODEL_PATH

router = APIRouter()

# -----------------------------
# DB dependency
# -----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Lazy-loaded Face Engine
# (prevents startup hanging)
# -----------------------------
_face_engine = None

def get_face_engine() -> FaceEngineONNX:
    global _face_engine
    if _face_engine is None:
        _face_engine = FaceEngineONNX(FACE_MODEL_PATH)
    return _face_engine

# -----------------------------
# Admin endpoints
# -----------------------------
@router.get("/persons")
def list_persons(db: Session = Depends(get_db)):
    """List enrolled persons (debug/admin)."""
    records = db.query(PersonBiometric).all()
    return [{"person_id": r.person_id, "full_name": r.full_name} for r in records]

@router.delete("/persons/{person_id}")
def delete_person(person_id: str, db: Session = Depends(get_db)):
    """Delete a person enrollment (debug/admin)."""
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(rec)
    db.commit()
    return {"deleted": True, "person_id": person_id}

# -----------------------------
# Biometric routes
# -----------------------------
@router.post("/enroll/face", response_model=EnrollResponse)
async def enroll_face(
    person_id: str = Form(...),
    full_name: str = Form(""),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Enroll a person's face embedding.
    Note: Quality checks are performed on the detected FACE region inside FaceEngineONNX.get_embedding().
    """
    try:
        engine = get_face_engine()

        img_bytes = await image.read()
        img = engine.read_image(img_bytes)

        # ✅ Face detection + face-only quality checks happen inside get_embedding()
        emb = engine.get_embedding(img)

        rec = crud.upsert_face_embedding(db, person_id, full_name, emb.tolist())
        return EnrollResponse(
            person_id=rec.person_id,
            full_name=rec.full_name or "",
            message="Face enrolled successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enroll failed: {e}")

@router.post("/match/face", response_model=MatchResponse)
async def match_face(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Match a face against enrolled embeddings.
    Note: Quality checks are performed on the detected FACE region inside FaceEngineONNX.get_embedding().
    """
    try:
        engine = get_face_engine()

        img_bytes = await image.read()
        img = engine.read_image(img_bytes)

        # ✅ Face detection + face-only quality checks happen inside get_embedding()
        query_emb = engine.get_embedding(img)

        records = crud.fetch_all_embeddings(db)
        if not records:
            return MatchResponse(
                matched=False,
                person_id=None,
                full_name=None,
                similarity=0.0,
                threshold=SIMILARITY_THRESHOLD,
            )

        best = None
        best_score = -1.0

        for r in records:
            db_emb = np.array(json.loads(r.face_embedding), dtype=np.float32)
            score = engine.cosine_similarity(query_emb, db_emb)

            if score > best_score:
                best_score = score
                best = r

        matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)

        return MatchResponse(
            matched=matched,
            person_id=best.person_id if matched else None,
            full_name=best.full_name if matched else None,
            similarity=float(best_score if best is not None else 0.0),
            threshold=SIMILARITY_THRESHOLD,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match failed: {e}")
