"""Deterministic post-processing for generated SQL."""
from __future__ import annotations

import re


_VALID_STATUS_FIELDS = ("is_valid", "data_status")
_VALID_TRUE_VALUES = ("有效", "是", "正常", "当前有效", "1有效", "true", "TRUE")


def normalize_valid_status_values(sql: str) -> str:
    """Normalize generated effective-status literals to the stored code '1'."""
    result = str(sql or "")
    values = "|".join(re.escape(value) for value in _VALID_TRUE_VALUES)
    fields = "|".join(re.escape(field) for field in _VALID_STATUS_FIELDS)
    pattern = re.compile(
        rf"(?P<field>(?:`?\w+`?\.)?`?(?:{fields})`?)\s*=\s*(?P<quote>['\"])(?:{values})(?P=quote)",
        flags=re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"{match.group('field')} = '1'", result)


def coalesce_sum_projections(sql: str) -> str:
    """Wrap bare SUM projections with COALESCE so empty aggregates return 0."""
    result = str(sql or "")
    pattern = re.compile(
        r"(?<!COALESCE\()(?P<expr>\bSUM\s*\([^()]+\))(?P<alias>\s+AS\s+`?\w+`?)",
        flags=re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        start = match.start("expr")
        prefix = result[max(0, start - 20):start].upper()
        if "COALESCE(" in prefix:
            return match.group(0)
        return f"COALESCE({match.group('expr')}, 0){match.group('alias')}"

    return pattern.sub(replace, result)


def postprocess_generated_sql(sql: str) -> str:
    """Apply safe deterministic repairs to LLM-generated SQL."""
    result = normalize_valid_status_values(sql)
    result = coalesce_sum_projections(result)
    return result
