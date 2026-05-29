"""Deterministic rule engine: hard-rule pre-check before LLM debate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.decision_semantics import (
    RULE_CATEGORY_BASIC,
    RULE_CATEGORY_EXCLUSION,
    RULE_CATEGORY_OTHER,
    build_item_semantics,
    normalize_rule_category,
)
from evidence.evidence_model import EvidenceBundle, EvidenceItem


@dataclass
class RuleCheckResult:
    """Result of checking one rule against its evidence."""

    rule_id: str
    category: str  # "basic" | "exclusion" | "other"
    status: str  # "passed" | "failed" | "missing" | "unknown"
    evidence_id: str | None = None
    reason: str = ""


@dataclass
class RuleEngineOutput:
    """Aggregated output from the deterministic rule engine."""

    passed: list[RuleCheckResult] = field(default_factory=list)
    failed: list[RuleCheckResult] = field(default_factory=list)
    missing: list[RuleCheckResult] = field(default_factory=list)
    unknown: list[RuleCheckResult] = field(default_factory=list)

    pre_decision: str | None = None  # "PASS" | "FAIL" | None
    pre_reason: str = ""

    @property
    def has_veto(self) -> bool:
        """True if any must-satisfy or exclusion rule failed."""
        return any(
            r.category in {RULE_CATEGORY_BASIC, RULE_CATEGORY_EXCLUSION}
            for r in self.failed
        )

    @property
    def all_basic_passed(self) -> bool:
        """True if all basic rules passed and no exclusion failures."""
        basic_results = [
            r
            for r in self.passed + self.failed + self.missing
            if r.category == RULE_CATEGORY_BASIC
        ]
        exclusion_failures = [
            r for r in self.failed if r.category == RULE_CATEGORY_EXCLUSION
        ]
        return (
            len(basic_results) > 0
            and all(r.status == "passed" for r in basic_results)
            and len(exclusion_failures) == 0
        )


def check_rule_against_evidence(
    rule_id: str,
    category: str,
    item: EvidenceItem | None,
) -> RuleCheckResult:
    """Check a single rule against its matched evidence item."""
    if item is None:
        return RuleCheckResult(
            rule_id=rule_id,
            category=category,
            status="missing",
            reason="No matching evidence was collected for this rule.",
        )

    semantics = build_item_semantics(item, category_hint=category)
    effect = semantics["semantic_decision_effect"]
    is_missing = semantics["semantic_is_missing_data"]

    if is_missing:
        return RuleCheckResult(
            rule_id=rule_id,
            category=category,
            status="missing",
            evidence_id=item.evidence_id,
            reason="Evidence data is missing or the query failed.",
        )

    if category == RULE_CATEGORY_EXCLUSION:
        # Exclusion rules are negative checks: a hit is a veto; an empty result
        # means no exclusion risk was found and must not block a PASS.
        if effect == "oppose":
            return RuleCheckResult(
                rule_id=rule_id,
                category=category,
                status="failed",
                evidence_id=item.evidence_id,
                reason="Exclusion condition triggered: risk evidence found.",
            )
        if effect == "support" or str(getattr(item, "exec_status", "") or "") == "no_data":
            return RuleCheckResult(
                rule_id=rule_id,
                category=category,
                status="passed",
                evidence_id=item.evidence_id,
                reason="Exclusion condition not triggered: no risk found.",
            )
    else:
        if effect == "support":
            return RuleCheckResult(
                rule_id=rule_id,
                category=category,
                status="passed",
                evidence_id=item.evidence_id,
                reason="Evidence supports the conclusion.",
            )
        if effect == "oppose":
            return RuleCheckResult(
                rule_id=rule_id,
                category=category,
                status="failed",
                evidence_id=item.evidence_id,
                reason="Evidence opposes the conclusion.",
            )

    return RuleCheckResult(
        rule_id=rule_id,
        category=category,
        status="unknown",
        evidence_id=getattr(item, "evidence_id", None),
        reason="Evidence state cannot be determined.",
    )


def run_rule_engine(
    bundle: EvidenceBundle,
    structured_rules: Any = None,
) -> RuleEngineOutput:
    """Run deterministic rules against an evidence bundle."""
    output = RuleEngineOutput()
    by_rule = bundle.by_rule

    rules_to_check: list[tuple[str, str]] = []
    if structured_rules is not None:
        for rule in getattr(structured_rules, "basic_conditions", []):
            rules_to_check.append((rule.rule_id, RULE_CATEGORY_BASIC))
        for rule in getattr(structured_rules, "exclusion_conditions", []):
            rules_to_check.append((rule.rule_id, RULE_CATEGORY_EXCLUSION))
        for rule in getattr(structured_rules, "inference_rules", []):
            rules_to_check.append((rule.rule_id, RULE_CATEGORY_OTHER))
        for rule in getattr(structured_rules, "calculation_rules", []):
            rules_to_check.append((rule.rule_id, RULE_CATEGORY_OTHER))
    else:
        for item in bundle.items:
            rules_to_check.append((item.rule_id, normalize_rule_category(item.category)))

    for rule_id, category in rules_to_check:
        item = by_rule.get(rule_id)
        result = check_rule_against_evidence(rule_id, category, item)
        {
            "passed": output.passed,
            "failed": output.failed,
            "missing": output.missing,
            "unknown": output.unknown,
        }[result.status].append(result)

    if output.has_veto:
        failures = [
            r
            for r in output.failed
            if r.category in {RULE_CATEGORY_BASIC, RULE_CATEGORY_EXCLUSION}
        ]
        output.pre_decision = "FAIL"
        output.pre_reason = (
            "Hard-rule veto triggered: "
            + ", ".join(r.rule_id for r in failures)
        )
    elif output.all_basic_passed and not output.missing and not output.unknown:
        output.pre_decision = "PASS"
        output.pre_reason = (
            "All must-satisfy rules passed and no exclusion condition was triggered."
        )

    return output
