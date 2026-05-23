from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .models import AnalysisContext, Issue
from .query_engine import member_actions_for_teams


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def issue_frame(issues: list[Issue]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=list(Issue.model_fields.keys()))
    df = pd.DataFrame([i.model_dump() for i in issues])
    df["severity_rank"] = df["severity"].map(SEVERITY_ORDER).fillna(9)
    return df.sort_values(["severity_rank", "category", "row_id"]).drop(columns=["severity_rank"])


def build_teams_summary(
    context: AnalysisContext,
    issues: list[Issue],
    prioritized_df: pd.DataFrame,
    groups: dict[str, Any],
    workload: pd.DataFrame,
    report_config: dict,
) -> str:
    high = [i for i in issues if i.severity in {"Critical", "High"}]
    due_overdue = prioritized_df[(prioritized_df["CurrentProgress"] < 100) & (prioritized_df["DaysToDue"].fillna(999) <= 0)]
    my_focus = groups["my_focus"].head(int(report_config.get("max_my_focus_items", 5)))
    max_items = int(report_config.get("max_teams_issues", 3))
    estimate = [i for i in issues if i.category in {"Estimate", "Breakdown"}][:max_items]
    dq = [i for i in issues if i.category == "Data Quality"][:max_items]
    delay = [i for i in issues if i.category in {"Schedule", "Workload"} and i.severity in {"Critical", "High"}][:max_items]
    questions = _first_nonempty(groups.get("questions_pm", []) + groups.get("follow_member", []) + groups.get("cleanup", []), 3)
    source_time = context.source_last_modified.strftime("%H:%M %Y-%m-%d") if context.source_last_modified else "unknown"

    lines = [
        f"Daily Work Control - {context.today.strftime('%Y-%m-%d')}",
        f"Rows {context.row_count} | High/Critical {len(high)} | My focus {len(groups['my_focus'])} | Due/overdue {len(due_overdue)}",
        f"Source modified: {source_time}",
        "",
        "My focus",
    ]
    lines.extend(_task_lines(my_focus, int(report_config.get("max_my_focus_items", 3))) or ["- No active high-priority personal focus item found."])
    lines.append("")
    lines.append("Team risks")
    lines.extend([f"- [{i.severity}] {i.pic or 'Unassigned'}: {i.issue_type} ({_shorten(i.evidence, 80)})" for i in delay] or ["- No major team delay risk found by rules."])
    lines.append("")
    lines.append("Member actions today")
    lines.extend(member_actions_for_teams(prioritized_df) or ["- No urgent member action found."])
    lines.append("")
    lines.append("Estimate/data")
    estimate_data = estimate + dq
    lines.extend([f"- [{i.severity}] Row {i.row_id or '-'} {i.issue_type}: {_shorten(i.evidence, 90)}" for i in estimate_data[:max_items]] or ["- No major estimate/data issue found."])
    lines.append("")
    lines.append("Daily questions")
    lines.extend([f"- {q}" for q in questions] or ["- Confirm top priorities, blockers, and recovery plans for due/overdue items."])
    lines.append("")
    lines.append(f"Full report: {context.report_markdown_path or 'not generated'}")
    return "\n".join(lines)


def build_and_save_reports(
    context: AnalysisContext,
    issues: list[Issue],
    prioritized_df: pd.DataFrame,
    groups: dict[str, Any],
    workload: pd.DataFrame,
    report_config: dict,
) -> tuple[Path, Path | None, str]:
    output = Path(report_config.get("output_folder", "./reports")).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    stamp = context.today.strftime("%Y%m%d_%H%M%S")
    md_path = output / f"daily_tracking_report_{stamp}.md"
    xlsx_path = output / f"daily_tracking_report_{stamp}.xlsx"
    context.report_markdown_path = md_path
    context.report_excel_path = xlsx_path

    teams_summary = build_teams_summary(context, issues, prioritized_df, groups, workload, report_config)
    issues_df = issue_frame(issues)
    md = _full_markdown(context, issues_df, prioritized_df, groups, workload, teams_summary, report_config)
    md_path.write_text(md, encoding="utf-8")

    excel_path: Path | None = None
    if report_config.get("write_excel", True):
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            _summary_df(context, issues, prioritized_df, groups).to_excel(writer, index=False, sheet_name="Summary")
            groups["my_focus"].to_excel(writer, index=False, sheet_name="MyFocusToday")
            groups["team_actions"].to_excel(writer, index=False, sheet_name="TeamActions")
            issues_df.to_excel(writer, index=False, sheet_name="Issues")
            workload.to_excel(writer, index=False, sheet_name="WorkloadByPIC")
            issues_df[issues_df["category"].eq("Data Quality")].to_excel(writer, index=False, sheet_name="DataQuality")
            prioritized_df.to_excel(writer, index=False, sheet_name="RawNormalizedData")
        excel_path = xlsx_path
    return md_path, excel_path, teams_summary


