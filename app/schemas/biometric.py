from pydantic import BaseModel

class EnrollResponse(BaseModel):
    person_id: str
    full_name: str
    message: str

class MatchResponse(BaseModel):
    matched: bool
    person_id: str | None
    full_name: str | None
    similarity: float
    threshold: float
    criminal_records: str | None = None


class PersonUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    address: str | None = None
    criminal_records: str | None = None
