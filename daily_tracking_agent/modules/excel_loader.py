from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .models import ExcelMetadata


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("\n", " ").split())


def _dedupe_columns(columns: list[Any]) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []
    for col in columns:
        base = str(col).strip() if str(col).strip() else "Unnamed"
        idx = counts.get(base, 0)
        counts[base] = idx + 1
        result.append(base if idx == 0 else f"{base}__dup{idx}")
    return result


def _score_header(row: pd.Series, expected: list[str]) -> int:
    row_values = {_norm(v) for v in row.tolist()}
    score = 0
    for col in expected:
        n = _norm(col)
        if n in row_values:
            score += 3
        elif any(n in value or value in n for value in row_values if value):
            score += 1
    return score


def _choose_sheet(path: Path, sheet_name: str | None) -> str:
    xls = pd.ExcelFile(path, engine="openpyxl")
    if sheet_name:
        if sheet_name not in xls.sheet_names:
            raise ValueError(f"Configured sheet '{sheet_name}' not found. Available sheets: {xls.sheet_names}")
        return sheet_name
    return xls.sheet_names[0]


def load_excel(temp_excel_path: str | Path, excel_config: dict, logger: logging.Logger) -> tuple[pd.DataFrame, ExcelMetadata]:
    path = Path(temp_excel_path)
    expected = list(excel_config.get("required_columns", []))
    search_rows = int(excel_config.get("header_search_rows", 30))
    sheet = _choose_sheet(path, excel_config.get("sheet_name"))

    preview = pd.read_excel(path, sheet_name=sheet, header=None, nrows=search_rows, engine="openpyxl")
    best_row = 0
    best_score = -1
    for idx, row in preview.iterrows():
        score = _score_header(row, expected)
        if score >= best_score:
            best_row = int(idx)
            best_score = score

    if best_score <= 0 and expected:
        logger.warning("Could not confidently detect header row; using first row.")
        best_row = 0

    df = pd.read_excel(path, sheet_name=sheet, header=best_row, engine="openpyxl")
    df.columns = _dedupe_columns(df.columns.tolist())
    df = df.dropna(how="all").reset_index(drop=True)
    df.attrs["excel_header_row"] = best_row + 1

    hierarchy_cols = [c for c in df.columns if _norm(c).split("__dup")[0] in {"common", "overall", "level", "item"}]
    for col in hierarchy_cols:
        df[col] = df[col].ffill()

    detected_norm = {_norm(c).split("__dup")[0] for c in df.columns}
    missing = [col for col in expected if _norm(col) not in detected_norm]
    metadata = ExcelMetadata(
        sheet_name=sheet,
        header_row=best_row + 1,
        row_count=len(df),
        source_path=path,
        missing_required_columns=missing,
        detected_columns=list(df.columns),
    )
    logger.info("Excel loaded: sheet=%s header_row=%s rows=%s", sheet, metadata.header_row, len(df))
    return df, metadata
