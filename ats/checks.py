"""Deterministic ATS format, content quality, integrity checks, and experience-years calculator."""

import re
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from ats.models import ATSCheckItem
from ats.security import detect_prompt_injection


# Common strong action verbs for resume bullets
ACTION_VERBS = {
    "accelerated", "accomplished", "achieved", "acquired", "acted", "adapted",
    "administered", "advanced", "advised", "advocated", "allocated", "analyzed",
    "anchored", "applied", "appraised", "architected", "arranged", "assembled",
    "assessed", "audited", "authored", "automated", "boosted", "briefed", "built",
    "calculated", "calibrated", "championed", "charted", "clarified", "classified",
    "coached", "collaborated", "collected", "commissioned", "compiled", "composed",
    "computed", "conceptualized", "conducted", "configured", "consolidated", "constructed",
    "consulted", "contained", "contracted", "contributed", "controlled", "converted",
    "coordinated", "counseled", "crafted", "created", "critiqued", "cultivated",
    "customized", "debugged", "decided", "defined", "delegated", "delivered",
    "demonstrated", "deployed", "designed", "detailed", "detected", "determined",
    "developed", "devised", "diagnosed", "directed", "discovered", "dispatched",
    "distributed", "documented", "doubled", "drafted", "drove", "earned", "edited",
    "educated", "elevated", "eliminated", "enabled", "enacted", "engineered",
    "enhanced", "enlarged", "enlisted", "ensured", "established", "estimated",
    "evaluated", "examined", "executed", "expanded", "expedited", "experimented",
    "explained", "explored", "facilitated", "fashioned", "finalized", "focused",
    "forecasted", "formulated", "fostered", "founded", "fulfilled", "generated",
    "governed", "guided", "halted", "handled", "headed", "heightened", "hired",
    "identified", "illustrated", "implemented", "improved", "improvised", "increased",
    "indexed", "influenced", "informed", "initiated", "innovated", "inspected",
    "inspired", "installed", "instituted", "instructed", "integrated", "intensified",
    "interpreted", "interviewed", "introduced", "invented", "investigated", "isolated",
    "launched", "lead", "led", "leveraged", "liaised", "lightened", "linked",
    "maintained", "managed", "mapped", "marketed", "mastered", "maximized", "measured",
    "mediated", "mentored", "merged", "minimized", "modeled", "moderated", "modernized",
    "modified", "monitored", "motivated", "navigated", "negotiated", "nurtured",
    "obtained", "operated", "optimized", "orchestrated", "organized", "originated",
    "outperformed", "overhauled", "oversaw", "partnered", "performed", "persuaded",
    "piloted", "pioneered", "planned", "positioned", "predicted", "prepared",
    "prescribed", "presented", "presided", "prevented", "prioritized", "processed",
    "produced", "programmed", "projected", "promoted", "proposed", "protected",
    "provided", "published", "pursued", "quantified", "raised", "ranked", "reached",
    "realized", "recommended", "reconciled", "recorded", "recruited", "redesigned",
    "reduced", "refined", "refocused", "reformed", "regulated", "rehabilitated",
    "reinforced", "rejuvenated", "remediated", "remodeled", "reorganized", "repaired",
    "replaced", "replenished", "reported", "represented", "researched", "resolved",
    "restored", "restructured", "revamped", "reviewed", "revised", "revitalized",
    "saved", "scaled", "scheduled", "screened", "scrutinized", "secured", "selected",
    "separated", "shaped", "simplified", "simulated", "slashed", "solidified",
    "solved", "spearheaded", "specialized", "specified", "standardized", "started",
    "steered", "streamlined", "strengthened", "structured", "substantiated", "succeeded",
    "summarized", "supervised", "supplied", "supported", "surpassed", "surveyed",
    "synthesized", "systematized", "tabulated", "targeted", "taught", "tested",
    "tracked", "trained", "transformed", "translated", "tripled", "troubleshot",
    "unified", "unlocked", "upgraded", "utilized", "validated", "valued", "visualized",
    "won", "wrote", "yielded"
}

# Weak phrases to discourage
WEAK_PHRASES = [
    "responsible for", "responsibilities included", "duties included",
    "worked on", "assisted with", "helped to", "participated in",
    "tasked with", "handled day-to-day", "involved in"
]

