"""Streamlit AppTest automated tests."""

from unittest.mock import patch, MagicMock
import pytest
from streamlit.testing.v1 import AppTest

from ats.models import (
    FullAnalysisResult, ScoreResult, ScoreAreaBreakdown,
    VerifiedRequirement, ATSCheckItem
)


@pytest.fixture
def mock_analysis_result():
    """Provides a synthetic analysis result for UI rendering tests."""
    score_res = ScoreResult(
        total_score=85.5,
        band="Strong",
        knockout_capped=False,
        injection_capped=False,
        candidate_years_used=5.0,
        required_years=4.0,
        breakdown={
            "must_skills": ScoreAreaBreakdown(area="Must-Have Skills", earned=36.0, maximum=40.0, percentage=90.0, description=""),
            "nice_skills": ScoreAreaBreakdown(area="Nice-to-Have Skills", earned=8.0, maximum=10.0, percentage=80.0, description=""),
            "experience": ScoreAreaBreakdown(area="Experience Fit", earned=18.0, maximum=20.0, percentage=90.0, description=""),
            "education": ScoreAreaBreakdown(area="Education", earned=5.0, maximum=5.0, percentage=100.0, description=""),
            "ats_format": ScoreAreaBreakdown(area="ATS Format", earned=13.5, maximum=15.0, percentage=90.0, description=""),
            "content_quality": ScoreAreaBreakdown(area="Content Impact", earned=8.0, maximum=10.0, percentage=80.0, description="")
        }
    )

    req = VerifiedRequirement(
        term="Python",
        category="hard_skill",
        importance="must",
        synonyms=[],
        raw_status="explicit",
        verified_status="found",
        demonstrated_in_experience=True,
        evidence="Built Python apps",
        evidence_verified=True,
        credit_ratio=1.0,
        points_earned=10.0,
        max_points=10.0,
        explanation="Verified in resume"
    )

    check = ATSCheckItem(
        id="fmt_readable",
        category="format",
        name="Machine-Readable Text",
        status="pass",
        points=3.0,
        max_points=3.0,
        detail="Valid text",
        fix=""
    )

    return FullAnalysisResult(
        job_title="Senior Backend Engineer",
        seniority="Senior",
        score=score_res,
        verified_requirements=[req],
        knockouts=[],
        ats_checks=[check],
        strengths=["Strong Python"],
        gaps=["Docker"],
        summary="Candidate matches well.",
        rewrites=[],
        top_fixes=[],
        model_used="gemini-3.8-flash",
        failover_occurred=False,
        pii_masked=True
    )


def test_app_loads_without_exceptions():
    """Verifies that app.py loads cleanly and presents inputs without unhandled exceptions."""
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception
    # Title is present
    assert any("ATS Resume Analyzer" in title.value for title in at.title)


def test_app_submission_without_key_triggers_error():
    """Attempting submission without an API key produces an error message."""
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    # Clear any env key in sidebar input
    if at.sidebar.text_input:
        at.sidebar.text_input[0].set_value("").run()

    # Find and click the form submit button
    submit_btn = next(b for b in at.button if "Run Comprehensive" in b.label)
    submit_btn.click().run()

    assert not at.exception
    # An error indicating missing API key should be displayed
    assert len(at.error) > 0
    assert any("API Key Error" in err.value for err in at.error)


@patch("ats.analysis.run_full_ats_analysis")
def test_full_analysis_workflow_renders_results(mock_run_analysis, mock_analysis_result):
    """Verifies that when analysis succeeds, results and tabs render cleanly."""
    mock_run_analysis.return_value = mock_analysis_result

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    # In session_state, set analysis_result directly to verify rendering of results and tabs
    at.session_state["analysis_result"] = mock_analysis_result
    at.run()

    assert not at.exception
    # Executive alignment summary should appear in info boxes
    assert any("Candidate matches well" in str(getattr(info, "value", "")) for info in at.info)
    # Target role caption
    assert any("Senior Backend Engineer" in str(getattr(cap, "value", "")) for cap in at.caption)
