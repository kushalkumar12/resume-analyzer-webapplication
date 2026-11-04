"""Defensive sanitization, normalization, and validation of LLM outputs."""

import re
import json
from typing import Dict, Any, List, Optional
from ats.models import (
    LLMAnalysisResponse, RequirementItem, KnockoutItem,
    ExperienceAssessment, RewriteSuggestion
)
from ats.security import sanitize_input_text


TAG_REGEX = re.compile(r"<[^>]+>")


def clean_str(val: Any, max_len: int = 500) -> str:
    """Strips control chars, HTML tags, and truncates to max_len."""
    if val is None:
        return ""
    text = str(val)
    text = TAG_REGEX.sub("", text)
    text = sanitize_input_text(text)
    return text.strip()[:max_len]


def clamp_float(val: Any, min_val: float = 0.0, max_val: float = 30.0, default: float = 0.0) -> float:
    """Safely converts to float and clamps within bounds."""
    try:
        f = float(val)
        return max(min_val, min(max_val, f))
    except (ValueError, TypeError):
        return default


def clamp_int(val: Any, min_val: int = 0, max_val: int = 2, default: int = 1) -> int:
    """Safely converts to int and clamps within bounds."""
    try:
        i = int(round(float(val)))
        return max(min_val, min(max_val, i))
    except (ValueError, TypeError):
        return default


