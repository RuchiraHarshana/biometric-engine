import json

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import require_register_access, require_verify_access
from app.core.config import MODEL_SERVICE_TIMEOUT, MODEL_SERVICE_URL
from app.storage.supabase_client import client as sb


router_fp_v2 = APIRouter()


def _v2_table_help() -> str:
    return (
        "Missing table fingerprint_templates_v2. "
        "Apply SQL migration in supabase/migration_add_fingerprint_v2.sql first."
    )


def _is_missing_table_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "fingerprint_templates_v2" in msg and ("does not exist" in msg or "404" in msg)


async def _post_model_service(path: str, files=None, data=None) -> dict:
    async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=MODEL_SERVICE_TIMEOUT) as client:
        resp = await client.post(path, files=files, data=data)

    if resp.status_code >= 400:
        try:
            payload = resp.json()
            detail = payload.get("detail") if isinstance(payload, dict) else resp.text
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=f"Model service error: {detail}")

    return resp.json()


@router_fp_v2.post("/experimental/enroll/fingerprint", tags=["Fingerprint V2"])
async def enroll_fingerprint_v2(
    person_id: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(None),
    mobile_number: str = Form(None),
    address: str = Form(None),
    criminal_records: str = Form(None),
    finger_label: str = Form("right_thumb"),
    capture_method: str = Form("image_upload"),
    image: UploadFile = File(...),
    _user=Depends(require_register_access),
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
        payload = await _post_model_service("/fingerprint_v2/template", files=files)

        if "error" in payload or "template" not in payload:
            quality = payload.get("quality_score")
            qtxt = f"{quality:.2f}" if isinstance(quality, (int, float)) else "N/A"
            raise HTTPException(
                status_code=400,
                detail=(
                    "Fingerprint V2 quality check failed. "
                    f"quality_score={qtxt}. Please recapture a clearer image."
                ),
            )

        template = payload["template"]

        # Keep compatibility with legacy enroll flow: ensure person exists first.
        person_payload = {
            "person_id": person_id,
            "full_name": full_name or None,
            "email": email,
            "mobile_number": mobile_number,
            "address": address,
            "criminal_records": criminal_records,
        }
        persons = await sb.get("persons", filters={"person_id": person_id})
        if persons:
            await sb.update("persons", {"person_id": person_id}, person_payload)
        else:
            await sb.insert("persons", person_payload)

        row_payload = {
            "person_id": person_id,
            "finger_label": finger_label,
            "template": template,
            "capture_method": capture_method,
            "algorithm": payload.get("algorithm", "akaze_v2"),
            "quality_score": payload.get("quality_score"),
        }

        existing = await sb.get("fingerprint_templates_v2", filters={"person_id": person_id, "finger_label": finger_label})
        if existing:
            await sb.update("fingerprint_templates_v2", {"id": existing[0].get("id")}, row_payload)
        else:
            await sb.insert("fingerprint_templates_v2", row_payload)

        return {
            "message": "Fingerprint enrolled successfully (experimental v2)",
            "person_id": person_id,
            "finger_label": finger_label,
            "algorithm": row_payload["algorithm"],
            "quality_score": row_payload["quality_score"],
        }
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e):
            raise HTTPException(status_code=500, detail=_v2_table_help())
        raise HTTPException(status_code=500, detail=f"Enroll fingerprint v2 failed: {e}")


@router_fp_v2.post("/experimental/match/fingerprint", tags=["Fingerprint V2"])
async def match_fingerprint_v2(
    image: UploadFile = File(...),
    finger_label: str = Form(""),
    _user=Depends(require_verify_access),
):
    try:
        filters = {"finger_label": finger_label} if finger_label else None
        rows = await sb.get("fingerprint_templates_v2", filters=filters)
        if not rows:
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "tier": "no_templates",
            }

        templates = []
        template_records = []
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
                "tier": "no_templates",
            }

        persons = await sb.get("persons")
        pmap = {p.get("person_id"): p for p in persons}

        img_bytes = await image.read()
        files = {
            "image": (
                image.filename or "fingerprint.jpg",
                img_bytes,
                image.content_type or "application/octet-stream",
            )
        }
        data = {"templates": json.dumps(templates)}
        payload = await _post_model_service("/fingerprint_v2/match", files=files, data=data)

        best_index = payload.get("best_index")
        score = float(payload.get("score", 0.0))
        matched = bool(payload.get("matched", False)) and best_index is not None

        rec = template_records[int(best_index)] if matched else None
        person_id = rec.get("person_id") if rec else None
        person = pmap.get(person_id, {}) if person_id else {}

        return {
            "matched": matched,
            "person_id": person_id,
            "full_name": person.get("full_name") if person else None,
            "similarity": score if matched else 0.0,
            "threshold": float(payload.get("threshold", 0.0)),
            "quality_score": float(payload.get("quality_score", 0.0)),
            "quality_threshold": float(payload.get("quality_threshold", 0.0)),
            "tier": payload.get("tier", "reject"),
            "algorithm": payload.get("algorithm", "akaze_v2"),
            "finger_label": rec.get("finger_label") if rec else (finger_label or None),
        }
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e):
            raise HTTPException(status_code=500, detail=_v2_table_help())
        raise HTTPException(status_code=500, detail=f"Match fingerprint v2 failed: {e}")
