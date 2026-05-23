from __future__ import annotations

from datetime import date

import pandas as pd

from .models import Issue


def analyze_workload(df: pd.DataFrame, today: date, capacity: dict) -> tuple[pd.DataFrame, list[Issue]]:
    today_ts = pd.Timestamp(today)
    week_end = today_ts + pd.Timedelta(days=6 - today_ts.weekday())
    active = df[
        (df["PIC"].fillna("").astype(str).str.strip() != "")
        & (df["CurrentProgress"] < 100)
        & (df["StartDatePlan"].isna() | (df["StartDatePlan"] <= week_end))
        & (df["EndDatePlan"].isna() | (df["EndDatePlan"] >= today_ts) | (df["EndDatePlan"] < today_ts))
    ].copy()

    if active.empty:
        return pd.DataFrame(columns=["PIC", "ActiveTasks", "DueToday", "Overdue", "RemainingMHWeek", "RemainingMHToday"]), []

    due_today_mask = active["EndDatePlan"] == today_ts
    overdue_mask = active["EndDatePlan"] < today_ts
    due_week_mask = active["EndDatePlan"].between(today_ts, week_end, inclusive="both") | overdue_mask

    summary = active.groupby("PIC", dropna=False).agg(
        ActiveTasks=("RowID", "count"),
        RemainingMHWeek=("RemainingMH", "sum"),
    ).reset_index()
    summary["DueToday"] = active[due_today_mask].groupby("PIC")["RowID"].count().reindex(summary["PIC"]).fillna(0).astype(int).values
    summary["Overdue"] = active[overdue_mask].groupby("PIC")["RowID"].count().reindex(summary["PIC"]).fillna(0).astype(int).values
    summary["RemainingMHToday"] = active[due_today_mask | overdue_mask].groupby("PIC")["RemainingMH"].sum().reindex(summary["PIC"]).fillna(0).values
    summary["TasksDueThisWeek"] = active[due_week_mask].groupby("PIC")["RowID"].count().reindex(summary["PIC"]).fillna(0).astype(int).values

    daily_cap = float(capacity.get("daily_mh", 8))
    weekly_cap = float(capacity.get("weekly_mh", 40))
    issues: list[Issue] = []
    for _, row in summary.iterrows():
        pic = str(row["PIC"])
        if float(row["RemainingMHToday"]) > daily_cap:
            issues.append(_issue(pic, "High", "Daily overload", f"{pic} has {float(row['RemainingMHToday']):.1f} MH due/overdue today, capacity {daily_cap:.1f}.", "Rebalance work, move dates, or reduce same-day scope.", "Can workload be redistributed today?", 25))
        if float(row["RemainingMHWeek"]) > weekly_cap:
            issues.append(_issue(pic, "High", "Weekly overload", f"{pic} has {float(row['RemainingMHWeek']):.1f} remaining MH this week, capacity {weekly_cap:.1f}.", "Confirm priorities and redistribute lower-priority work.", "Which tasks can be deferred or reassigned?", 25))
        if int(row["DueToday"]) >= 3:
            sev = "High" if float(row["RemainingMHToday"]) > daily_cap else "Medium"
            issues.append(_issue(pic, sev, "Too many due tasks for one PIC", f"{pic} has {int(row['DueToday'])} tasks due today.", "Confirm closure order and move non-critical work if needed.", "Which due-today items are truly must-close?", 15))
        if int(row["ActiveTasks"]) >= 5:
            issues.append(_issue(pic, "Medium", "Too many parallel tasks", f"{pic} has {int(row['ActiveTasks'])} active tasks.", "Reduce parallel work or clarify priority order.", "What is the top priority for this PIC today?", 10))
    return summary, issues


def _issue(pic: str, severity: str, issue_type: str, evidence: str, recommendation: str, question: str, impact: int) -> Issue:
    return Issue(
        row_id=None,
        pic=pic,
        milestone="",
        item="",
        severity=severity,  # type: ignore[arg-type]
        issue_type=issue_type,
        category="Workload",
        evidence=evidence,
        recommendation=recommendation,
        suggested_question=question,
        score_impact=impact,
        source="rule",
    )
