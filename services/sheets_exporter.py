import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Scopes define what permissions we're requesting from Google
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _get_sheet():
    """
    Authenticates with Google and returns the worksheet object.
    Called fresh on each export so credentials are always valid.
    """
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
    sheet_name = os.getenv("GOOGLE_SHEET_NAME", "CV Sorter Results")

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1

    return sheet


def ensure_headers(sheet):
    """
    Checks if headers exist in row 1. If not, writes them.
    This way we only write headers once, not on every export.
    """
    headers = [
        "Export Date", "Job Description", "Rank", "Candidate ID",
        "Name", "Current Role", "Years Experience",
        "AI Score", "Skills Match", "Experience Match", "Reasoning"
    ]
    first_row = sheet.row_values(1)
    if first_row != headers:
        sheet.insert_row(headers, 1)


def export_to_sheets(job_description: str, shortlisted: list) -> str:
    """
    Writes shortlisted candidates to Google Sheets.
    Each export adds new rows — preserving history of past searches.
    Returns the sheet URL for reference.
    """
    sheet = _get_sheet()
    ensure_headers(sheet)

    export_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = []
    for rank, candidate in enumerate(shortlisted, start=1):
        row = [
            export_date,
            job_description[:100] + "..." if len(job_description) > 100 else job_description,
            rank,
            candidate.get("candidate_id", ""),
            candidate.get("name", "Unknown"),
            candidate.get("current_role", ""),
            candidate.get("years_experience", ""),
            candidate.get("ai_score", 0),
            candidate.get("skills_match", 0),
            candidate.get("experience_match", 0),
            candidate.get("reasoning", "")
        ]
        rows.append(row)

    if rows:
        # append_rows adds all rows in one API call — more efficient than
        # adding one row at a time (avoids hitting Google's rate limits)
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet.spreadsheet.id}"
    print(f"📊 Exported {len(rows)} candidates to Google Sheets")
    return sheet_url