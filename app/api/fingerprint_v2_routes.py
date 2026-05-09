import json

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import require_register_access, require_verify_access
from app.core.config import (
    FINGERPRINT_V2_LIKENESS_THRESHOLD,
    FINGERPRINT_V2_QUALITY_THRESHOLD,
    FINGERPRINT_V2_THRESHOLD,
    MODEL_SERVICE_TIMEOUT,
    MODEL_SERVICE_URL,
)
from app.engines.fingerprint_engine_v2 import FingerprintEngineV2
from app.storage.supabase_client import client as sb


router_fp_v2 = APIRouter()
MAX_MATCH_BATCH_BYTES = 6 * 1024 * 1024
MAX_MATCH_BATCH_ITEMS = 120
_local_fp_v2 = FingerprintEngineV2()


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def _normalize_fingerprint_upload(img_bytes: bytes, max_dim: int = 1200) -> bytes:
    """Normalize large uploads to keep inference latency and payload size bounded."""
    try:
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            return img_bytes

        h, w = img.shape[:2]
        longest = max(h, w)
        if longest <= max_dim:
            return img_bytes

        scale = float(max_dim) / float(longest)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Encode as JPEG to keep body size predictable.
        ok, out = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return img_bytes
        return out.tobytes()
    except Exception:
        return img_bytes


def _v2_table_help() -> str:
    return (
        "Missing table fingerprint_templates_v2. "
        "Apply SQL migration in supabase/migration_add_fingerprint_v2.sql first."
    )


def _is_missing_table_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "fingerprint_templates_v2" in msg and ("does not exist" in msg or "404" in msg)


async def _post_model_service(path: str, files=None, data=None) -> dict:
    timeout = MODEL_SERVICE_TIMEOUT
    if "fingerprint_v2/match" in path:
        # Matching can be slower under larger template sets.
        timeout = max(float(MODEL_SERVICE_TIMEOUT), 90.0)

    try:
        async with httpx.AsyncClient(base_url=MODEL_SERVICE_URL, timeout=timeout) as client:
            resp = await client.post(path, files=files, data=data)
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail=f"Model service timeout: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Model service connection error: {e}")

    if resp.status_code >= 400:
        try:
            payload = resp.json()
            detail = payload.get("detail") if isinstance(payload, dict) else resp.text
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=f"Model service error: {detail}")

    try:
        payload = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model service returned invalid JSON: {e}")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail=f"Model service returned non-object payload: {type(payload).__name__}")
    return payload


def _deserialize_tpl(tpl) -> dict | None:
    """Safely convert a template from Supabase (may arrive as JSON string or dict)."""
    if isinstance(tpl, str):
        try:
            tpl = json.loads(tpl)
        except Exception:
            return None
    if not isinstance(tpl, dict):
        return None
    # Accept hybrid_v1, minutiae_v1, and legacy AKAZE formats
    if "minutiae" not in tpl and "des" not in tpl:
        return None
    return tpl


