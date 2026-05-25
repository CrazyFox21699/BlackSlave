from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

from .models import Issue
from .ollama_reviewer import answer_question_with_ollama


def answer_tracking_question(
    question: str,
    prioritized_df: pd.DataFrame,
    issues: list[Issue],
    today: datetime,
    config: dict,
    logger: Any,
    pics: list[str] | None = None,
) -> str:
    selected_pics = pics or _extract_pics(question, prioritized_df)
    if not selected_pics and _looks_member_question(question):
        return "Không tìm thấy PIC/member phù hợp trong tracking file. Thử dùng: `--pic Lion` hoặc `--pic Lion --pic Cat`."

    if selected_pics:
        base_answer = build_member_report(selected_pics, prioritized_df, issues, today, config.get("capacity", {}))
    else:
        base_answer = build_daily_brief(prioritized_df, issues, today)

    ollama_cfg = config.get("ollama", {})
    if ollama_cfg.get("enabled", False):
        refined = answer_question_with_ollama(question, base_answer, ollama_cfg, logger)
        if refined:
            return refined
    return base_answer


def build_daily_brief(prioritized_df: pd.DataFrame, issues: list[Issue], today: datetime) -> str:
    active = prioritized_df[(prioritized_df["CurrentProgress"] < 100)].sort_values("PriorityScore", ascending=False)
    high_issues = [i for i in issues if i.severity in {"Critical", "High"}]
    estimate_issues = [i for i in issues if i.category in {"Estimate", "Breakdown"}]
    lines = [
        f"Tracking quick check - {today.strftime('%Y-%m-%d')}",
        f"Open {len(active)} | High/Critical {len(high_issues)}",
        "",
        "Today:",
    ]
    lines.extend(_task_lines(active.head(5)) or ["- No open action found."])
    lines.append("")
    lines.append("Estimate/scope:")
    lines.extend(_issue_lines(estimate_issues[:3]) or ["- No major estimate/scope issue found."])
    return "\n".join(lines)


def build_member_report(pics: list[str], prioritized_df: pd.DataFrame, issues: list[Issue], today: datetime, capacity: dict | None = None) -> str:
    daily_capacity = float((capacity or {}).get("daily_mh", 8))
    normalized = {_pic_key(p): p for p in pics}
    mask = prioritized_df["PIC"].apply(_pic_key).isin(normalized)
    member_df = prioritized_df[mask & (prioritized_df["CurrentProgress"] < 100)].sort_values("PriorityScore", ascending=False)
    member_issues = [i for i in issues if (i.pic or "").lower() in normalized]

    lines = [f"Quick work check - {', '.join(pics)} - {today.strftime('%Y-%m-%d')}"]
    for pic in pics:
        pic_df = member_df[member_df["PIC"].apply(_pic_key) == _pic_key(pic)]
        pic_issues = [i for i in member_issues if _pic_key(i.pic) == _pic_key(pic)]
        high = [i for i in pic_issues if i.severity in {"Critical", "High"}]
        due = pic_df[pic_df["DaysToDue"].fillna(999) <= 0]
        today_scope = pic_df[(pic_df["DaysToDue"].fillna(999) <= 0) | (pic_df["PriorityScore"] >= 60)].copy()
        today_mh = float(today_scope["RemainingMH"].fillna(0).sum()) if not today_scope.empty else 0.0
        overload = today_mh > daily_capacity
        status = "OVER 8H - re-plan needed" if overload else "OK within 8H"
        delay = f"{len(due)} due/overdue" if len(due) else "no due/overdue"
        lines.extend([
            "",
            f"{pic}: {today_mh:.1f}/{daily_capacity:.1f}h, {status}; {delay}; {len(high)} high risk.",
            "Do today:",
        ])
        lines.extend(_task_lines(today_scope.head(4), prefix="  ", include_done=False) or ["  - No due/high-priority action found."])
        done = _done_lines(today_scope.head(2), prefix="  ")
        if done:
            lines.append("Done means:")
            lines.extend(done)
        risks = _issue_lines(pic_issues[:3], prefix="  ")
        if risks:
            lines.append("Watch:")
            lines.extend(risks)
    return "\n".join(lines)