# First person pronouns
FIRST_PERSON_PRONOUNS = re.compile(r"\b(i|me|my|mine|we|our|ours)\b", re.IGNORECASE)


def extract_bullet_points(text: str) -> List[str]:
    """Extracts bullet points or list items from text."""
    bullets = []
    lines = text.split("\n")
    bullet_prefix_regex = re.compile(r"^[\s]*[-*•–—▪▫\d+\.)]\s*(.*)$")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = bullet_prefix_regex.match(stripped)
        if match:
            content = match.group(1).strip()
            if len(content) > 10:
                bullets.append(content)
        elif len(stripped) > 20 and stripped.endswith((".", ";")):
            # Standalone sentence-like line in experience section
            bullets.append(stripped)

    return bullets


def extract_work_section(text: str) -> str:
    """Extracts non-education work experience lines from resume text."""
    lines = text.split("\n")
    work_lines = []
    in_education = False

    for line in lines:
        lower = line.lower()
        if any(h in lower for h in ["education", "academic", "university", "college", "degree"]):
            in_education = True
        elif any(h in lower for h in ["experience", "employment", "work history", "projects", "skills"]):
            in_education = False

        if not in_education and not any(deg in lower for deg in ["bachelor", "master", "phd", "b.s.", "m.s.", "b.tech", "m.tech", "diploma"]):
            work_lines.append(line)

    return "\n".join(work_lines)


def calculate_experience_years_from_text(text: str) -> float:
    """Parses date ranges from resume text and calculates non-overlapping years.

    Excludes education section dates to avoid inflating work experience.
    Supports formats like:
      - 2018 - 2022
      - Jan 2019 - Present
      - 03/2018 - 09/2021
      - September 2016 – Current
    """
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Months lookup
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9, "sept": 9, "oct": 10,
        "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    work_text = extract_work_section(text)

    # Date range regexes
    # Format 1: Month Year - Month Year / Present (e.g. Jan 2019 - Present)
    month_year_pattern = re.compile(
        r"\b([A-Za-z]{3,9})\s+(\d{4})\s*(?:-|–|—|to)\s*([A-Za-z]{3,9}|\d{4}|present|current|now)(?:\s+(\d{4}))?\b",
        re.IGNORECASE
    )

    # Format 2: Year - Year / Present (e.g. 2018 - 2022 or 2019 - Present)
    year_year_pattern = re.compile(
        r"\b(19\d\d|20\d\d)\s*(?:-|–|—|to)\s*(19\d\d|20\d\d|present|current|now)\b",
        re.IGNORECASE
    )

    ranges: List[Tuple[float, float]] = []

    # Parse Month Year
    for match in month_year_pattern.finditer(work_text):
        m1_str, y1_str, m2_or_y2, y2_extra = match.groups()
        m1 = months.get(m1_str.lower(), 1)
        try:
            y1 = int(y1_str)
        except ValueError:
            continue

        if 1970 <= y1 <= current_year + 1:
            start_val = y1 + (m1 - 1) / 12.0

            if m2_or_y2.lower() in ["present", "current", "now"]:
                end_val = current_year + (current_month - 1) / 12.0
            elif y2_extra:
                # m2_or_y2 is month, y2_extra is year
                m2 = months.get(m2_or_y2.lower(), 12)
                try:
                    y2 = int(y2_extra)
                    end_val = y2 + (m2 - 1) / 12.0
                except ValueError:
                    end_val = start_val
            else:
                # m2_or_y2 might be a year
                try:
                    y2 = int(m2_or_y2)
                    end_val = y2 + 11.0 / 12.0
                except ValueError:
                    end_val = start_val

            if end_val >= start_val and (end_val - start_val) <= 25.0:
                ranges.append((start_val, end_val))

    # Parse Year - Year
    for match in year_year_pattern.finditer(work_text):
        y1_str, y2_str = match.groups()
        try:
            y1 = int(y1_str)
            if y2_str.lower() in ["present", "current", "now"]:
                y2 = current_year
            else:
                y2 = int(y2_str)

            if 1970 <= y1 <= current_year + 1 and y2 >= y1 and (y2 - y1) <= 25:
                # Add if not already covered by Month-Year match
                ranges.append((float(y1), float(y2) + 0.99))
        except ValueError:
            continue

    if not ranges:
        return 0.0

    # Merge overlapping intervals
    ranges.sort(key=lambda r: r[0])
    merged = [ranges[0]]
    for current in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if current[0] <= prev_end:
            merged[-1] = (prev_start, max(prev_end, current[1]))
        else:
            merged.append(current)

    total_years = sum(end - start for start, end in merged)
    return round(min(max(total_years, 0.0), 30.0), 1)


