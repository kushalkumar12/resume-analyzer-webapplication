"""Actionable insights and top fixes with estimated point gains."""

from typing import List
from ats.models import TopFixItem, VerifiedRequirement, ATSCheckItem, ScoreResult


def generate_top_fixes(
    verified_reqs: List[VerifiedRequirement],
    ats_checks: List[ATSCheckItem],
    score_result: ScoreResult
) -> List[TopFixItem]:
    """Computes prioritized top recommendations with realistic estimated point gains."""
    fixes: List[TopFixItem] = []

    # 1. Missing Must-Have Skills
    for req in verified_reqs:
        if req.importance == "must" and req.verified_status in ["missing", "unverified"]:
            gain = round(req.max_points, 1)
            fixes.append(TopFixItem(
                title=f"Add '{req.term}' if you have genuine experience",
                category="Must-Have Skill",
                points_gain=gain,
                action=f"Include '{req.term}' in your professional experience or projects section with verifiable context and impact.",
                importance="high"
            ))

    # 2. Skills listed only in skills list (upgrade to demonstrated experience: +30% of max pts)
    for req in verified_reqs:
        if req.verified_status == "found" and req.credit_ratio == 0.7:
            gain = round(req.max_points * 0.3, 1)
            fixes.append(TopFixItem(
                title=f"Demonstrate '{req.term}' in work experience",
                category="Skill Demonstration",
                points_gain=gain,
                action=f"Move '{req.term}' beyond a standalone skills list by showing how you applied it in your job accomplishments.",
                importance="medium"
            ))

    # 3. Missing Nice-To-Have Skills
    for req in verified_reqs:
        if req.importance == "nice" and req.verified_status in ["missing", "unverified"]:
            gain = round(req.max_points, 1)
            fixes.append(TopFixItem(
                title=f"Include preferred skill '{req.term}'",
                category="Nice-To-Have Skill",
                points_gain=gain,
                action=f"Add '{req.term}' or equivalent technologies to strengthen your competitive match.",
                importance="low"
            ))

    # 4. ATS Format & Content Fixes
    for check in ats_checks:
        if check.status in ["warn", "fail"] and check.fix:
            potential_gain = round(check.max_points - check.points, 1)
            if potential_gain > 0.0:
                imp = "high" if check.status == "fail" else "medium"
                fixes.append(TopFixItem(
                    title=f"Fix ATS {check.category.title()}: {check.name}",
                    category=f"ATS {check.category.title()}",
                    points_gain=potential_gain,
                    action=check.fix,
                    importance=imp
                ))

    # Sort descending by point gain
    fixes.sort(key=lambda x: x.points_gain, reverse=True)
    return fixes[:7]  # Top 7 actionable items
