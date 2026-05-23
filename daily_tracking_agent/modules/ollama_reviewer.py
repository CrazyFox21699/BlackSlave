from __future__ import annotations

import json
import logging

import pandas as pd
import requests

from .models import Issue


def select_candidate_rows(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    candidates = df[
        (df["PriorityScore"] >= 40)
        | (df["ProgressGap"].fillna(0) >= 30)
        | (df["Est"].fillna(0) >= 16)
        | (df["Note"].astype(str).str.lower().str.contains("blocked|waiting|pending|tbd|confirm", regex=True, na=False))
    ].copy()
    return candidates.sort_values("PriorityScore", ascending=False).head(max_rows)


def review_with_ollama(df: pd.DataFrame, config: dict, logger: logging.Logger) -> list[Issue]:
    if not config.get("enabled", False):
        logger.info("Ollama disabled")
        return []
    base_url = str(config.get("base_url", "http://localhost:11434")).rstrip("/")
    model = config.get("model", "qwen2.5:7b")
    timeout = int(config.get("timeout_seconds", 60))
    max_rows = int(config.get("max_rows_for_ai_review", 20))
    issues: list[Issue] = []
    for _, row in select_candidate_rows(df, max_rows).iterrows():
        task = {
            "row_id": int(row["RowID"]),
            "pic": row.get("PIC", ""),
            "milestone": row.get("Milestone", ""),
            "item": row.get("Item", ""),
            "target": row.get("Target", ""),
            "progress": row.get("CurrentProgress", None),
            "previous": row.get("PreviousValue", None),
            "delta": row.get("Delta", None),
            "start": str(row.get("StartDatePlan", "")),
            "end": str(row.get("EndDatePlan", "")),
            "estimate_mh": row.get("Est", None),
            "note": row.get("Note", ""),
            "priority_score": row.get("PriorityScore", 0),
        }
        prompt = (
            "You are a project tracking reviewer for system/software task planning.\n"
            "Analyze the task below and detect:\n"
            "- unrealistic estimate\n- schedule inconsistency\n- progress inconsistency\n"
            "- missing information\n- project risk\n"
            "Return JSON only:\n"
            "{\"has_issue\": true/false, \"issue_type\": \"...\", \"severity\": \"Low/Medium/High\", "
            "\"reason\": \"...\", \"recommendation\": \"...\", \"suggested_question\": \"...\"}\n"
            f"Task:\n{json.dumps(task, default=str, ensure_ascii=False)}"
        )
        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = json.loads(payload.get("response", "{}"))
            if data.get("has_issue"):
                issues.append(Issue(
                    row_id=int(row["RowID"]),
                    pic=str(row.get("PIC", "") or ""),
                    milestone=str(row.get("Milestone", "") or ""),
                    item=str(row.get("Item", "") or ""),
                    severity=data.get("severity", "Medium") if data.get("severity") in {"Low", "Medium", "High", "Critical"} else "Medium",
                    issue_type=data.get("issue_type", "Ollama review issue"),
                    category="Ollama Review",
                    evidence=data.get("reason", ""),
                    recommendation=data.get("recommendation", "Recommend PM/PIC confirmation."),
                    suggested_question=data.get("suggested_question", ""),
                    score_impact=10,
                    source="ollama",
                ))
        except Exception as exc:  # Ollama is optional by requirement.
            logger.warning("Ollama review failed for row %s: %s", row.get("RowID"), exc)
            continue
    logger.info("Ollama review completed: issues=%s", len(issues))
    return issues


def answer_question_with_ollama(question: str, local_context: str, config: dict, logger: logging.Logger) -> str | None:
    """Ask local Ollama to rewrite/analyze a compact local context.

    The caller must pass only filtered report context, not the full workbook.
    """
    base_url = str(config.get("base_url", "http://localhost:11434")).rstrip("/")
    model = config.get("model", "qwen2.5:7b")
    timeout = int(config.get("timeout_seconds", 60))
    prompt = (
        "You are a local system/software project tracking assistant.\n"
        "Use only the local context below. Do not invent rows or dates.\n"
        "Answer in concise Vietnamese. Keep action items clear for daily meeting.\n\n"
        f"User question:\n{question}\n\n"
        f"Local tracking context:\n{local_context}\n"
    )
    try:
        resp = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        answer = str(resp.json().get("response", "")).strip()
        logger.info("Ollama answered tracking question")
        return answer or None
    except Exception as exc:
        logger.warning("Ollama question answer failed: %s", exc)
        return None
