from __future__ import annotations

import logging
import json
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
    allow_snapshot = bool(sync_config.get("allow_snapshot_when_locked", True))
    max_snapshot_age_hours = sync_config.get("max_snapshot_age_hours", max_age_hours)
    temp_folder = Path(temp_config.get("folder", "./temp")).expanduser()
    temp_folder.mkdir(parents=True, exist_ok=True)
    snapshot_folder = Path(sync_config.get("snapshot_folder") or temp_folder / "source_snapshots").expanduser()
    snapshot_folder.mkdir(parents=True, exist_ok=True)

    source_path = folder / tracking_file
    lock_path = folder / f"~${tracking_file}"
    snapshot_path = snapshot_folder / tracking_file
    snapshot_meta_path = snapshot_folder / f"{tracking_file}.snapshot.json"
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
            shutil.copy2(temp_path, snapshot_path)

            stat = source_path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)
            snapshot_created = datetime.now()
            snapshot_meta_path.write_text(
                json.dumps(
                    {
                        "source_path": str(source_path),
                        "source_last_modified": modified.isoformat(),
                        "snapshot_created": snapshot_created.isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
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

    if allow_snapshot and snapshot_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        temp_path = temp_folder / f"{snapshot_path.stem}_snapshot_{stamp}{snapshot_path.suffix}"
        shutil.copy2(snapshot_path, temp_path)
        meta = _load_snapshot_meta(snapshot_meta_path)
        modified = meta.get("source_last_modified") or datetime.fromtimestamp(snapshot_path.stat().st_mtime)
        snapshot_created = meta.get("snapshot_created") or datetime.fromtimestamp(snapshot_path.stat().st_mtime)
        age_hours = (datetime.now() - snapshot_created).total_seconds() / 3600
        if max_snapshot_age_hours is not None and age_hours > float(max_snapshot_age_hours):
            raise SyncValidationError(
                f"Timed out waiting for source file and fallback snapshot is too old "
                f"({age_hours:.1f}h > {max_snapshot_age_hours}h). Last error: {last_error}"
            )
        warning = Issue(
            severity="High",
            issue_type="Using fallback snapshot",
            category="Sync",
            evidence=(
                f"Could not copy live OneDrive file after {wait_seconds}s. "
                f"Using last successful local snapshot created {snapshot_created:%Y-%m-%d %H:%M}; "
                f"source file in that snapshot was last modified {modified:%Y-%m-%d %H:%M}. "
                f"Last live-file error: {last_error}"
            ),
            recommendation="Close the workbook or wait for OneDrive sync, then rerun if today's latest edits are required.",
            suggested_question="Is the fallback snapshot recent enough for today's control meeting?",
            score_impact=30,
            source="sync",
        )
        logger.warning("Using fallback snapshot: snapshot=%s temp=%s age_hours=%.1f", snapshot_path, temp_path, age_hours)
        return SyncResult(
            source_path=source_path,
            temp_path=temp_path,
            source_last_modified=modified,
            source_age_hours=age_hours,
            warnings=[warning],
        )

    raise SyncValidationError(
        f"Timed out after {wait_seconds}s waiting for synced tracking file readiness. Last error: {last_error}"
    )


def _load_snapshot_meta(path: Path) -> dict[str, datetime]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        result: dict[str, datetime] = {}
        for key in ("source_last_modified", "snapshot_created"):
            value = raw.get(key)
            if value:
                result[key] = datetime.fromisoformat(value)
        return result
    except (OSError, ValueError, TypeError):
        return {}
