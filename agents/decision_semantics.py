"""Single source of truth for decision semantics across backend and frontend."""
from __future__ import annotations

from typing import Any

from agents.base_agent import (
    CONCLUSION_FAIL,
    CONCLUSION_MISSING,
    CONCLUSION_PASS,
    STANCE_OPPOSE,
    STANCE_PENDING,
    STANCE_SUPPORT,
)

CLAUSE_STATUS_UNVERIFIED = "未证实"
CLAUSE_STATUS_NO_RISK = "未发现风险"
CLAUSE_STATUS_NEEDS_SUPPLEMENT = "待补充"

RULE_CATEGORY_BASIC = "basic"
RULE_CATEGORY_EXCLUSION = "exclusion"
RULE_CATEGORY_OTHER = "other"

EVIDENCE_STATE_HIT = "hit"
EVIDENCE_STATE_NOT_HIT = "not_hit"
EVIDENCE_STATE_MISSING_DATA = "missing_data"
EVIDENCE_STATE_UNKNOWN = "unknown"

DECISION_EFFECT_SUPPORT = "support"
DECISION_EFFECT_OPPOSE = "oppose"
DECISION_EFFECT_NEUTRAL = "neutral"


def normalize_rule_category(
    raw_category: str | None,
    *,
    fallback_category: str | None = None,
) -> str:
    category = (fallback_category or raw_category or "").strip().lower()
    if category in {RULE_CATEGORY_BASIC, RULE_CATEGORY_EXCLUSION}:
        return category
    source = str(raw_category or "")
    if "排除" in source:
        return RULE_CATEGORY_EXCLUSION
    if "基础" in source or "必须满足" in source:
        return RULE_CATEGORY_BASIC
    return RULE_CATEGORY_OTHER


def build_item_semantics(
    item: Any,
    *,
    category_hint: str | None = None,
) -> dict[str, Any]:
    category_code = normalize_rule_category(
        getattr(item, "category", None),
        fallback_category=category_hint,
    )
    exec_status = str(getattr(item, "exec_status", "") or "")
    supports_conclusion = getattr(item, "supports_conclusion", None)
    # Empty result means different things for different rule types:
    # - basic/must-satisfy rules need a positive hit, so no_data is missing.
    # - exclusion/risk rules are negative checks, so no_data means no risk hit.
    # - auxiliary rules should not independently force missing on no_data.
    hard_missing = exec_status in {"failed", "field_missing"}
    missing_data = hard_missing or (
        exec_status == "no_data" and category_code == RULE_CATEGORY_BASIC
    )

    if category_code == RULE_CATEGORY_EXCLUSION:
        if supports_conclusion is False:
            evidence_state = EVIDENCE_STATE_HIT
            decision_effect = DECISION_EFFECT_OPPOSE
            status = CONCLUSION_FAIL
            display_label = "反向证据"
            tag_type = "danger"
        elif supports_conclusion is True and not hard_missing:
            evidence_state = EVIDENCE_STATE_HIT
            decision_effect = DECISION_EFFECT_SUPPORT
            status = CONCLUSION_PASS
            display_label = CONCLUSION_PASS
            tag_type = "success"
        elif exec_status == "no_data" and not hard_missing:
            evidence_state = EVIDENCE_STATE_NOT_HIT
            decision_effect = DECISION_EFFECT_SUPPORT
            status = CLAUSE_STATUS_NO_RISK
            display_label = CLAUSE_STATUS_NO_RISK
            tag_type = "info"
        else:
            evidence_state = EVIDENCE_STATE_MISSING_DATA if hard_missing else EVIDENCE_STATE_UNKNOWN
            decision_effect = DECISION_EFFECT_NEUTRAL
            status = CLAUSE_STATUS_UNVERIFIED if hard_missing else CLAUSE_STATUS_NO_RISK
            display_label = status
            tag_type = "warning" if hard_missing else "info"
    else:
        if supports_conclusion is True and not hard_missing:
            evidence_state = EVIDENCE_STATE_HIT
            decision_effect = DECISION_EFFECT_SUPPORT
            status = CONCLUSION_PASS
            display_label = CONCLUSION_PASS
            tag_type = "success"
        elif supports_conclusion is False and not missing_data:
            evidence_state = EVIDENCE_STATE_HIT
            decision_effect = DECISION_EFFECT_OPPOSE
            status = CONCLUSION_FAIL
            display_label = CONCLUSION_FAIL
            tag_type = "danger"
        elif missing_data:
            evidence_state = EVIDENCE_STATE_MISSING_DATA
            decision_effect = DECISION_EFFECT_NEUTRAL
            status = CLAUSE_STATUS_UNVERIFIED
            display_label = CLAUSE_STATUS_UNVERIFIED
            tag_type = "warning"
        elif exec_status == "no_data" and category_code == RULE_CATEGORY_OTHER:
            evidence_state = EVIDENCE_STATE_NOT_HIT
            decision_effect = DECISION_EFFECT_NEUTRAL
            status = CLAUSE_STATUS_NO_RISK
            display_label = CLAUSE_STATUS_NO_RISK
            tag_type = "info"
        else:
            evidence_state = EVIDENCE_STATE_UNKNOWN
            decision_effect = DECISION_EFFECT_NEUTRAL
            status = CLAUSE_STATUS_UNVERIFIED
            display_label = CLAUSE_STATUS_UNVERIFIED
            tag_type = "warning"

    stance = {
        DECISION_EFFECT_SUPPORT: STANCE_SUPPORT,
        DECISION_EFFECT_OPPOSE: STANCE_OPPOSE,
        DECISION_EFFECT_NEUTRAL: STANCE_PENDING,
    }[decision_effect]

    return {
        "semantic_category": category_code,
        "semantic_evidence_state": evidence_state,
        "semantic_decision_effect": decision_effect,
        "semantic_status": status,
        "semantic_display_label": display_label,
        "semantic_tag_type": tag_type,
        "semantic_stance": stance,
        "semantic_is_missing_data": missing_data,
    }


