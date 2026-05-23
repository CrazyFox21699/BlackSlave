from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from .models import Issue, SyncResult


class SyncValidationError(RuntimeError):
    """Raised when the local OneDrive-synced source is not ready."""


def wait_for_synced_file(sync_config: dict, temp_config: dict, logger: logging.Logger) -> SyncResult:
    folder = Path(sync_config["folder_path"]).expanduser()
    tracking_file = sync_config["tracking_file"]
    wait_seconds = int(sync_config.get("wait_sync_seconds", 90))
    retry_seconds = max(1, int(sync_config.get("retry_interval_seconds", 5)))
    max_age_hours = sync_config.get("max_source_file_age_hours")
    fail_on_stale = bool(sync_config.get("fail_on_stale_source", False))
    temp_folder = Path(temp_config.get("folder", "./temp")).expanduser()
    temp_folder.mkdir(parents=True, exist_ok=True)

    source_path = folder / tracking_file
    lock_path = folder / f"~${tracking_file}"
    started = time.monotonic()
    last_error = ""

    if tracking_file.startswith("~$"):
        raise SyncValidationError(f"Tracking file points to an Excel lock file: {tracking_file}")

    while time.monotonic() - started <= wait_seconds:
        try:
            if not folder.exists():
                raise SyncValidationError(f"Synced folder does not exist: {folder}")
            if not folder.is_dir():
                raise SyncValidationError(f"Synced folder path is not a directory: {folder}")
            if not source_path.exists():
                raise SyncValidationError(f"Tracking file does not exist: {source_path}")
            if source_path.name.startswith("~$"):
                raise SyncValidationError(f"Source is an Excel temp lock file: {source_path}")
            if lock_path.exists():
                raise SyncValidationError(f"Excel lock file exists, workbook may be open or syncing: {lock_path}")

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            temp_path = temp_folder / f"{source_path.stem}_{stamp}{source_path.suffix}"
            shutil.copy2(source_path, temp_path)

            stat = source_path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)
            age_hours = (datetime.now() - modified).total_seconds() / 3600
            warnings: list[Issue] = []
            if max_age_hours is not None and age_hours > float(max_age_hours):
                issue = Issue(
                    severity="Medium",
                    issue_type="Stale source file",
                    category="Sync",
                    evidence=f"Source file age is {age_hours:.1f} hours, threshold is {max_age_hours} hours.",
                    recommendation="Confirm OneDrive sync status before using this report for planning.",
                    suggested_question="Is the local OneDrive copy up to date?",
                    source="sync",
                )
                if fail_on_stale:
                    raise SyncValidationError(issue.evidence)
                warnings.append(issue)

            logger.info("Sync validation passed: source=%s temp=%s", source_path, temp_path)
            return SyncResult(
                source_path=source_path,
                temp_path=temp_path,
                source_last_modified=modified,
                source_age_hours=age_hours,
                warnings=warnings,
            )
        except (PermissionError, OSError, SyncValidationError) as exc:
            last_error = str(exc)
            logger.warning("Sync validation retry: %s", last_error)
            time.sleep(retry_seconds)

    raise SyncValidationError(
        f"Timed out after {wait_seconds}s waiting for synced tracking file readiness. Last error: {last_error}"
    )
