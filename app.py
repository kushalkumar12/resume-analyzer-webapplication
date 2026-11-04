"""Streamlit ATS Resume Analyzer — Production Application.
Designed with Google Enterprise Material Design 3 standards.
"""

import os
import io
import json
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

import streamlit as st
import pandas as pd

from ats.models import FullAnalysisResult
from ats.security import (
    validate_api_key_format, scrub_sensitive_keys, escape_literal_text,
    validate_uploaded_file, SessionRateLimiter
)
from ats.extract import extract_document
from ats.registry import get_model_label, DEFAULT_APPROVED_MODELS
from ats.llm import fetch_available_models
from ats.analysis import run_full_ats_analysis
from ats.samples import SAMPLE_JOB_DESCRIPTION, SAMPLE_RESUME
from ats.viz import (
    make_score_gauge, make_radar_breakdown, make_points_stacked_bar,
    make_coverage_donut, make_requirements_credit_chart,
    make_ats_checks_status_chart, make_experience_bullet_chart
)
from ats.contacts import generate_recruiter_search_queries


load_dotenv()
logger = logging.getLogger("ats.app")

# Page configuration
st.set_page_config(
    page_title="ATS Resume Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Persistent Session State Management (Prevents data flushing across reruns)
if "rate_limiter" not in st.session_state:
    st.session_state["rate_limiter"] = SessionRateLimiter()

if "cached_models" not in st.session_state:
    st.session_state["cached_models"] = None

if "last_validated_key" not in st.session_state:
    st.session_state["last_validated_key"] = ""

if "analysis_result" not in st.session_state:
    st.session_state["analysis_result"] = None

if "api_key" not in st.session_state:
    st.session_state["api_key"] = os.getenv("GOOGLE_API_KEY", "")

if "jd_text" not in st.session_state:
    st.session_state["jd_text"] = ""

if "resume_text" not in st.session_state:
    st.session_state["resume_text"] = ""

if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "Light"

if "text_size" not in st.session_state:
    st.session_state["text_size"] = "Compact"


def inject_google_design_css(theme: str, text_size: str, high_contrast: bool):
    """Injects Google Material Design 3 tokens, restrained typography, and compact layout."""
    scale_multipliers = {
        "Compact": ("12px", "13.5px"),
        "Normal": ("13.5px", "15px"),
        "Large": ("15px", "16.5px"),
    }
    min_root, max_root = scale_multipliers.get(text_size, ("12px", "13.5px"))

    if theme == "Dark":
        bg_page = "#202124"
        bg_surface = "#292A2D"
        bg_sidebar = "#1E1F20"
        border_col = "#3C4043"
        text_primary = "#E8EAED"
        text_secondary = "#9AA0A6"
        brand_primary = "#8AB4F8"
        brand_hover = "#AECBFA"
        btn_primary_bg = "#8AB4F8"
        btn_primary_text = "#202124"
        input_bg = "#292A2D"
        card_bg = "#292A2D"
        menu_hover_bg = "#3C4043"
        menu_selected_bg = "#1E3048"
        alert_info_bg = "#1A2733"
        alert_info_border = "#8AB4F8"
        alert_info_text = "#8AB4F8"
        alert_success_bg = "#132D1B"
        alert_success_border = "#81C995"
        alert_success_text = "#81C995"
        alert_warn_bg = "#332B00"
        alert_warn_border = "#FDD663"
        alert_warn_text = "#FDD663"
        alert_err_bg = "#3C1717"
        alert_err_border = "#F28B82"
        alert_err_text = "#F28B82"
    else:
        bg_page = "#F8F9FA"
        bg_surface = "#FFFFFF"
        bg_sidebar = "#F1F3F4"
        border_col = "#DADCE0"
        text_primary = "#202124"
        text_secondary = "#5F6368"
        brand_primary = "#1A73E8"
        brand_hover = "#174EA6"
        btn_primary_bg = "#1A73E8"
        btn_primary_text = "#FFFFFF"
        input_bg = "#FFFFFF"
        card_bg = "#FFFFFF"
        menu_hover_bg = "#F1F3F4"
        menu_selected_bg = "#E8F0FE"
        alert_info_bg = "#E8F0FE"
        alert_info_border = "#1A73E8"
        alert_info_text = "#1967D2"
        alert_success_bg = "#E6F4EA"
        alert_success_border = "#1E8E3E"
        alert_success_text = "#137333"
        alert_warn_bg = "#FEF7E0"
        alert_warn_border = "#F9AB00"
        alert_warn_text = "#B06000"
        alert_err_bg = "#FCE8E6"
        alert_err_border = "#D93025"
        alert_err_text = "#C5221F"

    contrast_rules = ""
    if high_contrast:
        contrast_rules = """
        body, .stApp {
            background-color: #000000 !important;
            color: #FFFFFF !important;
        }
        p, span, label, h1, h2, h3, h4, h5, h6, .stMarkdown, .stText {
            color: #FFFFFF !important;
        }
        div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
            border-color: #FFFFFF !important;
            color: #FFFFFF !important;
        }
        """

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@400;500&display=swap');

    :root {{
        --font-primary: 'Google Sans', 'Roboto', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
        --font-mono: 'Roboto Mono', Consolas, 'SF Mono', Menlo, monospace;
        --font-root-min: {min_root};
        --font-root-max: {max_root};
        --bg-page: {bg_page};
        --bg-surface: {bg_surface};
        --bg-sidebar: {bg_sidebar};
        --border-color: {border_col};
        --text-primary: {text_primary};
        --text-secondary: {text_secondary};
        --primary: {brand_primary};
        --primary-hover: {brand_hover};
        --btn-primary-bg: {btn_primary_bg};
        --btn-primary-text: {btn_primary_text};
        --input-bg: {input_bg};
        --card-bg: {card_bg};
        --menu-hover-bg: {menu_hover_bg};
        --menu-selected-bg: {menu_selected_bg};
    }}

    /* Global Foundation */
    html, body, [class*="css"], .stApp {{
        font-family: var(--font-primary) !important;
        font-size: clamp(var(--font-root-min), 0.75vw + 9.5px, var(--font-root-max)) !important;
        line-height: 1.45;
        background-color: var(--bg-page) !important;
        color: var(--text-primary) !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
    }}

    /* Controlled, Professional Header Scale */
    h1, .stApp h1 {{
        font-family: var(--font-primary) !important;
        font-size: 1.25rem !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.3 !important;
        color: var(--text-primary) !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }}

    h2, .stApp h2 {{
        font-family: var(--font-primary) !important;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        letter-spacing: 0 !important;
        line-height: 1.35 !important;
        color: var(--text-primary) !important;
        margin-top: 0.75rem !important;
        margin-bottom: 0.25rem !important;
    }}

    h3, .stApp h3 {{
        font-family: var(--font-primary) !important;
        font-size: 0.92rem !important;
        font-weight: 500 !important;
        letter-spacing: 0 !important;
        line-height: 1.35 !important;
        color: var(--text-primary) !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.2rem !important;
    }}

    h4, h5, h6 {{
        font-family: var(--font-primary) !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
        margin-top: 0.35rem !important;
        margin-bottom: 0.2rem !important;
    }}

    p, span, label, div {{
        font-family: var(--font-primary);
        color: var(--text-primary);
    }}

    p {{
        font-size: 0.84rem !important;
        line-height: 1.45 !important;
        margin-bottom: 0.4rem !important;
    }}

    small, .stCaption {{
        font-size: 0.75rem !important;
        color: var(--text-secondary) !important;
    }}

    code, pre, kbd, samp {{
        font-family: var(--font-mono) !important;
        font-size: 0.82em !important;
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
    }}

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-color) !important;
    }}

    /* Form Controls & Inputs */
    input, textarea, div[data-baseweb="input"], div[data-baseweb="textarea"] {{
        font-family: var(--font-primary) !important;
        font-size: 0.84rem !important;
        background-color: var(--input-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
    }}

    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 1px var(--primary) !important;
    }}

    /* Selectbox Container (Closed State) */
    div[data-baseweb="select"] {{
        background-color: var(--input-bg) !important;
        border-radius: 4px !important;
    }}

    div[data-baseweb="select"] > div {{
        background-color: var(--input-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
        font-size: 0.84rem !important;
        font-family: var(--font-primary) !important;
    }}

    div[data-baseweb="select"] > div:hover {{
        border-color: var(--primary) !important;
    }}

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] p {{
        color: var(--text-primary) !important;
        font-family: var(--font-primary) !important;
    }}

    div[data-baseweb="select"] svg {{
        fill: var(--text-secondary) !important;
    }}

    /* BaseWeb Dropdown Popover and Menu (Open State - Fixes Black-on-Black) */
    div[data-baseweb="popover"] {{
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 16px rgba(60, 64, 67, 0.2) !important;
        z-index: 999999 !important;
    }}

    div[data-baseweb="popover"] > div,
    div[data-baseweb="popover"] div[role="listbox"],
    div[data-baseweb="popover"] ul[data-baseweb="menu"],
    div[data-baseweb="popover"] ul[role="listbox"] {{
        background-color: var(--bg-surface) !important;
        color: var(--text-primary) !important;
        padding: 4px 0 !important;
    }}

    div[data-baseweb="popover"] li[data-baseweb="menu-item"],
    div[data-baseweb="popover"] li[role="option"],
    div[data-baseweb="popover"] div[role="option"] {{
        background-color: var(--bg-surface) !important;
        color: var(--text-primary) !important;
        font-family: var(--font-primary) !important;
        font-size: 0.84rem !important;
        padding: 8px 14px !important;
        cursor: pointer !important;
        transition: background-color 0.12s ease !important;
    }}

    div[data-baseweb="popover"] li[data-baseweb="menu-item"] span,
    div[data-baseweb="popover"] li[role="option"] span,
    div[data-baseweb="popover"] div[role="option"] span,
    div[data-baseweb="popover"] li[data-baseweb="menu-item"] div,
    div[data-baseweb="popover"] li[role="option"] div,
    div[data-baseweb="popover"] div[role="option"] div,
    div[data-baseweb="popover"] li[data-baseweb="menu-item"] p,
    div[data-baseweb="popover"] li[role="option"] p,
    div[data-baseweb="popover"] div[role="option"] p {{
        color: var(--text-primary) !important;
        background-color: transparent !important;
    }}

    div[data-baseweb="popover"] li[data-baseweb="menu-item"]:hover,
    div[data-baseweb="popover"] li[role="option"]:hover,
    div[data-baseweb="popover"] div[role="option"]:hover {{
        background-color: var(--menu-hover-bg) !important;
    }}

    div[data-baseweb="popover"] li[data-baseweb="menu-item"][aria-selected="true"],
    div[data-baseweb="popover"] li[role="option"][aria-selected="true"],
    div[data-baseweb="popover"] div[role="option"][aria-selected="true"] {{
        background-color: var(--menu-selected-bg) !important;
    }}

    div[data-baseweb="popover"] li[data-baseweb="menu-item"][aria-selected="true"] span,
    div[data-baseweb="popover"] li[role="option"][aria-selected="true"] span,
    div[data-baseweb="popover"] div[role="option"][aria-selected="true"] span,
    div[data-baseweb="popover"] li[data-baseweb="menu-item"][aria-selected="true"] div,
    div[data-baseweb="popover"] li[role="option"][aria-selected="true"] div,
    div[data-baseweb="popover"] div[role="option"][aria-selected="true"] div {{
        color: var(--primary) !important;
        font-weight: 500 !important;
    }}

    /* Flagship Google Primary Button */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-primary"] {{
        font-family: var(--font-primary) !important;
        font-size: 0.86rem !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
        min-height: 38px !important;
        padding: 0 24px !important;
        letter-spacing: 0.02em !important;
        border: none !important;
        background-color: var(--btn-primary-bg) !important;
        color: var(--btn-primary-text) !important;
        box-shadow: 0 1px 2px 0 rgba(60, 64, 67, 0.30), 0 1px 3px 1px rgba(60, 64, 67, 0.15) !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {{
        background-color: var(--primary-hover) !important;
        color: var(--btn-primary-text) !important;
        box-shadow: 0 1px 3px 0 rgba(60, 64, 67, 0.30), 0 4px 8px 3px rgba(60, 64, 67, 0.15) !important;
        transform: translateY(-1px) !important;
    }}

    .stButton > button[kind="primary"]:active,
    .stButton > button[data-testid="baseButton-primary"]:active,
    button[data-testid="baseButton-primary"]:active {{
        transform: translateY(0px) !important;
        box-shadow: 0 1px 2px 0 rgba(60, 64, 67, 0.30) !important;
    }}

    /* Outlined / Secondary Buttons */
    .stButton > button:not([kind="primary"]):not([data-testid="baseButton-primary"]),
    .stDownloadButton > button,
    .stLinkButton > a {{
        font-family: var(--font-primary) !important;
        font-size: 0.83rem !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
        min-height: 34px !important;
        padding: 0 16px !important;
        letter-spacing: 0.01em !important;
        border: 1px solid var(--border-color) !important;
        background-color: var(--bg-surface) !important;
        color: var(--primary) !important;
        box-shadow: none !important;
        text-decoration: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.15s ease !important;
    }}

    .stButton > button:not([kind="primary"]):not([data-testid="baseButton-primary"]):hover,
    .stDownloadButton > button:hover,
    .stLinkButton > a:hover {{
        border-color: var(--primary) !important;
        background-color: var(--menu-selected-bg) !important;
        color: var(--primary) !important;
    }}

    /* Google Workspace Flat Tabs */
    button[data-baseweb="tab"] {{
        font-family: var(--font-primary) !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        padding: 0.45rem 1rem !important;
        border-radius: 0 !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        color: var(--text-secondary) !important;
        transition: color 0.12s ease !important;
    }}

    button[data-baseweb="tab"]:hover {{
        color: var(--text-primary) !important;
        background-color: var(--menu-hover-bg) !important;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--primary) !important;
        border-bottom: 2px solid var(--primary) !important;
        background: transparent !important;
        font-weight: 500 !important;
    }}

    /* KPI Metric Card Indicators */
    div[data-testid="stMetric"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        padding: 12px 16px !important;
        box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08) !important;
    }}

    div[data-testid="stMetricValue"] {{
        font-family: var(--font-primary) !important;
        font-weight: 600 !important;
        font-size: 1.45rem !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.01em !important;
    }}

    div[data-testid="stMetricLabel"] {{
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }}

    /* Radio Indicators */
    div[data-testid="stRadio"] [data-baseweb="radio"] {{
        cursor: pointer !important;
    }}

    div[data-testid="stRadio"] label {{
        color: var(--text-primary) !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
    }}

    /* Toggle Indicators */
    div[data-testid="stToggle"] label {{
        color: var(--text-primary) !important;
        font-size: 0.84rem !important;
    }}

    /* Checkbox Indicators */
    div[data-testid="stCheckbox"] label {{
        color: var(--text-primary) !important;
        font-size: 0.84rem !important;
    }}

    /* Compact Expanders */
    .streamlit-expanderHeader {{
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        padding: 0.4rem 0.6rem !important;
        border-radius: 4px !important;
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
    }}

    /* Alert / Callout Indicators */
    div[data-testid="stAlert"] {{
        border-radius: 4px !important;
        padding: 0.55rem 0.9rem !important;
        font-size: 0.84rem !important;
    }}

    div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
        font-size: 0.84rem !important;
    }}

    /* Alert Color Palettes */
    div[data-testid="stAlert"] {{
        background-color: var(--bg-surface) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }}

    div[data-testid="stStatusWidget"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
    }}

    /* Responsive Screen Container Sizing */
    .block-container {{
        max-width: 1360px !important;
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: clamp(1rem, 2.5vw, 2rem) !important;
        padding-right: clamp(1rem, 2.5vw, 2rem) !important;
    }}

    /* Executive Briefing Cards & Visual Chips */
    .briefing-card {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        padding: 16px !important;
        box-shadow: 0 1px 3px rgba(60, 64, 67, 0.08) !important;
        margin-bottom: 1rem !important;
    }}

    .kpi-micro-tile {{
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        padding: 8px 12px !important;
        margin-bottom: 8px !important;
    }}

    .kpi-micro-tile-label {{
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
    }}

    .kpi-micro-tile-val {{
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        margin-top: 2px !important;
    }}

    .action-fix-card {{
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
        border-left: 3px solid var(--primary) !important;
        border-radius: 4px !important;
        padding: 8px 12px !important;
        margin-bottom: 8px !important;
    }}

    .chip-gain {{
        background-color: #E6F4EA !important;
        color: #137333 !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        margin-right: 6px !important;
        display: inline-block !important;
    }}

    .chip-gain-dark {{
        background-color: #132D1B !important;
        color: #81C995 !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        margin-right: 6px !important;
        display: inline-block !important;
    }}

    /* Accessible Keyboard Focus Indicators */
    :focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible {{
        outline: 2px solid var(--primary) !important;
        outline-offset: 1px !important;
    }}

    {contrast_rules}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.title("Configuration")
    st.caption("Resume screening and job requirement evaluation")

    # API Key Input (Persistent in session_state)
    api_key_input = st.text_input(
        "Google AI Studio API Key",
        value=st.session_state["api_key"],
        type="password",
        autocomplete="off",
        key="api_key_widget",
        help="Get your key at https://aistudio.google.com/. Keys are kept strictly in session memory."
    )
    st.session_state["api_key"] = api_key_input

    api_key_valid, api_key_msg = validate_api_key_format(api_key_input)

    # Cached model listing
    available_models = DEFAULT_APPROVED_MODELS
    if api_key_valid:
        if st.session_state["cached_models"] is None or st.session_state["last_validated_key"] != api_key_input:
            try:
                live_models = fetch_available_models(api_key_input)
                st.session_state["cached_models"] = live_models
                st.session_state["last_validated_key"] = api_key_input
            except Exception as e:
                scrubbed_err = scrub_sensitive_keys(str(e), api_key_input)
                st.error(f"Authentication Failed: {scrubbed_err}")
                st.session_state["cached_models"] = None

        if st.session_state["cached_models"]:
            available_models = st.session_state["cached_models"]

    # Model selector
    model_options = available_models
    default_idx = 0
    if "gemini-3.8-flash" in model_options:
        default_idx = model_options.index("gemini-3.8-flash")

    selected_model = st.selectbox(
        "Evaluation Model",
        options=model_options,
        index=default_idx,
        format_func=get_model_label,
        help="Verified Gemini text generation models."
    )

    st.divider()

    # Display & Appearance Settings
    st.subheader("Appearance & Display")
    theme_choice = st.radio(
        "Theme",
        ["Light", "Dark"],
        index=0 if st.session_state["theme_mode"] == "Light" else 1,
        horizontal=True
    )
    st.session_state["theme_mode"] = theme_choice

    size_opts = ["Compact", "Normal", "Large"]
    cur_size_idx = size_opts.index(st.session_state["text_size"]) if st.session_state["text_size"] in size_opts else 0
    size_choice = st.selectbox("Text Scaling", size_opts, index=cur_size_idx)
    st.session_state["text_size"] = size_choice

    high_contrast = st.toggle("High Contrast Mode", value=False)
    screen_reader_mode = st.toggle("Accessible Tables Mode", value=False, help="Renders direct data tables in place of charts.")

    inject_google_design_css(theme_choice, size_choice, high_contrast)

    st.divider()

    # Session Reset
    if st.button("Clear session data", use_container_width=True):
        st.session_state["analysis_result"] = None
        st.session_state["jd_text"] = ""
        st.session_state["resume_text"] = ""
        st.session_state["rate_limiter"].reset_cooldown()
        st.success("Session data cleared.")
        st.rerun()

    st.caption("Privacy: Resumes are processed in memory and never stored.")


