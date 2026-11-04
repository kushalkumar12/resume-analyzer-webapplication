"""Recruiter and application contact extraction from Job Descriptions."""

import re
from typing import List, Dict, Any, Optional
from ats.models import JDContactDetails
from ats.security import sanitize_input_text


# Regex patterns for contact data
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b|"
    r"\b\+?\d{1,3}[-.\s]?\d{10}\b"
)
URL_REGEX = re.compile(
    r"(?:https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?:jobs|careers)\.[^\s<>\"']+)",
    re.IGNORECASE
)

# Recruiter / Hiring POC regex
RECRUITER_POC_PATTERNS = [
    re.compile(r"(?:recruiter|talent\s+partner|hiring\s+manager|contact|poc|point\s+of\s+contact)\s*:\s*([A-Za-z\s]{3,30})(?:\n|,|\.|$)", re.IGNORECASE),
    re.compile(r"(?:reach\s+out\s+to|send\s+(?:your\s+)?(?:resume|cv|application)\s+to)\s+([A-Za-z\s]{3,30})(?:\s+at|\s+via|\n|,|\.|$)", re.IGNORECASE),
]

# Submission instruction patterns
INSTRUCTION_PATTERNS = [
    re.compile(r"(?:how\s+to\s+apply|to\s+apply|application\s+instructions?)[^\n]*\n((?:[^\n]+\n){1,4})", re.IGNORECASE),
    re.compile(r"((?:please\s+send|submit\s+your|email\s+your)[^\n\.\;]+[\.\;])", re.IGNORECASE)
]


def extract_jd_contact_details(jd_text: str, llm_contact: Optional[JDContactDetails] = None) -> JDContactDetails:
    """Extracts contact emails, phone numbers, recruiter names, links, and submission instructions from JD."""
    if not jd_text:
        return JDContactDetails()

    clean_jd = sanitize_input_text(jd_text)

    # 1. Regex Emails
    emails = list(dict.fromkeys(EMAIL_REGEX.findall(clean_jd)))

    # 2. Regex Phone Numbers (filter out false positive years or short digit sequences)
    phones = []
    for p in PHONE_REGEX.findall(clean_jd):
        clean_p = p.strip()
        # Ensure it's not just a standalone year
        if not re.match(r"^(19\d\d|20\d\d)$", clean_p) and len(re.sub(r"\D", "", clean_p)) >= 10:
            if clean_p not in phones:
                phones.append(clean_p)

    # 3. Application / Career Links
    links = []
    for u in URL_REGEX.findall(clean_jd):
        u_clean = u.strip().rstrip(".,;)")
        if u_clean and u_clean not in links:
            links.append(u_clean)

    # 4. Recruiter POC names
    names = []
    for pat in RECRUITER_POC_PATTERNS:
        for match in pat.finditer(clean_jd):
            raw_name = match.group(1).strip()
            # Clean up words
            words = raw_name.split()
            if 1 <= len(words) <= 4 and not any(w in raw_name.lower() for w in ["apply", "email", "link", "resume", "the", "our", "this"]):
                if raw_name not in names:
                    names.append(raw_name.title())

    # 5. Instructions
    instructions = ""
    for pat in INSTRUCTION_PATTERNS:
        match = pat.search(clean_jd)
        if match:
            instructions = match.group(1).strip().replace("\n", " ")
            break

    # Merge with LLM-extracted details if available
    if llm_contact:
        for e in llm_contact.emails:
            if e and e not in emails:
                emails.append(e)
        for p in llm_contact.phone_numbers:
            if p and p not in phones:
                phones.append(p)
        for n in llm_contact.recruiter_names:
            if n and n not in names:
                names.append(n)
        for l in llm_contact.application_links:
            if l and l not in links:
                links.append(l)
        if not instructions and llm_contact.submission_instructions:
            instructions = llm_contact.submission_instructions

    return JDContactDetails(
        emails=emails,
        phone_numbers=phones,
        recruiter_names=names,
        application_links=links,
        submission_instructions=instructions
    )


def generate_recruiter_search_queries(job_title: str, company_name: Optional[str] = None) -> List[Dict[str, str]]:
    """Generates precise Google & LinkedIn search queries to identify verified hiring team members.

    Provides ethical, legitimate search parameters to locate recruiters and hiring managers.
    """
    clean_role = job_title.strip() if job_title else "Software Engineer"
    comp = company_name.strip() if company_name else ""

    queries = []

    # 1. Talent Acquisition / Recruiter Search
    if comp:
        q_recruiter = f'site:linkedin.com/in "{comp}" ("Technical Recruiter" OR "Talent Acquisition" OR "Sourcer")'
        queries.append({
            "title": f"Find {comp} Recruiters on LinkedIn",
            "query": q_recruiter,
            "url": f"https://www.google.com/search?q={q_recruiter.replace(' ', '+').replace('\"', '%22')}"
        })

        q_manager = f'site:linkedin.com/in "{comp}" ("Engineering Manager" OR "Head of" OR "Hiring Manager")'
        queries.append({
            "title": f"Find {comp} Hiring Managers on LinkedIn",
            "query": q_manager,
            "url": f"https://www.google.com/search?q={q_manager.replace(' ', '+').replace('\"', '%22')}"
        })
    else:
        q_recruiter = f'site:linkedin.com/in ("Technical Recruiter" OR "Talent Acquisition") "{clean_role}"'
        queries.append({
            "title": "Search Relevant Recruiters on LinkedIn",
            "query": q_recruiter,
            "url": f"https://www.google.com/search?q={q_recruiter.replace(' ', '+').replace('\"', '%22')}"
        })

    return queries
