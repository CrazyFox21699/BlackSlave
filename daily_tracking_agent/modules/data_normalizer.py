from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

import pandas as pd


CANONICAL_ALIASES: dict[str, list[str]] = {
    "PIC": ["pic", "owner", "assignee"],
    "Milestone": ["milestone"],
    "StartDatePlan": ["start date (plan)", "start date", "start plan", "planned start"],
    "EndDatePlan": ["end date (plan)", "end date", "end plan", "planned end", "due date"],
    "Est": ["est (mh) or sp", "est", "estimate", "estimated mh", "mh", "sp"],
    "Target": ["target"],
    "CurrentProgress": ["current progress", "progress", "actual progress"],
    "PreviousValue": ["previous value", "previous progress", "prev progress"],
    "Delta": ["delta", "progress delta"],
    "Note": ["note", "notes", "comment", "remarks"],
    "Item": ["item", "task", "task name"],
    "Level": ["level"],
    "Overall": ["overall"],
    "Common": ["common"],
    "Module": ["module"],
}


def _clean_name(name: Any) -> str:
    text = str(name or "").strip()
    text = re.sub(r"__dup\d+$", "", text)
    return " ".join(text.lower().replace("\n", " ").split())


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() in {"", "-", "nan", "NaN", "None"}


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    cleaned: dict[str, str] = {}
    for col in columns:
        # Keep the first physical column when Excel has duplicate names.
        # In the tracker screenshot, "Current Progress" appears twice; the
        # first one is the percentage input used for planning analysis.
        cleaned.setdefault(_clean_name(col), col)
    for alias in aliases:
        if alias in cleaned:
            return cleaned[alias]
    for alias in aliases:
        for clean, original in cleaned.items():
            if alias in clean:
                return original
    return None


def _parse_date(value: Any, today: date) -> pd.Timestamp | pd.NaT:
    if _is_blank(value) or isinstance(value, bool):
        return pd.NaT
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%d-%b", "%d-%B", "%d/%m", "%m/%d"):
            try:
                dt = datetime.strptime(text, fmt)
                return pd.Timestamp(year=today.year, month=dt.month, day=dt.day)
            except ValueError:
                continue
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    return parsed.normalize() if not pd.isna(parsed) else pd.NaT


def _parse_progress(value: Any) -> float | None:
    if _is_blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.endswith("%"):
            try:
                return float(text[:-1])
            except ValueError:
                return None
        try:
            num = float(text)
        except ValueError:
            return None
    else:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
    if 0 <= num <= 1:
        return num * 100
    return num


def _parse_est(value: Any) -> float | None:
    if _is_blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().lower().replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        return float(match.group(0))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_delta(value: Any) -> float | None:
    return _parse_progress(value)


def normalize_data(raw_df: pd.DataFrame, today: date) -> tuple[pd.DataFrame, dict[str, str]]:
    mapping: dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        found = _find_column(list(raw_df.columns), aliases)
        if found:
            mapping[canonical] = found

    norm = pd.DataFrame(index=raw_df.index)
    header_row = int(raw_df.attrs.get("excel_header_row", 1))
    norm["RowID"] = raw_df.index + header_row + 1
    for canonical in CANONICAL_ALIASES:
        src = mapping.get(canonical)
        norm[canonical] = raw_df[src] if src else pd.NA
        norm[f"Raw_{canonical}"] = raw_df[src].astype("object") if src else pd.NA

    for col in ["PIC", "Milestone", "Target", "Note", "Item", "Level", "Overall", "Common", "Module"]:
        norm[col] = norm[col].apply(lambda v: "" if _is_blank(v) else str(v).strip())

    norm["StartDatePlan"] = norm["Raw_StartDatePlan"].apply(lambda v: _parse_date(v, today))
    norm["EndDatePlan"] = norm["Raw_EndDatePlan"].apply(lambda v: _parse_date(v, today))
    norm["CurrentProgress"] = norm["Raw_CurrentProgress"].apply(_parse_progress).fillna(0).clip(lower=0, upper=100)
    norm["PreviousValue"] = norm["Raw_PreviousValue"].apply(_parse_progress)
    norm["Delta"] = norm["Raw_Delta"].apply(_parse_delta)
    norm["Est"] = norm["Raw_Est"].apply(_parse_est)

    today_ts = pd.Timestamp(today)
    duration = (norm["EndDatePlan"] - norm["StartDatePlan"]).dt.days + 1
    norm["DurationDays"] = duration.where(duration > 0)
    norm["DaysToDue"] = (norm["EndDatePlan"] - today_ts).dt.days
    norm["DaysElapsed"] = (today_ts - norm["StartDatePlan"]).dt.days + 1
    elapsed_ratio = norm["DaysElapsed"] / norm["DurationDays"]
    norm["ExpectedProgressByTime"] = (elapsed_ratio.clip(lower=0, upper=1) * 100).where(norm["DurationDays"].notna())
    norm["ProgressGap"] = norm["ExpectedProgressByTime"] - norm["CurrentProgress"]
    norm["RemainingMH"] = norm["Est"].fillna(0) * (1 - norm["CurrentProgress"].fillna(0) / 100)
    norm["PlannedMHDaily"] = norm["Est"] / norm["DurationDays"]

    text_cols = ["Common", "Overall", "Level", "Item", "Module", "Milestone", "Target", "Note"]
    norm["TaskText"] = norm[text_cols].fillna("").astype(str).agg(" ".join, axis=1).str.strip()
    content_mask = (
        norm["TaskText"].str.strip().ne("")
        | norm["PIC"].astype(str).str.strip().ne("")
        | norm["StartDatePlan"].notna()
        | norm["EndDatePlan"].notna()
    )
    norm = norm[content_mask].reset_index(drop=True)
    return norm, mapping