# --- MAIN INTERFACE HEADER ---
st.title("ATS Resume Analyzer")
st.markdown("Evaluate resume compatibility against target role requirements with evidence verification and deterministic scoring.")

# Load sample data shortcut button
if st.button("Load Sample Data (Cloud Engineer)"):
    st.session_state["jd_text"] = SAMPLE_JOB_DESCRIPTION
    st.session_state["resume_text"] = SAMPLE_RESUME
    st.rerun()


# --- INPUT INTERFACE (Direct widgets without st.form to preserve text across all reruns) ---
col_jd, col_res = st.columns([1, 1], gap="medium")

with col_jd:
    st.subheader("Job Description")
    jd_input = st.text_area(
        "Job Description Text",
        value=st.session_state["jd_text"],
        height=300,
        placeholder="Paste role requirements, mandatory qualifications, and responsibilities...",
        help="Include role responsibilities, required skills, and qualification thresholds.",
        label_visibility="collapsed"
    )
    st.session_state["jd_text"] = jd_input
    jd_words = len(jd_input.split()) if jd_input.strip() else 0
    st.caption(f"Target Role: {jd_words} words · Machine-Readable Format")

with col_res:
    st.subheader("Candidate Resume")
    res_tab_file, res_tab_text = st.tabs(["Upload Document", "Paste Text"])

    with res_tab_file:
        uploaded_file = st.file_uploader(
            "Upload Resume (.pdf or .docx)",
            type=["pdf", "docx"],
            help="Max 5 MB. PDF files must contain selectable text."
        )
        if uploaded_file is not None:
            file_kb = len(uploaded_file.getvalue()) // 1024 if hasattr(uploaded_file, "getvalue") else 0
            st.caption(f"Document: {uploaded_file.name} ({file_kb} KB) · Verified Upload")
        else:
            st.caption("Supported: .pdf (selectable text), .docx")

    with res_tab_text:
        resume_text_input = st.text_area(
            "Resume Text",
            value=st.session_state["resume_text"],
            height=230,
            placeholder="Paste raw candidate resume text here...",
            label_visibility="collapsed"
        )
        st.session_state["resume_text"] = resume_text_input
        res_words = len(resume_text_input.split()) if resume_text_input.strip() else 0
        st.caption(f"Candidate Scope: {res_words} words · Machine-Readable Format")

