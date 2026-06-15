from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate
from services.extractor import extract_text
import os
import shutil

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