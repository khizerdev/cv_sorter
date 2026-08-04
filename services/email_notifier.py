import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


def send_ranking_email(
    job_description: str,
    shortlisted: list,
    rejected: list,
    final_report: str,
    sheet_url: str = ""
):
    """
    Sends a formatted HTML email summarizing the ranking results.
    Uses Gmail SMTP with an App Password — no third-party service needed.
    """
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT")

    if not all([sender, password, recipient]):
        print("⚠️ Email credentials not configured — skipping email")
        return

    # Build HTML email body
    shortlist_rows = ""
    for rank, c in enumerate(shortlisted, start=1):
        shortlist_rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #e2e8f0">{rank}</td>
            <td style="padding:8px;border:1px solid #e2e8f0"><strong>{c.get('name', 'Unknown')}</strong></td>
            <td style="padding:8px;border:1px solid #e2e8f0">{c.get('current_role', '')}</td>
            <td style="padding:8px;border:1px solid #e2e8f0">{c.get('years_experience', '')} yrs</td>
            <td style="padding:8px;border:1px solid #e2e8f0">
                <strong style="color:#16a34a">{c.get('ai_score', 0)}/100</strong>
            </td>
            <td style="padding:8px;border:1px solid #e2e8f0">{c.get('reasoning', '')}</td>
        </tr>"""

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px">

        <h2 style="color:#1e293b">CV Sorter — Ranking Results</h2>

        <div style="background:#f8fafc;padding:12px;border-radius:6px;margin-bottom:20px">
            <strong>Job Description:</strong><br>
            {job_description}
        </div>

        <h3 style="color:#16a34a">✅ Shortlisted ({len(shortlisted)} candidates)</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
            <thead>
                <tr style="background:#f1f5f9">
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Rank</th>
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Name</th>
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Role</th>
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Experience</th>
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Score</th>
                    <th style="padding:8px;border:1px solid #e2e8f0;text-align:left">Reasoning</th>
                </tr>
            </thead>
            <tbody>{shortlist_rows}</tbody>
        </table>

        <h3 style="color:#dc2626">❌ Rejected ({len(rejected)} candidates)</h3>
        <p style="color:#64748b">{', '.join([c.get('name', 'Unknown') for c in rejected]) or 'None'}</p>

        <hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0">

        <h3>📋 AI Hiring Report</h3>
        <div style="background:#f8fafc;padding:16px;border-radius:6px;white-space:pre-wrap">{final_report}</div>

        {"<p><a href='" + sheet_url + "'>📊 View full results in Google Sheets</a></p>" if sheet_url else ""}

        <p style="color:#94a3b8;font-size:12px;margin-top:24px">Sent by CV Sorter Bot</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CV Sorter: {len(shortlisted)} candidates shortlisted"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        # Port 587 = TLS (secure) — always use this, never port 25
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"📧 Email sent to {recipient}")
    except Exception as e:
        # Email failure should NOT crash the ranking pipeline
        print(f"⚠️ Email failed: {e}")