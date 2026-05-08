import json
import os
from typing import Optional

import numpy as np
from fastapi import FastAPI, Request, HTTPException


MAX_MULTIPART_PART_SIZE = int(float(os.getenv("MAX_MULTIPART_PART_MB", "32")) * 1024 * 1024)

from app.core.config import FACE_MODEL_PATH
from app.engines.face_engine import FaceEngineONNX
from app.engines.fingerprint_engine import FingerprintEngine
from app.engines.fingerprint_engine_v2 import FingerprintEngineV2
from app.core.config import FINGERPRINT_FP_SCORE_THRESHOLD, FINGERPRINT_FP_HIGH, FINGERPRINT_FP_LOW, FINGERPRINT_REVIEW_SIMILARITY, FINGERPRINT_THRESHOLD

# Enforce a minimum effective similarity so older services or clients can't accept low similarities
EFFECTIVE_FINGERPRINT_THRESHOLD = max(FINGERPRINT_THRESHOLD, 0.85)

app = FastAPI(title="BioSecureGate Model Service")

_face_engine: Optional[FaceEngineONNX] = None


def get_face_engine() -> FaceEngineONNX:
    global _face_engine
    if _face_engine is None:
        _face_engine = FaceEngineONNX(FACE_MODEL_PATH)
    return _face_engine


fp_engine = FingerprintEngine()
fp_engine_v2 = FingerprintEngineV2()
FINGERPRINT_V2_THRESHOLD = float(os.getenv("FINGERPRINT_V2_THRESHOLD", "0.18"))
FINGERPRINT_V2_QUALITY_THRESHOLD = float(os.getenv("FINGERPRINT_V2_QUALITY_THRESHOLD", "0.35"))
FINGERPRINT_V2_FP_SCORE_THRESHOLD = float(os.getenv("FINGERPRINT_V2_FP_SCORE_THRESHOLD", "0.20"))
FINGERPRINT_V2_LIKENESS_THRESHOLD = float(os.getenv("FINGERPRINT_V2_LIKENESS_THRESHOLD", "0.42"))


