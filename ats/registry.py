"""Gemini model registry, version filtering, ranking, and failover management.

Source of Truth: https://ai.google.dev/gemini-api/docs/deprecations (as of 2026-10-09).
Only current Gemini text generation models are permitted.
Legacy 2.x, deprecated models, image/audio/multimodal-specialized, and embedding models are excluded.
"""

import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

# Centralized minimum supported version definition.
# Future versions (e.g. 3.9, 4.0) will automatically pass without code modifications.
MIN_VERSION: Dict[str, Tuple[int, int]] = {
    "flash": (3, 5),
    "flash-lite": (3, 5),
    "pro": (3, 1),
}

# Explicitly excluded or deprecated model identifiers
EXCLUDED_MODEL_IDS = {
    "gemini-3.1-flash-lite",  # Deprecated
    "gemini-3.1-flash-lite-preview",
}

# Blocked keyword substrings in model names
EXCLUDED_SUBSTRINGS = [
    "tts", "live", "image", "imagen", "nano-banana", "embedding", "embed",
    "omni", "robotics", "transcribe", "computer-use", "-latest", "realtime",
    "audio", "video", "vision", "chat-bison", "text-bison", "code-bison"
]

# Canonical descriptions for friendly UI display
MODEL_DESCRIPTIONS: Dict[str, str] = {
    "gemini-3.8-flash": "Balanced speed & accuracy (recommended)",
    "gemini-3.7-flash": "High-throughput text processing",
    "gemini-3.6-flash": "Fast structured extraction",
    "gemini-3.5-flash": "Established baseline text generation",
    "gemini-3.5-flash-lite": "Ultra-lightweight low-latency extraction",
    "gemini-3.1-pro-preview": "Deep reasoning & complex evaluation (preview)",
    "gemini-3.1-pro": "Deep reasoning & complex evaluation",
}

# Safe offline baseline if API listing is unavailable or before API key validation
DEFAULT_APPROVED_MODELS: List[str] = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
]


@dataclass
class ModelMetadata:
    id: str
    major: int
    minor: int
    tier: str  # 'flash', 'flash-lite', 'pro'
    is_preview: bool
    label: str
    description: str


# Regex matching allowed text models:
# e.g. gemini-3.8-flash, gemini-3.5-flash-lite, gemini-3.1-pro-preview, gemini-4.0-flash
MODEL_REGEX = re.compile(
    r"^gemini-(\d+)(?:\.(\d+))?-(flash-lite|flash|pro)(?:-(preview))?$",
    re.IGNORECASE
)


def parse_model_id(raw_id: str) -> Optional[ModelMetadata]:
    """Parses and validates a model ID against current Gemini text model rules."""
    clean_id = raw_id.strip()
    if clean_id.startswith("models/"):
        clean_id = clean_id[len("models/"):]
    lower_id = clean_id.lower()

    # Exclude blocked substrings
    if any(sub in lower_id for sub in EXCLUDED_SUBSTRINGS):
        return None

    # Exclude explicit deprecations
    if lower_id in EXCLUDED_MODEL_IDS:
        return None

    match = MODEL_REGEX.match(lower_id)
    if not match:
        return None

    major_str, minor_str, tier, preview_str = match.groups()
    major = int(major_str)
    minor = int(minor_str) if minor_str is not None else 0
    is_preview = bool(preview_str)

    # Exclude legacy 2.x and earlier
    if major < 3:
        return None

    # Check minimum version requirement for tier
    min_ver = MIN_VERSION.get(tier)
    if not min_ver:
        return None

    min_major, min_minor = min_ver
    if (major, minor) < (min_major, min_minor):
        return None

    tier_title = "Flash-Lite" if tier == "flash-lite" else ("Flash" if tier == "flash" else "Pro")
    version_str = f"{major}.{minor}" if minor != 0 or minor_str is not None else f"{major}"
    preview_tag = " (Preview)" if is_preview else ""
    desc = MODEL_DESCRIPTIONS.get(lower_id, "Gemini generation model")

    label = f"Gemini {version_str} {tier_title}{preview_tag} — {desc}"

    return ModelMetadata(
        id=lower_id,
        major=major,
        minor=minor,
        tier=tier,
        is_preview=is_preview,
        label=label,
        description=desc,
    )


def rank_models(models: List[ModelMetadata]) -> List[ModelMetadata]:
    """Ranks models: GA before preview, newest version first, Flash > Flash-Lite > Pro."""
    tier_priority = {"flash": 0, "flash-lite": 1, "pro": 2}

    def sort_key(m: ModelMetadata):
        # 1. GA (False = 0) before Preview (True = 1)
        # 2. Version descending (-major, -minor)
        # 3. Tier priority
        return (
            1 if m.is_preview else 0,
            -m.major,
            -m.minor,
            tier_priority.get(m.tier, 99),
            m.id,
        )

    return sorted(models, key=sort_key)


def filter_and_rank_models(model_names: List[str]) -> List[str]:
    """Filters raw model list to only valid current Gemini text models, ranked."""
    parsed: List[ModelMetadata] = []
    seen = set()

    for name in model_names:
        meta = parse_model_id(name)
        if meta and meta.id not in seen:
            seen.add(meta.id)
            parsed.append(meta)

    ranked = rank_models(parsed)
    return [m.id for m in ranked]


def get_model_label(model_id: str) -> str:
    """Returns a friendly UI label for a given model ID."""
    meta = parse_model_id(model_id)
    if meta:
        return meta.label
    return model_id


def build_failover_chain(selected_model: str, available_models: List[str], max_attempts: int = 3) -> List[str]:
    """Builds a failover chain: selected model, followed by the next best current models.

    Max 3 attempts, GA before preview, never legacy models.
    """
    cleaned_selected = selected_model.replace("models/", "").lower()
    valid_available = filter_and_rank_models(available_models)

    chain = []
    if cleaned_selected in valid_available:
        chain.append(cleaned_selected)
    elif parse_model_id(cleaned_selected):
        chain.append(cleaned_selected)

    for m in valid_available:
        if m not in chain:
            chain.append(m)
        if len(chain) >= max_attempts:
            break

    # If chain is still empty, fall back to approved defaults
    if not chain:
        for m in DEFAULT_APPROVED_MODELS[:max_attempts]:
            if m not in chain:
                chain.append(m)

    return chain[:max_attempts]
