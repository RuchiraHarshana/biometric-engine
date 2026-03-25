import json
import httpx
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.storage.supabase_client import client as sb
from app.core.config import FINGERPRINT_THRESHOLD, MODEL_SERVICE_URL, MODEL_SERVICE_TIMEOUT
from app.auth.dependencies import require_register_access, require_verify_access

router_fp = APIRouter()


async def _post_model_service(path: str, files=None, data=None) -> dict:
    async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=MODEL_SERVICE_TIMEOUT) as client:
        resp = await client.post(path, files=files, data=data)
    resp.raise_for_status()
    return resp.json()


@router_fp.post("/enroll/fingerprint", tags=["Fingerprint"])
async def enroll_fingerprint(
    person_id: str = Form(...),
    full_name: str = Form(""),

    # ✅ Optional profile fields
    email: str = Form(None),
    mobile_number: str = Form(None),
    address: str = Form(None),
    criminal_records: str = Form(None),

    # ✅ Capture method: image_upload | usb_scanner | laptop_scanner
    capture_method: str = Form("image_upload"),

    image: UploadFile = File(...),
    _user=Depends(require_register_access),
):
    VALID_METHODS = {"image_upload", "usb_scanner", "laptop_scanner"}
    if capture_method not in VALID_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid capture_method. Must be one of: {VALID_METHODS}")

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

        # upsert person
        persons = await sb.get("persons", filters={"person_id": person_id})
        person_payload = {
            "person_id": person_id,
            "full_name": full_name or None,
            "email": email,
            "mobile_number": mobile_number,
            "address": address,
            "criminal_records": criminal_records,
        }
        if persons:
            await sb.update("persons", {"person_id": person_id}, person_payload)
        else:
            await sb.insert("persons", person_payload)

        # upsert fingerprint template
        tpl_payload = {"person_id": person_id, "template": template, "capture_method": capture_method}
        existing = await sb.get("fingerprint_templates", filters={"person_id": person_id})
        if existing:
            await sb.update("fingerprint_templates", {"person_id": person_id}, tpl_payload)
        else:
            await sb.insert("fingerprint_templates", tpl_payload)

        return {
            "person_id": person_id,
            "full_name": full_name,
            "capture_method": capture_method,
            "message": "Fingerprint enrolled successfully",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enroll fingerprint failed: {e}")


@router_fp.post("/match/fingerprint", tags=["Fingerprint"])
async def match_fingerprint(
    image: UploadFile = File(...),
    _user=Depends(require_verify_access),
):
    try:
        templates = []
        template_records = []

        # fetch all fingerprint templates
        rows = await sb.get("fingerprint_templates")
        if not rows:
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "threshold": float(FINGERPRINT_THRESHOLD),
            }

        # build person map
        persons = await sb.get("persons")
        pmap = {p.get("person_id"): p for p in persons}

        for r in rows:
            tpl_obj = r.get("template")
            if not tpl_obj:
                continue
            templates.append(tpl_obj)
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

        person_id = best.get("person_id") if matched else None
        full_name = pmap.get(person_id, {}).get("full_name") if person_id else None

        return {
            "matched": matched,
            "person_id": person_id,
            "full_name": full_name,
            "similarity": float(best_score if matched else 0.0),
            "threshold": float(FINGERPRINT_THRESHOLD),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match fingerprint failed: {e}")
