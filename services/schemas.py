from pydantic import BaseModel, Field
from typing import List, Optional

class CandidateProfile(BaseModel):
    """
    The structured shape we want extracted from every CV.
    Pydantic will validate Groq's JSON output against this.
    """
    name: Optional[str] = Field(default=None, description="Full name of the candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    skills: List[str] = Field(default_factory=list, description="List of technical/professional skills")
    years_experience: Optional[float] = Field(default=None, description="Total years of professional experience")
    education: Optional[str] = Field(default=None, description="Highest degree or qualification")
    current_role: Optional[str] = Field(default=None, description="Most recent job title")
    summary: Optional[str] = Field(default=None, description="2-line professional summary")