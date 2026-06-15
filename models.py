from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10))           # "pdf" or "docx"
    raw_text = Column(Text, nullable=False)  # full extracted text
    upload_date = Column(DateTime, server_default=func.now())

    # Phase 2 will add: name, email, skills, years_experience, etc.
    # We leave them out for now to keep Phase 1 focused