def normalize_llm_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Defensively sanitizes raw dictionary parsed from LLM JSON response."""
    normalized: Dict[str, Any] = {}

    normalized["job_title"] = clean_str(raw.get("job_title", ""), max_len=150)
    normalized["seniority"] = clean_str(raw.get("seniority", "Mid-Level"), max_len=50)

    # Requirements
    raw_reqs = raw.get("requirements", [])
    if not isinstance(raw_reqs, list):
        raw_reqs = []

    seen_terms = set()
    cleaned_reqs: List[Dict[str, Any]] = []

    for item in raw_reqs[:30]:  # Cap at 30
        if not isinstance(item, dict):
            continue

        raw_term = clean_str(item.get("term", ""), max_len=80)
        if not raw_term:
            continue

        term_key = raw_term.lower()
        if term_key in seen_terms:
            continue
        seen_terms.add(term_key)

        category = clean_str(item.get("category", "hard_skill"), max_len=30).lower()
        if category not in ["hard_skill", "tool", "soft_skill", "certification", "domain"]:
            category = "hard_skill"

        importance = clean_str(item.get("importance", "must"), max_len=10).lower()
        if importance not in ["must", "nice"]:
            importance = "must"

        syns_raw = item.get("synonyms", [])
        synonyms = []
        if isinstance(syns_raw, list):
            for s in syns_raw[:6]:
                cs = clean_str(s, max_len=50)
                if cs and cs.lower() != term_key and cs.lower() not in [x.lower() for x in synonyms]:
                    synonyms.append(cs)

        raw_status = clean_str(item.get("status", "missing"), max_len=20).lower()
        if raw_status not in ["explicit", "implied", "missing"]:
            raw_status = "missing"

        evidence = clean_str(item.get("evidence", ""), max_len=300)
        demonstrated = bool(item.get("demonstrated_in_experience", False))

        # If evidence is empty, force status to missing
        if not evidence.strip():
            raw_status = "missing"
            demonstrated = False
            evidence = ""

        cleaned_reqs.append({
            "term": raw_term,
            "category": category,
            "importance": importance,
            "synonyms": synonyms,
            "status": raw_status,
            "demonstrated_in_experience": demonstrated,
            "evidence": evidence
        })

    normalized["requirements"] = cleaned_reqs

    # Knockouts
    raw_kos = raw.get("knockouts", [])
    if not isinstance(raw_kos, list):
        raw_kos = []

    cleaned_kos: List[Dict[str, Any]] = []
    for item in raw_kos[:10]:
        if not isinstance(item, dict):
            continue
        req_text = clean_str(item.get("requirement", ""), max_len=200)
        if not req_text:
            continue
        met = clean_str(item.get("met", "unknown"), max_len=10).lower()
        if met not in ["yes", "no", "unknown"]:
            met = "unknown"
        ev = clean_str(item.get("evidence", ""), max_len=300)
        cleaned_kos.append({"requirement": req_text, "met": met, "evidence": ev})

    normalized["knockouts"] = cleaned_kos

    # Experience
    raw_exp = raw.get("experience", {})
    if not isinstance(raw_exp, dict):
        raw_exp = {}
    normalized["experience"] = {
        "required_years": clamp_float(raw_exp.get("required_years", 0.0), 0.0, 30.0, 0.0),
        "candidate_years_estimate": clamp_float(raw_exp.get("candidate_years_estimate", 0.0), 0.0, 30.0, 0.0),
        "title_alignment": clamp_int(raw_exp.get("title_alignment", 1), 0, 2, 1)
    }

    # Education status
    edu_raw = clean_str(raw.get("education_status", "met"), max_len=20).lower()
    if edu_raw not in ["met", "partial", "not_met", "not_required"]:
        edu_raw = "met"
    normalized["education_status"] = edu_raw

    # Strengths & Gaps
    for field in ["strengths", "gaps"]:
        raw_list = raw.get(field, [])
        cleaned_list = []
        if isinstance(raw_list, list):
            for item in raw_list[:5]:
                c_item = clean_str(item, max_len=250)
                if c_item:
                    cleaned_list.append(c_item)
        normalized[field] = cleaned_list

    # Summary
    normalized["summary"] = clean_str(raw.get("summary", ""), max_len=1000)

    # Rewrites
    raw_rewrites = raw.get("rewrites", [])
    cleaned_rewrites: List[Dict[str, Any]] = []
    if isinstance(raw_rewrites, list):
        for item in raw_rewrites[:5]:
            if not isinstance(item, dict):
                continue
            orig = clean_str(item.get("original", ""), max_len=400)
            imp = clean_str(item.get("improved", ""), max_len=400)
            reas = clean_str(item.get("reason", ""), max_len=300)
            if orig and imp:
                cleaned_rewrites.append({"original": orig, "improved": imp, "reason": reas})
    normalized["rewrites"] = cleaned_rewrites

    # Contact Details
    raw_contacts = raw.get("contact_details", {})
    if isinstance(raw_contacts, dict):
        normalized["contact_details"] = {
            "emails": [clean_str(e, 100) for e in raw_contacts.get("emails", []) if clean_str(e, 100)][:5],
            "phone_numbers": [clean_str(p, 50) for p in raw_contacts.get("phone_numbers", []) if clean_str(p, 50)][:5],
            "recruiter_names": [clean_str(n, 100) for n in raw_contacts.get("recruiter_names", []) if clean_str(n, 100)][:5],
            "application_links": [clean_str(l, 300) for l in raw_contacts.get("application_links", []) if clean_str(l, 300)][:5],
            "submission_instructions": clean_str(raw_contacts.get("submission_instructions", ""), 500)
        }
    else:
        normalized["contact_details"] = {
            "emails": [], "phone_numbers": [], "recruiter_names": [], "application_links": [], "submission_instructions": ""
        }

    return normalized



def parse_and_validate_llm_response(raw_text: str) -> LLMAnalysisResponse:
    """Extracts JSON from raw LLM text, sanitizes, and parses into Pydantic model."""
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned an empty response.")

    clean_text = raw_text.strip()
    # Strip markdown code fences if present (e.g. ```json ... ```)
    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"\s*```$", "", clean_text, flags=re.MULTILINE)

    # Extract JSON object with regex if extra commentary exists
    json_obj = None
    try:
        json_obj = json.loads(clean_text)
    except Exception:
        # Match from first { to last }
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if match:
            json_obj = json.loads(match.group(0))
        else:
            raise ValueError("No valid JSON structure found in model output.")

    if not isinstance(json_obj, dict):
        raise ValueError("Model response is not a valid JSON object.")

    normalized_dict = normalize_llm_dict(json_obj)
    return LLMAnalysisResponse(**normalized_dict)
