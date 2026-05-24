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
    urgent_impact: dict[str, Any] | None = None,
) -> str:
    high = [i for i in issues if i.severity in {"Critical", "High"}]
    due_overdue = prioritized_df[(prioritized_df["CurrentProgress"] < 100) & (prioritized_df["DaysToDue"].fillna(999) <= 0)]
    my_focus = groups["my_focus"].head(int(report_config.get("max_my_focus_items", 5)))
    max_items = int(report_config.get("max_teams_issues", 3))
    dq = [i for i in issues if i.category == "Data Quality"]
    questions = _first_nonempty(groups.get("questions_pm", []) + groups.get("follow_member", []) + groups.get("cleanup", []), 3)
    source_time = context.source_last_modified.strftime("%H:%M %Y-%m-%d") if context.source_last_modified else "unknown"
    replan = _replan_needed(issues, prioritized_df, workload, max_items)
    data_fix = _data_fix(issues, max_items)
    urgent_lines = _urgent_impact_lines(urgent_impact, max_items)
    confidence, confidence_reason = _report_confidence(issues)
    overloaded = _overloaded_pics(workload)
    member_lines = member_actions_for_teams(prioritized_df, limit_pics=5, limit_tasks_per_pic=1)

    lines = [
        f"Daily tracking - {context.today.strftime('%Y-%m-%d')}",
        f"Rows {context.row_count} | High {len(high)} | Due/overdue {len(due_overdue)} | Overloaded {len(overloaded)} | Confidence {confidence}",
        f"Source: {source_time} ({confidence_reason})",
        "",
        "My focus",
    ]
    lines.extend(_task_lines(my_focus, min(int(report_config.get("max_my_focus_items", 3)), 3)) or ["- No active high-priority personal focus item found."])
    lines.append("")
    lines.append("Members")
    lines.extend(member_lines or ["- No urgent member action found."])
    lines.append("")
    lines.append("Re-plan")
    lines.extend(replan or ["- No urgent re-plan item found."])
    if urgent_lines:
        lines.append("")
        lines.append("Urgent/OT")
        lines.extend(urgent_lines)
    if data_fix:
        lines.append("")
        lines.append("Data fix")
        lines.extend(data_fix)
    if questions:
        lines.append("")
        lines.append("Ask")
        lines.extend([f"- {q}" for q in questions[:2]])
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
    urgent_impact: dict[str, Any] | None = None,
) -> tuple[Path, Path | None, str]:
    output = Path(report_config.get("output_folder", "./reports")).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    stamp = context.today.strftime("%Y%m%d_%H%M%S")
    md_path = output / f"daily_tracking_report_{stamp}.md"
    xlsx_path = output / f"daily_tracking_report_{stamp}.xlsx"
    context.report_markdown_path = md_path
    context.report_excel_path = xlsx_path

    teams_summary = build_teams_summary(context, issues, prioritized_df, groups, workload, report_config, urgent_impact)
    issues_df = issue_frame(issues)
    md = _full_markdown(context, issues_df, prioritized_df, groups, workload, teams_summary, report_config, urgent_impact)
    md_path.write_text(md, encoding="utf-8")

    excel_path: Path | None = None
    if report_config.get("write_excel", True):
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            _summary_df(context, issues, prioritized_df, groups).to_excel(writer, index=False, sheet_name="Summary")
            groups["my_focus"].to_excel(writer, index=False, sheet_name="MyFocusToday")
            groups["team_actions"].to_excel(writer, index=False, sheet_name="TeamActions")
            issues_df.to_excel(writer, index=False, sheet_name="Issues")
            workload.to_excel(writer, index=False, sheet_name="WorkloadByPIC")
            if urgent_impact and not urgent_impact.get("pic_summary", pd.DataFrame()).empty:
                urgent_impact["pic_summary"].to_excel(writer, index=False, sheet_name="UrgentImpact")
                urgent_impact["affected_tasks"].to_excel(writer, index=False, sheet_name="UrgentAffected")
            issues_df[issues_df["category"].eq("Data Quality")].to_excel(writer, index=False, sheet_name="DataQuality")
            prioritized_df.to_excel(writer, index=False, sheet_name="RawNormalizedData")
        excel_path = xlsx_path
    return md_path, excel_path, teams_summary


