"""Gemini API client, model invocation, retries, failover, and error classification."""

import time
import random
import logging
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types

from ats.models import LLMAnalysisResponse
from ats.prompts import SYSTEM_INSTRUCTION, build_analysis_prompt
from ats.validate import parse_and_validate_llm_response
from ats.registry import build_failover_chain, filter_and_rank_models, DEFAULT_APPROVED_MODELS
from ats.security import scrub_sensitive_keys

logger = logging.getLogger("ats.llm")


class LLMError(Exception):
    """Base exception for LLM operations."""
    def __init__(self, message: str, error_type: str = "other", retryable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class AuthError(LLMError):
    """Authentication or authorization failure."""
    def __init__(self, message: str):
        super().__init__(message, error_type="auth", retryable=False)


class QuotaError(LLMError):
    """Rate limit or quota exhaustion."""
    def __init__(self, message: str):
        super().__init__(message, error_type="quota", retryable=False)


class ModelNotFoundError(LLMError):
    """Requested model not found."""
    def __init__(self, message: str):
        super().__init__(message, error_type="not_found", retryable=False)


class TransientError(LLMError):
    """Temporary network or server failure."""
    def __init__(self, message: str):
        super().__init__(message, error_type="transient", retryable=True)


class SchemaParseError(LLMError):
    """Model returned malformed or non-conforming JSON."""
    def __init__(self, message: str):
        super().__init__(message, error_type="schema", retryable=True)


def classify_error(err: Exception, custom_key: Optional[str] = None) -> LLMError:
    """Classifies raw API exceptions into standard categories."""
    raw_str = scrub_sensitive_keys(str(err), custom_key)
    lower = raw_str.lower()

    if any(k in lower for k in ["401", "403", "api_key_invalid", "permission_denied", "unauthenticated", "invalid api key"]):
        return AuthError(f"Authentication failed: Invalid or unauthorized Gemini API key. {raw_str}")

    if any(k in lower for k in ["429", "resource_exhausted", "quota", "rate limit"]):
        return QuotaError(f"Quota or rate limit reached for this model. {raw_str}")

    if any(k in lower for k in ["404", "not_found", "model not found"]):
        return ModelNotFoundError(f"Model not found or unavailable for your API key. {raw_str}")

    if any(k in lower for k in ["500", "502", "503", "504", "deadline", "timeout", "timed out", "connection", "reset"]):
        return TransientError(f"Temporary Gemini server or network issue. {raw_str}")

    if any(k in lower for k in ["json", "schema", "validation", "pydantic"]):
        return SchemaParseError(f"Schema output parsing failure: {raw_str}")

    return LLMError(f"Gemini API request failed: {raw_str}", error_type="other", retryable=False)


def fetch_available_models(api_key: str) -> List[str]:
    """Queries live Gemini models API and returns filtered, ranked model IDs.

    Uses a per-request client instance.
    """
    try:
        client = genai.Client(api_key=api_key)
        raw_list = client.models.list()
        model_names = [m.name for m in raw_list]
        filtered = filter_and_rank_models(model_names)
        if filtered:
            return filtered
    except Exception as e:
        err = classify_error(e, api_key)
        if isinstance(err, AuthError):
            raise err
        logger.warning(f"Could not list live models ({err}); falling back to approved defaults.")

    return DEFAULT_APPROVED_MODELS


def invoke_gemini_single_attempt(
    client: genai.Client,
    model_id: str,
    prompt: str,
    use_thinking: bool = True
) -> str:
    """Executes a single generate_content call with Gemini."""
    clean_model = model_id.replace("models/", "")

    # For Gemini 2.x use temperature 0.0, for Gemini 3.x leave temperature default (None)
    is_gemini_2 = clean_model.startswith("gemini-2")
    temp = 0.0 if is_gemini_2 else None

    # Thinking configuration: calibrated for deep technical inference
    thinking_cfg = None
    if use_thinking and not is_gemini_2:
        try:
            if hasattr(types, "ThinkingConfig"):
                # Use balanced reasoning budget for Gemini 3.x
                thinking_cfg = types.ThinkingConfig(thinking_budget=1024)
        except Exception:
            thinking_cfg = None

    config_kwargs: Dict[str, Any] = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "response_mime_type": "application/json",
        "response_schema": LLMAnalysisResponse,
        "max_output_tokens": 12000,
        "seed": 42,
    }
    if temp is not None:
        config_kwargs["temperature"] = temp
    if thinking_cfg is not None:
        config_kwargs["thinking_config"] = thinking_cfg

    config = types.GenerateContentConfig(**config_kwargs)

    response = client.models.generate_content(
        model=clean_model,
        contents=prompt,
        config=config,
    )

    if not response or not response.text:
        raise ValueError("Model returned an empty text response.")

    return response.text


def analyze_with_failover(
    api_key: str,
    selected_model: str,
    job_description: str,
    resume_text: str,
    available_models: Optional[List[str]] = None,
    progress_callback: Optional[Any] = None
) -> Tuple[LLMAnalysisResponse, str, bool]:
    """Coordinates Gemini execution across failover chain with exponential backoff.

    Returns:
      (LLMAnalysisResponse, working_model_id, failover_occurred)
    """
    models_pool = available_models or DEFAULT_APPROVED_MODELS
    failover_chain = build_failover_chain(selected_model, models_pool, max_attempts=3)

    client = genai.Client(api_key=api_key)
    prompt = build_analysis_prompt(job_description, resume_text)

    last_error: Optional[Exception] = None

    for model_idx, current_model in enumerate(failover_chain):
        is_failover = (model_idx > 0)
        if progress_callback:
            progress_callback(f"Attempting analysis with model: `{current_model}`...")

        # Up to 2 retries on transient errors for the same model
        max_model_retries = 2
        for retry in range(max_model_retries + 1):
            use_thinking = (retry == 0)  # On second retry, disable thinking in case model rejected it

            try:
                raw_response = invoke_gemini_single_attempt(
                    client=client,
                    model_id=current_model,
                    prompt=prompt,
                    use_thinking=use_thinking
                )

                # Parse and validate structured output
                parsed_response = parse_and_validate_llm_response(raw_response)

                if progress_callback:
                    progress_callback(f"Analysis successful with `{current_model}`.")

                return parsed_response, current_model, is_failover

            except Exception as e:
                classified = classify_error(e, api_key)
                last_error = classified

                # If Authentication error, stop immediately without attempting failover
                if isinstance(classified, AuthError):
                    logger.error(f"Authentication failure: {classified}")
                    raise classified

                # If Quota or ModelNotFound, break retry loop to jump to next model immediately
                if isinstance(classified, (QuotaError, ModelNotFoundError)):
                    logger.warning(f"Model {current_model} unavailable ({classified.error_type}). Failing over...")
                    break

                # If Transient or Schema error, retry same model with exponential backoff + jitter
                if retry < max_model_retries and classified.retryable:
                    backoff = (2 ** retry) * 1.5 + random.uniform(0.1, 0.5)
                    logger.info(f"Retrying {current_model} after {backoff:.2f}s due to {classified.error_type}...")
                    time.sleep(backoff)
                    continue
                else:
                    break

    # If all models in failover chain exhausted
    msg = f"All models in failover chain failed. Last error: {scrub_sensitive_keys(str(last_error), api_key)}"
    raise LLMError(msg, error_type="exhausted")
