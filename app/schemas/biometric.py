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
