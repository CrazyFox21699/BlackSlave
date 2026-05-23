from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["Low", "Medium", "High", "Critical"]
IssueSource = Literal["rule", "ollama", "sync", "system"]


class Issue(BaseModel):
    row_id: int | str | None = None
    pic: str | None = None
    milestone: str | None = None
    item: str | None = None
    severity: Severity
    issue_type: str
    category: str
    evidence: str
    recommendation: str
    suggested_question: str = ""
    score_impact: int = 0
    source: IssueSource = "rule"


class SyncResult(BaseModel):
    source_path: Path
    temp_path: Path
    source_last_modified: datetime
    source_age_hours: float
    warnings: list[Issue] = Field(default_factory=list)


class ExcelMetadata(BaseModel):
    sheet_name: str
    header_row: int
    row_count: int
    source_path: Path
    missing_required_columns: list[str] = Field(default_factory=list)
    detected_columns: list[str] = Field(default_factory=list)


class AnalysisContext(BaseModel):
    today: datetime
    source_file: Path | None = None
    source_last_modified: datetime | None = None
    report_markdown_path: Path | None = None
    report_excel_path: Path | None = None
    row_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
