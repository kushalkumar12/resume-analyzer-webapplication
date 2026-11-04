"""Interactive, accessible Plotly data visualizations using colorblind-safe Okabe-Ito palette
and Google Material Design typography and theme tokens."""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from ats.models import FullAnalysisResult, ScoreResult, VerifiedRequirement, ATSCheckItem

# Colorblind-safe Okabe-Ito palette:
# https://jfly.uni-koeln.de/color/
COLOR_ORANGE = "#E69F00"
COLOR_SKY_BLUE = "#56B4E9"
COLOR_BLUISH_GREEN = "#009E73"
COLOR_YELLOW = "#F0E442"
COLOR_BLUE = "#1A73E8"
COLOR_VERMILION = "#D93025"
COLOR_REDDISH_PURPLE = "#CC79A7"
COLOR_GREY = "#80868B"

# Google enterprise font stack
STANDARD_CHART_FONT = dict(family="'Google Sans', 'Roboto', 'Inter', -apple-system, sans-serif")


def _chart_text_color(is_dark: bool) -> str:
    return "#E8EAED" if is_dark else "#202124"


def _chart_muted_color(is_dark: bool) -> str:
    return "#9AA0A6" if is_dark else "#5F6368"


def _chart_border_color(is_dark: bool) -> str:
    return "#3C4043" if is_dark else "#DADCE0"


