"""End-to-end ATS analysis coordination pipeline."""

from typing import List, Optional, Any, Tuple
from ats.models import FullAnalysisResult
from ats.checks import run_deterministic_checks, calculate_experience_years_from_text
from ats.security import mask_pii, detect_prompt_injection
from ats.llm import analyze_with_failover
from ats.scoring import verify_requirements, compute_deterministic_score
from ats.insights import generate_top_fixes
from ats.contacts import extract_jd_contact_details
from ats.enterprise import (
    build_recruiter_boolean_queries, analyze_tenure_and_stability, evaluate_xyz_formula
)
from ats.checks import extract_bullet_points


def run_full_ats_analysis(
    api_key: str,
    selected_model: str,
    job_description: str,
    resume_text: str,
    mask_pii_flag: bool = True,
    available_models: Optional[List[str]] = None,
    progress_callback: Optional[Any] = None
) -> FullAnalysisResult:
    """Coordinates the entire analysis pipeline:

    1. Runs deterministic format, content, and integrity checks locally on raw text.
    2. Calculates work experience years from date ranges.
    3. Masks PII if requested before calling Gemini.
    4. Invokes Gemini via failover chain for structured extraction.
    5. Verifies requirements and cited evidence quotes against raw resume text.
    6. Calculates deterministic score in code.
    7. Generates prioritized top fixes with point estimations.
    """
    if progress_callback:
        progress_callback("Running local ATS format and content checks...")

    # 1. Deterministic checks on original unmasked text
    ats_checks = run_deterministic_checks(resume_text)

    # 2. Integrity and experience calculations
    has_injection, _ = detect_prompt_injection(resume_text)
    code_experience_years = calculate_experience_years_from_text(resume_text)

    # 3. PII Masking
    if mask_pii_flag:
        if progress_callback:
            progress_callback("Masking PII (contact details, URLs, sensitive IDs)...")
        prepared_resume = mask_pii(resume_text)
    else:
        prepared_resume = resume_text

    # 4. Invoke LLM with failover
    if progress_callback:
        progress_callback("Querying Google Gemini for structured requirement extraction...")

    llm_resp, working_model, failover_occurred = analyze_with_failover(
        api_key=api_key,
        selected_model=selected_model,
        job_description=job_description,
        resume_text=prepared_resume,
        available_models=available_models,
        progress_callback=progress_callback
    )

    # 5. Verify requirements against original resume text
    if progress_callback:
        progress_callback("Verifying requirement citations and evidence against resume text...")

    verified_reqs = verify_requirements(llm_resp.requirements, resume_text)

    # 6. Compute deterministic score in code
    if progress_callback:
        progress_callback("Calculating deterministic score weights and category fit...")

    score_result, verified_reqs = compute_deterministic_score(
        verified_reqs=verified_reqs,
        knockouts=llm_resp.knockouts,
        ats_checks=ats_checks,
        llm_experience_years=llm_resp.experience.candidate_years_estimate,
        llm_required_years=llm_resp.experience.required_years,
        llm_title_alignment=llm_resp.experience.title_alignment,
        code_calculated_years=code_experience_years,
        education_status=llm_resp.education_status,
        has_prompt_injection=has_injection
    )

    # 7. Generate top fixes
    top_fixes = generate_top_fixes(verified_reqs, ats_checks, score_result)

    # 8. Extract contact details and recruiter info from JD
    contact_details = extract_jd_contact_details(job_description, llm_resp.contact_details)

    # 9. Enterprise screening assessments (Boolean, Tenure, Google X-Y-Z)
    boolean_queries = build_recruiter_boolean_queries(
        job_title=llm_resp.job_title,
        requirements=verified_reqs,
        resume_text=resume_text
    )
    tenure_info = analyze_tenure_and_stability(resume_text)
    bullets = extract_bullet_points(resume_text)
    xyz_info = evaluate_xyz_formula(bullets)

    return FullAnalysisResult(
        job_title=llm_resp.job_title or "Target Role",
        seniority=llm_resp.seniority or "Mid-Level",
        score=score_result,
        verified_requirements=verified_reqs,
        knockouts=llm_resp.knockouts,
        ats_checks=ats_checks,
        strengths=llm_resp.strengths,
        gaps=llm_resp.gaps,
        summary=llm_resp.summary,
        rewrites=llm_resp.rewrites,
        top_fixes=top_fixes,
        model_used=working_model,
        failover_occurred=failover_occurred,
        pii_masked=mask_pii_flag,
        contact_details=contact_details,
        tenure_analysis=tenure_info,
        xyz_analysis=xyz_info,
        boolean_queries=boolean_queries
    )