def member_actions_for_teams(prioritized_df: pd.DataFrame, limit_pics: int = 6, limit_tasks_per_pic: int = 2) -> list[str]:
    active = prioritized_df[
        (prioritized_df["PIC"].fillna("").astype(str).str.strip() != "")
        & (prioritized_df["CurrentProgress"] < 100)
        & ((prioritized_df["DaysToDue"].fillna(999) <= 2) | (prioritized_df["PriorityScore"] >= 60))
    ].sort_values(["PIC", "PriorityScore"], ascending=[True, False])
    lines: list[str] = []
    for pic, group in active.groupby("PIC", sort=True):
        if len(lines) >= limit_pics:
            break
        tasks = []
        for _, row in group.head(limit_tasks_per_pic).iterrows():
            due = _due_text(row.get("DaysToDue"))
            tasks.append(f"{row.get('Milestone', '')}/{row.get('Item', '')} {due} {float(row.get('CurrentProgress', 0)):.0f}%")
        lines.append(f"- {pic}: " + "; ".join(tasks))
    return lines


def _extract_pics(question: str, df: pd.DataFrame) -> list[str]:
    text = question.lower()
    compact_text = _pic_key(question)
    pics = sorted({str(pic).strip() for pic in df["PIC"].dropna().unique() if str(pic).strip()})
    return [
        pic for pic in pics
        if re.search(rf"\b{re.escape(pic.lower())}\b", text) or _pic_key(pic) in compact_text
    ]


def _looks_member_question(question: str) -> bool:
    text = question.lower()
    return any(word in text for word in ["lion", "cat", "tiger", "pic", "member", "bạn", "ban", "nhân sự", "nhan su"])


def _task_lines(df: pd.DataFrame, prefix: str = "", include_done: bool = False) -> list[str]:
    lines: list[str] = []
    for _, row in df.iterrows():
        done_hint = f" | Done: {_done_condition(row)}" if include_done else ""
        lines.append(
            f"{prefix}- Row {int(row.get('RowID'))}: {row.get('Item', '')} | {_due_text(row.get('DaysToDue'))} | "
            f"{float(row.get('RemainingMH', 0)):.1f}h left | {float(row.get('CurrentProgress', 0)):.0f}%"
            f"{done_hint}"
        )
    return lines


def _done_lines(df: pd.DataFrame, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for _, row in df.iterrows():
        lines.append(f"{prefix}- Row {int(row.get('RowID'))}: {_done_condition(row)}")
    return lines


def _done_condition(row: pd.Series) -> str:
    target = _format_target(row.get("Target", ""))
    note = str(row.get("Note", "") or "").strip()
    target_text = target if target and target != "0%" else "agreed target"
    blockers = "no blocker" if not _has_blocker(note) else "blocker owner/date confirmed"
    return f"reach {target_text} or update progress; {blockers}"


def _has_blocker(note: str) -> bool:
    return any(word in note.lower() for word in ["waiting", "pending", "blocked", "block", "tbd", "confirm", "clarify"])


def _format_target(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    if isinstance(value, (int, float)):
        number = float(value)
        if 0 <= number <= 1:
            return f"{number * 100:.0f}%"
        return f"{number:g}"
    text = str(value).strip()
    try:
        number = float(text)
        if 0 <= number <= 1:
            return f"{number * 100:.0f}%"
    except ValueError:
        pass
    return text


def _issue_lines(issues: list[Issue], prefix: str = "") -> list[str]:
    return [f"{prefix}- Row {issue.row_id or '-'}: {issue.issue_type}" for issue in issues]


def _due_text(value: object) -> str:
    if pd.isna(value):
        return "invalid date"
    days = int(value)
    if days < 0:
        return f"overdue {abs(days)}d"
    if days == 0:
        return "due today"
    return f"due in {days}d"


def _pic_key(value: object) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
