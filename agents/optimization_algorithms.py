"""Evidence scoring and weighted aggregation algorithms."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import (
    CONCLUSION_MISSING,
    CONCLUSION_PASS,
    STANCE_OPPOSE,
    STANCE_PENDING,
    STANCE_SUPPORT,
)
from evidence.evidence_model import EvidenceItem
from evidence.evidence_projection import EvidenceProjection


# ---------------------------------------------------------------------------
# Evidence scoring
# ---------------------------------------------------------------------------

def _score_source_reliability(item: EvidenceItem) -> float:
    """Score 0-100 based on data source reliability."""
    source = (item.category or "").lower()
    # Government/public data sources score higher
    gov_keywords = {"社保", "公积金", "税务", "工商", "民政", "公安", "不动产"}
    corp_keywords = {"企业", "法人", "股东", "注册"}
    personal_keywords = {"个人", "自述", "申报"}

    for kw in gov_keywords:
        if kw in (item.category or ""):
            return 90.0
    for kw in corp_keywords:
        if kw in (item.category or ""):
            return 70.0
    for kw in personal_keywords:
        if kw in (item.category or ""):
            return 50.0
    # SQL-based queries are generally reliable
    if item.sql and item.exec_status == "success":
        return 75.0
    return 60.0


def _score_timeliness(item: EvidenceItem) -> float:
    """Score 0-100 based on evidence freshness."""
    time_range = item.time_range or ""
    if not time_range:
        return 50.0  # unknown timeliness
    # Check for recent indicators
    for year in ["2026", "2025"]:
        if year in time_range:
            return 95.0
    for year in ["2024", "2023"]:
        if year in time_range:
            return 75.0
    for year in ["2022", "2021", "2020"]:
        if year in time_range:
            return 50.0
    return 40.0


def _score_completeness(item: EvidenceItem) -> float:
    """Score 0-100 based on field completeness."""
    checks = [
        bool(item.result_summary),
        bool(item.sql),
        item.exec_status == "success",
        bool(item.result_raw),
        item.supports_conclusion is not None,
    ]
    return (sum(checks) / len(checks)) * 100


def _score_relevance(item: EvidenceItem, category_hint: str | None) -> float:
    """Score 0-100 based on rule-evidence match."""
    if item.exec_status == "success" and item.supports_conclusion is not None:
        return 95.0
    if item.exec_status == "no_data":
        return 40.0
    if item.exec_status in ("failed", "field_missing"):
        return 20.0
    return 60.0


@dataclass
class EvidenceScore:
    score: float  # 0-100
    score_percent: str  # e.g. "78.5%"
    breakdown: dict[str, float]
    rank_reason: str


def score_evidence_item(
    item: EvidenceItem,
    category_hint: str | None = None,
) -> EvidenceScore:
    """Score a single evidence item across 4 dimensions.

    Returns:
        EvidenceScore with total score, percent string, breakdown dict, and
        human-readable rank reason.
    """
    breakdown = {
        "source_reliability": _score_source_reliability(item),
        "timeliness": _score_timeliness(item),
        "completeness": _score_completeness(item),
        "relevance": _score_relevance(item, category_hint),
    }

    # Weighted average
    weights = {
        "source_reliability": 0.30,
        "timeliness": 0.20,
        "completeness": 0.25,
        "relevance": 0.25,
    }
    total = sum(breakdown[k] * weights[k] for k in breakdown)
    total = round(total, 1)

    # Rank reason
    best = max(breakdown, key=breakdown.get)
    worst = min(breakdown, key=breakdown.get)
    reason_parts = []
    if breakdown[best] >= 80:
        reason_parts.append(f"{_dim_label(best)}强")
    if breakdown[worst] < 50:
        reason_parts.append(f"{_dim_label(worst)}不足")
    if not reason_parts:
        reason_parts.append("综合表现均衡")
    rank_reason = "，".join(reason_parts)

    return EvidenceScore(
        score=total,
        score_percent=f"{total / 100:.1%}",
        breakdown=breakdown,
        rank_reason=rank_reason,
    )


def _dim_label(key: str) -> str:
    return {
        "source_reliability": "来源可靠性",
        "timeliness": "时效性",
        "completeness": "完整性",
        "relevance": "相关性",
    }.get(key, key)


def sort_evidence_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Sort evidence items by score descending."""
    scored = [(score_evidence_item(it).score, it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored]


# ---------------------------------------------------------------------------
# Agent weighted aggregation
# ---------------------------------------------------------------------------

def _average_evidence_score(
    evidence_refs: list[str],
    evidence_scores: dict[str, float],
) -> float:
    """Average score of referenced evidence items."""
    if not evidence_refs:
        return 0.0
    scores = [evidence_scores.get(ref, 0.0) for ref in evidence_refs]
    return sum(scores) / len(scores)


def aggregate_weighted_stances(
    judgments: list[Any],
    projection: EvidenceProjection | None = None,
) -> dict[str, Any]:
    """Aggregate agent stances weighted by confidence × evidence quality.

    Returns:
        Dict with keys: weighted_support, weighted_oppose, weighted_pending,
        total_weight, dominant_stance, weighted_confidence.
    """
    from agents.decision_semantics import (
        build_item_semantics,
        DECISION_EFFECT_SUPPORT,
        DECISION_EFFECT_OPPOSE,
    )

    # Build evidence score map from projection cards
    evidence_scores: dict[str, float] = {}
    if projection:
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            evidence_scores[eid] = card.confidence * 100

    weighted_support = 0.0
    weighted_oppose = 0.0
    weighted_pending = 0.0
    total_weight = 0.0
    confidences = []

    for judgment in judgments:
        # Agent's own confidence
        agent_conf = getattr(judgment, "confidence", 0.5)
        # Quality of evidence this agent cited
        refs = getattr(judgment, "evidence_refs", [])
        ev_quality = _average_evidence_score(refs, evidence_scores) / 100.0

        # Combined weight: agent confidence × evidence quality
        weight = agent_conf * 0.6 + ev_quality * 0.4
        weight = max(weight, 0.1)  # floor to avoid zero-weight agents

        conclusion = getattr(judgment, "conclusion", None)
        stance = getattr(judgment, "stance", STANCE_PENDING)

        # Normalize stance from conclusion
        if conclusion == CONCLUSION_PASS:
            weighted_support += weight
        elif conclusion == "不符合":
            weighted_oppose += weight
        else:
            weighted_pending += weight

        total_weight += weight
        confidences.append(agent_conf)

    if total_weight == 0:
        dominant = STANCE_PENDING
    elif weighted_oppose > weighted_support and weighted_oppose > weighted_pending:
        dominant = STANCE_OPPOSE
    elif weighted_support > weighted_oppose and weighted_support > weighted_pending:
        dominant = STANCE_SUPPORT
    else:
        dominant = STANCE_PENDING

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "weighted_support": round(weighted_support, 3),
        "weighted_oppose": round(weighted_oppose, 3),
        "weighted_pending": round(weighted_pending, 3),
        "total_weight": round(total_weight, 3),
        "dominant_stance": dominant,
        "weighted_confidence": round(avg_confidence, 3),
    }


