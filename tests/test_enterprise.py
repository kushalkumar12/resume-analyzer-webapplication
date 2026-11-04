"""Tests for enterprise recruiter boolean queries, tenure stability, and Google X-Y-Z analysis."""

import pytest
from ats.models import RequirementItem, VerifiedRequirement
from ats.enterprise import (
    build_recruiter_boolean_queries, analyze_tenure_and_stability, evaluate_xyz_formula
)


def test_recruiter_boolean_query_generation():
    """Recruiter boolean query should structure must-have terms and detect presence."""
    verified = [
        VerifiedRequirement(
            term="Python",
            category="hard_skill",
            importance="must",
            synonyms=["py"],
            raw_status="explicit",
            verified_status="found",
            demonstrated_in_experience=True,
            evidence="Built Python microservices",
            evidence_verified=True,
            credit_ratio=1.0,
            points_earned=10.0,
            max_points=10.0,
            explanation="Direct match"
        ),
        VerifiedRequirement(
            term="Kubernetes",
            category="tool",
            importance="must",
            synonyms=["k8s"],
            raw_status="missing",
            verified_status="missing",
            demonstrated_in_experience=False,
            evidence="",
            evidence_verified=False,
            credit_ratio=0.0,
            points_earned=0.0,
            max_points=10.0,
            explanation="Missing"
        )
    ]
    resume = "Candidate with 5 years experience building Python microservices."
    queries = build_recruiter_boolean_queries("Senior Software Engineer", verified, resume)

    assert len(queries) >= 1
    tier1_query = queries[0]
    assert "Python" in tier1_query.matched_terms
    assert "Kubernetes" in tier1_query.missing_terms
    assert tier1_query.matched is False  # Because Kubernetes is missing


def test_tenure_stability_detection():
    """Detects short tenure and flags job-hopping risk when average tenure is low."""
    hopping_resume = """
    EXPERIENCE
    Engineer - Company A
    Jan 2021 - Jun 2021
    Engineer - Company B
    Jul 2021 - Dec 2021
    Engineer - Company C
    Jan 2022 - Jun 2022
    """
    res = analyze_tenure_and_stability(hopping_resume)
    assert res.job_count >= 3
    assert res.job_hopping_risk is True
    assert res.stability_band == "High Mobility"


def test_google_xyz_formula_evaluation():
    """Detects action verb + metric + method pattern."""
    bullets = [
        "Architected distributed streaming service handling 50k QPS by leveraging Kafka and Go.",
        "Responsible for bug fixing."
    ]
    res = evaluate_xyz_formula(bullets)
    assert res.total_bullets == 2
    assert res.xyz_compliant_bullets == 1
    assert "qps" in res.scale_indicators_found
