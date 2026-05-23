from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from modules.data_normalizer import normalize_data
from modules.estimate_analyzer import analyze_estimate_baselines
from modules.excel_loader import load_excel
from modules.logger_setup import setup_logger
from modules.models import AnalysisContext, Issue
from modules.ollama_reviewer import review_with_ollama
from modules.priority_engine import calculate_priorities
from modules.query_engine import answer_tracking_question
from modules.report_builder import build_and_save_reports
from modules.rule_checker import check_rules
from modules.sync_guard import SyncValidationError, wait_for_synced_file
from modules.teams_sender import send_teams_message
from modules.urgent_impact_analyzer import analyze_urgent_impact
from modules.workload_analyzer import analyze_workload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local-first Daily Tracking Control Tool")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Run analysis but do not send Teams message")
    parser.add_argument("--no-teams", action="store_true", help="Disable Teams notification")
    parser.add_argument("--no-ollama", action="store_true", help="Disable Ollama review")
    parser.add_argument("--with-ollama", action="store_true", help="Force-enable local Ollama review/Q&A for this run")
    parser.add_argument("--today", help="Override today date, YYYY-MM-DD")
    parser.add_argument("--ask", help="Ask a local tracking question, for example: 'Lion hôm nay làm gì?'")
    parser.add_argument("--pic", action="append", default=[], help="Filter question/report to one PIC. Can be repeated.")
    parser.add_argument("--send-answer-to-teams", action="store_true", help="Send --ask/--pic answer to Teams webhook.")
    return parser.parse_args()


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    config = load_config(config_path)
    logger = setup_logger(config.get("logs", {}).get("folder", Path(config_path).parent / "logs"))
    logger.info("Daily Tracking Agent started")

    today = datetime.strptime(args.today, "%Y-%m-%d") if args.today else datetime.now()
    base_dir = config_path.parent
    _resolve_relative_paths(config, base_dir)

    if args.with_ollama:
        config.setdefault("ollama", {})["enabled"] = True
    if args.no_ollama:
        config.setdefault("ollama", {})["enabled"] = False
    if args.no_teams or args.dry_run:
        config.setdefault("teams", {})["enabled"] = False

    try:
        result = run_analysis(config, today, logger)
    except SyncValidationError as exc:
        logger.error("Sync validation failed: %s", exc)
        if config.get("teams", {}).get("send_failure_notification", False) and not (args.no_teams or args.dry_run):
            send_teams_message(
                f"Daily Work Control Report failed before Excel analysis.\nReason: {exc}\nNo source Excel data was read.",
                config.get("teams", {}),
                logger,
            )
        return 2
    except Exception as exc:
        logger.exception("Daily report failed after sync validation: %s", exc)
        if config.get("teams", {}).get("send_failure_notification", False) and not (args.no_teams or args.dry_run):
            send_teams_message(
                f"Daily Work Control Report failed after sync validation.\nReason: {exc}\nTemp copy was used; source Excel was not modified.",
                config.get("teams", {}),
                logger,
            )
        return 1

    if args.ask or args.pic:
        question = args.ask or f"Xuất report hôm nay cho {', '.join(args.pic)}"
        answer = answer_tracking_question(
            question,
            result["prioritized_df"],
            result["issues"],
            today,
            config,
            logger,
            pics=args.pic,
        )
        print(answer)
        answer_path = _save_query_answer(answer, config.get("report", {}), today)
        print(f"\nSaved answer: {answer_path}")
        if args.send_answer_to_teams:
            send_teams_message(answer, config.get("teams", {}), logger, force_disabled=args.no_teams or args.dry_run)
        logger.info("Answered local tracking question")
        return 0

    try:
        md_path, xlsx_path, teams_summary = build_and_save_reports(
            result["context"],
            result["issues"],
            result["prioritized_df"],
            result["groups"],
            result["workload"],
            config.get("report", {}),
            result.get("urgent_impact"),
        )
        logger.info("Reports generated: markdown=%s excel=%s", md_path, xlsx_path)
        send_teams_message(teams_summary, config.get("teams", {}), logger, force_disabled=args.no_teams or args.dry_run)
        logger.info("Daily Tracking Agent completed: rows=%s issues=%s", result["context"].row_count, len(result["issues"]))
        return 0
    except Exception as exc:
        logger.exception("Daily report failed while building/sending outputs: %s", exc)
        return 1


