import json
from typing import Optional

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from app.core.config import FACE_MODEL_PATH
from app.engines.face_engine import FaceEngineONNX
from app.engines.fingerprint_engine import FingerprintEngine

app = FastAPI(title="BioSecureGate Model Service")

_face_engine: Optional[FaceEngineONNX] = None


def get_face_engine() -> FaceEngineONNX:
    global _face_engine
    if _face_engine is None:
        _face_engine = FaceEngineONNX(FACE_MODEL_PATH)
    return _face_engine


fp_engine = FingerprintEngine()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/face/embedding")
async def face_embedding(image: UploadFile = File(...)):
    try:
        engine = get_face_engine()
        img_bytes = await image.read()
        img = engine.read_image(img_bytes)
        emb = engine.get_embedding(img)
        return {"embedding": emb.tolist()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Face embedding failed: {e}")


@app.post("/fingerprint/template")
async def fingerprint_template(image: UploadFile = File(...)):
    try:
        img_bytes = await image.read()
        img = fp_engine.read_image(img_bytes)
        template = fp_engine.extract_template(img)
        return {"template": template}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint template failed: {e}")


@app.post("/fingerprint/match")
async def fingerprint_match(
    image: UploadFile = File(...),
    templates: str = Form(...),
):
    try:
        tpl_list = json.loads(templates)
        if not isinstance(tpl_list, list) or not tpl_list:
            return {"best_index": None, "score": 0.0}

        img_bytes = await image.read()
        img = fp_engine.read_image(img_bytes)
        query_tpl = fp_engine.extract_template(img)
        query_des = fp_engine.deserialize_des(query_tpl)

        best_index = None
        best_score = float("-inf")

        for i, tpl in enumerate(tpl_list):
            db_des = fp_engine.deserialize_des(tpl)
            score = fp_engine.match_score(query_des, db_des)
            if score > best_score:
                best_score = score
                best_index = i

        if best_index is None:
            return {"best_index": None, "score": 0.0}

        return {"best_index": int(best_index), "score": float(best_score)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fingerprint match failed: {e}")