# ---------------------------------------------------------------------------
# Clause-level confidence
# ---------------------------------------------------------------------------

def estimate_clause_confidence(
    item: EvidenceItem | None,
    category_hint: str | None = None,
) -> float:
    """Estimate confidence for a single clause based on its evidence quality."""
    if item is None:
        return 0.0
    score = score_evidence_item(item, category_hint)
    # Map 0-100 score to 0.0-1.0 confidence
    base = score.score / 100.0
    # Boost if manually verified
    if getattr(item, "manual_verified", False):
        base = min(base + 0.1, 1.0)
    # Penalty if missing data
    if item.exec_status in ("failed", "field_missing"):
        base = max(base - 0.2, 0.0)
    return round(base, 3)


# ---------------------------------------------------------------------------
# Argument-level confidence (objective, replaces Agent self-report)
# ---------------------------------------------------------------------------

def compute_argument_confidence(
    arg: Any,
    projection: EvidenceProjection | None = None,
    evidence_scores: dict[str, float] | None = None,
) -> float:
    """Compute objective confidence for an argument based on evidence quality.

    Replaces Agent self-reported confidence with measurable factors:
    1. Average score of referenced evidence (0.35)
    2. Completeness: resolved evidence ratio (0.25)
    3. Rule importance from projection (0.20)
    4. Evidence execution success rate (0.20)
    """
    from agents.debate_memory import Argument

    if evidence_scores is None:
        evidence_scores = {}

    refs = getattr(arg, "evidence_refs", []) or []
    if not refs:
        return 0.3  # no evidence → low confidence

    factors: list[tuple[float, float]] = []

    # 1. Average evidence score
    ref_scores = [evidence_scores.get(ref, 50.0) for ref in refs]
    avg_score = sum(ref_scores) / len(ref_scores)
    factors.append((avg_score / 100.0, 0.35))

    # 2. Completeness: how many refs are resolved in projection
    if projection:
        card_status = {}
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            card_status[eid] = card.status
        resolved = sum(
            1 for ref in refs
            if card_status.get(ref) in ("supports", "contradicts")
        )
        completeness = resolved / len(refs)
    else:
        completeness = 0.5  # unknown
    factors.append((completeness, 0.25))

    # 3. Rule importance (basic > exclusion > other)
    if projection:
        importance_scores = []
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            if eid in refs:
                # Higher confidence cards are more important rules
                importance_scores.append(card.confidence)
        avg_importance = sum(importance_scores) / len(importance_scores) if importance_scores else 0.5
    else:
        avg_importance = 0.5
    factors.append((avg_importance, 0.20))

    # 4. SQL execution success rate
    if projection:
        success_count = sum(
            1 for card in projection.cards
            if card.card_id.replace("card_", "") in refs
            and card.status in ("supports", "contradicts")
        )
        sql_rate = success_count / len(refs)
    else:
        sql_rate = 0.5
    factors.append((sql_rate, 0.20))

    confidence = sum(w * f for f, w in factors)
    return round(max(0.0, min(1.0, confidence)), 3)
