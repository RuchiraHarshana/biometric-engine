import json
import httpx
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.storage.supabase_client import client as sb
from app.core.config import FINGERPRINT_THRESHOLD, MODEL_SERVICE_URL, MODEL_SERVICE_TIMEOUT, FINGERPRINT_FP_SCORE_THRESHOLD

# Enforce a minimum runtime threshold to avoid stale-config matches
EFFECTIVE_FINGERPRINT_THRESHOLD = max(FINGERPRINT_THRESHOLD, 0.85)
from app.auth.dependencies import require_register_access, require_verify_access

import json as _json
import datetime as _dt
import os as _os


def _ensure_log_dir():
    d = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), '..', 'logs')
    d = _os.path.abspath(d)
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _log_match_request(entry: dict):
    try:
        d = _ensure_log_dir()
        p = _os.path.join(d, 'match_requests.log')
        with open(p, 'a', encoding='utf-8') as fh:
            ts = _dt.datetime.utcnow().isoformat() + 'Z'
            line = _json.dumps({'ts': ts, 'entry': entry}, ensure_ascii=False)
            fh.write(line + '\n')
    except Exception:
        pass

router_fp = APIRouter()


def _sanitize_similarity(sim: float) -> float:
    try:
        v = float(sim)
        return v if v >= 0.01 else 0.0
    except Exception:
        return 0.0


async def _post_model_service(path: str, files=None, data=None) -> dict:
    async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=MODEL_SERVICE_TIMEOUT) as client:
        resp = await client.post(path, files=files, data=data)

    # If model service returned an error, surface it to the API caller
    if resp.status_code >= 400:
        try:
            payload = resp.json()
            detail = payload.get("detail") if isinstance(payload, dict) else resp.text
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=f"Model service error: {detail}")

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
    """
    DEPRECATED / BLOCKED: This v1 endpoint is disabled to prevent bypassing v2 anti-diagram checks.
    Use /experimental/enroll/fingerprint.
    """
    raise HTTPException(
        status_code=410,
        detail="Legacy endpoint disabled. Use /api/experimental/enroll/fingerprint.",
    )

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

        # Model service returns an error dict (no 'template' key) when the image
        # doesn't look like a fingerprint or quality is too low.
        if "error" in payload or "template" not in payload:
            fp_score = payload.get("fp_score")
            score_str = f"{fp_score:.2f}" if fp_score is not None else "N/A"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Please double-check the uploaded fingerprint image — "
                    f"it may be too inky, blurry, or low quality. "
                    f"Quality score: {score_str}/1.00. "
                    f"Please try again with a clearer image."
                ),
            )

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

    except HTTPException:
        raise
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
                "threshold": float(EFFECTIVE_FINGERPRINT_THRESHOLD),
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
                "threshold": float(EFFECTIVE_FINGERPRINT_THRESHOLD),
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
        fp_score = float(payload.get("fp_score", 0.0))
        tier = payload.get("tier", "auto")

        # Handle tiers from model service
        if tier == "reject" or tier == "no_match":
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "threshold": float(EFFECTIVE_FINGERPRINT_THRESHOLD),
                "fp_score": fp_score,
                "tier": tier,
            }
        # Log the match attempt for debugging combined-verify frontend issues
        try:
            _log_match_request({
                'best_index': best_index,
                'best_score': best_score,
                'fp_score': fp_score,
                'tier': tier,
                'templates_count': len(templates),
            })
        except Exception:
            pass

        # If review requested, return candidate but mark review_required
        if tier == "review":
            candidate = None
            if best_index is not None:
                rec = template_records[int(best_index)]
                candidate = {
                    "person_id": rec.get("person_id"),
                    "full_name": pmap.get(rec.get("person_id"), {}).get("full_name"),
                    "criminal_records": pmap.get(rec.get("person_id"), {}).get("criminal_records"),
                }
            return {
                "matched": False,
                "person_id": candidate.get("person_id") if candidate else None,
                "full_name": candidate.get("full_name") if candidate else None,
                "similarity": _sanitize_similarity(float(best_score if best_index is not None else 0.0)),
                "threshold": float(EFFECTIVE_FINGERPRINT_THRESHOLD),
                "fp_score": fp_score,
                "tier": "review",
                "review_required": True,
            }

        # Auto tier: behave as before
        matched = (best_index is not None) and (best_score >= EFFECTIVE_FINGERPRINT_THRESHOLD)
        best = template_records[int(best_index)] if matched else None

        person_id = best.get("person_id") if matched else None
        full_name = pmap.get(person_id, {}).get("full_name") if person_id else None
        criminal_records = pmap.get(person_id, {}).get("criminal_records") if person_id else None

        return {
            "matched": matched,
            "person_id": person_id,
            "full_name": full_name,
            "similarity": _sanitize_similarity(float(best_score if matched else 0.0)),
            "threshold": float(EFFECTIVE_FINGERPRINT_THRESHOLD),
            "fp_score": fp_score,
            "tier": "auto",
            "criminal_records": criminal_records,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match fingerprint failed: {e}")
