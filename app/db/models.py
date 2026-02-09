from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class PersonBiometric(Base):
    __tablename__ = "person_biometrics"

    id = Column(Integer, primary_key=True, index=True)

    # Required basics
    person_id = Column(String(64), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)

    # Optional profile fields (NULL allowed)
    email = Column(String(255), nullable=True)
    mobile_number = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    criminal_records = Column(Text, nullable=True)

    # Biometrics (optional)
    face_embedding = Column(Text, nullable=True)          # JSON string
    fingerprint_template = Column(Text, nullable=True)    # JSON string

    # Face display (store file path)
    face_image_path = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
