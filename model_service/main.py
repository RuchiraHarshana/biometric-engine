import json
import os
from typing import Optional

import cv2
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
def _env_float_floor(name: str, default: float, floor: float) -> float:
    raw = os.getenv(name)
    try:
        v = float(raw) if raw is not None else float(default)
    except Exception:
        v = float(default)
    return max(v, floor)


def _env_int_floor(name: str, default: int, floor: int) -> int:
    raw = os.getenv(name)
    try:
        v = int(raw) if raw is not None else int(default)
    except Exception:
        v = int(default)
    return max(v, floor)


def _env_float_ceil(name: str, default: float, ceil: float) -> float:
    raw = os.getenv(name)
    try:
        v = float(raw) if raw is not None else float(default)
    except Exception:
        v = float(default)
    return min(v, ceil)


FINGERPRINT_V2_THRESHOLD = float(os.getenv("FINGERPRINT_V2_THRESHOLD", "0.18"))
FINGERPRINT_V2_QUALITY_THRESHOLD = _env_float_floor("FINGERPRINT_V2_QUALITY_THRESHOLD", 0.30, 0.30)
FINGERPRINT_V2_FP_SCORE_THRESHOLD = float(os.getenv("FINGERPRINT_V2_FP_SCORE_THRESHOLD", "0.20"))
FINGERPRINT_V2_LIKENESS_THRESHOLD = _env_float_floor("FINGERPRINT_V2_LIKENESS_THRESHOLD", 0.58, 0.58)
FINGERPRINT_V2_MIN_COVERAGE = _env_float_floor("FINGERPRINT_V2_MIN_COVERAGE", 0.14, 0.14)
FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY = _env_float_floor("FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY", 0.58, 0.58)
FINGERPRINT_V2_MIN_KP_COUNT = _env_int_floor("FINGERPRINT_V2_MIN_KP_COUNT", 35, 35)
FINGERPRINT_V2_MIN_KP_SPREAD = _env_float_floor("FINGERPRINT_V2_MIN_KP_SPREAD", 0.12, 0.12)
FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO", 0.28, 0.28)
FINGERPRINT_V2_MAX_TILE_COVERAGE_STD = _env_float_ceil("FINGERPRINT_V2_MAX_TILE_COVERAGE_STD", 0.24, 0.24)
FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT = _env_int_floor("FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT", 45, 45)
FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO = _env_float_ceil("FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO", 0.32, 0.32)
FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO", 0.20, 0.20)
FINGERPRINT_V2_MIN_MEAN_PERIODICITY = _env_float_floor("FINGERPRINT_V2_MIN_MEAN_PERIODICITY", 4.5, 4.5)
FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO = _env_float_floor("FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO", 0.12, 0.12)
FINGERPRINT_V2_MATCH_ROTATIONS = tuple(int(x) for x in os.getenv("FINGERPRINT_V2_MATCH_ROTATIONS", "-12,-6,0,6,12").split(",") if x.strip())


