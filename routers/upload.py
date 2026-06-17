from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate
from services.extractor import extract_text
import os
import shutil
import json
from services.groq_extractor import extract_structured_data

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_DIR = "uploads"
ALLOWED_TYPES = {"pdf", "docx", "doc"}

@router.post("/upload")
async def upload_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Get file extension and validate it
    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not supported. Use PDF, DOCX, or DOC."
        )

    # Save the uploaded file to the uploads/ folder
    save_path = os.path.join(UPLOAD_DIR, filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text using our service
    try:
        raw_text = extract_text(save_path, ext)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")

    if not raw_text:
        raise HTTPException(status_code=422, detail="Could not extract any text from this file.")

    # Save to database
    candidate = Candidate(
        filename=filename,
        file_type=ext,
        raw_text=raw_text
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return {
        "message": "CV uploaded and processed successfully",
        "candidate_id": candidate.id,
        "filename": candidate.filename,
        "text_length": len(raw_text),
        "preview": raw_text[:300] + "..." if len(raw_text) > 300 else raw_text
    }


@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return [
        {
            "id": c.id,
            "filename": c.filename,
            "file_type": c.file_type,
            "upload_date": c.upload_date,
            "text_length": len(c.raw_text)
        }
        for c in candidates
    ]

@router.post("/process/{candidate_id}")
def process_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """
    Takes a candidate's raw_text, sends it to Groq,
    and updates the record with structured data.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        profile = extract_structured_data(candidate.raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq extraction failed: {str(e)}")

    # Update the candidate record with structured fields
    candidate.name = profile.name
    candidate.email = profile.email
    candidate.phone = profile.phone
    candidate.skills = json.dumps(profile.skills)  # list -> JSON string
    candidate.years_experience = profile.years_experience
    candidate.education = profile.education
    candidate.current_role = profile.current_role
    candidate.summary = profile.summary
    candidate.is_processed = 1

    db.commit()
    db.refresh(candidate)

    return {
        "message": "Candidate processed successfully",
        "candidate_id": candidate.id,
        "profile": profile.model_dump()
    }


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "id": candidate.id,
        "filename": candidate.filename,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "skills": json.loads(candidate.skills) if candidate.skills else [],
        "years_experience": candidate.years_experience,
        "education": candidate.education,
        "current_role": candidate.current_role,
        "summary": candidate.summary,
        "is_processed": bool(candidate.is_processed)
    }