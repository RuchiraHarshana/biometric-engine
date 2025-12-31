import json
from sqlalchemy.orm import Session
from app.db.models import PersonBiometric



def upsert_face_embedding(db: Session, person_id: str, full_name: str, embedding_list: list[float]):
    emb_str = json.dumps(embedding_list)

    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if rec:
        rec.full_name = full_name
        rec.face_embedding = emb_str
    else:
        rec = PersonBiometric(person_id=person_id, full_name=full_name, face_embedding=emb_str)
        db.add(rec)

    db.commit()
    db.refresh(rec)
    return rec

def fetch_all_embeddings(db: Session):
    return db.query(PersonBiometric).all()


def upsert_fingerprint_template(db, person_id: str, full_name: str, template_dict: dict):
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()
    if rec is None:
        rec = PersonBiometric(person_id=person_id, full_name=full_name)

    rec.fingerprint_template = json.dumps(template_dict)
    if full_name:
        rec.full_name = full_name

    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec