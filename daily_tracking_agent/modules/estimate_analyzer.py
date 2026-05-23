from __future__ import annotations

import pandas as pd

from .models import Issue


def analyze_estimate_baselines(df: pd.DataFrame, baselines: dict) -> list[Issue]:
    issues: list[Issue] = []
    for _, row in df.iterrows():
        est = row.get("Est")
        if est is None or pd.isna(est):
            continue
        text = str(row.get("TaskText", "")).lower()
        for name, cfg in baselines.items():
            keywords = [str(k).lower() for k in cfg.get("keywords", [])]
            if not any(k in text for k in keywords):
                continue
            est_f = float(est)
            min_mh = float(cfg.get("min_mh", 0))
            max_mh = float(cfg.get("max_mh", 10**9))
            if est_f < min_mh:
                issues.append(_issue(row, "High", "Possible underestimate", f"{name} baseline expects at least {min_mh:g} MH, but Est={est_f:g} MH.", "Recommend PM/PIC confirmation of assumptions."))
            elif est_f > max_mh:
                issues.append(_issue(row, "Medium", "Possible overestimate or aggregated scope", f"{name} baseline max is {max_mh:g} MH, but Est={est_f:g} MH.", "Confirm whether this item should be split or scoped more clearly."))
            break
    return issues


def _issue(row: pd.Series, severity: str, issue_type: str, evidence: str, recommendation: str) -> Issue:
    return Issue(
        row_id=int(row.get("RowID", 0)),
        pic=str(row.get("PIC", "") or ""),
        milestone=str(row.get("Milestone", "") or ""),
        item=str(row.get("Item", "") or ""),
        severity=severity,  # type: ignore[arg-type]
        issue_type=issue_type,
        category="Estimate",
        evidence=evidence,
        recommendation=recommendation,
        suggested_question="Can PM/PIC confirm estimate scope and assumptions?",
        score_impact=15,
        source="rule",
    )
