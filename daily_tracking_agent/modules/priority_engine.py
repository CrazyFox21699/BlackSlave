from __future__ import annotations

from datetime import date

import pandas as pd

from .models import Issue


ESTIMATE_RISK_TYPES = {
    "Possible underestimate": 20,
    "Estimate may be over-aggregated": 15,
    "Possible overestimate": 8,
    "Possible overestimate or aggregated scope": 15,
}


def calculate_priorities(df: pd.DataFrame, issues: list[Issue], my_pic_names: list[str], today: date) -> tuple[pd.DataFrame, dict[str, pd.DataFrame | list[str]]]:
    result = df.copy()
    row_issue_types: dict[int, set[str]] = {}
    for issue in issues:
        try:
            rid = int(issue.row_id) if issue.row_id is not None else None
        except (TypeError, ValueError):
            rid = None
        if rid is not None:
            row_issue_types.setdefault(rid, set()).add(issue.issue_type)

    scores: list[int] = []
    for _, row in result.iterrows():
        score = 0
        days = row.get("DaysToDue")
        if not pd.isna(days):
            d = int(days)
            if d < 0:
                score += 50
            elif d == 0:
                score += 40
            elif d == 1:
                score += 30
            elif d == 2:
                score += 20
            elif 3 <= d <= 5:
                score += 10
        cur = float(row.get("CurrentProgress", 0) or 0)
        if cur < 30:
            score += 25
        elif cur < 60:
            score += 15
        elif cur < 80:
            score += 8
        delta = row.get("Delta")
        if delta is not None and not pd.isna(delta) and float(delta) == 0 and _active(row, today):
            score += 10
        prev = row.get("PreviousValue")
        if prev is not None and not pd.isna(prev) and cur < float(prev):
            score += 20
        remaining = float(row.get("RemainingMH", 0) or 0)
        if remaining >= 16:
            score += 20
        elif remaining >= 8:
            score += 15
        elif remaining >= 4:
            score += 8
        for issue_type in row_issue_types.get(int(row["RowID"]), set()):
            score += ESTIMATE_RISK_TYPES.get(issue_type, 0)
            if issue_type == "Invalid planning date":
                score += 30
            elif issue_type == "Missing PIC":
                score += 30
            elif issue_type == "Missing estimate":
                score += 10
        note = str(row.get("Note", "")).lower()
        if "blocked" in note or "block" in note:
            score += 25
        elif "waiting" in note:
            score += 15
        elif any(w in note for w in ["tbd", "confirm"]):
            score += 10
        text = str(row.get("TaskText", "")).lower()
        if any(w in text for w in ["architecture", "system spec", "requirement", "interface", "integration", "impact analysis"]):
            score += 15
        elif any(w in text for w in ["code", "test"]):
            score += 8
        scores.append(score)
    result["PriorityScore"] = scores
    result["PriorityClass"] = result["PriorityScore"].apply(_priority_class)

    my_names = {_pic_key(n) for n in my_pic_names if str(n).strip()}
    active = result[(result["CurrentProgress"] < 100) & result.apply(lambda r: _active_or_due(r, today), axis=1)].copy()
    my_focus = active[active["PIC"].apply(_pic_key).isin(my_names)].sort_values("PriorityScore", ascending=False)
    team_actions = active[
        (active["DaysToDue"].fillna(999) <= 0) | (active["PriorityClass"].isin(["High", "Critical"]))
    ].sort_values(["PIC", "PriorityScore"], ascending=[True, False])
    questions_pm = [i.suggested_question for i in issues if i.category in {"Estimate", "Breakdown"} and i.suggested_question]
    follow_member = [i.suggested_question for i in issues if i.category in {"Schedule", "Progress"} and i.suggested_question]
    cleanup = [i.suggested_question for i in issues if i.category == "Data Quality" and i.suggested_question]
    return result, {
        "my_focus": my_focus,
        "team_actions": team_actions,
        "questions_pm": _dedupe(questions_pm),
        "follow_member": _dedupe(follow_member),
        "cleanup": _dedupe(cleanup),
    }


def _priority_class(score: int) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _active(row: pd.Series, today: date) -> bool:
    t = pd.Timestamp(today)
    start = row.get("StartDatePlan")
    end = row.get("EndDatePlan")
    return not pd.isna(start) and not pd.isna(end) and start <= t <= end and float(row.get("CurrentProgress", 0) or 0) < 100


def _active_or_due(row: pd.Series, today: date) -> bool:
    t = pd.Timestamp(today)
    start = row.get("StartDatePlan")
    end = row.get("EndDatePlan")
    if pd.isna(start) or pd.isna(end):
        return True
    return start <= t or end <= t


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _pic_key(value: object) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
