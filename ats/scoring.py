"""Deterministic ATS scoring engine computed entirely in verified code."""

from typing import List, Tuple, Dict, Any
from ats.models import (
    LLMAnalysisResponse, RequirementItem, VerifiedRequirement,
    ScoreResult, ScoreAreaBreakdown, ATSCheckItem, KnockoutItem
)
from ats.matching import (
    matches_term_in_text, verify_evidence_quote, is_skill_in_standalone_list_only
)


def verify_requirements(
    requirements: List[RequirementItem],
    resume_text: str
) -> List[VerifiedRequirement]:
    """Verifies each LLM requirement against original resume text and assigns credit."""
    verified_list: List[VerifiedRequirement] = []

    for req in requirements:
        term = req.term
        synonyms = req.synonyms
        evidence = req.evidence
        raw_status = req.status
        is_demonstrated = req.demonstrated_in_experience

        # Verify evidence quote authenticity in resume
        is_ev_valid = verify_evidence_quote(evidence, resume_text) if evidence else False

        # Check if canonical term or synonyms literally appear in the resume
        has_term = matches_term_in_text(term, resume_text, synonyms)

        # Determine verified status and credit ratio
        credit_ratio = 0.0
        verified_status = "missing"
        explanation = ""

        # Recency decay multiplier (Enterprise ATS standard):
        # - recent (current/last 3 yrs): 1.0x
        # - past (3-6 yrs ago): 0.75x
        # - ancient (>6 yrs ago): 0.40x
        # - unknown/skills-only: 1.0x (unpenalized if baseline is already discounted)
        recency = getattr(req, "recency", "unknown")
        recency_factor = 1.0
        if is_demonstrated:
            if recency == "ancient":
                recency_factor = 0.40
            elif recency == "past":
                recency_factor = 0.75

        if raw_status == "missing" or not evidence.strip():
            credit_ratio = 0.0
            verified_status = "missing"
            explanation = "Skill was not found in the resume and no evidence was provided."

        elif has_term and is_ev_valid:
            # Term exists and evidence is authentic
            in_skills_only = is_skill_in_standalone_list_only(term, resume_text)
            if is_demonstrated and not in_skills_only:
                credit_ratio = round(1.0 * recency_factor, 2)
                verified_status = "found"
                if recency_factor < 1.0:
                    explanation = f"Demonstrated in work experience ({recency} tenure, {int(credit_ratio*100)}% credit after recency decay)."
                else:
                    explanation = "Directly mentioned and demonstrated with authentic experience evidence (100% credit)."
            else:
                # Big Tech ATS screeners penalize standalone uncorroborated skill blocks
                credit_ratio = 0.35
                verified_status = "found"
                explanation = "Listed in skills section but uncorroborated in work experience/projects (35% partial credit)."

        elif not has_term and is_ev_valid and raw_status == "implied":
            # Term not explicitly named, but authentic resume evidence proves implied application
            credit_ratio = round(0.6 * recency_factor, 2)
            verified_status = "implied"
            explanation = f"Implied application supported by verified resume evidence ({int(credit_ratio*100)}% credit)."

        elif (raw_status in ["explicit", "implied"]) and not is_ev_valid:
            # LLM claimed match but evidence quote is hallucinated/unverified
            credit_ratio = 0.0
            verified_status = "unverified"
            explanation = "Unverified: AI cited evidence that could not be verified in the resume text (0% credit)."

        else:
            credit_ratio = 0.0
            verified_status = "missing"
            explanation = "Requirement missing from resume."

        verified_list.append(VerifiedRequirement(
            term=term,
            category=req.category,
            importance=req.importance,
            synonyms=synonyms,
            raw_status=raw_status,
            verified_status=verified_status,
            demonstrated_in_experience=is_demonstrated,
            recency=recency,
            recency_factor=recency_factor,
            evidence=evidence,
            evidence_verified=is_ev_valid,
            credit_ratio=credit_ratio,
            points_earned=0.0,  # Computed in scoring step
            max_points=0.0,     # Computed in scoring step
            explanation=explanation,
        ))

    return verified_list


