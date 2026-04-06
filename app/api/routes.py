import json
from typing import Optional

import numpy as np
import httpx
import os
import random
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.storage.supabase_storage import upload_face_image, delete_face_image
from app.storage.supabase_client import client as sb
from app.auth import supabase_service

from app.schemas.biometric import EnrollResponse, MatchResponse
from app.schemas.biometric import PersonUpdate
from app.schemas.verify import VerifyResponse

from app.core.config import SIMILARITY_THRESHOLD, FINGERPRINT_THRESHOLD, MODEL_SERVICE_URL, MODEL_SERVICE_TIMEOUT
from app.auth.dependencies import require_admin, require_register_access, require_verify_access, require_officer

# ✅ Import fingerprint router
from app.api.fingerprint_routes import router_fp


router = APIRouter()


def _sanitize_similarity(sim: float) -> float:
    try:
        v = float(sim)
        return v if v >= 0.01 else 0.0
    except Exception:
        return 0.0


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


# MOCK: Replace get_face_embedding with a dummy embedding for testing
async def get_face_embedding(image: UploadFile, image_bytes: bytes) -> np.ndarray:
    files = {"image": (image.filename or "face.jpg", image_bytes, image.content_type or "application/octet-stream")}
    payload = await _post_model_service("/face/embedding", files=files)
    return np.array(payload["embedding"], dtype=np.float32)


# -----------------------------
# Admin endpoints
# -----------------------------
@router.get("/persons", tags=["Admin"])
async def list_persons(_admin=Depends(require_admin)):
    persons = await sb.get("persons")
    out = []
    for p in persons:
        person_id = p.get("person_id")
        has_face = bool((await sb.get("face_embeddings", filters={"person_id": person_id})))
        has_fp = bool((await sb.get("fingerprint_templates", filters={"person_id": person_id})))
        out.append(
            {
                "person_id": person_id,
                "full_name": p.get("full_name"),
                "email": p.get("email"),
                "mobile_number": p.get("mobile_number"),
                "address": p.get("address"),
                "criminal_records": p.get("criminal_records"),
                "has_face": has_face,
                "has_fingerprint": has_fp,
                "face_image_key": p.get("face_image_key"),
                "face_image_url": p.get("face_image_url"),
            }
        )
    return out


@router.get("/persons/{person_id}", tags=["Persons"])
async def get_person(person_id: str, _user=Depends(require_officer)):
    recs = await sb.get("persons", filters={"person_id": person_id})
    if not recs:
        raise HTTPException(status_code=404, detail="Person not found")
    p = recs[0]
    has_face = bool((await sb.get("face_embeddings", filters={"person_id": person_id})))
    has_fp = bool((await sb.get("fingerprint_templates", filters={"person_id": person_id})))
    return {
        "person_id": p.get("person_id"),
        "full_name": p.get("full_name"),
        "email": p.get("email"),
        "mobile_number": p.get("mobile_number"),
        "address": p.get("address"),
        "criminal_records": p.get("criminal_records"),
        "has_face": has_face,
        "has_fingerprint": has_fp,
    }


@router.get("/persons/{person_id}/face-image", tags=["Persons"])
async def get_face_image(person_id: str, _user=Depends(require_officer)):
    recs = await sb.get("persons", filters={"person_id": person_id})
    if not recs or not recs[0].get("face_image_url"):
        raise HTTPException(status_code=404, detail="Face image not found")
    return RedirectResponse(recs[0].get("face_image_url"))


@router.delete("/persons/{person_id}", tags=["Admin"])
async def delete_person(person_id: str, _admin=Depends(require_admin)):
    recs = await sb.get("persons", filters={"person_id": person_id})
    if not recs:
        raise HTTPException(status_code=404, detail="Person not found")
    rec = recs[0]

    if rec.get("face_image_key"):
        try:
            await delete_face_image(rec.get("face_image_key"))
        except Exception:
            pass

    # delete dependent records first
    await sb.delete("face_embeddings", {"person_id": person_id})
    await sb.delete("fingerprint_templates", {"person_id": person_id})
    await sb.delete("persons", {"person_id": person_id})
    return {"deleted": True, "person_id": person_id}


