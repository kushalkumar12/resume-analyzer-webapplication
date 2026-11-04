"""Unit tests for LLM error classification, mock failover, and JSON normalization."""

import json
from unittest.mock import MagicMock, patch
import pytest

from ats.llm import (
    classify_error, AuthError, QuotaError, ModelNotFoundError, TransientError,
    analyze_with_failover
)
from ats.validate import parse_and_validate_llm_response, normalize_llm_dict


def test_classify_error_types():
    """Validates error categorization into Auth, Quota, NotFound, Transient."""
    assert isinstance(classify_error(Exception("401 Unauthorized: API_KEY_INVALID")), AuthError)
    assert isinstance(classify_error(Exception("403 Forbidden: PERMISSION_DENIED")), AuthError)
    assert isinstance(classify_error(Exception("429 Resource exhausted: Quota exceeded")), QuotaError)
    assert isinstance(classify_error(Exception("404 Model not found")), ModelNotFoundError)
    assert isinstance(classify_error(Exception("503 Service Unavailable")), TransientError)
    assert isinstance(classify_error(Exception("Deadline exceeded")), TransientError)


def test_normalize_llm_dict_clamps_and_deduplicates():
    """Validates defensive normalization of raw LLM dictionary."""
    raw_data = {
        "job_title": "<script>Senior Engineer</script>",
        "seniority": "Senior",
        "requirements": [
            {
                "term": "Python",
                "importance": "must",
                "status": "explicit",
                "evidence": "Built Python apps"
            },
            {
                "term": "python",  # Duplicate term
                "importance": "must",
                "status": "explicit",
                "evidence": "Python coding"
            },
            {
                "term": "Kafka",
                "importance": "must",
                "status": "explicit",
                "evidence": ""  # Empty evidence should force missing status
            }
        ],
        "experience": {
            "required_years": 99.0,  # Should clamp to 30.0
            "candidate_years_estimate": -5.0,  # Should clamp to 0.0
            "title_alignment": 5  # Should clamp to 2
        }
    }
    normalized = normalize_llm_dict(raw_data)

    # HTML tags stripped
    assert "<script>" not in normalized["job_title"]
    assert "Senior Engineer" in normalized["job_title"]

    # Term deduplication: only 1 Python
    reqs = normalized["requirements"]
    terms = [r["term"].lower() for r in reqs]
    assert terms.count("python") == 1

    # Empty evidence forced to missing
    kafka_req = next(r for r in reqs if r["term"] == "Kafka")
    assert kafka_req["status"] == "missing"

    # Clamping
    assert normalized["experience"]["required_years"] == 30.0
    assert normalized["experience"]["candidate_years_estimate"] == 0.0
    assert normalized["experience"]["title_alignment"] == 2


@patch("ats.llm.genai.Client")
def test_mock_failover_on_quota_error(mock_client_class):
    """When the first model hits a Quota error, it fails over to the next model."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    sample_json = json.dumps({
        "job_title": "Cloud Architect",
        "seniority": "Senior",
        "requirements": [
            {"term": "Python", "importance": "must", "status": "explicit", "evidence": "Python services"}
        ],
        "knockouts": [],
        "experience": {"required_years": 5.0, "candidate_years_estimate": 6.0, "title_alignment": 2},
        "education_status": "met",
        "strengths": ["Strong Python"],
        "gaps": [],
        "summary": "Good match",
        "rewrites": []
    })

    # First call raises 429 Quota, second call succeeds
    mock_resp_fail = MagicMock()
    mock_resp_success = MagicMock()
    mock_resp_success.text = sample_json

    mock_client.models.generate_content.side_effect = [
        Exception("429 ResourceExhausted: rate limit exceeded"),
        mock_resp_success
    ]

    resp, working_model, failover = analyze_with_failover(
        api_key="AIzaSyD_TEST_KEY_12345678901234567",
        selected_model="gemini-3.8-flash",
        job_description="Need Python engineer",
        resume_text="Python services",
        available_models=["gemini-3.8-flash", "gemini-3.7-flash"]
    )

    assert working_model == "gemini-3.7-flash"
    assert failover is True
    assert resp.job_title == "Cloud Architect"


@patch("ats.llm.genai.Client")
def test_auth_error_halts_immediately(mock_client_class):
    """Auth error must stop execution immediately without trying remaining failover models."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_client.models.generate_content.side_effect = Exception("401 Unauthorized: API_KEY_INVALID")

    with pytest.raises(AuthError):
        analyze_with_failover(
            api_key="AIzaSyD_INVALID_KEY_12345678901234",
            selected_model="gemini-3.8-flash",
            job_description="Need engineer",
            resume_text="Resume text",
            available_models=["gemini-3.8-flash", "gemini-3.7-flash"]
        )

    # Should have called only once before stopping
    assert mock_client.models.generate_content.call_count == 1
