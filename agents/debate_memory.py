"""Argument data structures and argumentation graph for debate memory."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from agents.proof_standards import (
    DEFEAT_THRESHOLD_BY_STANDARD,
    ProofStandard,
)


class ArgumentStance(str, Enum):
    """Structured stance for an argument."""
    PASS = "pass"               # supports approval
    REJECT = "reject"           # opposes approval
    INSUFFICIENT = "insufficient"  # data insufficient / pending


class AttackType(str, Enum):
    """Types of attack between arguments (ASPIC+ terminology).

    Maps to standard argumentation theory:
    - REBUTTAL: attacking the conclusion (same evidence, opposite conclusion)
    - UNDERCUT: attacking the inference/reasoning chain
    - UNDERMINING: attacking the evidence premises
    - DEFEATER: direct rule exception (contradictory stances)
    - POLICY_MISMATCH: wrong policy clause applied
    """
    REBUTTAL = "rebuttal"              # was EVIDENCE_CONFLICT
    DEFEATER = "defeater"              # was RULE_CONFLICT
    UNDERCUT = "undercut"              # was LOGIC_FLAW
    UNDERMINING = "undermining"        # was MISSING_DATA
    POLICY_MISMATCH = "policy_mismatch"  # unchanged


# Attack weight by type — stronger attacks are more likely to defeat an argument
ATTACK_WEIGHT: dict[AttackType, float] = {
    AttackType.REBUTTAL: 0.9,
    AttackType.POLICY_MISMATCH: 0.8,
    AttackType.DEFEATER: 0.7,
    AttackType.UNDERMINING: 0.6,
    AttackType.UNDERCUT: 0.5,
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
    proof_standard: ProofStandard = ProofStandard.PREPONDERANCE  # burden of proof


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
        """Grounded Semantics with proof-standard-aware defeat relation.

        Based on Dung (1995) Abstract Argumentation Framework:
        1. Start with arguments that have no attackers → acceptable (in grounded extension)
        2. Arguments whose all attackers are defeated → acceptable
        3. Arguments attacked by acceptable attackers with sufficient strength → defeated
        4. Repeat until fixpoint

        Defeat criterion (standard strength-based):
            effective_strength = attack.weight * attacker.confidence
            defeat iff effective_strength >= proof_standard_threshold * target.confidence

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
                        base_threshold = DEFEAT_THRESHOLD_BY_STANDARD.get(
                            arg.proof_standard, 0.55,
                        )
                        threshold = base_threshold * arg.confidence
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

    # Attack type → human-readable label for conflict summary
    _ATTACK_LABELS: ClassVar[dict[AttackType, str]] = {
        AttackType.REBUTTAL: "结论冲突",
        AttackType.DEFEATER: "规则对立",
        AttackType.UNDERCUT: "推理质疑",
        AttackType.UNDERMINING: "证据缺失",
        AttackType.POLICY_MISMATCH: "条款误用",
    }

    def summarize_conflicts(self, max_items: int = 6) -> str:
        """从攻击边生成结构化冲突摘要，供 debate_respond prompt 注入。

        纯数据格式化，无 LLM 调用，线程安全。
        """
        if not self.attack_edges:
            return ""

        lines: list[str] = ["【核心分歧】"]
        for i, edge in enumerate(self.attack_edges[:max_items]):
            attacker = self.arguments.get(edge.attacker_id)
            target = self.arguments.get(edge.target_id)
            attacker_name = attacker.source_agent if attacker else edge.attacker_id
            target_name = target.source_agent if target else edge.target_id
            label = self._ATTACK_LABELS.get(edge.attack_type, edge.attack_type.value)
            lines.append(
                f"{i + 1}. [{label}] {attacker_name} → {target_name}：{edge.evidence}"
            )

        if len(self.attack_edges) > max_items:
            lines.append(f"…等共 {len(self.attack_edges)} 项分歧")

        return "\n".join(lines)

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
                    "proof_standard": a.proof_standard.value,
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