def run_analysis(config: dict, today: datetime, logger) -> dict:
    sync = wait_for_synced_file(config["sync"], config.get("temp", {}), logger)
    issues: list[Issue] = list(sync.warnings)
    context = AnalysisContext(
        today=today,
        source_file=sync.source_path,
        source_last_modified=sync.source_last_modified,
    )

    raw_df, metadata = load_excel(sync.temp_path, config.get("excel", {}), logger)
    context.row_count = metadata.row_count
    context.metadata = metadata.model_dump()
    context.metadata.update({
        "max_full_report_issues": config.get("report", {}).get("max_full_report_issues", 30),
        "include_raw_issue_table": config.get("report", {}).get("include_raw_issue_table", False),
    })
    issues.extend(_schema_issues(metadata.missing_required_columns))

    norm_df, column_mapping = normalize_data(raw_df, today.date())
    context.row_count = len(norm_df)
    logger.info("Column mapping: %s", column_mapping)

    issues.extend(check_rules(norm_df, today.date(), config.get("capacity", {})))
    workload, workload_issues = analyze_workload(norm_df, today.date(), config.get("capacity", {}))
    issues.extend(workload_issues)
    issues.extend(analyze_estimate_baselines(norm_df, config.get("estimate_baseline", {})))

    prioritized_df, groups = calculate_priorities(
        norm_df,
        issues,
        config.get("user", {}).get("my_pic_names", []),
        today.date(),
    )
    issues.extend(review_with_ollama(prioritized_df, config.get("ollama", {}), logger))
    prioritized_df, groups = calculate_priorities(
        prioritized_df.drop(columns=["PriorityScore", "PriorityClass"], errors="ignore"),
        issues,
        config.get("user", {}).get("my_pic_names", []),
        today.date(),
    )
    urgent_impact, urgent_issues = analyze_urgent_impact(
        prioritized_df,
        config.get("capacity", {}),
        config.get("urgent", {}),
        today.date(),
    )
    issues.extend(urgent_issues)
    prioritized_df, groups = calculate_priorities(
        prioritized_df.drop(columns=["PriorityScore", "PriorityClass"], errors="ignore"),
        issues,
        config.get("user", {}).get("my_pic_names", []),
        today.date(),
    )
    return {
        "context": context,
        "issues": issues,
        "prioritized_df": prioritized_df,
        "groups": groups,
        "workload": workload,
        "urgent_impact": urgent_impact,
    }


def _schema_issues(missing: list[str]) -> list[Issue]:
    return [
        Issue(
            severity="High",
            issue_type="Missing expected column",
            category="Data Quality",
            evidence=f"Expected column not detected: {col}",
            recommendation="Check workbook schema/header row before using planning results.",
            suggested_question=f"Can we restore or map the missing column '{col}'?",
            score_impact=30,
            source="rule",
        )
        for col in missing
    ]


def _resolve_relative_paths(config: dict, base_dir: Path) -> None:
    for section, key in [("sync", "folder_path"), ("temp", "folder"), ("report", "output_folder"), ("logs", "folder")]:
        value = config.get(section, {}).get(key)
        if value and not Path(value).is_absolute():
            config[section][key] = str((base_dir / value).resolve())


def _save_query_answer(answer: str, report_config: dict, today: datetime) -> Path:
    output = Path(report_config.get("output_folder", "./reports")).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"tracking_query_answer_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.md"
    path.write_text(answer + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
