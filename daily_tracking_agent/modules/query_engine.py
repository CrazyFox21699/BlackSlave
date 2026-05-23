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
        base_answer = build_member_report(selected_pics, prioritized_df, issues, today)
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
        f"Daily brief - {today.strftime('%Y-%m-%d')}",
        f"Open tasks: {len(active)} | High/Critical issues: {len(high_issues)}",
        "",
        "Top actions today",
    ]
    lines.extend(_task_lines(active.head(8)) or ["- No open action found."])
    lines.append("")
    lines.append("Top estimate/scope risks")
    lines.extend(_issue_lines(estimate_issues[:5]) or ["- No major estimate/scope issue found."])
    return "\n".join(lines)


def build_member_report(pics: list[str], prioritized_df: pd.DataFrame, issues: list[Issue], today: datetime) -> str:
    normalized = {p.lower(): p for p in pics}
    mask = prioritized_df["PIC"].astype(str).str.lower().isin(normalized)
    member_df = prioritized_df[mask & (prioritized_df["CurrentProgress"] < 100)].sort_values("PriorityScore", ascending=False)
    member_issues = [i for i in issues if (i.pic or "").lower() in normalized]

    lines = [f"Member work report - {', '.join(pics)} - {today.strftime('%Y-%m-%d')}"]
    for pic in pics:
        pic_df = member_df[member_df["PIC"].astype(str).str.lower() == pic.lower()]
        pic_issues = [i for i in member_issues if (i.pic or "").lower() == pic.lower()]
        high = [i for i in pic_issues if i.severity in {"Critical", "High"}]
        due = pic_df[pic_df["DaysToDue"].fillna(999) <= 0]
        lines.extend([
            "",
            f"{pic}",
            f"- Open tasks: {len(pic_df)} | Due/overdue: {len(due)} | High/Critical issues: {len(high)}",
            "- Today actions:",
        ])
        lines.extend(_task_lines(pic_df.head(6), prefix="  ") or ["  - No open task found."])
        lines.append("- Risks/clarifications:")
        lines.extend(_issue_lines(pic_issues[:5], prefix="  ") or ["  - No major risk found."])
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
    pics = sorted({str(pic).strip() for pic in df["PIC"].dropna().unique() if str(pic).strip()})
    return [pic for pic in pics if re.search(rf"\b{re.escape(pic.lower())}\b", text)]


def _looks_member_question(question: str) -> bool:
    text = question.lower()
    return any(word in text for word in ["lion", "cat", "tiger", "pic", "member", "bạn", "ban", "nhân sự", "nhan su"])


def _task_lines(df: pd.DataFrame, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for _, row in df.iterrows():
        lines.append(
            f"{prefix}- [{row.get('PriorityClass')}] Row {int(row.get('RowID'))}: "
            f"{row.get('Milestone', '')}/{row.get('Item', '')} | {_due_text(row.get('DaysToDue'))} | "
            f"Rem {float(row.get('RemainingMH', 0)):.1f} MH | Progress {float(row.get('CurrentProgress', 0)):.0f}%"
        )
    return lines


def _issue_lines(issues: list[Issue], prefix: str = "") -> list[str]:
    return [
        f"{prefix}- [{issue.severity}] Row {issue.row_id or '-'} {issue.issue_type}: {issue.evidence}"
        for issue in issues
    ]


def _due_text(value: object) -> str:
    if pd.isna(value):
        return "invalid date"
    days = int(value)
    if days < 0:
        return f"overdue {abs(days)}d"
    if days == 0:
        return "due today"
    return f"due in {days}d"