col_c1, col_c2 = st.columns([1, 1])
with col_c1:
    mask_pii_toggle = st.checkbox(
        "Mask PII (contact details, URLs, personal IDs) before sending to LLM",
        value=True,
        help="Local checks run on original text; LLM evaluation receives masked tokens."
    )
with col_c2:
    consent_checkbox = st.checkbox(
        "I consent to transmitting resume text to Google Gemini for evaluation.",
        value=True
    )

submit_button = st.button("Run Comprehensive ATS Analysis", type="primary", use_container_width=True)


# --- SUBMISSION PROCESSING ---
if submit_button:
    # 1. Validate API Key
    if not api_key_valid:
        st.error(f"API Key Error: {api_key_msg}. Please enter a valid Google AI Studio key in the sidebar.")
    elif not consent_checkbox:
        st.warning("Consent Required: You must consent to transmitting data to the Gemini API.")
    else:
        # 2. Check rate limit
        rate_ok, rate_msg = st.session_state["rate_limiter"].check()
        if not rate_ok:
            st.warning(f"Cooldown Active: {rate_msg}")
        else:
            # 3. Extract resume text
            final_resume_text = ""
            extraction_valid = True

            if uploaded_file is not None:
                file_bytes = uploaded_file.read()
                is_valid_upload, upload_err = validate_uploaded_file(uploaded_file.name, file_bytes)
                if not is_valid_upload:
                    st.error(f"Upload Security Error: {upload_err}")
                    extraction_valid = False
                else:
                    try:
                        ext_result = extract_document(uploaded_file.name, file_bytes)
                        if ext_result.is_scanned_or_empty:
                            st.error(f"Document Parsing Warning: {ext_result.warning}")
                            extraction_valid = False
                        else:
                            final_resume_text = ext_result.text
                            st.session_state["resume_text"] = final_resume_text
                    except Exception as e:
                        st.error(f"Document Extraction Failed: {scrub_sensitive_keys(str(e), api_key_input)}")
                        extraction_valid = False
            elif resume_text_input.strip():
                final_resume_text = resume_text_input.strip()
            elif st.session_state["resume_text"].strip():
                final_resume_text = st.session_state["resume_text"].strip()

            # 4. Validate input contents
            if extraction_valid:
                if not jd_input.strip():
                    st.warning("Please provide a Job Description to evaluate against.")
                elif not final_resume_text.strip():
                    st.warning("Please upload a resume file or paste resume text.")
                elif len(final_resume_text.split()) < 30:
                    st.warning("Resume text is too short (< 30 words). Please provide a complete resume.")
                else:
                    # 5. Execute analysis with step-by-step executive progress tracking
                    with st.status("Evaluating candidate profile against target role requirements...", expanded=True) as status_box:
                        try:
                            def update_progress(msg: str):
                                status_box.write(f"Status: {msg}")

                            result = run_full_ats_analysis(
                                api_key=api_key_input,
                                selected_model=selected_model,
                                job_description=jd_input,
                                resume_text=final_resume_text,
                                mask_pii_flag=mask_pii_toggle,
                                available_models=available_models,
                                progress_callback=update_progress
                            )

                            st.session_state["analysis_result"] = result
                            st.session_state["rate_limiter"].record_run()
                            status_box.update(label="Evaluation completed successfully", state="complete", expanded=False)
                            st.toast("Analysis completed successfully.")

                        except Exception as e:
                            status_box.update(label="Analysis Failed", state="error", expanded=True)
                            scrubbed_msg = scrub_sensitive_keys(str(e), api_key_input)
                            st.error(f"Error during analysis: {scrubbed_msg}")
                            st.session_state["rate_limiter"].reset_cooldown()


