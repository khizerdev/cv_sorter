from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate
from services.extractor import extract_text
import os
import shutil
import json
from services.groq_extractor import extract_structured_data
from services.vector_store import upsert_candidate, search_candidates
from services.scoring_agent import run_agent
from services.sheets_exporter import export_to_sheets
from services.email_notifier import send_ranking_email

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
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        profile = extract_structured_data(candidate.raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq extraction failed: {str(e)}")

    candidate.name = profile.name
    candidate.email = profile.email
    candidate.phone = profile.phone
    candidate.skills = json.dumps(profile.skills)
    candidate.years_experience = profile.years_experience
    candidate.education = profile.education
    candidate.current_role = profile.current_role
    candidate.summary = profile.summary
    candidate.is_processed = 1

    db.commit()
    db.refresh(candidate)

    # NEW: push to ChromaDB now that structured fields are ready
    upsert_candidate(candidate)

    return {
        "message": "Candidate processed and indexed successfully",
        "candidate_id": candidate.id,
        "profile": profile.model_dump()
    }


@router.post("/search")
def search_by_job_description(job_description: str, top_n: int = 5):
    """
    The core 'sorting' feature: paste a job description,
    get back ranked candidates by semantic similarity.
    """
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")

    matches = search_candidates(job_description, top_n)
    return {
        "job_description": job_description,
        "matches": matches
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

@router.post("/rank")
def rank_candidates(job_description: str, top_n: int = 5):
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")

    if top_n < 1 or top_n > 20:
        raise HTTPException(status_code=400, detail="top_n must be between 1 and 20")

    try:
        result = run_agent(job_description, top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed: {str(e)}")

    sheet_url = ""

    # Export to Google Sheets if candidates were shortlisted
    if result["shortlisted"]:
        try:
            sheet_url = export_to_sheets(job_description, result["shortlisted"])
        except Exception as e:
            print(f"⚠️ Sheets export failed: {e}")

    # Send email notification
    # try:
    #     send_ranking_email(
    #         job_description=job_description,
    #         shortlisted=result["shortlisted"],
    #         rejected=result["rejected"],
    #         final_report=result["final_report"] or "",
    #         sheet_url=sheet_url
    #     )
    # except Exception as e:
    #     print(f"⚠️ Email notification failed: {e}")

    return {
        **result,
        "sheet_url": sheet_url
    }