def conclusion_tag_type(conclusion: str | None) -> str:
    if conclusion == CONCLUSION_PASS:
        return "success"
    if conclusion == CONCLUSION_FAIL:
        return "danger"
    return "warning"


def aggregate_final_conclusion_from_judgments(
    judgments: list[Any],
    *,
    projection: Any | None = None,
    evidence_items: list[Any] | None = None,
    bundle: Any | None = None,
    structured_rules: Any | None = None,
) -> str:
    """Aggregate judgments into a final conclusion.

    When projection/evidence_items/bundle are provided, delegates to the
    unified three-layer decision engine. Otherwise falls back to simple
    majority voting for backward compatibility.
    """
    # Use unified decision engine when context is available
    if projection is not None or evidence_items is not None or bundle is not None:
        try:
            from agents.unified_decision_engine import decide
            verdict = decide(
                judgments,
                projection=projection,
                evidence_items=evidence_items,
                bundle=bundle,
                structured_rules=structured_rules,
            )
            return verdict.conclusion
        except Exception:
            pass  # fall through to legacy logic

    # Legacy simple majority voting
    def effective_stance(judgment: Any) -> str:
        conclusion = getattr(judgment, "conclusion", None)
        if conclusion == CONCLUSION_PASS:
            return STANCE_SUPPORT
        if conclusion == CONCLUSION_FAIL:
            return STANCE_OPPOSE
        if conclusion == CONCLUSION_MISSING:
            return STANCE_PENDING
        return str(getattr(judgment, "stance", STANCE_PENDING) or STANCE_PENDING)

    stance_counts = {
        STANCE_SUPPORT: 0,
        STANCE_OPPOSE: 0,
        STANCE_PENDING: 0,
    }
    for judgment in judgments:
        stance = effective_stance(judgment)
        stance_counts[stance] = stance_counts.get(stance, 0) + 1

    total = sum(stance_counts.values())
    if total == 0:
        return CONCLUSION_MISSING

    if stance_counts[STANCE_OPPOSE] > total / 2:
        return CONCLUSION_FAIL
    if stance_counts[STANCE_SUPPORT] > total / 2:
        return CONCLUSION_PASS
    return CONCLUSION_MISSING
