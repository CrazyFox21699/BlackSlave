from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from .models import Issue


BLOCKING_WORDS = ["waiting", "pending", "block", "blocked", "tbd", "confirm", "clarify"]
COMPLEX_WORDS = [
    "architecture", "design", "interface", "impact analysis", "customer review", "oem review",
    "requirement analysis", "system spec", "specification", "integration", "bring-up",
    "debug", "validation", "migration", "release",
]
ACTION_WORDS = ["update", "review", "analyze", "explain", "align", "test", "fix", "prepare", "implement", "validate"]
SIMPLE_WORDS = ["minor", "typo", "format", "small fix", "comment reply", "documentation clean-up"]
GENERIC_NAMES = ["spec-action", "code-action", "task", "module update", "review", "update"]


def _blank(value: object) -> bool:
    return value is None or pd.isna(value) or str(value).strip() == ""


def _text(row: pd.Series) -> str:
    return str(row.get("TaskText", "")).lower()


def _base_issue(row: pd.Series, severity: str, issue_type: str, category: str, evidence: str, recommendation: str, question: str = "", impact: int = 0) -> Issue:
    return Issue(
        row_id=int(row.get("RowID", 0)) if not pd.isna(row.get("RowID", pd.NA)) else None,
        pic=str(row.get("PIC", "") or ""),
        milestone=str(row.get("Milestone", "") or ""),
        item=str(row.get("Item", "") or ""),
        severity=severity,  # type: ignore[arg-type]
        issue_type=issue_type,
        category=category,
        evidence=evidence,
        recommendation=recommendation,
        suggested_question=question,
        score_impact=impact,
        source="rule",
    )


