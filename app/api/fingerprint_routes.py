import json
import httpx
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.core.config import FINGERPRINT_THRESHOLD, MODEL_SERVICE_URL, MODEL_SERVICE_TIMEOUT

router_fp = APIRouter()
async def _post_model_service(path: str, files=None, data=None) -> dict:
    async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=MODEL_SERVICE_TIMEOUT) as client:
        resp = await client.post(path, files=files, data=data)
    resp.raise_for_status()
    return resp.json()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router_fp.post("/enroll/fingerprint", tags=["Fingerprint"])
async def enroll_fingerprint(
    person_id: str = Form(...),
    full_name: str = Form(""),

    # ✅ Optional profile fields
    email: str = Form(None),
    mobile_number: str = Form(None),
    address: str = Form(None),
    criminal_records: str = Form(None),

    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        img_bytes = await image.read()
        files = {
            "image": (
                image.filename or "fingerprint.jpg",
                img_bytes,
                image.content_type or "application/octet-stream",
            )
        }
        payload = await _post_model_service("/fingerprint/template", files=files)
        template = payload["template"]

        rec = crud.upsert_fingerprint_template(
            db=db,
            person_id=person_id,
            full_name=full_name,
            template_dict=template,
            email=email,
            mobile_number=mobile_number,
            address=address,
            criminal_records=criminal_records,
        )

        return {
            "person_id": rec.person_id,
            "full_name": rec.full_name,
            "message": "Fingerprint enrolled successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enroll fingerprint failed: {e}")


@router_fp.post("/match/fingerprint", tags=["Fingerprint"])
async def match_fingerprint(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        records = crud.fetch_all_embeddings(db)
        templates = []
        template_records = []

        for r in records:
            if not getattr(r, "fingerprint_template", None):
                continue
            templates.append(json.loads(r.fingerprint_template))
            template_records.append(r)

        if not templates:
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "threshold": float(FINGERPRINT_THRESHOLD),
            }

        img_bytes = await image.read()
        files = {
            "image": (
                image.filename or "fingerprint.jpg",
                img_bytes,
                image.content_type or "application/octet-stream",
            )
        }
        data = {"templates": json.dumps(templates)}
        payload = await _post_model_service("/fingerprint/match", files=files, data=data)

        best_index = payload.get("best_index")
        best_score = float(payload.get("score", 0.0))

        matched = (best_index is not None) and (best_score >= FINGERPRINT_THRESHOLD)
        best = template_records[int(best_index)] if matched else None

        return {
            "matched": matched,
            "person_id": best.person_id if matched else None,
            "full_name": best.full_name if matched else None,
            "similarity": float(best_score if matched else 0.0),
            "threshold": float(FINGERPRINT_THRESHOLD),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match fingerprint failed: {e}")
