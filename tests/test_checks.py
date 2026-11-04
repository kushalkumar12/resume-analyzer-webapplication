"""Tests for ATS format, content checks, and experience years calculation."""

import pytest
from ats.checks import (
    run_deterministic_checks, calculate_experience_years_from_text,
    extract_bullet_points
)
from ats.samples import SAMPLE_RESUME


def test_sample_resume_deterministic_checks():
    """Verify that a well-formatted professional resume passes standard checks."""
    checks = run_deterministic_checks(SAMPLE_RESUME)
    check_dict = {c.id: c for c in checks}

    # Should pass machine-readable text
    assert check_dict["fmt_readable"].status == "pass"

    # Should pass glyphs check
    assert check_dict["fmt_glyphs"].status == "pass"

    # Should pass contact info (has email, phone, links)
    assert check_dict["fmt_contact"].status == "pass"

    # Should pass sections (Experience, Education, Skills, Summary)
    assert check_dict["fmt_sections"].status == "pass"

    # Should pass metrics check (has numbers, percentages, etc.)
    assert check_dict["cnt_metrics"].status == "pass"

    # Should pass action verbs check (Architected, Built, Automated, etc.)
    assert check_dict["cnt_verbs"].status == "pass"

    # No prompt injection
    assert check_dict["int_injection"].status == "pass"


def test_scanned_or_short_resume_fails():
    """Verify that very short or empty extracted text triggers a format failure."""
    short_text = "Page 1 scan\nImage file"
    checks = run_deterministic_checks(short_text)
    readable_check = next(c for c in checks if c.id == "fmt_readable")
    assert readable_check.status == "fail"


def test_first_person_pronouns_detected():
    """Verify that excessive first-person pronouns trigger a warning or fail."""
    pronoun_resume = """
    Jane Doe | engineer@example.com | (555) 123-4567 | linkedin.com/in/jane
    Summary: I am an engineer. In my previous role, I led our team. We delivered my project.
    Experience:
    - I managed our database and I solved critical bugs for my team.
    """
    checks = run_deterministic_checks(pronoun_resume)
    pronoun_check = next(c for c in checks if c.id == "cnt_pronouns")
    assert pronoun_check.status in ["warn", "fail"]


def test_experience_years_calculation_merges_dates():
    """Verify date ranges parsing and merging overlapping employment periods."""
    resume_with_dates = """
    EXPERIENCE
    Senior Software Engineer | Acme Corp
    Jan 2021 - Present
    - Built microservices in Python.

    Software Engineer | Beta Corp
    June 2019 - Dec 2020
    - Backend API engineering.

    Junior Developer | Startup Inc
    Jan 2018 - May 2019
    - Web development.

    EDUCATION
    Bachelor of Science in Computer Science
    University of California | 2014 - 2018
    """
    years = calculate_experience_years_from_text(resume_with_dates)
    # Work experience from 2018 to Present is ~7-8+ years (education 2014-2018 ignored)
    assert years >= 6.0
    assert years <= 10.0


def test_experience_years_with_overlaps():
    """Overlapping jobs shouldn't double-count tenure."""
    overlapping_resume = """
    EXPERIENCE
    Job A: 2020 - 2022
    Job B (part time): 2020 - 2021
    Job C: 2022 - 2024
    """
    years = calculate_experience_years_from_text(overlapping_resume)
    # 2020 to 2024 is ~4-5 years, not 2+1+2=5+
    assert 3.5 <= years <= 5.5