# --- DISPLAY RESULTS (Persisted across reruns) ---
analysis_data: Optional[FullAnalysisResult] = st.session_state.get("analysis_result")
is_dark = (st.session_state["theme_mode"] == "Dark")

if analysis_data is not None:
    st.divider()
    score_res = analysis_data.score

    # Model and Status Banner
    failover_badge = " | Failover model utilized" if analysis_data.failover_occurred else ""
    pii_badge = " | PII Masked" if analysis_data.pii_masked else ""
    st.caption(f"Evaluated with **{analysis_data.model_used}**{failover_badge}{pii_badge} · Role: **{escape_literal_text(analysis_data.job_title)}** ({escape_literal_text(analysis_data.seniority)})")

    # Score Caps / Knockouts
    if score_res.knockout_capped:
        st.warning("Score Capped at 60%: One or more mandatory knockout requirements were not satisfied.")
    if score_res.injection_capped:
        st.error("Score Capped at 30%: Prompt manipulation or adversarial instructions were detected in the resume text.")

    # 3-Column Unified Executive Scorecard
    top_col1, top_col2, top_col3 = st.columns([1.1, 1.2, 1.7], gap="medium")

    with top_col1:
        st.markdown("##### Overall Match")
        if not screen_reader_mode:
            gauge_fig, gauge_alt, gauge_df = make_score_gauge(score_res, is_dark=is_dark)
            if gauge_fig:
                st.plotly_chart(gauge_fig, use_container_width=True)
                with st.expander("Score Details Table", expanded=False):
                    st.dataframe(gauge_df, use_container_width=True, hide_index=True)
            else:
                st.metric("ATS Match Score", f"{score_res.total_score}/100", f"Band: {score_res.band}")
        else:
            st.subheader(f"ATS Score: {score_res.total_score}/100 ({score_res.band})")

    with top_col2:
        st.markdown("##### Core Alignment Metrics")
        must_earned = score_res.breakdown["must_skills"].earned if "must_skills" in score_res.breakdown else 0.0
        must_max = score_res.breakdown["must_skills"].maximum if "must_skills" in score_res.breakdown else 40.0
        must_pct = int((must_earned / must_max) * 100) if must_max else 0

        pass_chk = sum(1 for c in analysis_data.ats_checks if c.status == "pass")
        tot_chk = len(analysis_data.ats_checks)

        cand_yrs = score_res.candidate_years_used
        req_yrs = score_res.required_years

        st.markdown(f"""
        <div class="kpi-micro-tile">
            <div class="kpi-micro-tile-label">Must-Have Skills Match</div>
            <div class="kpi-micro-tile-val">{must_pct}% ({must_earned:.0f}/{must_max:.0f} pts)</div>
        </div>
        <div class="kpi-micro-tile">
            <div class="kpi-micro-tile-label">Relevant Experience</div>
            <div class="kpi-micro-tile-val">{cand_yrs:.1f} yrs <span style="font-size:0.75rem; color:var(--text-secondary);">(vs {req_yrs:.1f} req)</span></div>
        </div>
        <div class="kpi-micro-tile">
            <div class="kpi-micro-tile-label">ATS Screening Compliance</div>
            <div class="kpi-micro-tile-val">{pass_chk} of {tot_chk} Rules Passed</div>
        </div>
        """, unsafe_allow_html=True)

    with top_col3:
        st.markdown("##### Executive Summary & Action Items")
        st.info(analysis_data.summary or "Evaluation completed.")

        if analysis_data.top_fixes:
            gain_chip_class = "chip-gain-dark" if is_dark else "chip-gain"
            for fix in analysis_data.top_fixes[:2]:
                st.markdown(f"""
                <div class="action-fix-card">
                    <span class="{gain_chip_class}">+{fix.points_gain} pts</span>
                    <strong>{escape_literal_text(fix.title)}</strong>
                    <div style="font-size:0.78rem; color:var(--text-secondary); margin-top:3px;">{escape_literal_text(fix.action)}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("No critical deficits found.")

    # Direct contact notice
    contacts = analysis_data.contact_details
    has_direct_contacts = bool(contacts and (contacts.emails or contacts.phone_numbers or contacts.recruiter_names or contacts.application_links))
    if has_direct_contacts:
        st.success(f"Direct Contact Details Detected: Found {len(contacts.emails)} Email(s), {len(contacts.phone_numbers)} Phone(s), and {len(contacts.recruiter_names)} Named Contact(s). See the 'Recruiter & Contacts' tab below.")

    st.markdown("---")

    # Dynamic live count badges for ambient tab navigation
    total_reqs = len(analysis_data.verified_requirements)
    matched_reqs = sum(1 for r in analysis_data.verified_requirements if r.verified_status in ["found", "implied"])
    reqs_badge = f" ({matched_reqs}/{total_reqs} Matched)" if total_reqs else ""

    pass_checks = sum(1 for c in analysis_data.ats_checks if c.status == "pass")
    total_checks = len(analysis_data.ats_checks)
    ats_badge = f" ({pass_checks}/{total_checks} Pass)" if total_checks else ""

    rewrites_count = len(analysis_data.rewrites)
    revis_badge = f" ({rewrites_count} Suggestions)" if rewrites_count else ""

    leads_count = (len(contacts.emails) + len(contacts.phone_numbers) + len(contacts.recruiter_names)) if contacts else 0
    cnt_badge = f" ({leads_count} Leads)" if leads_count > 0 else ""

    tab_overview, tab_keywords, tab_enterprise, tab_ats, tab_improve, tab_contacts, tab_parser, tab_export = st.tabs([
        "Overview",
        f"Requirements & Skills{reqs_badge}",
        "Big Tech Screening (Boolean / X-Y-Z)",
        f"ATS Compliance{ats_badge}",
        f"Actionable Revisions{revis_badge}",
        f"Recruiter & Contacts{cnt_badge}",
        "ATS Parser Preview",
        "Export Report"
    ])

    # --- TAB 1: OVERVIEW ---
    with tab_overview:
        st.subheader("Evaluation Dimensions")

        c_ov1, c_ov2 = st.columns([1, 1], gap="medium")

        with c_ov1:
            st.markdown("##### Dimension Radar Fit")
            radar_fig, radar_alt, radar_df = make_radar_breakdown(score_res, is_dark=is_dark)
            if not screen_reader_mode and radar_fig:
                st.plotly_chart(radar_fig, use_container_width=True)
            with st.expander("Radar Breakdown Table", expanded=screen_reader_mode):
                st.dataframe(radar_df, use_container_width=True, hide_index=True)

        with c_ov2:
            st.markdown("##### Points Earned vs Available")
            pts_fig, pts_alt, pts_df = make_points_stacked_bar(score_res, is_dark=is_dark)
            if not screen_reader_mode and pts_fig:
                st.plotly_chart(pts_fig, use_container_width=True)
            with st.expander("Points Breakdown Table", expanded=screen_reader_mode):
                st.dataframe(pts_df, use_container_width=True, hide_index=True)

        st.markdown("##### Relevant Experience Tenure")
        exp_fig, exp_alt, exp_df = make_experience_bullet_chart(score_res, is_dark=is_dark)
        if not screen_reader_mode and exp_fig:
            st.plotly_chart(exp_fig, use_container_width=True)
        with st.expander("Experience Comparison Table", expanded=screen_reader_mode):
            st.dataframe(exp_df, use_container_width=True, hide_index=True)

        if analysis_data.knockouts:
            st.markdown("##### Mandatory Knockout Criteria")
            ko_rows = []
            for ko in analysis_data.knockouts:
                met_badge = "Met" if ko.met == "yes" else ("Unmet" if ko.met == "no" else "Unknown")
                ko_rows.append({
                    "Requirement": ko.requirement,
                    "Status": met_badge,
                    "Evidence in Resume": ko.evidence or "None cited"
                })
            st.table(pd.DataFrame(ko_rows))

    # --- TAB 2: KEYWORDS & REQUIREMENTS ---
    with tab_keywords:
        st.subheader("Requirement Verification & Skill Alignment")

        ck1, ck2 = st.columns([1, 1], gap="medium")
        with ck1:
            st.markdown("##### Skill Match Distribution")
            don_fig, don_alt, don_df = make_coverage_donut(analysis_data.verified_requirements, is_dark=is_dark)
            if not screen_reader_mode and don_fig:
                st.plotly_chart(don_fig, use_container_width=True)
            with st.expander("Match Distribution Data", expanded=screen_reader_mode):
                st.dataframe(don_df, use_container_width=True, hide_index=True)

        with ck2:
            st.markdown("##### Top Requirement Credit Awarded")
            cred_fig, cred_alt, cred_df = make_requirements_credit_chart(analysis_data.verified_requirements, is_dark=is_dark)
            if not screen_reader_mode and cred_fig:
                st.plotly_chart(cred_fig, use_container_width=True)
            with st.expander("Top Requirements Data", expanded=screen_reader_mode):
                st.dataframe(cred_df, use_container_width=True, hide_index=True)

        st.markdown("##### Complete Requirements Roster")

        req_table_data = []
        for r in analysis_data.verified_requirements:
            status_text = {
                "found": "Found",
                "implied": "Implied",
                "unverified": "Unverified",
                "missing": "Missing"
            }.get(r.verified_status, r.verified_status.title())

            req_table_data.append({
                "Requirement": r.term,
                "Category": r.category.replace("_", " ").title(),
                "Priority": r.importance.upper(),
                "Match Status": status_text,
                "Recency": getattr(r, "recency", "unknown").title(),
                "Credit Awarded": f"{int(r.credit_ratio * 100)}%",
                "Points": f"{r.points_earned} / {r.max_points}",
                "Verified Evidence Quote": r.evidence or "-",
                "Verification Details": r.explanation
            })

        req_df = pd.DataFrame(req_table_data)
        st.dataframe(req_df, use_container_width=True, hide_index=True)

    # --- TAB 3: BIG TECH ENTERPRISE SCREENING ---
    with tab_enterprise:
        st.subheader("Enterprise Screening & Talent Sourcing Analysis")
        st.caption("How senior recruiters at Tier-1 tech companies and enterprise ATS platforms screen this profile.")

        ent_col1, ent_col2 = st.columns([1, 1], gap="medium")

        with ent_col1:
            st.markdown("##### Recruiter Boolean Search Simulator")
            st.caption("Recruiters search talent pools using precise Boolean queries. If your resume fails these, you won't appear in candidate search results.")
            if analysis_data.boolean_queries:
                for bq in analysis_data.boolean_queries:
                    status_badge = "PASSED (Candidate Found)" if bq.matched else "FAILED (Candidate Filtered Out)"
                    with st.expander(f"{bq.name}: {status_badge}", expanded=True):
                        st.code(bq.query_string, language="text")
                        if bq.matched_terms:
                            st.write(f"**Found in Resume:** {', '.join(bq.matched_terms)}")
                        if bq.missing_terms:
                            st.write(f"**Missing Critical Terms:** {', '.join(bq.missing_terms)}")
            else:
                st.info("No Boolean queries generated.")

        with ent_col2:
            st.markdown("##### Google X-Y-Z Impact & Scale Assessment")
            st.caption("Google Formula: *'Accomplished [X] measured by [Y] by doing [Z]'*.")
            xyz = analysis_data.xyz_analysis
            if xyz:
                st.write(f"**Compliance Rate:** {int(xyz.compliance_rate * 100)}% ({xyz.xyz_compliant_bullets} of {xyz.total_bullets} bullets)")
                st.info(xyz.summary)
                if xyz.scale_indicators_found:
                    st.write(f"**Scale Indicators Detected:** `{', '.join(xyz.scale_indicators_found)}`")
                else:
                    st.warning("No enterprise scale keywords (e.g., QPS, latency, millions, TB, throughput) detected. Add explicit scope and scale to your bullets.")

            st.markdown("##### Career Stability & Tenure Analysis")
            tenure = analysis_data.tenure_analysis
            if tenure:
                st.write(f"**Average Tenure per Role:** {tenure.average_tenure_years} years across {tenure.job_count} distinct roles")
                st.write(f"**Stability Band:** `{tenure.stability_band}`")
                if tenure.job_hopping_risk:
                    st.warning(tenure.summary)
                else:
                    st.success(tenure.summary)

    # --- TAB 4: ATS COMPLIANCE CHECKS ---
    with tab_ats:
        st.subheader("ATS Format & Content Checks")

        ats_fig, ats_alt, ats_df = make_ats_checks_status_chart(analysis_data.ats_checks, is_dark=is_dark)
        if not screen_reader_mode and ats_fig:
            st.plotly_chart(ats_fig, use_container_width=True)
        with st.expander("ATS Check Status Counts", expanded=screen_reader_mode):
            st.dataframe(ats_df, use_container_width=True, hide_index=True)

        st.markdown("##### Individual Compliance Checks")
        for check in analysis_data.ats_checks:
            status_label = "Pass" if check.status == "pass" else ("Warning" if check.status == "warn" else "Fail")
            with st.expander(f"{status_label}: {check.name} ({check.points}/{check.max_points} pts)", expanded=(check.status != "pass")):
                st.write(f"**Category:** {check.category.title()}")
                st.write(f"**Diagnostic Details:** {check.detail}")
                if check.fix:
                    st.info(f"**Recommended Action:** {check.fix}")

    # --- TAB 4: ACTIONABLE REVISIONS ---
    with tab_improve:
        st.subheader("Targeted Improvements & Evidence-Based Rewrites")

        ci1, ci2 = st.columns([1, 1], gap="medium")
        with ci1:
            st.markdown("##### Demonstrated Strengths")
            if analysis_data.strengths:
                for s in analysis_data.strengths:
                    st.markdown(f"- {escape_literal_text(s)}")
            else:
                st.write("No specific strengths extracted.")

        with ci2:
            st.markdown("##### Skill & Experience Gaps")
            if analysis_data.gaps:
                for g in analysis_data.gaps:
                    st.markdown(f"- {escape_literal_text(g)}")
            else:
                st.write("No major gaps detected.")

        st.markdown("---")
        st.subheader("Evidence-Based Bullet Point Rewrites")
        st.caption("Rewrites use verified factual points with metrics placeholders like `[X%]` to avoid hallucinating achievements.")

        if analysis_data.rewrites:
            for idx, rw in enumerate(analysis_data.rewrites):
                with st.expander(f"Revision {idx + 1}: {escape_literal_text(rw.original[:60])}...", expanded=True):
                    st.markdown(f"**Original Bullet:**  \n> {escape_literal_text(rw.original)}")
                    st.markdown(f"**Improved ATS Bullet:**  \n> **{escape_literal_text(rw.improved)}**")
                    st.info(f"**Rationale:** {escape_literal_text(rw.reason)}")
        else:
            st.write("No specific bullet revisions suggested.")

    # --- TAB 5: RECRUITER & APPLICATION CONTACTS ---
    with tab_contacts:
        st.subheader("Recruiter & Application Contacts")
        st.caption("Extracted contact information from job posting and targeted search queries for hiring personnel.")

        contacts = analysis_data.contact_details
        has_contacts = bool(contacts and (contacts.emails or contacts.phone_numbers or contacts.recruiter_names or contacts.application_links or contacts.submission_instructions))

        if has_contacts:
            c_cnt1, c_cnt2 = st.columns([1, 1], gap="medium")
            with c_cnt1:
                st.markdown("##### Contact Details Identified in Job Posting")
                if contacts.emails:
                    st.write("**Application Emails:**")
                    for email in contacts.emails:
                        st.markdown(f"- `{escape_literal_text(email)}`")
                if contacts.phone_numbers:
                    st.write("**Phone Numbers:**")
                    for phone in contacts.phone_numbers:
                        st.markdown(f"- `{escape_literal_text(phone)}`")
                if contacts.recruiter_names:
                    st.write("**Named Contact / Recruiter:**")
                    for name in contacts.recruiter_names:
                        st.markdown(f"- **{escape_literal_text(name)}**")

            with c_cnt2:
                st.markdown("##### Application Links & Instructions")
                if contacts.application_links:
                    st.write("**Career / Application Links:**")
                    for link in contacts.application_links:
                        st.markdown(f"- [{escape_literal_text(link)}]({link})")
                if contacts.submission_instructions:
                    st.write("**Submission Instructions:**")
                    st.info(escape_literal_text(contacts.submission_instructions))
        else:
            st.info("No direct email addresses or phone numbers were detected inside the job description text.")

        st.markdown("---")
        st.subheader("Target Recruiter & Hiring Manager Search Queries")
        st.caption("Calibrated search queries to locate technical recruiters and hiring managers on LinkedIn:")

        queries = generate_recruiter_search_queries(analysis_data.job_title)
        for q in queries:
            q_col1, q_col2 = st.columns([3, 1])
            with q_col1:
                st.markdown(f"**{escape_literal_text(q['title'])}**  \n`{escape_literal_text(q['query'])}`")
            with q_col2:
                st.link_button("Open Search", q["url"], use_container_width=True)

        st.markdown("---")
        st.subheader("Recruiter Outreach Template")
        st.caption("A professional outreach message template for contacting hiring leads:")

        outreach_template = f"""Subject: Regarding {analysis_data.job_title} role

Dear [Hiring Manager / Recruiter Name],

I noticed the {analysis_data.job_title} opening at [Company Name] and evaluated my background against the core requirements. With hands-on experience in the required technical stack, I believe I can make an immediate contribution to your team.

I have submitted my application through the official portal, and wanted to reach out directly to express my enthusiasm. Would you be open to a brief conversation regarding the position?

Best regards,
[Your Name]
[Your LinkedIn Profile] | [Your Portfolio/GitHub]
"""
        st.code(outreach_template, language="markdown")

    # --- TAB 7: ATS PARSER PREVIEW ---
    with tab_parser:
        st.subheader("Raw ATS Parser Visual Stream")
        st.caption("This is the exact linear text extracted by applicant tracking systems (Workday, Greenhouse, Taleo). Verify that tables or columns did not scramble reading order.")
        raw_res_text = st.session_state.get("resume_text", "")
        if raw_res_text:
            st.text_area(
                "Extracted Text Stream",
                value=raw_res_text,
                height=450,
                disabled=True,
                help="If text from multi-column tables is interspersed or out of order, convert your resume to a single-column format."
            )
        else:
            st.info("No resume text loaded.")

    # --- TAB 8: EXPORT ---
    with tab_export:
        st.subheader("Export Analysis Reports")
        st.caption("Reports summarize compatibility metrics and recommendations.")

        md_lines = [
            f"# ATS Compatibility Report: {analysis_data.job_title}",
            f"**Overall ATS Score:** {score_res.total_score}/100 ({score_res.band})",
            f"**Evaluated by:** {analysis_data.model_used}",
            "",
            "## Summary",
            analysis_data.summary,
            "",
            "## Score Breakdown",
            "| Dimension | Earned | Max | % |",
            "|---|---|---|---|",
        ]
        for v in score_res.breakdown.values():
            md_lines.append(f"| {v.area} | {v.earned} | {v.maximum} | {v.percentage}% |")

        md_lines.extend(["", "## Top Recommendations"])
        for fix in analysis_data.top_fixes:
            md_lines.append(f"- **+{fix.points_gain} pts**: {fix.title} — {fix.action}")

        md_report = "\n".join(md_lines)

        csv_df = pd.DataFrame([
            {
                "Requirement": r.term,
                "Category": r.category,
                "Importance": r.importance,
                "Match Status": r.verified_status,
                "Credit Ratio": r.credit_ratio,
                "Points Earned": r.points_earned,
                "Max Points": r.max_points,
                "Evidence": r.evidence,
                "Explanation": r.explanation
            }
            for r in analysis_data.verified_requirements
        ])
        csv_data = csv_df.to_csv(index=False)
        json_data = analysis_data.model_dump_json(indent=2)

        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            st.download_button(
                "Download Markdown Report",
                data=md_report,
                file_name="ats_compatibility_report.md",
                mime="text/markdown",
                use_container_width=True
            )
        with exp_col2:
            st.download_button(
                "Download Requirements CSV",
                data=csv_data,
                file_name="ats_requirements.csv",
                mime="text/csv",
                use_container_width=True
            )
        with exp_col3:
            st.download_button(
                "Download Full Analysis JSON",
                data=json_data,
                file_name="ats_analysis.json",
                mime="application/json",
                use_container_width=True
            )

        st.caption("Notice: This application provides compatibility estimates based on standard ATS screening heuristics.")