def _full_markdown(context: AnalysisContext, issues_df: pd.DataFrame, df: pd.DataFrame, groups: dict[str, Any], workload: pd.DataFrame, teams_summary: str, report_config: dict) -> str:
    max_issues = int(report_config.get("max_full_report_issues", 30))
    sections = [
        f"# Daily Work Control Report - {context.today.strftime('%Y-%m-%d')}",
        "## Executive Summary",
        teams_summary,
        "## My Focus Today",
        _df_md(groups["my_focus"].head(20), ["RowID", "PIC", "Milestone", "Item", "DaysToDue", "RemainingMH", "CurrentProgress", "PriorityScore", "PriorityClass"]),
        "## Team Actions by PIC",
        _df_md(groups["team_actions"].head(20), ["RowID", "PIC", "Milestone", "Item", "DaysToDue", "RemainingMH", "CurrentProgress", "PriorityScore", "PriorityClass"]),
        "## Delay Risks",
        _issue_md(issues_df, ["Schedule", "Progress"], max_issues),
        "## Estimate Concerns",
        _issue_md(issues_df, ["Estimate", "Breakdown"], max_issues),
        "## Workload Overload",
        _df_md(workload, list(workload.columns)),
        "## Data Quality Issues",
        _issue_md(issues_df, ["Data Quality", "Sync"], max_issues),
        "## Ollama Review Comments",
        _issue_md(issues_df, ["Ollama Review"], max_issues),
        "## Suggested Daily Meeting Questions",
        "\n".join(f"- {q}" for q in _first_nonempty(groups.get("questions_pm", []) + groups.get("follow_member", []) + groups.get("cleanup", []), 10)) or "- No specific questions generated.",
    ]
    if context.metadata.get("include_raw_issue_table", False):
        sections.extend(["## Raw Issue Table", _df_md(issues_df.head(max_issues), list(issues_df.columns))])
    return "\n\n".join(sections) + "\n"


def _summary_df(context: AnalysisContext, issues: list[Issue], df: pd.DataFrame, groups: dict[str, Any]) -> pd.DataFrame:
    high = len([i for i in issues if i.severity in {"Critical", "High"}])
    return pd.DataFrame([
        {"Metric": "ReportDate", "Value": context.today.strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "RowsChecked", "Value": context.row_count},
        {"Metric": "IssueCount", "Value": len(issues)},
        {"Metric": "CriticalHighIssues", "Value": high},
        {"Metric": "MyFocusItems", "Value": len(groups["my_focus"])},
        {"Metric": "TeamDueOverdueTasks", "Value": int(((df["CurrentProgress"] < 100) & (df["DaysToDue"].fillna(999) <= 0)).sum())},
    ])


def _task_lines(df: pd.DataFrame, limit: int) -> list[str]:
    lines: list[str] = []
    for _, row in df.head(limit).iterrows():
        due = "Invalid date" if pd.isna(row.get("DaysToDue")) else ("Overdue" if int(row["DaysToDue"]) < 0 else f"Due in {int(row['DaysToDue'])}d")
        lines.append(f"- [{row.get('PriorityClass')}] {row.get('PIC', '')} | {row.get('Milestone', '')}/{row.get('Item', '')} | {due} | Rem {float(row.get('RemainingMH', 0)):.1f} MH | {float(row.get('CurrentProgress', 0)):.0f}%")
    return lines


def _issue_md(issues_df: pd.DataFrame, categories: list[str], limit: int = 30) -> str:
    if issues_df.empty:
        return "No issues."
    part = issues_df[issues_df["category"].isin(categories)].head(limit)
    return _df_md(part, ["row_id", "pic", "milestone", "item", "severity", "issue_type", "evidence", "recommendation", "suggested_question"])


def _df_md(df: pd.DataFrame, columns: list[str]) -> str:
    if df is None or df.empty:
        return "No rows."
    existing = [c for c in columns if c in df.columns]
    safe = df[existing].copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")
    return safe.to_markdown(index=False)


def _shorten(text: str, limit: int) -> str:
    value = " ".join(str(text).split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _first_nonempty(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result
