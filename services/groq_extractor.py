import os
import json
from groq import Groq
from dotenv import load_dotenv
from services.schemas import CandidateProfile

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

EXTRACTION_PROMPT = """You are a CV/resume parsing assistant. Extract structured information from the CV text below.

Return ONLY a valid JSON object with these exact keys — no markdown, no explanation, no code fences:
{
  "name": "full name or null",
  "email": "email address or null",
  "phone": "phone number or null",
  "skills": ["list", "of", "skills"],
  "years_experience": number or null,
  "education": "highest qualification or null",
  "current_role": "most recent job title or null",
  "summary": "2-line professional summary"
}

Rules:
- If a field is not found in the text, use null (not "N/A" or empty string)
- skills should be a list of specific technical or professional skills, max 15 items
- years_experience must be a number (e.g. 3.5), not a string
- Do not invent information that isn't in the CV text

CV TEXT:
{cv_text}
"""

def extract_structured_data(raw_text: str) -> CandidateProfile:
    """
    Sends raw CV text to Groq, gets back structured JSON,
    validates it against CandidateProfile schema.
    """
    # Truncate very long CVs to stay within token limits
    truncated_text = raw_text[:8000]

    prompt = EXTRACTION_PROMPT.replace("{cv_text}", truncated_text)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,  # deterministic — same input gives same output
        response_format={"type": "json_object"},  # forces valid JSON
    )

    raw_json = response.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq returned invalid JSON: {e}\nRaw output: {raw_json}")

    # This is where Pydantic validates the shape and types
    profile = CandidateProfile(**parsed)
    return profile