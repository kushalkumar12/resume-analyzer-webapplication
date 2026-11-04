"""Recruiter boolean search simulation, tenure stability, and Google X-Y-Z formula evaluations."""

import re
from typing import List, Dict, Tuple, Set, Optional
from pydantic import BaseModel, Field

from ats.models import RequirementItem, VerifiedRequirement
from ats.matching import get_aliases, build_term_regex


class BooleanQuery(BaseModel):
    """A realistic recruiter Boolean search string."""
    name: str = Field(..., description="Query purpose (e.g. Mandatory Core, Tier 1 Tech Stack)")
    query_string: str = Field(..., description="Raw Boolean query string formatted for ATS / LinkedIn Recruiter")
    matched: bool = Field(default=False, description="Whether candidate resume matches this query")
    matched_terms: List[str] = Field(default_factory=list, description="Terms found in candidate resume")
    missing_terms: List[str] = Field(default_factory=list, description="Terms missing from candidate resume")


class TenureAnalysisResult(BaseModel):
    """Analysis of candidate career stability and tenure."""
    average_tenure_years: float = Field(default=0.0, description="Average tenure per role")
    job_count: int = Field(default=0, description="Number of distinct roles identified")
    job_hopping_risk: bool = Field(default=False, description="True if high frequency job change (<1.2 years avg)")
    stability_band: str = Field(default="Good", description="Stable, Moderate, or High Mobility")
    summary: str = Field(default="", description="Detailed summary for hiring manager")


class XYZFormulaResult(BaseModel):
    """Assessment of bullet points according to Google's X-Y-Z formula: Accomplished [X], measured by [Y], by doing [Z]."""
    total_bullets: int = 0
    xyz_compliant_bullets: int = 0
    compliance_rate: float = 0.0
    scale_indicators_found: List[str] = Field(default_factory=list, description="Scale words e.g. QPS, TB, users, revenue")
    status: str = "pass"
    summary: str = ""


# Scale keywords common in Big Tech resume reviews
SCALE_KEYWORDS = [
    "qps", "rps", "throughput", "latency", "concurrent", "users", "mau", "dau",
    "terabytes", "petabytes", "gigabytes", "tb", "pb", "gb", "clusters", "nodes",
    "revenue", "budget", "million", "billion", "arr", "mrr", "cost reduction"
]


def build_recruiter_boolean_queries(
    job_title: str,
    requirements: List[VerifiedRequirement],
    resume_text: str
) -> List[BooleanQuery]:
    """Generates 2 to 3 enterprise recruiter Boolean search strings and evaluates candidate match.
    
    Mimics Workday, Greenhouse, Taleo, and LinkedIn Recruiter candidate sourcing filters.
    """
    queries: List[BooleanQuery] = []
    lower_resume = resume_text.lower()

    # Query 1: Minimum Core Skills (Must-have hard skills and tools)
    must_haves = [r for r in requirements if r.importance == "must" and r.category in ["hard_skill", "tool"]]
    if must_haves:
        # Take top 3-4 must haves
        top_must = must_haves[:4]
        query_parts = []
        found_terms = []
        missing_terms = []

        for req in top_must:
            aliases = list(get_aliases(req.term))[:3]
            # e.g. ("Python" OR "py")
            part = "(" + " OR ".join(f'"{a}"' for a in aliases) + ")"
            query_parts.append(part)

            # Check if candidate has it
            if req.verified_status in ["found", "implied"]:
                found_terms.append(req.term)
            else:
                missing_terms.append(req.term)

        query_str = " AND ".join(query_parts)
        is_matched = len(missing_terms) == 0
        queries.append(BooleanQuery(
            name="Tier 1 Minimum Technical Bar",
            query_string=query_str,
            matched=is_matched,
            matched_terms=found_terms,
            missing_terms=missing_terms
        ))

    # Query 2: Title Alignment + Key Tool
    if job_title:
        title_clean = job_title.strip()
        title_part = f'("{title_clean}")'
        # Grab top tool or domain
        top_tools = [r for r in requirements if r.category in ["tool", "domain"]]
        if top_tools:
            tool_req = top_tools[0]
            tool_aliases = list(get_aliases(tool_req.term))[:2]
            tool_part = "(" + " OR ".join(f'"{a}"' for a in tool_aliases) + ")"
            q2_str = f"{title_part} AND {tool_part}"

            # Check matching
            title_pat = build_term_regex(title_clean)
            has_title = bool(title_pat.search(resume_text))
            has_tool = tool_req.verified_status in ["found", "implied"]

            q2_matched = has_title and has_tool
            found_q2 = []
            miss_q2 = []
            if has_title:
                found_q2.append(title_clean)
            else:
                miss_q2.append(title_clean)
            if has_tool:
                found_q2.append(tool_req.term)
            else:
                miss_q2.append(tool_req.term)

            queries.append(BooleanQuery(
                name="Role Title & Domain Specialization",
                query_string=q2_str,
                matched=q2_matched,
                matched_terms=found_q2,
                missing_terms=miss_q2
            ))

    return queries