def run_deterministic_checks(resume_text: str) -> List[ATSCheckItem]:
    """Runs all deterministic format, content, and integrity checks."""
    checks: List[ATSCheckItem] = []
    lower_text = resume_text.lower()
    words = resume_text.split()
    word_count = len(words)

    # ====================
    # 1. FORMAT CHECKS (Total max: 15 pts)
    # ====================

    # Format 1: Machine-readable text
    if word_count < 50:
        checks.append(ATSCheckItem(
            id="fmt_readable",
            category="format",
            name="Machine-Readable Text",
            status="fail",
            points=0.0,
            max_points=3.0,
            detail=f"Only {word_count} words extracted. Document appears empty or scanned without OCR.",
            fix="Upload a text-native PDF or DOCX file exported directly from Word, Google Docs, or LaTeX."
        ))
    else:
        checks.append(ATSCheckItem(
            id="fmt_readable",
            category="format",
            name="Machine-Readable Text",
            status="pass",
            points=3.0,
            max_points=3.0,
            detail=f"Document contains {word_count} cleanly extractable words.",
            fix=""
        ))

    # Format 2: Clean fonts and glyphs
    cid_match = bool(re.search(r"\(cid:\d+\)", resume_text))
    replacement_char = "\ufffd" in resume_text
    if cid_match or replacement_char:
        checks.append(ATSCheckItem(
            id="fmt_glyphs",
            category="format",
            name="Font & Character Encoding",
            status="fail",
            points=0.0,
            max_points=2.0,
            detail="Document contains broken character encodings (CID fonts or replacement characters) that corrupt ATS parsing.",
            fix="Re-export your PDF using standard Unicode fonts (e.g. Arial, Calibri, Times New Roman, Helvetica)."
        ))
    else:
        checks.append(ATSCheckItem(
            id="fmt_glyphs",
            category="format",
            name="Font & Character Encoding",
            status="pass",
            points=2.0,
            max_points=2.0,
            detail="Standard characters and glyphs detected without encoding corruption.",
            fix=""
        ))

    # Format 3: Contact details
    has_email = bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", resume_text))
    has_phone = bool(re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b|\b\d{10}\b", resume_text))
    has_link = bool(re.search(r"(?:linkedin\.com|github\.com|http|www)", lower_text))

    contact_pts = 0.0
    contact_status = "pass"
    missing_contact = []
    if has_email:
        contact_pts += 1.0
    else:
        missing_contact.append("email")
    if has_phone:
        contact_pts += 1.0
    else:
        missing_contact.append("phone number")
    if has_link:
        contact_pts += 0.5
    else:
        missing_contact.append("professional link (LinkedIn/GitHub)")

    if len(missing_contact) >= 2:
        contact_status = "fail"
    elif len(missing_contact) == 1:
        contact_status = "warn"

    checks.append(ATSCheckItem(
        id="fmt_contact",
        category="format",
        name="Contact Information",
        status=contact_status,
        points=contact_pts,
        max_points=2.5,
        detail="Contact details found: " + (f"Missing {', '.join(missing_contact)}." if missing_contact else "Email, phone, and profile links verified."),
        fix=f"Include your {' and '.join(missing_contact)} clearly in the contact header." if missing_contact else ""
    ))

    # Format 4: Standard section headings
    found_sections = []
    for heading, display in [
        (["experience", "employment", "work history"], "Experience"),
        (["education", "academics"], "Education"),
        (["skills", "technologies", "competencies"], "Skills"),
        (["summary", "profile", "objective"], "Summary"),
    ]:
        if any(h in lower_text for h in heading):
            found_sections.append(display)

    if len(found_sections) >= 3:
        sec_status = "pass"
        sec_pts = 2.5
    elif len(found_sections) == 2:
        sec_status = "warn"
        sec_pts = 1.5
    else:
        sec_status = "fail"
        sec_pts = 0.5

    checks.append(ATSCheckItem(
        id="fmt_sections",
        category="format",
        name="Standard Section Headings",
        status=sec_status,
        points=sec_pts,
        max_points=2.5,
        detail=f"Detected sections: {', '.join(found_sections) if found_sections else 'None'}.",
        fix="Use standard ATS section headings like 'Professional Experience', 'Education', 'Skills', and 'Summary'."
    ))

    # Format 5: Document Length
    if 350 <= word_count <= 950:
        len_status = "pass"
        len_pts = 2.5
        len_detail = f"Ideal length: {word_count} words (fits standard 1-2 pages)."
        len_fix = ""
    elif 250 <= word_count < 350 or 950 < word_count <= 1300:
        len_status = "warn"
        len_pts = 1.5
        len_detail = f"Word count ({word_count} words) is borderline. 1-page resumes typically need 350-600 words; 2 pages need 600-900 words."
        len_fix = "Expand on key accomplishments if too brief, or condense bullet points if too long."
    else:
        len_status = "fail"
        len_pts = 0.5
        len_detail = f"Word count ({word_count} words) is out of range."
        len_fix = "Target 350 to 900 words for optimal ATS parsing and recruiter readability."

    checks.append(ATSCheckItem(
        id="fmt_length",
        category="format",
        name="Document Length",
        status=len_status,
        points=len_pts,
        max_points=2.5,
        detail=len_detail,
        fix=len_fix
    ))

    # Format 6: Layout & column artifacts
    # Look for unusual tabs, pipe tables, or tabular alignment artifacts
    pipe_count = resume_text.count("|")
    tab_count = resume_text.count("\t")
    if pipe_count > 15 or tab_count > 25:
        checks.append(ATSCheckItem(
            id="fmt_layout",
            category="format",
            name="Single-Column Layout",
            status="warn",
            points=1.0,
            max_points=2.5,
            detail=f"Detected multiple table or column indicators ({pipe_count} vertical bars, {tab_count} tabs). Multi-column tables often scramble ATS parsing order.",
            fix="Convert multi-column tables and text boxes into a clean single-column linear layout."
        ))
    else:
        checks.append(ATSCheckItem(
            id="fmt_layout",
            category="format",
            name="Single-Column Layout",
            status="pass",
            points=2.5,
            max_points=2.5,
            detail="Clean linear text layout without problematic multi-column artifacts.",
            fix=""
        ))

    # ====================
    # 2. CONTENT QUALITY CHECKS (Total max: 10 pts)
    # ====================

    bullets = extract_bullet_points(resume_text)
    total_bullets = max(len(bullets), 1)

    # Content 1: Quantified achievements (>= 30% of bullets with numbers/metrics)
    # Exclude standalone 4-digit years like 2020
    metric_regex = re.compile(r"(?:\d+%\b|\$\d+|\b\d+\s*(?:k|m|b|gb|tb|ms|x)\b|\b\d{1,3}(?:,\d{3})+\b|\b[1-9]\d{0,2}\b(?!\d{3}))")
    quantified_bullets = 0
    for b in bullets:
        # Check if contains numbers other than just a year
        clean_b = re.sub(r"\b(19\d\d|20\d\d)\b", "", b)
        if metric_regex.search(clean_b):
            quantified_bullets += 1

    quant_pct = quantified_bullets / total_bullets if bullets else 0.0
    if quant_pct >= 0.30:
        q_status = "pass"
        q_pts = 3.0
        q_detail = f"{int(quant_pct * 100)}% of bullets ({quantified_bullets}/{total_bullets}) contain measurable numbers or metrics."
        q_fix = ""
    elif quant_pct >= 0.15:
        q_status = "warn"
        q_pts = 1.5
        q_detail = f"{int(quant_pct * 100)}% of bullets contain metrics. Aim for at least 30% to demonstrate tangible business impact."
        q_fix = "Quantify results with percentages, dollar amounts, performance speeds, or volume metrics."
    else:
        q_status = "fail"
        q_pts = 0.5
        q_detail = f"Only {int(quant_pct * 100)}% of bullets contain quantified metrics."
        q_fix = "Add specific numbers, percentage improvements, time saved, or scale to your bullet points."

    checks.append(ATSCheckItem(
        id="cnt_metrics",
        category="content",
        name="Quantified Achievements",
        status=q_status,
        points=q_pts,
        max_points=3.0,
        detail=q_detail,
        fix=q_fix
    ))

    # Content 2: Strong action verbs (>= 50% of bullets)
    action_verb_bullets = 0
    for b in bullets:
        first_word = re.sub(r"[^\w]", "", b.split()[0].lower()) if b.split() else ""
        if first_word in ACTION_VERBS:
            action_verb_bullets += 1

    action_pct = action_verb_bullets / total_bullets if bullets else 0.0
    if action_pct >= 0.50:
        av_status = "pass"
        av_pts = 3.0
        av_detail = f"{int(action_pct * 100)}% of bullets ({action_verb_bullets}/{total_bullets}) begin with strong action verbs."
        av_fix = ""
    elif action_pct >= 0.25:
        av_status = "warn"
        av_pts = 1.5
        av_detail = f"{int(action_pct * 100)}% of bullets begin with action verbs. Target at least 50%."
        av_fix = "Begin each bullet with impactful verbs (e.g., 'Architected', 'Spearheaded', 'Optimized', 'Automated')."
    else:
        av_status = "fail"
        av_pts = 0.5
        av_detail = f"Only {int(action_pct * 100)}% of bullets begin with recognizable action verbs."
        av_fix = "Replace passive descriptions with decisive action verbs at the start of every bullet."

    checks.append(ATSCheckItem(
        id="cnt_verbs",
        category="content",
        name="Strong Action Verbs",
        status=av_status,
        points=av_pts,
        max_points=3.0,
        detail=av_detail,
        fix=av_fix
    ))

    # Content 3: Weak phrases check
    found_weak = [p for p in WEAK_PHRASES if p in lower_text]
    if not found_weak:
        checks.append(ATSCheckItem(
            id="cnt_weak_phrases",
            category="content",
            name="Avoidance of Passive Language",
            status="pass",
            points=2.0,
            max_points=2.0,
            detail="No passive clichés like 'responsible for' or 'duties included' found.",
            fix=""
        ))
    else:
        checks.append(ATSCheckItem(
            id="cnt_weak_phrases",
            category="content",
            name="Avoidance of Passive Language",
            status="warn" if len(found_weak) <= 2 else "fail",
            points=1.0 if len(found_weak) <= 2 else 0.0,
            max_points=2.0,
            detail=f"Detected passive phrasing: '{', '.join(found_weak[:3])}'.",
            fix="Replace passive duty listings with direct action verbs demonstrating leadership and execution."
        ))

    # Content 4: First-person pronouns check
    pronoun_matches = FIRST_PERSON_PRONOUNS.findall(resume_text)
    if not pronoun_matches:
        checks.append(ATSCheckItem(
            id="cnt_pronouns",
            category="content",
            name="First-Person Pronoun Avoidance",
            status="pass",
            points=2.0,
            max_points=2.0,
            detail="Zero first-person pronouns (I, me, my, we) detected.",
            fix=""
        ))
    else:
        checks.append(ATSCheckItem(
            id="cnt_pronouns",
            category="content",
            name="First-Person Pronoun Avoidance",
            status="warn" if len(pronoun_matches) <= 2 else "fail",
            points=1.0 if len(pronoun_matches) <= 2 else 0.0,
            max_points=2.0,
            detail=f"Found {len(pronoun_matches)} first-person pronoun(s) (e.g. '{pronoun_matches[0]}').",
            fix="Standard professional resumes use implied first-person without explicit 'I', 'my', or 'we'."
        ))

    # ====================
    # 3. INTEGRITY CHECK (Prompt injection / ATS override)
    # ====================
    is_injected, injection_snippets = detect_prompt_injection(resume_text)
    if is_injected:
        checks.append(ATSCheckItem(
            id="int_injection",
            category="integrity",
            name="Resume Integrity & Prompt Injection",
            status="fail",
            points=0.0,
            max_points=0.0,
            detail=f"Suspicious ATS override or prompt manipulation text detected: '{injection_snippets[0]}'.",
            fix="Remove all prompt injection attempts or system instructions from the resume."
        ))
    else:
        checks.append(ATSCheckItem(
            id="int_injection",
            category="integrity",
            name="Resume Integrity & Prompt Injection",
            status="pass",
            points=0.0,
            max_points=0.0,
            detail="No prompt injection or adversarial text detected.",
            fix=""
        ))

    return checks
