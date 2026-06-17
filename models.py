from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func
from database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10))
    raw_text = Column(Text, nullable=False)
    upload_date = Column(DateTime, server_default=func.now())

    # New structured fields from Groq (Phase 2)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    skills = Column(Text, nullable=True)          # stored as JSON string
    years_experience = Column(Float, nullable=True)
    education = Column(String(255), nullable=True)
    current_role = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    is_processed = Column(Integer, default=0)     # 0 = not processed, 1 = processed