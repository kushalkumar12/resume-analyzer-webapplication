"""Pydantic schemas and data models for ATS evaluation and LLM structured responses."""

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class RequirementItem(BaseModel):
    """Atomic requirement extracted from Job Description with resume match assessment."""
    term: str = Field(..., description="Canonical name of the skill, tool, or qualification")
    category: Literal["hard_skill", "tool", "soft_skill", "certification", "domain"] = Field(
        default="hard_skill",
        description="Requirement category"
    )
    importance: Literal["must", "nice"] = Field(
        default="must",
        description="Whether requirement is must-have or nice-to-have"
    )
    synonyms: List[str] = Field(
        default_factory=list,
        description="2-5 synonyms, aliases, or equivalent terms"
    )
    status: Literal["explicit", "implied", "missing"] = Field(
        default="missing",
        description="Whether requirement is explicitly named, implied with evidence, or missing"
    )
    demonstrated_in_experience: bool = Field(
        default=False,
        description="True only if used in work experience/projects rather than just listed in skills"
    )
    recency: Literal["recent", "past", "ancient", "unknown"] = Field(
        default="unknown",
        description="'recent' if in current/last 3 years role, 'past' if 3-6 years ago, 'ancient' if >6 years ago"
    )
    evidence: str = Field(
        default="",
        description="Verbatim quote from the resume (at most 25 words) supporting this requirement"
    )


class KnockoutItem(BaseModel):
    """Hard filters such as degree, clearance, mandatory license, visa, or location."""
    requirement: str = Field(..., description="The non-negotiable prerequisite")
    met: Literal["yes", "no", "unknown"] = Field(default="unknown", description="Whether met by candidate")
    evidence: str = Field(default="", description="Verbatim quote or note from resume")


class ExperienceAssessment(BaseModel):
    """Experience requirements and candidate alignment."""
    required_years: float = Field(default=0.0, ge=0.0, le=30.0, description="Minimum years required by JD")
    candidate_years_estimate: float = Field(default=0.0, ge=0.0, le=30.0, description="Estimated relevant candidate years")
    title_alignment: int = Field(default=1, ge=0, le=2, description="Job title alignment: 0=low, 1=moderate, 2=strong")


class RewriteSuggestion(BaseModel):
    """Evidence-based resume bullet rewrite without fabricated metrics."""
    original: str = Field(..., description="Original resume bullet or line")
    improved: str = Field(..., description="Improved version with action verbs and placeholders like [X%]")
    reason: str = Field(..., description="Why this rewrite improves ATS matching and recruiter impact")


class JDContactDetails(BaseModel):
    """Contact information and recruiter details extracted from the Job Description."""
    emails: List[str] = Field(default_factory=list, description="Emails mentioned in JD for applications or questions")
    phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers mentioned in JD")
    recruiter_names: List[str] = Field(default_factory=list, description="Recruiter, hiring manager, or contact names mentioned in JD")
    application_links: List[str] = Field(default_factory=list, description="Direct application links or career portals mentioned in JD")
    submission_instructions: str = Field(default="", description="Specific application instructions from JD")


class LLMAnalysisResponse(BaseModel):
    """Structured response schema expected from Gemini."""
    job_title: str = Field(default="", description="Job title from JD")
    seniority: str = Field(default="Mid-Level", description="Seniority level e.g. Junior, Mid, Senior, Lead")
    requirements: List[RequirementItem] = Field(
        default_factory=list,
        description="8-25 atomic requirements extracted from the JD"
    )
    knockouts: List[KnockoutItem] = Field(
        default_factory=list,
        description="Hard filters/eligibility prerequisites"
    )
    experience: ExperienceAssessment = Field(default_factory=ExperienceAssessment)
    education_status: Literal["met", "partial", "not_met", "not_required"] = Field(
        default="met",
        description="Education requirement status"
    )
    strengths: List[str] = Field(default_factory=list, description="Top strengths (max 5)")
    gaps: List[str] = Field(default_factory=list, description="Top missing areas (max 5)")
    summary: str = Field(default="", description="High-level candidate alignment summary")
    rewrites: List[RewriteSuggestion] = Field(default_factory=list, description="Targeted bullet rewrites (max 5)")
    contact_details: Optional[JDContactDetails] = Field(default_factory=JDContactDetails)


class VerifiedRequirement(BaseModel):
    """Requirement after deterministic code-level verification."""
    term: str
    category: str
    importance: Literal["must", "nice"]
    synonyms: List[str]
    raw_status: str
    verified_status: Literal["found", "implied", "unverified", "missing"]
    demonstrated_in_experience: bool
    recency: Literal["recent", "past", "ancient", "unknown"] = "unknown"
    recency_factor: float = 1.0
    evidence: str
    evidence_verified: bool
    credit_ratio: float  # calibrated credit after verification & recency decay
    points_earned: float
    max_points: float
    explanation: str


class ATSCheckItem(BaseModel):
    """Individual deterministic ATS format or content check."""
    id: str
    category: Literal["format", "content", "integrity"]
    name: str
    status: Literal["pass", "warn", "fail"]
    points: float
    max_points: float
    detail: str
    fix: str


class ScoreAreaBreakdown(BaseModel):
    """Score breakdown for a specific dimension."""
    area: str
    earned: float
    maximum: float
    percentage: float
    description: str


class ScoreResult(BaseModel):
    """Deterministic score calculation outcome."""
    total_score: float = Field(..., ge=0.0, le=100.0)
    band: Literal["Strong", "Good", "Partial", "Weak"]
    knockout_capped: bool = False
    injection_capped: bool = False
    breakdown: Dict[str, ScoreAreaBreakdown] = Field(default_factory=dict)
    candidate_years_used: float
    required_years: float


class TopFixItem(BaseModel):
    """Actionable improvement with estimated point gain."""
    title: str
    category: str
    points_gain: float
    action: str
    importance: Literal["high", "medium", "low"]


class FullAnalysisResult(BaseModel):
    """Complete consolidated analysis output."""
    job_title: str
    seniority: str
    score: ScoreResult
    verified_requirements: List[VerifiedRequirement]
    knockouts: List[KnockoutItem]
    ats_checks: List[ATSCheckItem]
    strengths: List[str]
    gaps: List[str]
    summary: str
    rewrites: List[RewriteSuggestion]
    top_fixes: List[TopFixItem]
    model_used: str
    failover_occurred: bool = False
    pii_masked: bool = False
    contact_details: Optional[JDContactDetails] = Field(default_factory=JDContactDetails)
    tenure_analysis: Optional[Any] = None
    xyz_analysis: Optional[Any] = None
    boolean_queries: List[Any] = Field(default_factory=list)
