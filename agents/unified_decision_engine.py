"""Three-layer decision pipeline: rule engine → weighted vote → majority fallback."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import CONCLUSION_FAIL, CONCLUSION_MISSING, CONCLUSION_PASS
from agents.rule_engine import RuleEngineOutput, run_rule_engine
from agents.optimization_algorithms import aggregate_weighted_stances
from evidence.evidence_model import EvidenceBundle, EvidenceItem
from evidence.evidence_projection import EvidenceProjection


@dataclass
class DecisionVerdict:
    """Final decision from the three-layer pipeline."""

    conclusion: str  # CONCLUSION_PASS / CONCLUSION_FAIL / CONCLUSION_MISSING
    confidence: float  # 0.0 - 1.0
    method: str  # "rule_override" | "weighted_vote" | "majority"
    breakdown: dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = False
    rule_engine_output: RuleEngineOutput | None = None


def _majority_vote(judgments: list[Any]) -> tuple[str, float]:
    """Simple majority voting fallback. Returns (conclusion, confidence)."""
    counts = {CONCLUSION_PASS: 0, CONCLUSION_FAIL: 0, CONCLUSION_MISSING: 0}
    confidences = []
    for j in judgments:
        conclusion = getattr(j, "conclusion", CONCLUSION_MISSING)
        counts[conclusion] = counts.get(conclusion, 0) + 1
        confidences.append(getattr(j, "confidence", 0.5))

    total = sum(counts.values())
    if total == 0:
        return CONCLUSION_MISSING, 0.0

    # Check for strict majority
    for c in [CONCLUSION_FAIL, CONCLUSION_PASS]:
        if counts[c] > total / 2:
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
            return c, round(avg_conf, 3)

    return CONCLUSION_MISSING, 0.3


def decide(
    judgments: list[Any],
    projection: EvidenceProjection | None = None,
    evidence_items: list[EvidenceItem] | None = None,
    structured_rules: Any = None,
    bundle: EvidenceBundle | None = None,
) -> DecisionVerdict:
    """Run the three-layer decision pipeline.

    Layer 1: Rule engine — hard rules (one-vote veto / one-vote pass).
    Layer 2: Weighted vote — confidence × evidence quality weighting.
    Layer 3: Majority fallback — simple >50% vote.

    Args:
        judgments: List of AgentJudgment objects.
        projection: EvidenceProjection for weighted scoring.
        evidence_items: List of EvidenceItem for rule engine.
        structured_rules: PolicyConfig.structured_rules for rule engine.
        bundle: EvidenceBundle (alternative to evidence_items for rule engine).

    Returns:
        DecisionVerdict with conclusion, confidence, method, breakdown.
    """
    breakdown: dict[str, Any] = {}

    # ── Layer 1: Rule Engine ──────────────────────────────────────────────
    rule_output: RuleEngineOutput | None = None
    if bundle is not None:
        rule_output = run_rule_engine(bundle, structured_rules)
    elif evidence_items is not None:
        # Build a temporary bundle
        from datetime import datetime
        temp_bundle = EvidenceBundle(
            id_card="temp",
            items=evidence_items,
        )
        rule_output = run_rule_engine(temp_bundle, structured_rules)

    if rule_output is not None:
        breakdown["rule_engine"] = {
            "passed": len(rule_output.passed),
            "failed": len(rule_output.failed),
            "missing": len(rule_output.missing),
            "pre_decision": rule_output.pre_decision,
            "pre_reason": rule_output.pre_reason,
        }

        if rule_output.pre_decision == "FAIL":
            return DecisionVerdict(
                conclusion=CONCLUSION_FAIL,
                confidence=0.95,
                method="rule_override",
                breakdown=breakdown,
                rule_engine_output=rule_output,
            )
        if rule_output.pre_decision == "PASS":
            # Rule engine says PASS, but still run weighted vote for confidence
            # If weighted vote agrees, high confidence; if not, flag for review
            breakdown["rule_engine_verdict"] = "PASS"

    # ── Layer 2: Weighted Vote ────────────────────────────────────────────
    weighted = aggregate_weighted_stances(judgments, projection)
    breakdown["weighted_vote"] = {
        "support": weighted["weighted_support"],
        "oppose": weighted["weighted_oppose"],
        "pending": weighted["weighted_pending"],
        "dominant": weighted["dominant_stance"],
        "confidence": weighted["weighted_confidence"],
    }

    from agents.base_agent import STANCE_OPPOSE, STANCE_SUPPORT

    if weighted["dominant_stance"] == STANCE_OPPOSE:
        # Weighted vote says FAIL
        if rule_output and rule_output.pre_decision == "PASS":
            # Conflict: rule engine says PASS, weighted says FAIL
            return DecisionVerdict(
                conclusion=CONCLUSION_FAIL,
                confidence=weighted["weighted_confidence"],
                method="weighted_vote",
                breakdown=breakdown,
                requires_human_review=True,
                rule_engine_output=rule_output,
            )
        return DecisionVerdict(
            conclusion=CONCLUSION_FAIL,
            confidence=weighted["weighted_confidence"],
            method="weighted_vote",
            breakdown=breakdown,
            rule_engine_output=rule_output,
        )

    if weighted["dominant_stance"] == STANCE_SUPPORT:
        # Weighted total of support vs oppose
        total = weighted["total_weight"]
        support_ratio = weighted["weighted_support"] / total if total > 0 else 0
        if support_ratio > 0.6:
            return DecisionVerdict(
                conclusion=CONCLUSION_PASS,
                confidence=weighted["weighted_confidence"],
                method="weighted_vote",
                breakdown=breakdown,
                rule_engine_output=rule_output,
            )

    # ── Layer 3: Majority Fallback ────────────────────────────────────────
    majority_conclusion, majority_conf = _majority_vote(judgments)
    breakdown["majority_vote"] = {
        "conclusion": majority_conclusion,
        "confidence": majority_conf,
    }

    if majority_conclusion in (CONCLUSION_PASS, CONCLUSION_FAIL):
        return DecisionVerdict(
            conclusion=majority_conclusion,
            confidence=majority_conf,
            method="majority",
            breakdown=breakdown,
            rule_engine_output=rule_output,
        )

    # No clear consensus
    return DecisionVerdict(
        conclusion=CONCLUSION_MISSING,
        confidence=0.0,
        method="majority",
        breakdown=breakdown,
        requires_human_review=True,
        rule_engine_output=rule_output,
    )