def analyze_tenure_and_stability(resume_text: str) -> TenureAnalysisResult:
    """Analyzes candidate role frequency and flags job hopping risks."""
    from ats.checks import extract_work_section
    work_text = extract_work_section(resume_text)

    # Count distinct job/tenure entries
    date_range_regex = re.compile(
        r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?\b(19\d\d|20\d\d)\b"
        r"\s*(?:-|–|—|to)\s*"
        r"(?:(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?\b(19\d\d|20\d\d)\b|present|current|now)",
        re.IGNORECASE
    )

    matches = list(date_range_regex.finditer(work_text))
    job_count = max(len(matches), 1)

    from ats.checks import calculate_experience_years_from_text
    total_years = calculate_experience_years_from_text(resume_text)

    avg_tenure = round(total_years / job_count, 1) if job_count > 0 else total_years

    # In Big Tech screening:
    # < 1.2 years avg tenure across >= 3 jobs = high mobility flag
    if job_count >= 3 and avg_tenure < 1.2:
        return TenureAnalysisResult(
            average_tenure_years=avg_tenure,
            job_count=job_count,
            job_hopping_risk=True,
            stability_band="High Mobility",
            summary=f"Average tenure is {avg_tenure} years across {job_count} roles. Multiple short tenures (<1.2 years) may raise questions regarding candidate retention in enterprise loops."
        )
    elif avg_tenure >= 2.5:
        return TenureAnalysisResult(
            average_tenure_years=avg_tenure,
            job_count=job_count,
            job_hopping_risk=False,
            stability_band="Stable",
            summary=f"Strong career stability with an average tenure of {avg_tenure} years across {job_count} roles."
        )
    else:
        return TenureAnalysisResult(
            average_tenure_years=avg_tenure,
            job_count=job_count,
            job_hopping_risk=False,
            stability_band="Moderate",
            summary=f"Balanced career progression with an average tenure of {avg_tenure} years across {job_count} roles."
        )


def evaluate_xyz_formula(bullets: List[str]) -> XYZFormulaResult:
    """Evaluates whether resume bullets follow the Google X-Y-Z formula and demonstrate scale."""
    if not bullets:
        return XYZFormulaResult(
            total_bullets=0,
            xyz_compliant_bullets=0,
            compliance_rate=0.0,
            status="fail",
            summary="No standard bullet points detected in resume."
        )

    # Google formula: Accomplished [X] (action verb + deliverable) measured by [Y] (metric/number) by doing [Z] (method/tool/action)
    from ats.checks import ACTION_VERBS
    metric_regex = re.compile(r"(?:\d+%\b|\$\d+|\b\d+\s*(?:k|m|b|gb|tb|ms|x)\b|\b\d{1,3}(?:,\d{3})+\b|\b[1-9]\d{0,2}\b(?!\d{3}))")
    by_doing_regex = re.compile(r"\b(by|using|utilizing|via|through|leveraging|implementing|architecting|building)\b", re.IGNORECASE)

    scale_found = set()
    compliant_count = 0

    for b in bullets:
        first_word = re.sub(r"[^\w]", "", b.split()[0].lower()) if b.split() else ""
        has_action = first_word in ACTION_VERBS
        clean_b = re.sub(r"\b(19\d\d|20\d\d)\b", "", b)
        has_metric = bool(metric_regex.search(clean_b))
        has_how = bool(by_doing_regex.search(b))

        # Check scale keywords
        lower_b = b.lower()
        for kw in SCALE_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower_b):
                scale_found.add(kw)

        if has_action and has_metric and has_how:
            compliant_count += 1

    total = len(bullets)
    rate = round(compliant_count / total, 2)

    status = "pass" if rate >= 0.25 else ("warn" if rate >= 0.10 else "fail")
    summary = f"{compliant_count} of {total} bullets ({int(rate*100)}%) follow the Google X-Y-Z structure (Action + Quantified Metric + Method/Tool)."

    return XYZFormulaResult(
        total_bullets=total,
        xyz_compliant_bullets=compliant_count,
        compliance_rate=rate,
        scale_indicators_found=sorted(list(scale_found)),
        status=status,
        summary=summary
    )