@router.patch("/persons/{person_id}", tags=["Admin"])
async def update_person(person_id: str, body: PersonUpdate, user=Depends(require_officer)):
    """Partial update for person records.

    - Officers may update basic fields.
    - Only admins may modify `criminal_records`.
    Changes are recorded to `person_audits` for auditing.
    """
    recs = await sb.get("persons", filters={"person_id": person_id})
    if not recs:
        raise HTTPException(status_code=404, detail="Person not found")

    # enforce field-level permission
    if body.criminal_records is not None and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins may modify criminal records")

    # build update payload from provided fields
    update_payload = {}
    if body.full_name is not None:
        update_payload["full_name"] = body.full_name
    if body.email is not None:
        update_payload["email"] = body.email
    if body.mobile_number is not None:
        update_payload["mobile_number"] = body.mobile_number
    if body.address is not None:
        update_payload["address"] = body.address
    if body.criminal_records is not None:
        update_payload["criminal_records"] = body.criminal_records

    if not update_payload:
        return {"updated": False, "detail": "No fields to update"}

    # perform update in Supabase
    await sb.update("persons", {"person_id": person_id}, update_payload)

    # record audit (best-effort; requires `person_audits` table to exist)
    try:
        import json as _json
        from datetime import datetime as _dt

        audit_payload = {
            "person_id": person_id,
            "changed_by": user.get("id"),
            "changed_at": _dt.utcnow().isoformat() + "Z",
            "changes": _json.dumps(update_payload),
        }
        await sb.insert("person_audits", audit_payload)
    except Exception:
        # don't fail the update if audit recording is not available
        pass

    # return updated record
    updated = await sb.get("persons", filters={"person_id": person_id})
    return {"updated": True, "person": updated[0] if updated else None}


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
    _user=Depends(require_register_access),
):
    try:
        print("[enroll_face] reading image bytes...")
        img_bytes = await image.read()
        print(f"[enroll_face] got {len(img_bytes)} bytes")
        emb = await get_face_embedding(image, img_bytes)
        print("[enroll_face] got embedding")

        face_key, face_url = await upload_face_image(
            person_id=person_id,
            image_bytes=img_bytes,
            content_type=image.content_type,
        )
        print(f"[enroll_face] uploaded face image: {face_key}")

        # upsert person
        persons = await sb.get("persons", filters={"person_id": person_id})
        print(f"[enroll_face] sb.get persons: {persons}")
        person_payload = {
            "person_id": person_id,
            "full_name": full_name or None,
            "email": email,
            "mobile_number": mobile_number,
            "address": address,
            "criminal_records": criminal_records,
            "face_image_key": face_key,
            "face_image_url": face_url,
        }
        if persons:
            print("[enroll_face] updating person record")
            await sb.update("persons", {"person_id": person_id}, person_payload)
        else:
            print("[enroll_face] inserting person record")
            await sb.insert("persons", person_payload)

        # upsert face embedding
        emb_payload = {"person_id": person_id, "embedding": emb.tolist()}
        existing = await sb.get("face_embeddings", filters={"person_id": person_id})
        print(f"[enroll_face] sb.get face_embeddings: {existing}")
        if existing:
            print("[enroll_face] updating face embedding")
            await sb.update("face_embeddings", {"person_id": person_id}, emb_payload)
        else:
            print("[enroll_face] inserting face embedding")
            await sb.insert("face_embeddings", emb_payload)

        print("[enroll_face] SUCCESS")
        return EnrollResponse(person_id=person_id, full_name=full_name or "", message="Face enrolled successfully")

    except HTTPException:
        print("[enroll_face] HTTPException raised")
        raise
    except ValueError as e:
        print(f"[enroll_face] ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[enroll_face] Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Enroll failed: {e}")


