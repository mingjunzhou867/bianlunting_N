"""Argument data structures and argumentation graph for debate memory."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ArgumentStance(str, Enum):
    """Structured stance for an argument."""
    PASS = "pass"               # supports approval
    REJECT = "reject"           # opposes approval
    INSUFFICIENT = "insufficient"  # data insufficient / pending


class AttackType(str, Enum):
    """Types of attack between arguments."""
    EVIDENCE_CONFLICT = "evidence_conflict"      # same evidence, opposite conclusion
    RULE_CONFLICT = "rule_conflict"              # different rules, contradictory conclusions
    LOGIC_FLAW = "logic_flaw"                    # reasoning chain has flaws
    MISSING_DATA = "missing_data"                # argument depends on missing data
    POLICY_MISMATCH = "policy_mismatch"          # wrong policy clause applied


# Attack weight by type — stronger attacks are more likely to defeat an argument
ATTACK_WEIGHT: dict[AttackType, float] = {
    AttackType.EVIDENCE_CONFLICT: 0.9,
    AttackType.POLICY_MISMATCH: 0.8,
    AttackType.RULE_CONFLICT: 0.7,
    AttackType.MISSING_DATA: 0.6,
    AttackType.LOGIC_FLAW: 0.5,
}


@dataclass
class Argument:
    """A single argument produced by an agent in a debate round."""
    arg_id: str                    # "arg_{agent}_{round}_{seq}"
    text: str                      # argument content
    source_agent: str              # agent that produced this
    round_num: int                 # debate round
    evidence_refs: list[str]       # referenced evidence IDs
    stance: ArgumentStance         # structured stance
    confidence: float              # objective confidence (from compute_argument_confidence)
    attacks: list[str]             # Agent-suggested attack targets (validated by AttackDetector)
    supported_by: list[str]        # supporting argument IDs
    attack_type: AttackType | None = None  # if this is an attacking argument
    status: str = "active"         # "active" | "defeated" | "undecided"


@dataclass
class AttackRelation:
    """A validated attack relation between two arguments."""
    attacker_id: str
    target_id: str
    attack_type: AttackType
    evidence: str                  # basis for the attack
    weight: float                  # 0.0-1.0


@dataclass
class ArgumentGraph:
    """Manages arguments and attack relations with acceptable set computation."""
    arguments: dict[str, Argument] = field(default_factory=dict)
    attack_edges: list[AttackRelation] = field(default_factory=list)

    def add_argument(self, arg: Argument) -> None:
        self.arguments[arg.arg_id] = arg

    def add_attack(self, attack: AttackRelation) -> None:
        self.attack_edges.append(attack)

    def get_active_arguments(self) -> list[Argument]:
        return [a for a in self.arguments.values() if a.status == "active"]

    def get_attacks_on(self, arg_id: str) -> list[AttackRelation]:
        return [e for e in self.attack_edges if e.target_id == arg_id]

    def get_attacks_by(self, arg_id: str) -> list[AttackRelation]:
        return [e for e in self.attack_edges if e.attacker_id == arg_id]

    def compute_acceptable_set(self) -> set[str]:
        """Simplified Grounded Semantics: iteratively find acceptable arguments.

        1. Start with arguments that have no attackers → acceptable
        2. Arguments attacked only by non-acceptable args → acceptable
        3. Arguments attacked by acceptable args with high weight → defeated
        4. Repeat until stable

        Returns:
            Set of acceptable argument IDs.
        """
        if not self.arguments:
            return set()

        acceptable: set[str] = set()
        defeated: set[str] = set()
        changed = True
        max_iterations = len(self.arguments) + 1

        for _ in range(max_iterations):
            if not changed:
                break
            changed = False

            for arg_id, arg in self.arguments.items():
                if arg_id in acceptable or arg_id in defeated:
                    continue

                attackers = self.get_attacks_on(arg_id)
                if not attackers:
                    # No attackers → acceptable
                    acceptable.add(arg_id)
                    arg.status = "active"
                    changed = True
                    continue

                # Check if all attackers are defeated or not acceptable
                effective_attackers = [
                    a for a in attackers
                    if a.attacker_id not in defeated
                ]

                if not effective_attackers:
                    # All attackers defeated → this arg is acceptable
                    acceptable.add(arg_id)
                    changed = True
                    continue

                # Check if any attacker is acceptable with sufficient weight
                has_strong_attack = False
                for attack in effective_attackers:
                    if attack.attacker_id in acceptable:
                        attacker = self.arguments.get(attack.attacker_id)
                        attacker_confidence = attacker.confidence if attacker else 0.0
                        effective_strength = attack.weight * attacker_confidence
                        threshold = max(0.55, arg.confidence * 0.85)
                        if effective_strength >= threshold:
                            has_strong_attack = True
                            break

                if has_strong_attack:
                    defeated.add(arg_id)
                    arg.status = "defeated"
                    changed = True
                elif not any(a.attacker_id in acceptable for a in effective_attackers):
                    # No acceptable attackers → this arg becomes acceptable
                    acceptable.add(arg_id)
                    changed = True

        # Mark remaining non-acceptable, non-defeated as undecided
        for arg_id, arg in self.arguments.items():
            if arg_id not in acceptable and arg_id not in defeated:
                arg.status = "undecided"

        return acceptable

    def finalize_arguments(self) -> dict[str, str]:
        """Compute acceptable set and return arg_id → final status.

        UNDECIDED arguments are explicitly marked for human review.
        """
        acceptable = self.compute_acceptable_set()
        result = {}
        for arg_id, arg in self.arguments.items():
            if arg_id in acceptable:
                result[arg_id] = "accepted"
            elif arg.status == "defeated":
                result[arg_id] = "defeated"
            else:
                result[arg_id] = "undecided"
        return result

    def has_converged(self, previous_acceptable: set[str]) -> bool:
        """Check if the acceptable set has stabilized."""
        current = self.compute_acceptable_set()
        return current == previous_acceptable

    def has_new_attacks(self, since_round: int) -> bool:
        """Check if any new attacks were added since a given round."""
        # This is checked by comparing attack_edges count before/after a round
        return True  # placeholder — actual check done in orchestrator

    def to_dict(self) -> dict[str, Any]:
        """Serialize the graph for persistence/debugging."""
        return {
            "arguments": {
                aid: {
                    "arg_id": a.arg_id,
                    "text": a.text,
                    "source_agent": a.source_agent,
                    "round_num": a.round_num,
                    "evidence_refs": a.evidence_refs,
                    "stance": a.stance.value,
                    "confidence": a.confidence,
                    "attacks": a.attacks,
                    "supported_by": a.supported_by,
                    "attack_type": a.attack_type.value if a.attack_type else None,
                    "status": a.status,
                }
                for aid, a in self.arguments.items()
            },
            "attack_edges": [
                {
                    "attacker": e.attacker_id,
                    "target": e.target_id,
                    "type": e.attack_type.value,
                    "evidence": e.evidence,
                    "weight": e.weight,
                }
                for e in self.attack_edges
            ],
            "acceptable_count": sum(
                1 for a in self.arguments.values() if a.status == "active"
            ),
            "defeated_count": sum(
                1 for a in self.arguments.values() if a.status == "defeated"
            ),
            "undecided_count": sum(
                1 for a in self.arguments.values() if a.status == "undecided"
            ),
        }
