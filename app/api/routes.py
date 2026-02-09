import json
from typing import Optional
from pathlib import Path

import numpy as np
import httpx
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import PersonBiometric

from app.schemas.biometric import EnrollResponse, MatchResponse
from app.schemas.verify import VerifyResponse

from app.core.config import SIMILARITY_THRESHOLD, FINGERPRINT_THRESHOLD, MODEL_SERVICE_URL, MODEL_SERVICE_TIMEOUT

# ✅ Import fingerprint router
from app.api.fingerprint_routes import router_fp


router = APIRouter()

UPLOAD_DIR = Path("app/uploads/faces")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _post_model_service(path: str, files=None, data=None) -> dict:
    async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=MODEL_SERVICE_TIMEOUT) as client:
        resp = await client.post(path, files=files, data=data)
    resp.raise_for_status()
    return resp.json()


async def get_face_embedding(image: UploadFile, image_bytes: bytes) -> np.ndarray:
    files = {"image": (image.filename or "face.jpg", image_bytes, image.content_type or "application/octet-stream")}
    payload = await _post_model_service("/face/embedding", files=files)
    return np.array(payload["embedding"], dtype=np.float32)


# -----------------------------
# Admin endpoints
# -----------------------------
@router.get("/persons", tags=["Admin"])
def list_persons(db: Session = Depends(get_db)):
    records = db.query(PersonBiometric).all()
    return [
        {
            "person_id": r.person_id,
            "full_name": r.full_name,

            "email": r.email,
            "mobile_number": r.mobile_number,
            "address": r.address,
            "criminal_records": r.criminal_records,

            "has_face": bool(r.face_embedding),
            "has_fingerprint": bool(getattr(r, "fingerprint_template", None)),

            "face_image_path": r.face_image_path,
            "face_image_url": f"/api/persons/{r.person_id}/face-image" if r.face_image_path else None,
        }
        for r in records
    ]


@router.get("/persons/{person_id}/face-image", tags=["Admin"])
def get_face_image(person_id: str, db: Session = Depends(get_db)):
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if not rec or not rec.face_image_path:
        raise HTTPException(status_code=404, detail="Face image not found")

    path = Path(rec.face_image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Face image file missing on disk")

    return FileResponse(path)


@router.delete("/persons/{person_id}", tags=["Admin"])
def delete_person(person_id: str, db: Session = Depends(get_db)):
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Person not found")

    # delete face file if exists
    if rec.face_image_path:
        try:
            p = Path(rec.face_image_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass

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

    # ✅ Optional profile fields (will appear in Swagger)
    email: str = Form(None),
    mobile_number: str = Form(None),
    address: str = Form(None),
    criminal_records: str = Form(None),

    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        img_bytes = await image.read()
        emb = await get_face_embedding(image, img_bytes)

        # ✅ Save face image to disk for displaying later
        save_path = UPLOAD_DIR / f"{person_id}.jpg"
        save_path.write_bytes(img_bytes)

        rec = crud.upsert_face_embedding(
            db=db,
            person_id=person_id,
            full_name=full_name,
            embedding_list=emb.tolist(),
            email=email,
            mobile_number=mobile_number,
            address=address,
            criminal_records=criminal_records,
            face_image_path=str(save_path),
        )

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
    try:
        img_bytes = await image.read()
        query_emb = await get_face_embedding(image, img_bytes)

        records = crud.fetch_all_embeddings(db)
        if not records:
            return MatchResponse(
                matched=False,
                person_id=None,
                full_name=None,
                similarity=0.0,
                threshold=float(SIMILARITY_THRESHOLD),
            )

        best = None
        best_score = float("-inf")

        for r in records:
            if not r.face_embedding:
                continue
            db_emb = np.array(json.loads(r.face_embedding), dtype=np.float32)
            score = float(np.dot(query_emb, db_emb))
            if score > best_score:
                best_score = score
                best = r

        matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)

        return MatchResponse(
            matched=matched,
            person_id=best.person_id if matched else None,
            full_name=best.full_name if matched else None,
            similarity=float(best_score if best is not None else 0.0),
            threshold=float(SIMILARITY_THRESHOLD),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match failed: {e}")


# -----------------------------
# ✅ Combined endpoint (Face + Fingerprint)
# -----------------------------
@router.post("/verify", response_model=VerifyResponse, tags=["Verify"])
async def verify(
    face_image: Optional[UploadFile] = File(None),
    fingerprint_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if face_image is None and fingerprint_image is None:
        raise HTTPException(status_code=400, detail="Provide at least face_image or fingerprint_image")

    records = crud.fetch_all_embeddings(db)
    if not records:
        return VerifyResponse(
            face_provided=face_image is not None,
            fingerprint_provided=fingerprint_image is not None,
            face_matched=None,
            face_person_id=None,
            face_full_name=None,
            face_similarity=None,
            face_threshold=float(SIMILARITY_THRESHOLD),
            fingerprint_matched=None,
            fingerprint_person_id=None,
            fingerprint_full_name=None,
            fingerprint_similarity=None,
            fingerprint_threshold=float(FINGERPRINT_THRESHOLD),
            access_granted=False,
            decision_rule="no_enrollments_in_db",
        )

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
        face_bytes = await face_image.read()
        query_emb = await get_face_embedding(face_image, face_bytes)

        best = None
        best_score = float("-inf")

        for r in records:
            if not r.face_embedding:
                continue
            db_emb = np.array(json.loads(r.face_embedding), dtype=np.float32)
            score = float(np.dot(query_emb, db_emb))
            if score > best_score:
                best_score = score
                best = r

        face_similarity = float(best_score if best is not None else 0.0)
        face_matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)

        if face_matched:
            face_person_id = best.person_id
            face_full_name = best.full_name

    # ---------- FINGERPRINT ----------
    if fingerprint_image is not None:
        templates = []
        template_records = []

        for r in records:
            tpl_str = getattr(r, "fingerprint_template", None)
            if not tpl_str:
                continue
            templates.append(json.loads(tpl_str))
            template_records.append(r)

        if templates:
            fp_bytes = await fingerprint_image.read()
            files = {
                "image": (
                    fingerprint_image.filename or "fingerprint.jpg",
                    fp_bytes,
                    fingerprint_image.content_type or "application/octet-stream",
                )
            }
            data = {"templates": json.dumps(templates)}
            payload = await _post_model_service("/fingerprint/match", files=files, data=data)

            best_index = payload.get("best_index")
            best_score = float(payload.get("score", 0.0))

            fp_similarity = best_score
            fp_matched = (best_index is not None) and (best_score >= FINGERPRINT_THRESHOLD)

            if fp_matched:
                best = template_records[int(best_index)]
                fp_person_id = best.person_id
                fp_full_name = best.full_name

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


# keep existing fingerprint endpoints
router.include_router(router_fp)
