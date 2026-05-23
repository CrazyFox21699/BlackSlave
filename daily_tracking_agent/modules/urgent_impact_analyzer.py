from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .models import Issue


DEFAULT_URGENT_KEYWORDS = [
    "urgent", "hotfix", "ad-hoc", "adhoc", "unplanned", "escalation",
    "support", "interrupt", "firefighting", "production issue", "customer urgent",
]


def analyze_urgent_impact(
    df: pd.DataFrame,
    capacity: dict,
    urgent_config: dict | None,
    today: date,
) -> tuple[dict[str, Any], list[Issue]]:
    config = urgent_config or {}
    if not config.get("enabled", True):
        return _empty_result(), []

    keywords = [str(k).lower() for k in config.get("keywords", DEFAULT_URGENT_KEYWORDS)]
    impact_window_days = int(config.get("impact_window_days", 5))
    daily_capacity = float(capacity.get("daily_mh", 8))

    active = df[df["CurrentProgress"].fillna(0) < 100].copy()
    if active.empty:
        return _empty_result(), []

    text = active["TaskText"].fillna("").astype(str).str.lower()
    note = active["Note"].fillna("").astype(str).str.lower()
    urgent_mask = text.apply(lambda value: any(k in value for k in keywords)) | note.apply(lambda value: any(k in value for k in keywords))
    urgent_tasks = active[urgent_mask].copy()
    urgent_tasks = urgent_tasks[urgent_tasks["PIC"].fillna("").astype(str).str.strip() != ""]

    if urgent_tasks.empty:
        return _empty_result(), []

    today_scope = active[
        (active["DaysToDue"].fillna(999) <= 0)
        | (active["PriorityScore"].fillna(0) >= 60)
    ].copy()
    impact_scope = active[
        (active["DaysToDue"].fillna(999) <= impact_window_days)
        | (active["PriorityScore"].fillna(0) >= 60)
    ].copy()

    pic_rows: list[dict[str, Any]] = []
    affected_rows: list[dict[str, Any]] = []
    issues: list[Issue] = []

    for pic, urgent_group in urgent_tasks.groupby("PIC"):
        urgent_mh = float(urgent_group["RemainingMH"].fillna(0).sum())
        today_group = today_scope[today_scope["PIC"].astype(str).eq(str(pic))]
        today_total_mh = float(today_group["RemainingMH"].fillna(0).sum())
        ot_mh = max(0.0, today_total_mh - daily_capacity)
        affected = impact_scope[
            impact_scope["PIC"].astype(str).eq(str(pic))
            & ~impact_scope["RowID"].isin(urgent_group["RowID"])
        ].sort_values(["DaysToDue", "PriorityScore"], ascending=[True, False])

        pic_rows.append({
            "PIC": pic,
            "UrgentTasks": len(urgent_group),
            "UrgentRemainingMH": round(urgent_mh, 2),
            "TodayTotalMH": round(today_total_mh, 2),
            "DailyCapacityMH": daily_capacity,
            "EstimatedOTMH": round(ot_mh, 2),
            "AffectedTaskCount": len(affected),
        })

        for _, row in affected.head(5).iterrows():
            affected_rows.append({
                "PIC": pic,
                "UrgentRemainingMH": round(urgent_mh, 2),
                "EstimatedOTMH": round(ot_mh, 2),
                "AffectedRowID": int(row.get("RowID")),
                "AffectedMilestone": row.get("Milestone", ""),
                "AffectedItem": row.get("Item", ""),
                "DaysToDue": row.get("DaysToDue"),
                "RemainingMH": round(float(row.get("RemainingMH", 0) or 0), 2),
                "PriorityScore": int(row.get("PriorityScore", 0) or 0),
            })

        if ot_mh > 0:
            issues.append(Issue(
                row_id=None,
                pic=str(pic),
                milestone="",
                item="",
                severity="High",
                issue_type="Urgent work causes overtime risk",
                category="Urgent Impact",
                evidence=f"{pic} has {urgent_mh:.1f} MH urgent/unplanned work and {today_total_mh:.1f} MH total priority work today, capacity {daily_capacity:.1f} MH.",
                recommendation=f"Confirm priority trade-off, reassign work, or plan about {ot_mh:.1f} MH overtime.",
                suggested_question=f"{pic}: which planned task should move because urgent work consumes capacity today?",
                score_impact=25,
                source="rule",
            ))
        elif len(affected) > 0:
            issues.append(Issue(
                row_id=None,
                pic=str(pic),
                milestone="",
                item="",
                severity="Medium",
                issue_type="Urgent work may displace planned tasks",
                category="Urgent Impact",
                evidence=f"{pic} has {urgent_mh:.1f} MH urgent/unplanned work and {len(affected)} planned task(s) due soon/high priority.",
                recommendation="Confirm what should be paused, moved, or protected today.",
                suggested_question=f"{pic}: does urgent work affect any due-soon planned task?",
                score_impact=15,
                source="rule",
            ))

    result = {
        "pic_summary": pd.DataFrame(pic_rows),
        "urgent_tasks": urgent_tasks.sort_values(["PIC", "PriorityScore"], ascending=[True, False]),
        "affected_tasks": pd.DataFrame(affected_rows),
        "keywords": keywords,
        "impact_window_days": impact_window_days,
    }
    return result, issues


def _empty_result() -> dict[str, Any]:
    return {
        "pic_summary": pd.DataFrame(),
        "urgent_tasks": pd.DataFrame(),
        "affected_tasks": pd.DataFrame(),
        "keywords": DEFAULT_URGENT_KEYWORDS,
        "impact_window_days": 5,
    }