@router.post("/match/face", response_model=MatchResponse, tags=["Face"])
async def match_face(image: UploadFile = File(...), _user=Depends(require_verify_access)):
    try:
        img_bytes = await image.read()
        query_emb = await get_face_embedding(image, img_bytes)

        # fetch all embeddings
        embeddings = await sb.get("face_embeddings")
        if not embeddings:
            return MatchResponse(matched=False, person_id=None, full_name=None, similarity=0.0, threshold=float(SIMILARITY_THRESHOLD))

        best = None
        best_score = float("-inf")
        # build persons map
        persons = await sb.get("persons")
        pmap = {p.get("person_id"): p for p in persons}

        for r in embeddings:
            emb_list = r.get("embedding")
            if not emb_list:
                continue
            db_emb = np.array(emb_list, dtype=np.float32)
            score = float(np.dot(query_emb, db_emb))
            if score > best_score:
                best_score = score
                best = r

        matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)
        person_id = best.get("person_id") if matched else None
        full_name = pmap.get(person_id, {}).get("full_name") if person_id else None
        criminal_records = pmap.get(person_id, {}).get("criminal_records") if person_id else None

        return MatchResponse(
            matched=matched,
            person_id=person_id,
            full_name=full_name,
            similarity=_sanitize_similarity(float(best_score if best is not None else 0.0)),
            threshold=float(SIMILARITY_THRESHOLD),
            criminal_records=criminal_records,
        )

    except HTTPException:
        raise
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
    _user=Depends(require_verify_access),
):
    if face_image is None and fingerprint_image is None:
        raise HTTPException(status_code=400, detail="Provide at least face_image or fingerprint_image")

    embeddings = await sb.get("face_embeddings")
    persons = await sb.get("persons")
    pmap = {p.get("person_id"): p for p in persons}

    if not embeddings:
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

        for r in embeddings:
            emb_list = r.get("embedding")
            if not emb_list:
                continue
            db_emb = np.array(emb_list, dtype=np.float32)
            score = float(np.dot(query_emb, db_emb))
            if score > best_score:
                best_score = score
                best = r

        face_similarity = float(best_score if best is not None else 0.0)
        face_matched = (best is not None) and (best_score >= SIMILARITY_THRESHOLD)

        if face_matched:
            face_person_id = best.get("person_id")
            face_full_name = pmap.get(face_person_id, {}).get("full_name")
            face_criminal_records = pmap.get(face_person_id, {}).get("criminal_records")

    # ---------- FINGERPRINT ----------
    if fingerprint_image is not None:
        # Build templates from enrolled fingerprint templates table
        tpl_rows = await sb.get("fingerprint_templates")
        templates = []
        template_records = []
        for r in tpl_rows:
            tpl_obj = r.get("template")
            if not tpl_obj:
                continue
            templates.append(tpl_obj)
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

            # log payload for debugging combined-verify issues
            try:
                import os as _os, json as _json, datetime as _dt
                d = _os.path.join(_os.path.dirname(__file__), '..', 'logs')
                _os.makedirs(d, exist_ok=True)
                p = _os.path.join(d, 'combined_match_requests.log')
                with open(p, 'a', encoding='utf-8') as fh:
                    fh.write(_json.dumps({'ts': _dt.datetime.utcnow().isoformat() + 'Z', 'payload': payload}) + '\n')
            except Exception:
                pass

            best_index = payload.get("best_index")
            best_score = float(payload.get("score", 0.0))

            fp_similarity = best_score
            # enforce runtime minimum threshold (safety)
            EFFECTIVE_FINGERPRINT_THRESHOLD = max(FINGERPRINT_THRESHOLD, 0.85)
            fp_matched = (best_index is not None) and (best_score >= EFFECTIVE_FINGERPRINT_THRESHOLD)

            if fp_matched:
                best = template_records[int(best_index)]
                fp_person_id = best.get("person_id")
                fp_full_name = pmap.get(fp_person_id, {}).get("full_name")
                fp_criminal_records = pmap.get(fp_person_id, {}).get("criminal_records")

    face_provided = face_image is not None
    fp_provided = fingerprint_image is not None

    if face_provided and fp_provided:
        # If both matched but to different persons, flag a mismatch and deny
        if bool(face_matched) and bool(fp_matched) and face_person_id and fp_person_id and face_person_id != fp_person_id:
            access_granted = False
            decision_rule = "mismatch: face and fingerprint belong to different persons"
            cross_modal_mismatch = True
            mismatch_message = "Face and fingerprint match different enrolled persons"
        else:
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
        face_criminal_records=locals().get('face_criminal_records', None),

        fingerprint_matched=fp_matched,
        fingerprint_person_id=fp_person_id,
        fingerprint_full_name=fp_full_name,
        fingerprint_similarity=fp_similarity,
        fingerprint_threshold=float(FINGERPRINT_THRESHOLD),
        fingerprint_criminal_records=locals().get('fp_criminal_records', None),
        cross_modal_mismatch=locals().get('cross_modal_mismatch', False),
        mismatch_message=locals().get('mismatch_message', None),

        access_granted=access_granted,
        decision_rule=decision_rule,
    )


# keep existing fingerprint endpoints
router.include_router(router_fp)