async def _read_form_upload(request: Request, field: str = "image"):
    form = await request.form(max_part_size=MAX_MULTIPART_PART_SIZE)
    upload = form.get(field)
    if upload is None:
        raise HTTPException(status_code=400, detail=f"Missing '{field}' file field")
    return upload, form


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/face/embedding")
async def face_embedding(request: Request):
    try:
        engine = get_face_engine()
        image, _ = await _read_form_upload(request, "image")
        img_bytes = await image.read()
        img = engine.read_image(img_bytes)
        emb = engine.get_embedding(img)
        return {"embedding": emb.tolist()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face embedding failed: {e}")


@app.post("/fingerprint/template")
async def fingerprint_template(request: Request):
    try:
        image, _ = await _read_form_upload(request, "image")
        img_bytes = await image.read()
        img = fp_engine.read_image(img_bytes)
        comps = fp_engine.fingerprint_score_components(img)
        fp_score = float(comps.get("score", 0.0))
        if fp_score < FINGERPRINT_FP_SCORE_THRESHOLD:
            # Return diagnostics on failure
            return {
                "error": "Image does not appear to be a fingerprint.",
                "fp_score": fp_score,
                "fp_components": comps
            }

        template = fp_engine.extract_template(img)
        return {"template": template, "fp_score": fp_score, "fp_components": comps}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint template failed: {e}")


@app.post("/fingerprint/match")
async def fingerprint_match(request: Request):
    try:
        image, form = await _read_form_upload(request, "image")
        templates = form.get("templates")
        if not templates:
            raise HTTPException(status_code=400, detail="Missing 'templates' form field")

        tpl_list = json.loads(templates)
        if not isinstance(tpl_list, list) or not tpl_list:
            return {"best_index": None, "score": 0.0}

        img_bytes = await image.read()
        img = fp_engine.read_image(img_bytes)
        # compute fingerprint-likeness score first
        comps = fp_engine.fingerprint_score_components(img)
        fp_score = float(comps.get("score", 0.0))

        # Tier 1: clear reject
        if fp_score < FINGERPRINT_FP_LOW:
            return {"best_index": None, "score": 0.0, "fp_score": fp_score, "fp_components": comps, "tier": "reject"}

        # Proceed to extract template and match for mid/high tiers
        query_tpl = fp_engine.extract_template(img)
        q_des, q_kps = fp_engine.deserialize_template(query_tpl)

        best_index = None
        best_score = float("-inf")

        for i, tpl in enumerate(tpl_list):
            db_des, db_kps = fp_engine.deserialize_template(tpl)
            score = fp_engine.match_score((q_des, q_kps), (db_des, db_kps))
            if score > best_score:
                best_score = score
                best_index = i

        if best_index is None:
            return {"best_index": None, "score": 0.0, "fp_score": fp_score, "fp_components": comps, "tier": "no_match"}

        # Enforce effective similarity threshold
        if best_score < EFFECTIVE_FINGERPRINT_THRESHOLD:
            # still return components and tier info but do not expose a match
            return {"best_index": None, "score": float(best_score), "fp_score": fp_score, "fp_components": comps, "tier": "reject_low_similarity"}

        # Tier 3: clear auto-accept path
        if fp_score >= FINGERPRINT_FP_HIGH:
            return {"best_index": int(best_index), "score": float(best_score), "fp_score": fp_score, "fp_components": comps, "tier": "auto"}

        # Tier 2: borderline — use a review threshold
        if best_score >= FINGERPRINT_THRESHOLD:
            return {"best_index": int(best_index), "score": float(best_score), "fp_score": fp_score, "fp_components": comps, "tier": "auto"}
        elif best_score >= FINGERPRINT_REVIEW_SIMILARITY:
            return {"best_index": int(best_index), "score": float(best_score), "fp_score": fp_score, "fp_components": comps, "tier": "review"}
        else:
            return {"best_index": None, "score": float(best_score), "fp_score": fp_score, "fp_components": comps, "tier": "reject"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint match failed: {e}")


@app.post("/fingerprint_v2/template")
async def fingerprint_template_v2(request: Request):
    try:
        image, _ = await _read_form_upload(request, "image")
        img_bytes = await image.read()
        img = fp_engine_v2.read_image(img_bytes)

        # Dedicated v2 fingerprint-likeness gate designed to reject drawings/diagrams.
        likeness = fp_engine_v2.fingerprint_likeness_components(img)
        like_score = float(likeness.get("score", 0.0))
        if like_score < FINGERPRINT_V2_LIKENESS_THRESHOLD:
            return {
                "error": "Image does not appear to be a fingerprint.",
                "likeness_score": like_score,
                "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
                "likeness_components": likeness,
            }

        # Gate 2 — v2 quality score (edge density + sharpness).
        quality = fp_engine_v2.quality_score(img)
        if quality < FINGERPRINT_V2_QUALITY_THRESHOLD:
            return {
                "error": "Fingerprint image quality too low. Please use a clearer, well-lit image.",
                "quality_score": quality,
                "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
            }

        template = fp_engine_v2.extract_template(img)
        return {
            "template": template,
            "quality_score": quality,
            "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
            "likeness_score": like_score,
            "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
            "likeness_components": likeness,
            "algorithm": "akaze_v2",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint v2 template failed: {e}")


@app.post("/fingerprint_v2/match")
async def fingerprint_match_v2(request: Request):
    try:
        image, form = await _read_form_upload(request, "image")
        templates = form.get("templates")
        if not templates:
            raise HTTPException(status_code=400, detail="Missing 'templates' form field")

        tpl_list = json.loads(templates)
        if not isinstance(tpl_list, list) or not tpl_list:
            return {"best_index": None, "score": 0.0, "matched": False, "tier": "no_templates"}

        img_bytes = await image.read()
        img = fp_engine_v2.read_image(img_bytes)

        # Gate 1 — dedicated v2 fingerprint-likeness detector.
        likeness = fp_engine_v2.fingerprint_likeness_components(img)
        like_score = float(likeness.get("score", 0.0))
        if like_score < FINGERPRINT_V2_LIKENESS_THRESHOLD:
            return {
                "best_index": None,
                "score": 0.0,
                "matched": False,
                "tier": "reject_non_fingerprint",
                "likeness_score": like_score,
                "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
                "likeness_components": likeness,
            }

        # Gate 2 — v2 quality score.
        quality = fp_engine_v2.quality_score(img)
        if quality < FINGERPRINT_V2_QUALITY_THRESHOLD:
            return {
                "best_index": None,
                "score": 0.0,
                "matched": False,
                "tier": "reject_quality",
                "quality_score": quality,
                "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
            }

        query_tpl = fp_engine_v2.extract_template(img)

        best_index = None
        best_score = float("-inf")
        for i, tpl in enumerate(tpl_list):
            score = fp_engine_v2.match_score(query_tpl, tpl)
            if score > best_score:
                best_score = score
                best_index = i

        if best_index is None:
            return {
                "best_index": None,
                "score": 0.0,
                "matched": False,
                "tier": "no_match",
                "quality_score": quality,
                "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
                "threshold": FINGERPRINT_V2_THRESHOLD,
            }

        matched = best_score >= FINGERPRINT_V2_THRESHOLD
        tier = "auto" if matched else "reject_low_similarity"
        return {
            "best_index": int(best_index) if matched else None,
            "score": float(best_score),
            "matched": bool(matched),
            "tier": tier,
            "quality_score": quality,
            "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
            "likeness_score": like_score,
            "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
            "likeness_components": likeness,
            "threshold": FINGERPRINT_V2_THRESHOLD,
            "algorithm": "akaze_v2",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint v2 match failed: {e}")
