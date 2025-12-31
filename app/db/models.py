from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class PersonBiometric(Base):
    __tablename__ = "person_biometrics"

    id = Column(Integer, primary_key=True, index=True)

    # business identifier (what you use in API)
    person_id = Column(String(64), unique=True, index=True, nullable=False)

    full_name = Column(String(255), nullable=True)

    # store face embedding as JSON string (can be NULL if only fingerprint enrolled)
    face_embedding = Column(Text, nullable=True)

    # store fingerprint template as JSON string (can be NULL if only face enrolled)
    fingerprint_template = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
