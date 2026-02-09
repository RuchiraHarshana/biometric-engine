import json
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.engines.fingerprint_engine import FingerprintEngine
from app.core.config import FINGERPRINT_THRESHOLD

router_fp = APIRouter()
fp_engine = FingerprintEngine()


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
        img = fp_engine.read_image(img_bytes)
        template = fp_engine.extract_template(img)

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
        img_bytes = await image.read()
        img = fp_engine.read_image(img_bytes)
        query_tpl = fp_engine.extract_template(img)
        query_des = fp_engine.deserialize_des(query_tpl)

        records = crud.fetch_all_embeddings(db)

        best = None
        best_score = -1.0

        for r in records:
            if not getattr(r, "fingerprint_template", None):
                continue
            tpl = json.loads(r.fingerprint_template)
            db_des = fp_engine.deserialize_des(tpl)
            score = fp_engine.match_score(query_des, db_des)

            if score > best_score:
                best_score = score
                best = r

        matched = (best is not None) and (best_score >= FINGERPRINT_THRESHOLD)

        return {
            "matched": matched,
            "person_id": best.person_id if matched else None,
            "full_name": best.full_name if matched else None,
            "similarity": float(best_score if best is not None else 0.0),
            "threshold": float(FINGERPRINT_THRESHOLD),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match fingerprint failed: {e}")
