from pydantic import BaseModel
from typing import Optional


class VerifyResponse(BaseModel):
    face_provided: bool
    fingerprint_provided: bool

    face_matched: Optional[bool] = None
    face_person_id: Optional[str] = None
    face_full_name: Optional[str] = None
    face_similarity: Optional[float] = None
    face_threshold: Optional[float] = None
    face_criminal_records: Optional[str] = None

    fingerprint_matched: Optional[bool] = None
    fingerprint_person_id: Optional[str] = None
    fingerprint_full_name: Optional[str] = None
    fingerprint_similarity: Optional[float] = None
    fingerprint_threshold: Optional[float] = None
    fingerprint_criminal_records: Optional[str] = None

    # Final decision
    access_granted: bool
    decision_rule: str
    # Cross-modal mismatch: when face and fingerprint both match but to different persons
    cross_modal_mismatch: Optional[bool] = None
    mismatch_message: Optional[str] = None
