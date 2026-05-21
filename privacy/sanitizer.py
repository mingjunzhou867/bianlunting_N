"""Privacy helpers for separating runtime identifiers from LLM-facing text."""
from __future__ import annotations

import re
from typing import Any


TARGET_ID_CARD_PLACEHOLDER = "<TARGET_ID_CARD>"
SQL_ID_CARD_PLACEHOLDER = "id_card_replace"

ID_CARD_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])(\d{6})[0-9A-Za-z]{8}([0-9A-Za-z]{4})(?![0-9A-Za-z])"
)


def mask_id_card(value: str | None) -> str:
    text = str(value or "").strip()
    if len(text) >= 14:
        return f"{text[:6]}********{text[-4:]}"
    return text


def mask_id_cards_for_display(value: Any) -> str:
    text = str(value or "")
    return ID_CARD_PATTERN.sub(lambda match: f"{match.group(1)}********{match.group(2)}", text)


def sanitize_for_llm(value: Any, target_id_card: str | None = None, replacement: str = TARGET_ID_CARD_PLACEHOLDER) -> str:
    text = str(value or "")
    if target_id_card:
        text = text.replace(str(target_id_card), replacement)
    return ID_CARD_PATTERN.sub(replacement, text)


def prepare_sql_for_execution(sql: str, target_id_card: str) -> str:
    return (
        str(sql or "")
        .replace(TARGET_ID_CARD_PLACEHOLDER, target_id_card)
        .replace(SQL_ID_CARD_PLACEHOLDER, target_id_card)
    )