def make_score_gauge(score_result: ScoreResult, is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """1. Score gauge chart with performance bands and alt-text."""
    score = score_result.total_score
    band = score_result.band

    alt_text = f"Overall ATS Score Gauge: {score} out of 100 ({band} fit). Range from 0 to 100."
    df = pd.DataFrame([{"Metric": "Overall ATS Score", "Value": score, "Rating Band": band}])

    try:
        bar_color = COLOR_BLUISH_GREEN if score >= 80 else (COLOR_SKY_BLUE if score >= 65 else (COLOR_ORANGE if score >= 50 else COLOR_VERMILION))
        text_col = _chart_text_color(is_dark)
        muted_col = _chart_muted_color(is_dark)
        border_col = _chart_border_color(is_dark)
        bg_card = "#292A2D" if is_dark else "#F8F9FA"

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 34, "color": text_col, "family": "'Google Sans', 'Roboto', sans-serif"}},
            title={"text": f"<b>ATS Match Score</b><br><span style='font-size:12px; color:{muted_col};'>Band: {band}</span>", "font": {"size": 15, "color": text_col}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": muted_col},
                "bar": {"color": bar_color, "thickness": 0.28},
                "bgcolor": bg_card,
                "borderwidth": 1,
                "bordercolor": border_col,
                "steps": [
                    {"range": [0, 50], "color": "#442726" if is_dark else "#FCE8E6"},
                    {"range": [50, 65], "color": "#4A3B18" if is_dark else "#FEF7E0"},
                    {"range": [65, 80], "color": "#1C355E" if is_dark else "#E8F0FE"},
                    {"range": [80, 100], "color": "#133821" if is_dark else "#E6F4EA"},
                ],
                "threshold": {
                    "line": {"color": text_col, "width": 3},
                    "thickness": 0.8,
                    "value": score
                }
            }
        ))
        fig.update_layout(
            height=210,
            margin=dict(l=15, r=15, t=30, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_radar_breakdown(score_result: ScoreResult, is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """2. Radar chart of the six evaluation dimensions as percentage of max."""
    if not score_result.breakdown:
        return None, "No evaluation breakdown data available.", pd.DataFrame()

    areas = []
    pcts = []
    for k, v in score_result.breakdown.items():
        areas.append(v.area)
        pcts.append(v.percentage)

    if not areas:
        return None, "No dimension data available.", pd.DataFrame()

    radar_areas = areas + [areas[0]]
    radar_pcts = pcts + [pcts[0]]

    df = pd.DataFrame([
        {"Area": v.area, "Earned": v.earned, "Max": v.maximum, "Percentage": f"{v.percentage}%"}
        for v in score_result.breakdown.values()
    ])
    alt_text = "Radar Chart displaying percentage scores across 6 ATS evaluation dimensions: " + "; ".join(f"{v.area}: {v.percentage}%" for v in score_result.breakdown.values())

    try:
        text_col = _chart_text_color(is_dark)
        border_col = _chart_border_color(is_dark)

        fig = go.Figure(go.Scatterpolar(
            r=radar_pcts,
            theta=radar_areas,
            fill='toself',
            fillcolor='rgba(26, 115, 232, 0.25)' if not is_dark else 'rgba(138, 180, 248, 0.25)',
            line=dict(color=COLOR_BLUE if not is_dark else "#8AB4F8", width=2),
            marker=dict(size=6, color=COLOR_BLUE if not is_dark else "#8AB4F8")
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%", gridcolor=border_col, tickfont=dict(size=10, color=text_col)),
                angularaxis=dict(direction="clockwise", gridcolor=border_col, tickfont=dict(size=11, color=text_col))
            ),
            showlegend=False,
            height=280,
            margin=dict(l=30, r=30, t=25, b=25),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_points_stacked_bar(score_result: ScoreResult, is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """3. Stacked bar chart: points earned vs points remaining per area."""
    if not score_result.breakdown:
        return None, "No points data available.", pd.DataFrame()

    areas = []
    earned = []
    remaining = []

    for v in score_result.breakdown.values():
        areas.append(v.area)
        earned.append(v.earned)
        remaining.append(round(max(0.0, v.maximum - v.earned), 2))

    df = pd.DataFrame({
        "Area": areas,
        "Points Earned": earned,
        "Points Remaining": remaining,
    })
    alt_text = "Stacked Bar Chart comparing points earned against remaining points for each evaluation area."

    try:
        text_col = _chart_text_color(is_dark)
        border_col = _chart_border_color(is_dark)
        empty_bar = "#3C4043" if is_dark else "#E8EAED"

        fig = go.Figure(data=[
            go.Bar(name='Points Earned', y=areas, x=earned, orientation='h', marker_color=COLOR_BLUISH_GREEN),
            go.Bar(name='Potential Gain', y=areas, x=remaining, orientation='h', marker_color=empty_bar)
        ])
        fig.update_layout(
            barmode='stack',
            height=260,
            margin=dict(l=15, r=15, t=25, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=text_col, size=11)),
            xaxis=dict(title="Score Points", range=[0, 42], gridcolor=border_col, tickfont=dict(color=text_col, size=10)),
            yaxis=dict(tickfont=dict(color=text_col, size=11)),
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_coverage_donut(verified_reqs: List[VerifiedRequirement], is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """4. Donut chart of requirement coverage (Found, Implied, Unverified, Missing)."""
    counts = {"found": 0, "implied": 0, "unverified": 0, "missing": 0}
    for r in verified_reqs:
        status = r.verified_status
        if status in counts:
            counts[status] += 1
        else:
            counts["missing"] += 1

    labels = ["Found", "Implied", "Unverified", "Missing"]
    values = [counts["found"], counts["implied"], counts["unverified"], counts["missing"]]
    colors = [COLOR_BLUISH_GREEN, COLOR_SKY_BLUE, COLOR_ORANGE, COLOR_VERMILION]

    df = pd.DataFrame({"Status": labels, "Count": values})
    alt_text = f"Donut Chart showing requirement match distribution: {counts['found']} found, {counts['implied']} implied, {counts['unverified']} unverified, {counts['missing']} missing."

    try:
        text_col = _chart_text_color(is_dark)
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.58,
            marker=dict(colors=colors),
            textinfo='label+value',
            insidetextorientation='radial',
            textfont=dict(size=11, family="'Google Sans', 'Roboto', sans-serif")
        )])
        fig.update_layout(
            height=270,
            margin=dict(l=15, r=15, t=15, b=15),
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, font=dict(color=text_col, size=11)),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_requirements_credit_chart(verified_reqs: List[VerifiedRequirement], is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """5. Horizontal bar chart of credit per requirement labelled must/nice."""
    if not verified_reqs:
        return None, "No requirements extracted.", pd.DataFrame()

    sorted_reqs = sorted(verified_reqs, key=lambda r: (r.importance == "must", r.credit_ratio), reverse=True)[:15]

    terms = [f"{r.term} ({r.importance.upper()})" for r in sorted_reqs]
    credit_pcts = [int(r.credit_ratio * 100) for r in sorted_reqs]
    colors = [
        COLOR_BLUISH_GREEN if r.credit_ratio == 1.0 else
        (COLOR_SKY_BLUE if r.credit_ratio == 0.7 else
         (COLOR_ORANGE if r.credit_ratio == 0.6 else COLOR_VERMILION))
        for r in sorted_reqs
    ]

    df = pd.DataFrame([
        {
            "Requirement": r.term,
            "Importance": r.importance.title(),
            "Match Status": r.verified_status.title(),
            "Credit (%)": f"{int(r.credit_ratio * 100)}%",
            "Points": f"{r.points_earned} / {r.max_points}"
        }
        for r in sorted_reqs
    ])
    alt_text = "Horizontal Bar Chart showing match percentage and credit earned for individual job requirements."

    try:
        text_col = _chart_text_color(is_dark)
        border_col = _chart_border_color(is_dark)

        fig = go.Figure(go.Bar(
            y=terms,
            x=credit_pcts,
            orientation='h',
            marker=dict(color=colors),
            text=[f"{p}%" for p in credit_pcts],
            textposition='auto',
            textfont=dict(size=10, color="#FFFFFF")
        ))
        fig.update_layout(
            height=max(280, len(terms) * 24),
            xaxis=dict(title="Credit Awarded (%)", range=[0, 105], gridcolor=border_col, tickfont=dict(color=text_col, size=10)),
            yaxis=dict(autorange="reversed", tickfont=dict(color=text_col, size=11)),
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_ats_checks_status_chart(checks: List[ATSCheckItem], is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """6. Stacked bar chart of ATS check status (pass, warn, fail) for format and content."""
    cats = ["format", "content"]
    data = {
        "pass": [sum(1 for c in checks if c.category == cat and c.status == "pass") for cat in cats],
        "warn": [sum(1 for c in checks if c.category == cat and c.status == "warn") for cat in cats],
        "fail": [sum(1 for c in checks if c.category == cat and c.status == "fail") for cat in cats],
    }

    df = pd.DataFrame([
        {
            "Category": c.category.title(),
            "Check": c.name,
            "Status": c.status.upper(),
            "Score": f"{c.points} / {c.max_points}",
            "Detail": c.detail
        }
        for c in checks
    ])
    alt_text = "Stacked Bar Chart of ATS compliance check statuses across Format and Content Quality."

    try:
        text_col = _chart_text_color(is_dark)
        border_col = _chart_border_color(is_dark)

        fig = go.Figure(data=[
            go.Bar(name='Pass', x=["ATS Format", "Content Quality"], y=data["pass"], marker_color=COLOR_BLUISH_GREEN),
            go.Bar(name='Warning', x=["ATS Format", "Content Quality"], y=data["warn"], marker_color=COLOR_ORANGE),
            go.Bar(name='Fail', x=["ATS Format", "Content Quality"], y=data["fail"], marker_color=COLOR_VERMILION)
        ])
        fig.update_layout(
            barmode='stack',
            height=250,
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=text_col, size=11)),
            yaxis=dict(title="Checks", gridcolor=border_col, tickfont=dict(color=text_col, size=10)),
            xaxis=dict(tickfont=dict(color=text_col, size=11)),
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df


def make_experience_bullet_chart(score_result: ScoreResult, is_dark: bool = False) -> Tuple[Optional[go.Figure], str, pd.DataFrame]:
    """7. Bullet indicator of Candidate Years vs Required Years."""
    cand_years = score_result.candidate_years_used
    req_years = score_result.required_years

    df = pd.DataFrame([{
        "Candidate Relevant Years": f"{cand_years:.1f} yrs",
        "Required Years": f"{req_years:.1f} yrs" if req_years > 0 else "None specified",
        "Alignment": "Sufficient" if cand_years >= req_years else "Under requirement"
    }])
    alt_text = f"Experience comparison: Candidate has {cand_years:.1f} relevant years compared to {req_years:.1f} years required by job description."

    try:
        text_col = _chart_text_color(is_dark)
        border_col = _chart_border_color(is_dark)
        step_bg = "#3C4043" if is_dark else "#F1F3F4"
        step_active = "#2D2F31" if is_dark else "#E8EAED"

        max_range = max(10.0, max(cand_years, req_years) + 3.0)
        fig = go.Figure(go.Indicator(
            mode="number+gauge",
            value=cand_years,
            number={"suffix": " yrs", "font": {"size": 30, "color": text_col, "family": "'Google Sans', 'Roboto', sans-serif"}},
            title={"text": f"<b>Experience Tenure</b><br><span style='font-size:11px;color:{_chart_muted_color(is_dark)};'>Candidate vs Required</span>", "font": {"size": 13, "color": text_col}},
            gauge={
                "shape": "bullet",
                "axis": {"range": [0, max_range], "tickfont": dict(color=text_col, size=10)},
                "threshold": {
                    "line": {"color": COLOR_VERMILION, "width": 3},
                    "thickness": 0.8,
                    "value": req_years
                },
                "bar": {"color": COLOR_BLUE if not is_dark else "#8AB4F8", "thickness": 0.5},
                "steps": [
                    {"range": [0, req_years], "color": step_bg},
                    {"range": [req_years, max_range], "color": step_active}
                ]
            }
        ))
        fig.update_layout(
            height=160,
            margin=dict(l=15, r=15, t=30, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="'Google Sans', 'Roboto', sans-serif", color=text_col)
        )
        return fig, alt_text, df
    except Exception:
        return None, alt_text, df
