"""Tests for model filtering, version requirements, ranking, and failover chain."""

import pytest
from ats.registry import (
    parse_model_id, filter_and_rank_models, build_failover_chain,
    MIN_VERSION
)


def test_current_models_pass_filter():
    """Valid current Gemini text models should parse and pass."""
    valid_ids = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-pro-preview",
        "gemini-3.1-pro",
    ]
    for mid in valid_ids:
        meta = parse_model_id(mid)
        assert meta is not None, f"Expected {mid} to be valid"
        assert meta.id == mid.lower()


def test_future_models_auto_included():
    """Future versions >= 3.5 should automatically be allowed without code changes."""
    assert parse_model_id("gemini-3.9-flash") is not None
    assert parse_model_id("gemini-4.0-flash") is not None
    assert parse_model_id("gemini-4.0-pro") is not None


def test_legacy_2x_excluded():
    """Legacy 2.x and earlier models must be rejected."""
    legacy_ids = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
    ]
    for mid in legacy_ids:
        assert parse_model_id(mid) is None, f"Legacy model {mid} should be excluded"


def test_deprecated_31_flash_lite_excluded():
    """gemini-3.1-flash-lite is explicitly deprecated and must be excluded."""
    assert parse_model_id("gemini-3.1-flash-lite") is None
    assert parse_model_id("gemini-3.1-flash-lite-preview") is None


def test_specialized_and_embedding_excluded():
    """Non-text, embedding, TTS, Live, and -latest alias models must be excluded."""
    excluded = [
        "text-embedding-004",
        "gemini-3.5-flash-live",
        "gemini-3.5-flash-tts",
        "gemini-3.5-flash-image",
        "nano-banana-001",
        "gemini-flash-latest",
        "gemini-pro-vision",
    ]
    for mid in excluded:
        assert parse_model_id(mid) is None, f"{mid} should be excluded"


def test_ranking_order():
    """Ranking order must put GA before Preview, newest first, and Flash > Flash-Lite > Pro."""
    raw_list = [
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash",
    ]
    ranked = filter_and_rank_models(raw_list)

    # All GA models should come before Preview
    assert ranked.index("gemini-3.8-flash") < ranked.index("gemini-3.1-pro-preview")
    # 3.8 before 3.7
    assert ranked.index("gemini-3.8-flash") < ranked.index("gemini-3.7-flash")
    # 3.7 before 3.5
    assert ranked.index("gemini-3.7-flash") < ranked.index("gemini-3.5-flash")


def test_failover_chain_capped_at_three():
    """Failover chain must start with selected model, max 3, no legacy models."""
    available = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.0-flash",  # legacy, should be dropped
    ]
    chain = build_failover_chain("gemini-3.7-flash", available, max_attempts=3)
    assert len(chain) == 3
    assert chain[0] == "gemini-3.7-flash"
    assert "gemini-2.0-flash" not in chain
