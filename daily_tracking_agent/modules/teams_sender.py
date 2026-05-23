from __future__ import annotations

import logging
import time

import requests


def send_teams_message(summary_text: str, config: dict, logger: logging.Logger, force_disabled: bool = False) -> bool:
    if force_disabled or not config.get("enabled", False):
        logger.info("Teams sending disabled")
        return False
    webhook_url = str(config.get("webhook_url", "")).strip()
    if not webhook_url or "PASTE_" in webhook_url:
        logger.warning("Teams webhook URL is not configured")
        return False
    last_error = ""
    for attempt in range(1, 4):
        try:
            resp = requests.post(webhook_url, json={"text": summary_text}, timeout=30)
            if 200 <= resp.status_code < 300:
                logger.info("Teams message sent")
                return True
            last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
            logger.warning("Teams send attempt %s failed: %s", attempt, last_error)
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.warning("Teams send attempt %s failed: %s", attempt, exc)
        time.sleep(2)
    logger.error("Teams send failed after retries: %s", last_error)
    return False
