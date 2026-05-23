from __future__ import annotations

from datetime import date
from pathlib import Path
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

    urgent_tasks = _detect_urgent_tasks(active, keywords)
    external_tasks = _load_external_urgent_tasks(config, today)
    if not external_tasks.empty:
        urgent_tasks = pd.concat([urgent_tasks, external_tasks], ignore_index=True, sort=False)

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
        planned_today_mh = float(today_group["RemainingMH"].fillna(0).sum())
        today_total_mh = planned_today_mh + urgent_mh
        ot_mh = max(0.0, today_total_mh - daily_capacity)
        affected = impact_scope[
            impact_scope["PIC"].astype(str).eq(str(pic))
            & ~impact_scope["RowID"].isin(urgent_group["RowID"])
        ].sort_values(["DaysToDue", "PriorityScore"], ascending=[True, False])

        pic_rows.append({
            "PIC": pic,
            "UrgentTasks": len(urgent_group),
            "UrgentRemainingMH": round(urgent_mh, 2),
            "PlannedTodayMH": round(planned_today_mh, 2),
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


def build_urgent_short_summary(urgent_impact: dict[str, Any], today: date) -> str:
    summary = urgent_impact.get("pic_summary", pd.DataFrame())
    affected = urgent_impact.get("affected_tasks", pd.DataFrame())
    urgent_tasks = urgent_impact.get("urgent_tasks", pd.DataFrame())
    if summary is None or summary.empty:
        return f"Urgent Impact Update - {today.isoformat()}\n\nNo open urgent/unplanned task found."

    lines = [f"Urgent Impact Update - {today.isoformat()}", ""]
    for _, row in summary.iterrows():
        pic = row.get("PIC")
        urgent_mh = float(row.get("UrgentRemainingMH", 0) or 0)
        planned_mh = float(row.get("PlannedTodayMH", 0) or 0)
        total_mh = float(row.get("TodayTotalMH", 0) or 0)
        cap = float(row.get("DailyCapacityMH", 8) or 8)
        ot = float(row.get("EstimatedOTMH", 0) or 0)
        lines.append(f"{pic}: urgent {urgent_mh:.1f}h + planned {planned_mh:.1f}h = {total_mh:.1f}/{cap:.1f}h -> OT {ot:.1f}h")

        pic_urgent = urgent_tasks[urgent_tasks["PIC"].astype(str).eq(str(pic))] if urgent_tasks is not None and not urgent_tasks.empty else pd.DataFrame()
        for _, urgent in pic_urgent.head(3).iterrows():
            lines.append(f"- urgent: {urgent.get('Item', '')} ({float(urgent.get('RemainingMH', 0) or 0):.1f}h)")

        pic_affected = affected[affected["PIC"].astype(str).eq(str(pic))] if affected is not None and not affected.empty else pd.DataFrame()
        if not pic_affected.empty:
            lines.append("May affect:")
            for _, task in pic_affected.head(3).iterrows():
                lines.append(
                    f"- Row {task.get('AffectedRowID')}: {task.get('AffectedMilestone', '')}/{task.get('AffectedItem', '')}, "
                    f"due {_format_due(task.get('DaysToDue'))}, rem {float(task.get('RemainingMH', 0) or 0):.1f}h"
                )
        lines.append("Decision: reassign/defer affected tasks or accept OT.")
        lines.append("")
    return "\n".join(lines).strip()


def _detect_urgent_tasks(active: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    text = active["TaskText"].fillna("").astype(str).str.lower()
    note = active["Note"].fillna("").astype(str).str.lower()
    urgent_mask = text.apply(lambda value: any(k in value for k in keywords)) | note.apply(lambda value: any(k in value for k in keywords))
    urgent_tasks = active[urgent_mask].copy()
    urgent_tasks = urgent_tasks[urgent_tasks["PIC"].fillna("").astype(str).str.strip() != ""]
    if not urgent_tasks.empty:
        urgent_tasks["UrgentSource"] = "tracking"
    return urgent_tasks


def _load_external_urgent_tasks(config: dict, today: date) -> pd.DataFrame:
    external_file = str(config.get("external_file", "") or "").strip()
    if not external_file:
        return pd.DataFrame()
    path = Path(external_file).expanduser()
    if not path.exists():
        return pd.DataFrame()

    raw = pd.read_csv(path)
    if raw.empty:
        return pd.DataFrame()
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    if "pic" not in raw.columns or "estimate_mh" not in raw.columns or "item" not in raw.columns:
        return pd.DataFrame()

    rows = raw.copy()
    if "status" in rows.columns:
        rows = rows[~rows["status"].fillna("").astype(str).str.lower().isin(["done", "cancelled", "canceled", "closed"])]
    if "date" in rows.columns:
        dates = pd.to_datetime(rows["date"], errors="coerce").dt.date
        rows = rows[dates.isna() | (dates == today)]
    if rows.empty:
        return pd.DataFrame()

    est = pd.to_numeric(rows["estimate_mh"], errors="coerce").fillna(0)
    result = pd.DataFrame({
        "RowID": rows.get("id", pd.Series(range(1, len(rows) + 1))).apply(lambda v: f"urgent-{v}"),
        "PIC": rows["pic"].fillna("").astype(str).str.strip(),
        "Milestone": "Urgent",
        "Item": rows["item"].fillna("").astype(str).str.strip(),
        "Target": rows.get("due", pd.Series(["today"] * len(rows))).fillna("today").astype(str),
        "Note": rows.get("reason", pd.Series([""] * len(rows))).fillna("").astype(str),
        "CurrentProgress": 0.0,
        "RemainingMH": est,
        "DaysToDue": 0,
        "PriorityScore": 100,
        "PriorityClass": "Critical",
        "TaskText": rows["item"].fillna("").astype(str) + " " + rows.get("reason", pd.Series([""] * len(rows))).fillna("").astype(str),
        "UrgentSource": "external",
    })
    return result[result["PIC"].astype(str).str.strip() != ""]


def _format_due(value: object) -> str:
    if pd.isna(value):
        return "invalid date"
    days = int(value)
    if days < 0:
        return f"overdue {abs(days)}d"
    if days == 0:
        return "today"
    return f"in {days}d"


def _empty_result() -> dict[str, Any]:
    return {
        "pic_summary": pd.DataFrame(),
        "urgent_tasks": pd.DataFrame(),
        "affected_tasks": pd.DataFrame(),
        "keywords": DEFAULT_URGENT_KEYWORDS,
        "impact_window_days": 5,
    }
