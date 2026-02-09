import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import PersonBiometric


def _set_if_provided(rec: PersonBiometric, field: str, value: Optional[str]) -> None:
    """
    Only update if value is provided (not None and not empty string).
    This prevents overwriting existing DB values with NULL by accident.
    """
    if value is not None and value != "":
        setattr(rec, field, value)


def upsert_face_embedding(
    db: Session,
    person_id: str,
    full_name: str,
    embedding_list,
    email: str = None,
    mobile_number: str = None,
    address: str = None,
    criminal_records: str = None,
    face_image_path: str = None,
) -> PersonBiometric:
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()

    if rec is None:
        rec = PersonBiometric(person_id=person_id)
        db.add(rec)

    # update basics
    if full_name is not None:
        rec.full_name = full_name

    # optional fields (only if provided)
    _set_if_provided(rec, "email", email)
    _set_if_provided(rec, "mobile_number", mobile_number)
    _set_if_provided(rec, "address", address)
    _set_if_provided(rec, "criminal_records", criminal_records)

    # embedding saved as JSON string
    rec.face_embedding = json.dumps(embedding_list)

    # face image path (only if provided)
    _set_if_provided(rec, "face_image_path", face_image_path)

    db.commit()
    db.refresh(rec)
    return rec


def upsert_fingerprint_template(
    db: Session,
    person_id: str,
    full_name: str,
    template_dict: Dict[str, Any],
    email: str = None,
    mobile_number: str = None,
    address: str = None,
    criminal_records: str = None,
) -> PersonBiometric:
    rec = db.query(PersonBiometric).filter(PersonBiometric.person_id == person_id).first()

    if rec is None:
        rec = PersonBiometric(person_id=person_id)
        db.add(rec)

    # update basics
    if full_name is not None:
        rec.full_name = full_name

    # optional fields (only if provided)
    _set_if_provided(rec, "email", email)
    _set_if_provided(rec, "mobile_number", mobile_number)
    _set_if_provided(rec, "address", address)
    _set_if_provided(rec, "criminal_records", criminal_records)

    # template saved as JSON string
    rec.fingerprint_template = json.dumps(template_dict)

    db.commit()
    db.refresh(rec)
    return rec


def fetch_all_embeddings(db: Session):
    # returns PersonBiometric rows
    return db.query(PersonBiometric).all()