def compute_deterministic_score(
    verified_reqs: List[VerifiedRequirement],
    knockouts: List[KnockoutItem],
    ats_checks: List[ATSCheckItem],
    llm_experience_years: float,
    llm_required_years: float,
    llm_title_alignment: int,
    code_calculated_years: float,
    education_status: str,
    has_prompt_injection: bool
) -> Tuple[ScoreResult, List[VerifiedRequirement]]:
    """Calculates final transparent ATS score using explicit weights and rules.

    Weights (Total 100):
      - Must-have skills: 40 pts
      - Nice-to-have skills: 10 pts
      - Experience fit: 20 pts
      - Education: 5 pts
      - ATS format: 15 pts
      - Content quality: 10 pts
    """
    # 1. Skills Scoring
    must_reqs = [r for r in verified_reqs if r.importance == "must"]
    nice_reqs = [r for r in verified_reqs if r.importance == "nice"]

    # Dynamic weight adjustment if no must or no nice requirements exist
    must_weight = 40.0
    nice_weight = 10.0
    if not must_reqs and nice_reqs:
        nice_weight = 50.0
        must_weight = 0.0
    elif must_reqs and not nice_reqs:
        must_weight = 50.0
        nice_weight = 0.0
    elif not must_reqs and not nice_reqs:
        must_weight = 0.0
        nice_weight = 0.0

    must_earned = 0.0
    if must_reqs:
        pts_per_must = must_weight / len(must_reqs)
        for r in must_reqs:
            r.max_points = round(pts_per_must, 2)
            r.points_earned = round(pts_per_must * r.credit_ratio, 2)
            must_earned += r.points_earned
    must_earned = min(must_earned, must_weight)

    nice_earned = 0.0
    if nice_reqs:
        pts_per_nice = nice_weight / len(nice_reqs)
        for r in nice_reqs:
            r.max_points = round(pts_per_nice, 2)
            r.points_earned = round(pts_per_nice * r.credit_ratio, 2)
            nice_earned += r.points_earned
    nice_earned = min(nice_earned, nice_weight)

    # 2. Experience Fit (20 pts)
    # Take conservative minimum between LLM estimate and code date-range calculator
    candidate_years_used = max(0.0, min(llm_experience_years, code_calculated_years) if code_calculated_years > 0 else llm_experience_years)

    if llm_required_years <= 0.0:
        years_ratio = 1.0
    else:
        years_ratio = min(candidate_years_used / llm_required_years, 1.0)

    title_ratio = min(max(llm_title_alignment / 2.0, 0.0), 1.0)
    exp_earned = round(20.0 * (0.6 * years_ratio + 0.4 * title_ratio), 2)
    exp_earned = min(exp_earned, 20.0)

    # 3. Education (5 pts)
    edu_map = {
        "met": 5.0,
        "not_required": 5.0,
        "partial": 3.0,
        "not_met": 0.0
    }
    edu_earned = edu_map.get(education_status.lower(), 5.0)

    # 4. ATS Format Checks (15 pts)
    fmt_checks = [c for c in ats_checks if c.category == "format"]
    fmt_raw_pts = sum(c.points for c in fmt_checks)
    fmt_max_raw = sum(c.max_points for c in fmt_checks) or 15.0
    fmt_earned = round(15.0 * (fmt_raw_pts / fmt_max_raw), 2)
    fmt_earned = min(fmt_earned, 15.0)

    # 5. Content Quality Checks (10 pts)
    cnt_checks = [c for c in ats_checks if c.category == "content"]
    cnt_raw_pts = sum(c.points for c in cnt_checks)
    cnt_max_raw = sum(c.max_points for c in cnt_checks) or 10.0
    cnt_earned = round(10.0 * (cnt_raw_pts / cnt_max_raw), 2)
    cnt_earned = min(cnt_earned, 10.0)

    # Sum raw total
    raw_total = must_earned + nice_earned + exp_earned + edu_earned + fmt_earned + cnt_earned
    final_score = round(min(max(raw_total, 0.0), 100.0), 1)

    # 6. Apply Caps
    # Knockout cap: any knockout marked 'no' caps score at 60.0
    has_failed_knockout = any(k.met.lower() == "no" for k in knockouts)
    knockout_capped = False
    if has_failed_knockout and final_score > 60.0:
        final_score = 60.0
        knockout_capped = True

    # Prompt injection cap: caps score at 30.0
    injection_capped = False
    if has_prompt_injection and final_score > 30.0:
        final_score = 30.0
        injection_capped = True

    # Band classification
    if final_score >= 80.0:
        band = "Strong"
    elif final_score >= 65.0:
        band = "Good"
    elif final_score >= 50.0:
        band = "Partial"
    else:
        band = "Weak"

    breakdown = {
        "must_skills": ScoreAreaBreakdown(
            area="Must-Have Skills",
            earned=must_earned,
            maximum=must_weight,
            percentage=round((must_earned / must_weight * 100), 1) if must_weight > 0 else 100.0,
            description="Core non-negotiable technical & functional skills"
        ),
        "nice_skills": ScoreAreaBreakdown(
            area="Nice-to-Have Skills",
            earned=nice_earned,
            maximum=nice_weight,
            percentage=round((nice_earned / nice_weight * 100), 1) if nice_weight > 0 else 100.0,
            description="Preferred qualifications and bonus competencies"
        ),
        "experience": ScoreAreaBreakdown(
            area="Experience Fit",
            earned=exp_earned,
            maximum=20.0,
            percentage=round((exp_earned / 20.0 * 100), 1),
            description="Tenure alignment and job title seniority"
        ),
        "education": ScoreAreaBreakdown(
            area="Education & Credentials",
            earned=edu_earned,
            maximum=5.0,
            percentage=round((edu_earned / 5.0 * 100), 1),
            description="Degree and academic prerequisites"
        ),
        "ats_format": ScoreAreaBreakdown(
            area="ATS Readability & Format",
            earned=fmt_earned,
            maximum=15.0,
            percentage=round((fmt_earned / 15.0 * 100), 1),
            description="Document parsing compatibility, layout, and sections"
        ),
        "content_quality": ScoreAreaBreakdown(
            area="Content Impact",
            earned=cnt_earned,
            maximum=10.0,
            percentage=round((cnt_earned / 10.0 * 100), 1),
            description="Quantified metrics, active verbs, and concise writing"
        )
    }

    score_result = ScoreResult(
        total_score=final_score,
        band=band,
        knockout_capped=knockout_capped,
        injection_capped=injection_capped,
        breakdown=breakdown,
        candidate_years_used=candidate_years_used,
        required_years=llm_required_years
    )

    return score_result, verified_reqs