def check_rules(df: pd.DataFrame, today: date, capacity: dict) -> list[Issue]:
    issues: list[Issue] = []
    today_ts = pd.Timestamp(today)
    daily_mh = float(capacity.get("daily_mh", 8))
    for _, row in df.iterrows():
        cur = float(row.get("CurrentProgress", 0) or 0)
        prev = row.get("PreviousValue")
        delta = row.get("Delta")
        est = row.get("Est")
        start = row.get("StartDatePlan")
        end = row.get("EndDatePlan")
        days_to_due = row.get("DaysToDue")
        planned_daily = row.get("PlannedMHDaily")
        text = _text(row)
        note = str(row.get("Note", "") or "").lower()
        item_milestone = f"{row.get('Item', '')} {row.get('Milestone', '')}".lower()

        if _blank(row.get("PIC")):
            sev = "High" if ((not pd.isna(end) and end <= today_ts) or cur < 100) else "Medium"
            issues.append(_base_issue(row, sev, "Missing PIC", "Data Quality", "PIC is empty.", "Assign a PIC before daily planning.", "Who owns this item?", 30))

        if pd.isna(start) or pd.isna(end):
            issues.append(_base_issue(row, "High", "Invalid planning date", "Data Quality", f"Start={row.get('Raw_StartDatePlan')}, End={row.get('Raw_EndDatePlan')}", "Correct invalid planning date values.", "Can PM/PIC correct the invalid date row?", 30))
        elif start > end:
            issues.append(_base_issue(row, "High", "Invalid schedule", "Data Quality", f"Start date {start.date()} is after end date {end.date()}.", "Fix the planned date range.", "What is the intended schedule?", 30))

        if delta is not None and not pd.isna(delta) and prev is not None and not pd.isna(prev):
            expected_delta = cur - float(prev)
            if abs(float(delta) - expected_delta) > 1:
                issues.append(_base_issue(row, "Medium", "Delta mismatch", "Data Quality", f"Delta={delta:.1f}, expected {expected_delta:.1f}.", "Update Delta or progress values so tracking math is consistent.", "Which progress value is correct?", 10))

        if not pd.isna(end) and end < today_ts and cur < 100:
            issues.append(_base_issue(row, "High", "Overdue", "Schedule", f"End date {end.date()} passed with progress {cur:.0f}%.", "Confirm recovery plan and revised completion date.", "Can PIC confirm recovery plan for overdue item?", 50))
        if not pd.isna(end) and end == today_ts and cur < 100:
            sev = "High" if cur < 80 else "Medium"
            issues.append(_base_issue(row, sev, "Due today not completed", "Schedule", f"Due today with progress {cur:.0f}%.", "Confirm if it can finish today or needs replanning.", "Can this close today?", 40))
        if not pd.isna(days_to_due) and 0 <= float(days_to_due) <= 2 and cur < 50:
            issues.append(_base_issue(row, "High", "Near deadline with low progress", "Schedule", f"Due in {int(days_to_due)} days with progress {cur:.0f}%.", "Escalate blocker or reduce scope.", "What support is needed before deadline?", 25))
        if not pd.isna(start) and start < today_ts and cur == 0:
            sev = "High" if not pd.isna(days_to_due) and float(days_to_due) <= 2 else "Medium"
            issues.append(_base_issue(row, sev, "No progress after planned start", "Schedule", "Planned start has passed but progress is 0%.", "Ask PIC to update progress or blocker.", "Has this task actually started?", 15))
        if not pd.isna(start) and start > today_ts and cur > 0:
            issues.append(_base_issue(row, "Low", "Progress before planned start", "Schedule", f"Progress {cur:.0f}% before planned start {start.date()}.", "Confirm planned dates or actual progress.", "Should planned start be updated?", 5))
        if not pd.isna(planned_daily) and float(planned_daily) > daily_mh:
            issues.append(_base_issue(row, "High", "Unrealistic daily workload", "Schedule", f"Planned {float(planned_daily):.1f} MH/day exceeds capacity {daily_mh:.1f}.", "Adjust dates, effort, or split task.", "Can PM/PIC confirm the schedule is feasible?", 25))

        if prev is not None and not pd.isna(prev) and cur < float(prev):
            issues.append(_base_issue(row, "Medium", "Progress regression", "Progress", f"Current {cur:.0f}% is below previous {float(prev):.0f}%.", "Confirm if regression is real or a data update error.", "Why did progress decrease?", 20))
        if not pd.isna(start) and not pd.isna(end) and start <= today_ts <= end and cur < 100 and (delta is not None and not pd.isna(delta) and float(delta) == 0):
            sev = "High" if not pd.isna(days_to_due) and float(days_to_due) <= 2 else "Medium"
            issues.append(_base_issue(row, sev, "No progress update", "Progress", "Active task has Delta=0.", "Request current status and blocker details.", "What changed since yesterday?", 10))
        if cur == 100 and any(w in note for w in BLOCKING_WORDS):
            issues.append(_base_issue(row, "High", "Completion status conflict", "Progress", f"Progress is 100% but note contains pending/blocking text: {row.get('Note')}", "Clarify whether task is truly complete.", "Is this item done or still waiting?", 20))
        gap = row.get("ProgressGap")
        if gap is not None and not pd.isna(gap) and float(gap) >= 30:
            issues.append(_base_issue(row, "High", "Behind expected progress", "Progress", f"Expected {float(row.get('ExpectedProgressByTime')):.0f}%, actual {cur:.0f}%.", "Confirm recovery plan or revise schedule.", "What is needed to close the progress gap?", 25))

        has_task_text = bool(str(row.get("TaskText", "")).strip())
        if (est is None or pd.isna(est) or float(est) == 0) and has_task_text:
            issues.append(_base_issue(row, "Medium", "Missing estimate", "Estimate", "Estimate is empty or zero.", "Add an MH/SP estimate for planning.", "Can PM/PIC provide estimate?", 10))
        if est is not None and not pd.isna(est):
            est_f = float(est)
            if any(w in text for w in COMPLEX_WORDS) and est_f <= 2:
                issues.append(_base_issue(row, "High", "Possible underestimate", "Estimate", f"Complex system task has Est={est_f:g} MH.", "Recommend PM/PIC confirmation of scope and assumptions.", "Does this estimate include analysis, review, and rework?", 20))
            action_count = sum(1 for w in ACTION_WORDS if w in text)
            if action_count >= 3 and est_f <= 4:
                issues.append(_base_issue(row, "High" if est_f <= 2 else "Medium", "Possible underestimate due to multi-deliverable scope", "Estimate", f"{action_count} action keywords with Est={est_f:g} MH.", "Clarify deliverables or split scope.", "Are multiple hidden deliverables included?", 20))
            if any(w in text for w in SIMPLE_WORDS) and est_f >= 16:
                issues.append(_base_issue(row, "Medium", "Possible overestimate", "Estimate", f"Simple task wording with Est={est_f:g} MH.", "Confirm if scope includes more than a minor update.", "What work is included in this estimate?", 8))
            if est_f >= 40 and any(name == item_milestone.strip() or name in item_milestone for name in GENERIC_NAMES):
                issues.append(_base_issue(row, "High", "Estimate may be over-aggregated", "Estimate", f"Generic task name with Est={est_f:g} MH.", "Split into smaller controllable items.", "Can PM confirm whether this includes multiple hidden sub-tasks?", 15))
            if est_f >= 16:
                issues.append(_base_issue(row, "High" if est_f >= 40 else "Medium", "Task too large", "Breakdown", f"Est={est_f:g} MH.", "Consider splitting into smaller items with measurable targets.", "Can this be broken down for daily control?", 10))
            if est_f >= 8 and any(name in item_milestone for name in GENERIC_NAMES):
                issues.append(_base_issue(row, "Medium", "Unclear task scope", "Breakdown", "Large estimate with generic item/milestone.", "Clarify task scope and acceptance criteria.", "What exact deliverable will close this item?", 10))
            if est_f >= 16 and cur < 30 and not pd.isna(days_to_due) and float(days_to_due) <= 2:
                issues.append(_base_issue(row, "High", "Large task at delay risk", "Estimate", f"Est={est_f:g} MH, progress={cur:.0f}%, due in {int(days_to_due)} days.", "Confirm recovery plan or replan scope/date.", "What is the realistic finish plan?", 20))

        if str(row.get("Target", "")).strip() == "100%" and not str(row.get("Note", "")).strip() and any(name in item_milestone for name in GENERIC_NAMES):
            issues.append(_base_issue(row, "Medium", "Target not measurable", "Breakdown", "Target is only 100% and task name is generic.", "Define concrete deliverable or acceptance criteria.", "What does 100% mean for this task?", 10))
        if any(w in note for w in ["waiting", "blocked", "pending", "clarify", "confirm"]) and delta is not None and not pd.isna(delta) and float(delta) > 0:
            issues.append(_base_issue(row, "Medium", "Progress increased despite dependency", "Dependency", f"Note suggests dependency but Delta={float(delta):.0f}%.", "Clarify what progressed and what remains blocked.", "Which part is still blocked?", 10))
        if any(w in note for w in ["waiting", "blocked", "pending"]) and not _has_recovery_detail(note):
            issues.append(_base_issue(row, "High", "Blocked item without recovery action", "Dependency", f"Note lacks clear owner/action/date: {row.get('Note')}", "Add owner, next action, and expected recovery date.", "Who owns the recovery action and by when?", 25))
    return issues


def _has_recovery_detail(note: str) -> bool:
    has_date = bool(pd.Series([note]).str.contains(r"\d{1,2}[-/]\d{1,2}|\d{4}").iloc[0])
    has_owner_hint = any(token in note for token in [" by ", " owner", " pic", "@", " with "])
    has_action = any(token in note for token in ["ask", "confirm", "follow", "align", "send", "review", "reply"])
    return has_date and has_owner_hint and has_action