def _local_match_payload_compat(img_bytes: bytes, tpl_batch: list[dict], fallback_detail: str = "") -> dict:
    """Compat stub — routes now call match route logic directly."""
    return {
        "best_index": None,
        "score": 0.0,
        "matched": False,
            "tier": "no_match",
            "fallback_reason": fallback_detail,
        }


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
        if not img_bytes or len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty image file")
        img_bytes = _normalize_fingerprint_upload(img_bytes)

        # Run full minutiae pipeline locally — no model-service round-trip needed
        img = _local_fp_v2.read_image(img_bytes)
        analysis = _local_fp_v2.analyze(img)
        likeness   = _safe_float(analysis["likeness"], 0.0)
        quality    = _safe_float(analysis["quality"], 0.0)
        count      = int(analysis["minutiae_count"])
        likeness_threshold = _safe_float(FINGERPRINT_V2_LIKENESS_THRESHOLD, 0.50)
        quality_threshold  = _safe_float(FINGERPRINT_V2_QUALITY_THRESHOLD, 0.28)

        if likeness < likeness_threshold:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Image does not appear to be a fingerprint "
                    f"(likeness_score={likeness:.3f}, threshold={likeness_threshold:.2f}, "
                    f"minutiae_count={count}). Please upload a clear fingerprint scan."
                ),
            )
        if quality < quality_threshold:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Fingerprint image quality too low "
                    f"(quality_score={quality:.3f}, threshold={quality_threshold:.2f}, "
                    f"minutiae_count={count}). Please use a clearer fingerprint image."
                ),
            )

        template = analysis["template"]

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
            "algorithm": "hybrid_v2",
            "quality_score": quality,
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
    """
    Match a fingerprint image against all stored templates using the local engine
    directly (no model-service round-trips per batch). This is fast, reliable, and
    not subject to Cloud Run per-request timeout accumulation.
    """
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

        # Collect valid template records.
        template_records = [r for r in rows if r.get("template")]
        if not template_records:
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
        if not img_bytes or len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty image file")
        img_bytes = _normalize_fingerprint_upload(img_bytes)

        # Single-pass analysis: quality + likeness + template in one call
        img      = _local_fp_v2.read_image(img_bytes)
        analysis = _local_fp_v2.analyze(img)
        like_score         = _safe_float(analysis["likeness"], 0.0)
        quality            = _safe_float(analysis["quality"], 0.0)
        likeness_threshold = _safe_float(FINGERPRINT_V2_LIKENESS_THRESHOLD, 0.50)
        quality_threshold  = _safe_float(FINGERPRINT_V2_QUALITY_THRESHOLD, 0.28)

        if like_score < likeness_threshold:
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "likeness_score": like_score,
                "likeness_threshold": likeness_threshold,
                "minutiae_count": analysis["minutiae_count"],
                "reasons": ["low_likeness_score"],
                "tier": "reject_non_fingerprint",
                "algorithm": "hybrid_v2",
                "finger_label": finger_label or None,
            }

        if quality < quality_threshold:
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "quality_score": quality,
                "quality_threshold": quality_threshold,
                "minutiae_count": analysis["minutiae_count"],
                "reasons": ["low_quality_fingerprint_image"],
                "tier": "reject_quality",
                "algorithm": "hybrid_v2",
                "finger_label": finger_label or None,
            }

        query_tpl = analysis["template"]
        threshold = _safe_float(FINGERPRINT_V2_THRESHOLD, 0.50)

        # Match query template against every stored template (rotation tolerance
        # is built into the minutiae matching algorithm — no multi-angle variants needed)
        best_score  = float("-inf")
        best_rec    = None
        stale_count = 0
        for r in template_records:
            raw_tpl = r.get("template")
            tpl = _deserialize_tpl(raw_tpl)
            if tpl is None:
                continue
            try:
                s = _safe_float(_local_fp_v2.match_score(query_tpl, tpl), 0.0)
            except ValueError as exc:
                if str(exc).startswith("STALE_TEMPLATE:"):
                    stale_count += 1
                continue
            except Exception:
                continue
            if s > best_score:
                best_score = s
                best_rec   = r

        if best_rec is None:
            if stale_count > 0:
                return {
                    "matched": False,
                    "person_id": None,
                    "full_name": None,
                    "similarity": 0.0,
                    "tier": "stale_templates",
                    "message": (
                        f"{stale_count} stored template(s) were enrolled with the old engine "
                        "(hybrid_v1) and are incompatible with the current engine (hybrid_v2). "
                        "Please re-enroll all persons from the admin panel."
                    ),
                    "algorithm": "hybrid_v2",
                }
            return {
                "matched": False,
                "person_id": None,
                "full_name": None,
                "similarity": 0.0,
                "quality_score": quality,
                "quality_threshold": quality_threshold,
                "likeness_score": like_score,
                "threshold": threshold,
                "tier": "no_match",
                "algorithm": "hybrid_v2",
            }

        best_score = max(0.0, best_score)
        matched   = best_score >= threshold
        person_id = best_rec.get("person_id")
        person    = pmap.get(person_id, {}) if person_id else {}

        # Detect likely stale enrollment: best score suspiciously low AND stored
        # template algorithm != current engine.  Even if version tags match (both
        # say hybrid_v2), the fingerprint might have been enrolled on a different
        # server build.  Guide the user to re-enroll when score looks wrong.
        stored_alg = ""
        stored_tpl = _deserialize_tpl(best_rec.get("template"))
        if stored_tpl:
            stored_alg = stored_tpl.get("algorithm", "")
        hint = None
        if not matched and best_score < 0.30:
            hint = (
                "Similarity is very low. If you enrolled and matched the same fingerprint image, "
                "this usually means the stored template was created by a different engine version. "
                f"Stored template algorithm: '{stored_alg}'. "
                "Please re-enroll this person from the admin panel and try again."
            )

        return {
            "matched": matched,
            "person_id": person_id if matched else None,
            "candidate_person_id": person_id,
            "full_name": person.get("full_name") if (matched and person) else None,
            "candidate_full_name": person.get("full_name") if person else None,
            "similarity": best_score,
            "threshold": threshold,
            "quality_score": quality,
            "quality_threshold": quality_threshold,
            "likeness_score": like_score,
            "likeness_threshold": likeness_threshold,
            "minutiae_count": analysis["minutiae_count"],
            "tier": "auto" if matched else "reject_low_similarity",
            "hint": hint,
            "algorithm": "hybrid_v2",
            "finger_label": best_rec.get("finger_label") or (finger_label or None),
        }
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e):
            raise HTTPException(status_code=500, detail=_v2_table_help())
        # Return a structured failure instead of 500 to avoid opaque frontend fetch errors.
        return {
            "matched": False,
            "person_id": None,
            "full_name": None,
            "similarity": 0.0,
            "tier": "match_internal_error",
            "detail": f"Match fingerprint v2 failed: {e}",
        }
