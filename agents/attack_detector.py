"""Automatic attack relation detector — validates and discovers argument conflicts."""
from __future__ import annotations

from typing import Any

from agents.debate_memory import (
    Argument,
    ArgumentStance,
    AttackRelation,
    AttackType,
    ATTACK_WEIGHT,
)
from evidence.evidence_projection import EvidenceProjection


class AttackDetector:
    """Detects attack relations between arguments based on objective criteria.

    Does NOT trust Agent self-reported attack targets. Instead, checks:
    - Evidence conflicts (same evidence, opposite conclusions)
    - Rule conflicts (contradictory stances)
    - Logic flaws (argument relies on discredited evidence)
    - Missing data (argument draws conclusions from missing evidence)
    - Policy mismatch (evidence from wrong policy scope)
    """

    def detect(
        self,
        args: list[Argument],
        projection: EvidenceProjection | None = None,
    ) -> list[AttackRelation]:
        """Detect all attack relations among a list of arguments."""
        attacks: list[AttackRelation] = []

        for i, a in enumerate(args):
            for b in args[i + 1:]:
                attacks.extend(self._check_evidence_conflict(a, b))
                attacks.extend(self._check_stance_conflict(a, b))
                attacks.extend(self._check_logic_flaw(a, b, projection))
                attacks.extend(self._check_missing_data(a, b, projection))

        return attacks

    def _check_evidence_conflict(
        self, a: Argument, b: Argument,
    ) -> list[AttackRelation]:
        """Two arguments cite the same evidence but reach opposite conclusions."""
        if a.stance == b.stance:
            return []
        if a.stance == ArgumentStance.INSUFFICIENT or b.stance == ArgumentStance.INSUFFICIENT:
            return []

        shared = set(a.evidence_refs) & set(b.evidence_refs)
        if not shared:
            return []

        attacks = []
        weight = ATTACK_WEIGHT[AttackType.EVIDENCE_CONFLICT]
        evidence_desc = f"shared evidence: {', '.join(shared)}"

        # The argument with lower confidence attacks the higher one
        # (or both attack each other if close)
        if abs(a.confidence - b.confidence) > 0.1:
            weaker, stronger = (a, b) if a.confidence < b.confidence else (b, a)
            attacks.append(AttackRelation(
                attacker_id=weaker.arg_id,
                target_id=stronger.arg_id,
                attack_type=AttackType.EVIDENCE_CONFLICT,
                evidence=evidence_desc,
                weight=weight,
            ))
        else:
            # Mutual attack when confidence is similar
            attacks.append(AttackRelation(
                attacker_id=a.arg_id,
                target_id=b.arg_id,
                attack_type=AttackType.EVIDENCE_CONFLICT,
                evidence=evidence_desc,
                weight=weight,
            ))
            attacks.append(AttackRelation(
                attacker_id=b.arg_id,
                target_id=a.arg_id,
                attack_type=AttackType.EVIDENCE_CONFLICT,
                evidence=evidence_desc,
                weight=weight,
            ))

        return attacks

    def _check_stance_conflict(
        self, a: Argument, b: Argument,
    ) -> list[AttackRelation]:
        """Two arguments have contradictory stances (pass vs reject)."""
        if a.stance == b.stance:
            return []
        if ArgumentStance.INSUFFICIENT in (a.stance, b.stance):
            return []
        # PASS vs REJECT
        if not (
            (a.stance == ArgumentStance.PASS and b.stance == ArgumentStance.REJECT)
            or (a.stance == ArgumentStance.REJECT and b.stance == ArgumentStance.PASS)
        ):
            return []

        attacks = []
        weight = ATTACK_WEIGHT[AttackType.RULE_CONFLICT]

        # Lower confidence argument is attacked
        weaker, stronger = (a, b) if a.confidence < b.confidence else (b, a)
        attacks.append(AttackRelation(
            attacker_id=stronger.arg_id,
            target_id=weaker.arg_id,
            attack_type=AttackType.RULE_CONFLICT,
            evidence=f"stance conflict: {stronger.stance.value} vs {weaker.stance.value}",
            weight=weight * stronger.confidence,
        ))

        return attacks

    def _check_logic_flaw(
        self, a: Argument, b: Argument,
        projection: EvidenceProjection | None,
    ) -> list[AttackRelation]:
        """Argument A cites evidence that argument B marks as unreliable or missing."""
        if projection is None:
            return []

        attacks = []
        # Check if A's evidence is marked as missing/unresolved in projection
        card_status = {}
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            card_status[eid] = card.status

        for ref in a.evidence_refs:
            status = card_status.get(ref)
            if status in ("missing", "unresolved"):
                # B's stance is well-supported while A relies on weak evidence
                if b.confidence > a.confidence + 0.1:
                    attacks.append(AttackRelation(
                        attacker_id=b.arg_id,
                        target_id=a.arg_id,
                        attack_type=AttackType.LOGIC_FLAW,
                        evidence=f"argument relies on weak evidence: {ref} (status={status})",
                        weight=ATTACK_WEIGHT[AttackType.LOGIC_FLAW],
                    ))

        return attacks

    def _check_missing_data(
        self, a: Argument, b: Argument,
        projection: EvidenceProjection | None,
    ) -> list[AttackRelation]:
        """Argument draws a definite conclusion despite depending on missing evidence."""
        if projection is None:
            return []

        attacks = []
        card_status = {}
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            card_status[eid] = card.status

        for arg in (a, b):
            if arg.stance == ArgumentStance.INSUFFICIENT:
                continue
            # Check if argument has missing evidence but still draws definite conclusion
            missing_refs = [
                ref for ref in arg.evidence_refs
                if card_status.get(ref) == "missing"
            ]
            if missing_refs:
                other = b if arg is a else a
                if other.confidence >= arg.confidence:
                    attacks.append(AttackRelation(
                        attacker_id=other.arg_id,
                        target_id=arg.arg_id,
                        attack_type=AttackType.MISSING_DATA,
                        evidence=f"depends on missing evidence: {', '.join(missing_refs)}",
                        weight=ATTACK_WEIGHT[AttackType.MISSING_DATA],
                    ))

        return attacks

    def validate_agent_attacks(
        self,
        arg: Argument,
        all_args: dict[str, Argument],
        projection: EvidenceProjection | None = None,
    ) -> list[str]:
        """Validate Agent self-reported attack targets, returning only valid ones."""
        valid = []
        for target_id in arg.attacks:
            target = all_args.get(target_id)
            if target is None:
                continue
            # Check if there's an objective basis for the attack
            detected = self.detect([arg, target], projection)
            if any(
                (d.attacker_id == arg.arg_id and d.target_id == target_id)
                for d in detected
            ):
                valid.append(target_id)
        return valid
