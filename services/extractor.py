import fitz  # PyMuPDF
import docx
import mammoth
import os

def extract_text(file_path: str, file_type: str) -> str:
    """
    Extract raw text from a PDF or DOCX/DOC file.
    Returns a plain string of all text content.
    """
    if file_type == "pdf":
        return _extract_from_pdf(file_path)
    elif file_type == "docx":
        return _extract_from_docx(file_path)
    elif file_type == "doc":
        return _extract_from_doc(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

def _extract_from_pdf(file_path: str) -> str:
    text_parts = []
    # fitz.open reads the PDF file from disk
    with fitz.open(file_path) as doc:
        for page in doc:
            # get_text() returns all text on this page
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()

def _extract_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    # Each paragraph is a block of text in Word
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs).strip()

def _extract_from_doc(file_path: str) -> str:
    # mammoth converts old .doc binary format to plain text
    with open(file_path, "rb") as f:
        result = mammoth.extract_raw_text(f)
    return result.value.strip()