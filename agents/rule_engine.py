"""Deterministic rule engine — hard-rule pre-check before LLM debate."""
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

    # Top-level pre-decision
    pre_decision: str | None = None  # "PASS" | "FAIL" | None (need debate)
    pre_reason: str = ""

    @property
    def has_veto(self) -> bool:
        """True if any must-satisfy rule failed → one-vote veto."""
        return any(r.category == RULE_CATEGORY_BASIC for r in self.failed)

    @property
    def all_basic_passed(self) -> bool:
        """True if all basic rules passed and no exclusion failures."""
        basic_results = [r for r in self.passed + self.failed + self.missing
                         if r.category == RULE_CATEGORY_BASIC]
        exclusion_failures = [r for r in self.failed
                              if r.category == RULE_CATEGORY_EXCLUSION]
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
            reason="未找到匹配的证据",
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
            reason="证据数据缺失或查询失败",
        )

    if category == RULE_CATEGORY_EXCLUSION:
        # exclusion: supports_conclusion=False means risk found → FAIL
        if effect == "oppose":
            return RuleCheckResult(
                rule_id=rule_id, category=category, status="failed",
                evidence_id=item.evidence_id,
                reason="排除条件触发：发现风险证据",
            )
        if effect == "support":
            return RuleCheckResult(
                rule_id=rule_id, category=category, status="passed",
                evidence_id=item.evidence_id,
                reason="排除条件未触发",
            )
    else:
        # basic / other: supports_conclusion=True means PASS
        if effect == "support":
            return RuleCheckResult(
                rule_id=rule_id, category=category, status="passed",
                evidence_id=item.evidence_id,
                reason="证据支持结论",
            )
        if effect == "oppose":
            return RuleCheckResult(
                rule_id=rule_id, category=category, status="failed",
                evidence_id=item.evidence_id,
                reason="证据反对结论",
            )

    return RuleCheckResult(
        rule_id=rule_id, category=category, status="unknown",
        evidence_id=getattr(item, "evidence_id", None),
        reason="证据状态无法确定",
    )


def run_rule_engine(
    bundle: EvidenceBundle,
    structured_rules: Any = None,
) -> RuleEngineOutput:
    """Run deterministic rules against evidence bundle.

    Args:
        bundle: Collected evidence.
        structured_rules: PolicyConfig.structured_rules (StructuredRules) with
            basic_conditions, exclusion_conditions, inference_rules,
            calculation_rules. If None, checks all bundle items directly.

    Returns:
        RuleEngineOutput with pre-decision.
    """
    output = RuleEngineOutput()
    by_rule = bundle.by_rule

    rules_to_check: list[tuple[str, str]] = []  # (rule_id, category)

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
            cat = normalize_rule_category(item.category)
            rules_to_check.append((item.rule_id, cat))

    for rule_id, category in rules_to_check:
        item = by_rule.get(rule_id)
        result = check_rule_against_evidence(rule_id, category, item)
        {
            "passed": output.passed,
            "failed": output.failed,
            "missing": output.missing,
            "unknown": output.unknown,
        }[result.status].append(result)

    # Pre-decision logic
    if output.has_veto:
        failed_basic = [r for r in output.failed
                        if r.category == RULE_CATEGORY_BASIC]
        output.pre_decision = "FAIL"
        output.pre_reason = (
            f"必须满足条件未通过（{', '.join(r.rule_id for r in failed_basic)}），一票否决"
        )
    elif output.all_basic_passed and not output.missing and not output.unknown:
        output.pre_decision = "PASS"
        output.pre_reason = "所有必须满足条件通过，无排除条件触发，无缺失证据"

    return output