def _full_markdown(context: AnalysisContext, issues_df: pd.DataFrame, df: pd.DataFrame, groups: dict[str, Any], workload: pd.DataFrame, teams_summary: str, report_config: dict, urgent_impact: dict[str, Any] | None = None) -> str:
    max_issues = int(report_config.get("max_full_report_issues", 30))
    sections = [
        f"# Daily Work Control Report - {context.today.strftime('%Y-%m-%d')}",
        "## Executive Summary",
        teams_summary,
        "## Today Commitment",
        "\n".join(member_actions_for_teams(df, limit_pics=20, limit_tasks_per_pic=3)) or "No urgent member action found.",
        "## Re-plan Needed",
        "\n".join(_replan_needed_from_frames(issues_df, df, workload, 30)) or "No urgent re-plan item found.",
        "## Urgent Impact / OT",
        _urgent_impact_md(urgent_impact),
        "## Blockers",
        "\n".join(_blockers_from_frame(issues_df, 30)) or "No blocker found.",
        "## Data Quality Must Fix",
        "\n".join(_data_fix_from_frame(issues_df, 30)) or "No urgent data quality fix found.",
        "## Workload Heatmap",
        _workload_heatmap_md(workload),
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


def _replan_needed(issues: list[Issue], df: pd.DataFrame, workload: pd.DataFrame, limit: int) -> list[str]:
    issues_df = issue_frame(issues)
    return _replan_needed_from_frames(issues_df, df, workload, limit)


def _replan_needed_from_frames(issues_df: pd.DataFrame, df: pd.DataFrame, workload: pd.DataFrame, limit: int) -> list[str]:
    lines: list[str] = []
    for _, row in _overloaded_pics(workload).head(limit).iterrows():
        lines.append(f"- {row.get('PIC')}: workload {float(row.get('RemainingMHToday', 0)):.1f} MH today, reassign/split/re-prioritize.")
    if not issues_df.empty:
        replan_types = {
            "Overdue", "Due today not completed", "Unrealistic daily workload",
            "Estimate may be over-aggregated", "Task too large", "Unclear task scope",
            "Large task at delay risk",
        }
        part = issues_df[issues_df["issue_type"].isin(replan_types)].head(limit)
        for _, issue in part.iterrows():
            lines.append(f"- Row {_cell(issue, 'row_id')}: [{_cell(issue, 'severity')}] {_cell(issue, 'pic') or 'Unassigned'} {_cell(issue, 'issue_type')} - {_shorten(_cell(issue, 'evidence'), 100)}")
    return _dedupe_lines(lines)[:limit]


def _blockers(issues: list[Issue], limit: int) -> list[str]:
    return _blockers_from_frame(issue_frame(issues), limit)


def _blockers_from_frame(issues_df: pd.DataFrame, limit: int) -> list[str]:
    if issues_df.empty:
        return []
    mask = (
        issues_df["issue_type"].astype(str).str.contains("Blocked|dependency", case=False, na=False)
        | issues_df["evidence"].astype(str).str.contains("waiting|blocked|pending|TBD|confirm|clarify", case=False, na=False)
    )
    return [
        f"- Row {_cell(row, 'row_id')}: [{_cell(row, 'severity')}] {_cell(row, 'pic') or 'Unassigned'} {_cell(row, 'issue_type')} - {_shorten(_cell(row, 'evidence'), 110)}"
        for _, row in issues_df[mask].head(limit).iterrows()
    ]


def _data_fix(issues: list[Issue], limit: int) -> list[str]:
    return _data_fix_from_frame(issue_frame(issues), limit)


def _data_fix_from_frame(issues_df: pd.DataFrame, limit: int) -> list[str]:
    if issues_df.empty:
        return []
    part = issues_df[issues_df["category"].isin(["Data Quality", "Sync"])].head(limit)
    return [
        f"- Row {_cell(row, 'row_id')}: [{_cell(row, 'severity')}] {_cell(row, 'issue_type')} - {_shorten(_cell(row, 'evidence'), 110)}"
        for _, row in part.iterrows()
    ]


def _workload_heatmap_md(workload: pd.DataFrame) -> str:
    if workload is None or workload.empty:
        return "No workload data."
    rows = workload.copy()
    rows["DailyStatus"] = rows["RemainingMHToday"].apply(lambda v: "OVER" if float(v or 0) > 8 else "OK")
    rows["WeeklyStatus"] = rows["RemainingMHWeek"].apply(lambda v: "OVER" if float(v or 0) > 40 else "OK")
    return _df_md(rows, ["PIC", "ActiveTasks", "DueToday", "Overdue", "RemainingMHToday", "DailyStatus", "RemainingMHWeek", "WeeklyStatus"])


def _urgent_impact_lines(urgent_impact: dict[str, Any] | None, limit: int) -> list[str]:
    if not urgent_impact:
        return []
    summary = urgent_impact.get("pic_summary", pd.DataFrame())
    affected = urgent_impact.get("affected_tasks", pd.DataFrame())
    if summary is None or summary.empty:
        return []
    lines: list[str] = []
    for _, row in summary.head(limit).iterrows():
        lines.append(
            f"- {row.get('PIC')}: urgent {float(row.get('UrgentRemainingMH', 0)):.1f} MH, "
            f"today total {float(row.get('TodayTotalMH', 0)):.1f}/{float(row.get('DailyCapacityMH', 8)):.1f} MH, "
            f"OT {float(row.get('EstimatedOTMH', 0)):.1f} MH, affected tasks {int(row.get('AffectedTaskCount', 0))}"
        )
        if affected is not None and not affected.empty:
            top = affected[affected["PIC"].astype(str).eq(str(row.get("PIC")))].head(2)
            for _, item in top.iterrows():
                lines.append(
                    f"  - may affect Row {item.get('AffectedRowID')}: {item.get('AffectedMilestone', '')}/{item.get('AffectedItem', '')}, "
                    f"due {_format_days_to_due(item.get('DaysToDue'))}, rem {float(item.get('RemainingMH', 0)):.1f} MH"
                )
    return lines[: max(limit * 3, limit)]


def _urgent_impact_md(urgent_impact: dict[str, Any] | None) -> str:
    if not urgent_impact:
        return "No urgent/unplanned work detected from tracking keywords."
    summary = urgent_impact.get("pic_summary", pd.DataFrame())
    urgent_tasks = urgent_impact.get("urgent_tasks", pd.DataFrame())
    affected = urgent_impact.get("affected_tasks", pd.DataFrame())
    if summary is None or summary.empty:
        return "No urgent/unplanned work detected from tracking keywords."
    sections = [
        "### Summary",
        _df_md(summary, ["PIC", "UrgentTasks", "UrgentRemainingMH", "TodayTotalMH", "DailyCapacityMH", "EstimatedOTMH", "AffectedTaskCount"]),
        "### Urgent / Unplanned Tasks",
        _df_md(urgent_tasks, ["RowID", "PIC", "Milestone", "Item", "DaysToDue", "RemainingMH", "CurrentProgress", "PriorityScore", "Note"]),
        "### Potentially Affected Planned Tasks",
        _df_md(affected, ["PIC", "AffectedRowID", "AffectedMilestone", "AffectedItem", "DaysToDue", "RemainingMH", "PriorityScore", "EstimatedOTMH"]),
    ]
    return "\n\n".join(sections)


def _format_days_to_due(value: object) -> str:
    if pd.isna(value):
        return "invalid date"
    days = int(value)
    if days < 0:
        return f"overdue {abs(days)}d"
    if days == 0:
        return "today"
    return f"in {days}d"


def _overloaded_pics(workload: pd.DataFrame) -> pd.DataFrame:
    if workload is None or workload.empty or "RemainingMHToday" not in workload.columns:
        return pd.DataFrame()
    return workload[workload["RemainingMHToday"].fillna(0) > 8].sort_values("RemainingMHToday", ascending=False)


def _report_confidence(issues: list[Issue]) -> tuple[str, str]:
    data_quality_count = len([i for i in issues if i.category in {"Data Quality", "Sync"}])
    critical_quality = len([i for i in issues if i.category in {"Data Quality", "Sync"} and i.severity in {"Critical", "High"}])
    if critical_quality >= 3 or data_quality_count >= 8:
        return "Low", f"{data_quality_count} data/sync issues, {critical_quality} high/critical"
    if critical_quality or data_quality_count >= 3:
        return "Medium", f"{data_quality_count} data/sync issues"
    return "High", "no major data quality issue found"


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


def _cell(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    if pd.isna(value):
        return ""
    return str(value)


def _dedupe_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        if line and line not in result:
            result.append(line)
    return result


def _first_nonempty(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result
