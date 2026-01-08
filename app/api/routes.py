import json
from typing import Optional

import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import PersonBiometric

from app.engines.face_engine import FaceEngineONNX
from app.schemas.biometric import EnrollResponse, MatchResponse

# ✅ NEW: Combined verify schema (create app/schemas/verify.py)
from app.schemas.verify import VerifyResponse

# ✅ Fingerprint engine + threshold
from app.engines.fingerprint_engine import FingerprintEngine
from app.core.config import SIMILARITY_THRESHOLD, FACE_MODEL_PATH, FINGERPRINT_THRESHOLD

# ✅ Import fingerprint router
from app.api.fingerprint_routes import router_fp


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
_face_engine: Optional[FaceEngineONNX] = None

def get_face_engine() -> FaceEngineONNX:
    global _face_engine
    if _face_engine is None:
        _face_engine = FaceEngineONNX(FACE_MODEL_PATH)
    return _face_engine


# -----------------------------
# Fingerprint engine (lightweight)
# -----------------------------
fp_engine = FingerprintEngine()


# -----------------------------
# Admin endpoints
# -----------------------------
@router.get("/persons", tags=["Admin"])
def list_persons(db: Session = Depends(get_db)):
    """List enrolled persons (debug/admin)."""
    records = db.query(PersonBiometric).all()
    return [
        {
            "person_id": r.person_id,
            "full_name": r.full_name,
            "has_face": bool(r.face_embedding),
            "has_fingerprint": bool(getattr(r, "fingerprint_template", None)),
        }
        for r in records
    ]


@router.delete("/persons/{person_id}", tags=["Admin"])
def delete_person(person_id: str, db: Session = Depends(get_db)):
    """Delete a person enrollment (debug/admin)."""
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(rec)
    db.commit()
    return {"deleted": True, "person_id": person_id}


# -----------------------------
# Face routes
# -----------------------------
@router.post("/enroll/face", response_model=EnrollResponse, tags=["Face"])
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


@router.post("/match/face", response_model=MatchResponse, tags=["Face"])
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
            if not r.face_embedding:
                continue
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


# -----------------------------
# ✅ NEW: Combined endpoint (Face + Fingerprint)
# -----------------------------
@router.post("/verify", response_model=VerifyResponse, tags=["Verify"])
async def verify(
    face_image: Optional[UploadFile] = File(None),
    fingerprint_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Combined verification endpoint.

    Decision rule:
    - If BOTH provided => BOTH must match (2FA).
    - If only one provided => that one must match.
    """
    if face_image is None and fingerprint_image is None:
        raise HTTPException(status_code=400, detail="Provide at least face_image or fingerprint_image")

    records = crud.fetch_all_embeddings(db)
    if not records:
        return VerifyResponse(
            face_provided=face_image is not None,
            fingerprint_provided=fingerprint_image is not None,
            access_granted=False,
            decision_rule="no_enrollments_in_db",
        )

    # defaults
    face_matched = None
    face_person_id = None
    face_full_name = None
    face_similarity = None

    fp_matched = None
    fp_person_id = None
    fp_full_name = None
    fp_similarity = None

    # ---------- FACE ----------
    if face_image is not None:
        try:
            engine = get_face_engine()
            face_bytes = await face_image.read()
            img = engine.read_image(face_bytes)
            query_emb = engine.get_embedding(img)

            best = None
            best_score = -1.0

            for r in records:
                if not r.face_embedding:
                    continue
                db_emb = np.array(json.loads(r.face_embedding), dtype=np.float32)
                score = engine.cosine_similarity(query_emb, db_emb)
                if score > best_score:
                    best_score = score
                    best = r

            face_matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)
            face_similarity = float(best_score if best is not None else 0.0)
            if face_matched:
                face_person_id = best.person_id
                face_full_name = best.full_name

        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Face error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Face verify failed: {e}")

    # ---------- FINGERPRINT ----------
    if fingerprint_image is not None:
        try:
            fp_bytes = await fingerprint_image.read()
            fp_img = fp_engine.read_image(fp_bytes)

            query_tpl = fp_engine.extract_template(fp_img)
            query_des = fp_engine.deserialize_des(query_tpl)

            best = None
            best_score = -1.0

            for r in records:
                tpl_str = getattr(r, "fingerprint_template", None)
                if not tpl_str:
                    continue
                tpl = json.loads(tpl_str)
                db_des = fp_engine.deserialize_des(tpl)
                score = fp_engine.match_score(query_des, db_des)
                if score > best_score:
                    best_score = score
                    best = r

            fp_matched = (best is not None) and (best_score >= FINGERPRINT_THRESHOLD)
            fp_similarity = float(best_score if best is not None else 0.0)
            if fp_matched:
                fp_person_id = best.person_id
                fp_full_name = best.full_name

        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Fingerprint error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Fingerprint verify failed: {e}")

    # ---------- DECISION ----------
    face_provided = face_image is not None
    fp_provided = fingerprint_image is not None

    if face_provided and fp_provided:
        access_granted = bool(face_matched) and bool(fp_matched)
        decision_rule = "2FA: face AND fingerprint required"
    elif face_provided:
        access_granted = bool(face_matched)
        decision_rule = "1FA: face only"
    else:
        access_granted = bool(fp_matched)
        decision_rule = "1FA: fingerprint only"

    return VerifyResponse(
        face_provided=face_provided,
        fingerprint_provided=fp_provided,

        face_matched=face_matched,
        face_person_id=face_person_id,
        face_full_name=face_full_name,
        face_similarity=face_similarity,
        face_threshold=float(SIMILARITY_THRESHOLD),

        fingerprint_matched=fp_matched,
        fingerprint_person_id=fp_person_id,
        fingerprint_full_name=fp_full_name,
        fingerprint_similarity=fp_similarity,
        fingerprint_threshold=float(FINGERPRINT_THRESHOLD),

        access_granted=access_granted,
        decision_rule=decision_rule,
    )


# -----------------------------
# ✅ Include fingerprint routes (keeps your existing endpoints)
# -----------------------------
router.include_router(router_fp, tags=["Fingerprint"])