def _rotate_gray(img: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = img.shape[:2]
    c = (w / 2.0, h / 2.0)
    m = cv2.getRotationMatrix2D(c, angle_deg, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _extract_v2_query_templates(img: np.ndarray) -> list[tuple[dict, int]]:
    """Build rotation-tolerant query templates for stable same-finger matching."""
    variants: list[tuple[dict, int]] = []
    for ang in FINGERPRINT_V2_MATCH_ROTATIONS:
        try:
            view = img if ang == 0 else _rotate_gray(img, float(ang))
            tpl = fp_engine_v2.extract_template(view)
            variants.append((tpl, int(ang)))
        except Exception:
            continue
    return variants


def _v2_likeness_verdict(likeness: dict) -> tuple[bool, list[str]]:
    score = float(likeness.get("score", 0.0))
    coverage = float(likeness.get("coverage", 0.0))
    entropy = float(likeness.get("orientation_entropy", 0.0))
    kp_count = int(likeness.get("kp_count", 0))
    kp_spread = float(likeness.get("kp_spread", 0.0))
    tile_active_ratio = float(likeness.get("tile_active_ratio", 0.0))
    tile_coverage_std = float(likeness.get("tile_coverage_std", 0.0))
    edge_component_count = int(likeness.get("edge_component_count", 0))
    largest_edge_component_ratio = float(likeness.get("largest_edge_component_ratio", 1.0))
    periodic_tile_ratio = float(likeness.get("periodic_tile_ratio", 0.0))
    mean_periodicity = float(likeness.get("mean_periodicity", 0.0))
    ridge_block_ratio = float(likeness.get("ridge_block_ratio", 0.0))
    line_count = int(likeness.get("line_count", 0))
    circle_count = int(likeness.get("circle_count", 0))

    reasons = []
    if score < FINGERPRINT_V2_LIKENESS_THRESHOLD:
        reasons.append("low_likeness_score")
    if coverage < FINGERPRINT_V2_MIN_COVERAGE:
        reasons.append("low_coverage")
    if entropy < FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY:
        reasons.append("low_orientation_entropy")
    if kp_count < FINGERPRINT_V2_MIN_KP_COUNT:
        reasons.append("low_keypoint_count")
    if kp_spread < FINGERPRINT_V2_MIN_KP_SPREAD:
        reasons.append("low_keypoint_spread")
    if tile_active_ratio < FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO:
        reasons.append("low_tile_active_ratio")
    if tile_coverage_std > FINGERPRINT_V2_MAX_TILE_COVERAGE_STD:
        reasons.append("high_tile_coverage_std")
    if edge_component_count < FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT:
        reasons.append("low_edge_component_count")
    if largest_edge_component_ratio > FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO:
        reasons.append("high_largest_edge_component_ratio")
    # Periodicity signals are useful but can be weak on valid low-contrast captures.
    # Do not reject on periodic metrics alone; require sparse global structure too.
    weak_periodicity = (
        periodic_tile_ratio < FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO
        and mean_periodicity < FINGERPRINT_V2_MIN_MEAN_PERIODICITY
        and ridge_block_ratio < FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO
    )
    if weak_periodicity and (coverage < 0.18 or edge_component_count < 60):
        reasons.append("weak_ridge_periodicity_with_sparse_structure")

    # Hard reject for obvious non-fingerprint structure.
    if coverage < 0.06 and kp_count < 18 and edge_component_count < 25:
        reasons.append("obvious_non_fingerprint_sparse_signal")

    # Consensus gate: a valid fingerprint should satisfy most core structure signals.
    core_failures = 0
    core_failures += int(coverage < FINGERPRINT_V2_MIN_COVERAGE)
    core_failures += int(kp_count < FINGERPRINT_V2_MIN_KP_COUNT)
    core_failures += int(kp_spread < FINGERPRINT_V2_MIN_KP_SPREAD)
    core_failures += int(tile_active_ratio < FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO)
    core_failures += int(edge_component_count < FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT)
    core_failures += int(largest_edge_component_ratio > FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO)
    if core_failures >= 4:
        reasons.append("low_core_fingerprint_signal")

    # Explicit non-fingerprint geometry veto.
    # Only reject if we have MANY geometric primitives AND sparse edges
    if (line_count >= 5 or circle_count >= 3) and edge_component_count < 100:
        reasons.append("diagram_like_geometric_primitives")

    # Composite anti-diagram vetoes. Keep these strict for sparse, line-drawing patterns
    # while avoiding false rejects on weak real captures.
    if coverage < 0.05 and edge_component_count < 20:
        reasons.append("diagram_like_sparse_topology")
    if largest_edge_component_ratio > 0.50 and edge_component_count < 30:
        reasons.append("diagram_like_dominant_stroke")

    return len(reasons) == 0, reasons


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
        ok_like, like_reasons = _v2_likeness_verdict(likeness)
        if not ok_like:
            return {
                "error": "Image does not appear to be a fingerprint.",
                "likeness_score": like_score,
                "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
                "min_coverage": FINGERPRINT_V2_MIN_COVERAGE,
                "min_orientation_entropy": FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY,
                "min_kp_count": FINGERPRINT_V2_MIN_KP_COUNT,
                "min_kp_spread": FINGERPRINT_V2_MIN_KP_SPREAD,
                "min_tile_active_ratio": FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO,
                "max_tile_coverage_std": FINGERPRINT_V2_MAX_TILE_COVERAGE_STD,
                "min_edge_component_count": FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT,
                "max_largest_edge_component_ratio": FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO,
                "min_periodic_tile_ratio": FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO,
                "min_mean_periodicity": FINGERPRINT_V2_MIN_MEAN_PERIODICITY,
                "min_ridge_block_ratio": FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO,
                "reasons": like_reasons,
                "likeness_components": likeness,
            }

        # Gate 2 — v2 quality score (edge density + sharpness).
        quality = fp_engine_v2.quality_score(img)
        if quality < FINGERPRINT_V2_QUALITY_THRESHOLD:
            return {
                "error": "Fingerprint image quality too low. Please use a clearer, well-lit image.",
                "quality_score": quality,
                "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
                "reasons": ["low_quality_fingerprint_image"],
                "likeness_score": like_score,
                "likeness_components": likeness,
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
        ok_like, like_reasons = _v2_likeness_verdict(likeness)
        if not ok_like:
            return {
                "best_index": None,
                "score": 0.0,
                "matched": False,
                "tier": "reject_non_fingerprint",
                "likeness_score": like_score,
                "likeness_threshold": FINGERPRINT_V2_LIKENESS_THRESHOLD,
                "min_coverage": FINGERPRINT_V2_MIN_COVERAGE,
                "min_orientation_entropy": FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY,
                "min_kp_count": FINGERPRINT_V2_MIN_KP_COUNT,
                "min_kp_spread": FINGERPRINT_V2_MIN_KP_SPREAD,
                "min_tile_active_ratio": FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO,
                "max_tile_coverage_std": FINGERPRINT_V2_MAX_TILE_COVERAGE_STD,
                "min_edge_component_count": FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT,
                "max_largest_edge_component_ratio": FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO,
                "min_periodic_tile_ratio": FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO,
                "min_mean_periodicity": FINGERPRINT_V2_MIN_MEAN_PERIODICITY,
                "min_ridge_block_ratio": FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO,
                "reasons": like_reasons,
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
                "reasons": ["low_quality_fingerprint_image"],
            }

        query_tpl_variants = _extract_v2_query_templates(img)
        if not query_tpl_variants:
            return {
                "best_index": None,
                "score": 0.0,
                "matched": False,
                "tier": "reject_quality",
                "quality_score": quality,
                "quality_threshold": FINGERPRINT_V2_QUALITY_THRESHOLD,
                "reasons": ["insufficient_fingerprint_features"],
            }

        best_index = None
        best_score = float("-inf")
        best_rotation = 0
        for i, tpl in enumerate(tpl_list):
            local_best = float("-inf")
            local_rot = 0
            for q_tpl, rot in query_tpl_variants:
                score = fp_engine_v2.match_score(q_tpl, tpl)
                if score > local_best:
                    local_best = score
                    local_rot = rot
            score = local_best
            if score > best_score:
                best_score = score
                best_index = i
                best_rotation = local_rot

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
            "best_index": int(best_index),
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
            "query_rotation_deg": int(best_rotation),
            "query_variants": len(query_tpl_variants),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint v2 match failed: {e}")
