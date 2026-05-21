"""Test third batch: debate_memory, attack_detector, argumentation integration."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.debate_memory import (
    Argument,
    ArgumentGraph,
    ArgumentStance,
    AttackRelation,
    AttackType,
    ATTACK_WEIGHT,
)
from agents.attack_detector import AttackDetector
from agents.optimization_algorithms import compute_argument_confidence
from evidence.evidence_projection import EvidenceProjection, EvidenceSummaryCard


def make_arg(arg_id, stance, refs, confidence=0.7, source="agent_test", attacks=None):
    return Argument(
        arg_id=arg_id,
        text=f"Argument {arg_id}",
        source_agent=source,
        round_num=0,
        evidence_refs=refs,
        stance=stance,
        confidence=confidence,
        attacks=attacks or [],
        supported_by=[],
    )


# ── Test 1: ArgumentGraph basic operations ───────────────────────────────
def test_argument_graph_basic():
    print("=" * 60)
    print("TEST 1: ArgumentGraph basic operations")
    print("=" * 60)

    graph = ArgumentGraph()
    a1 = make_arg("a1", ArgumentStance.PASS, ["ev_R001"], 0.8)
    a2 = make_arg("a2", ArgumentStance.REJECT, ["ev_R002"], 0.6)

    graph.add_argument(a1)
    graph.add_argument(a2)
    assert len(graph.arguments) == 2
    print("  [OK] Add arguments")

    # Add attack
    attack = AttackRelation(
        attacker_id="a1", target_id="a2",
        attack_type=AttackType.REBUTTAL,
        evidence="shared R001", weight=0.9,
    )
    graph.add_attack(attack)
    assert len(graph.attack_edges) == 1
    print("  [OK] Add attack")

    # Active arguments
    active = graph.get_active_arguments()
    assert len(active) == 2
    print("  [OK] Active arguments")

    # Serialization
    d = graph.to_dict()
    assert "arguments" in d
    assert "attack_edges" in d
    print("  [OK] Serialization")
    print()


# ── Test 2: Acceptable set computation ───────────────────────────────────
def test_acceptable_set():
    print("=" * 60)
    print("TEST 2: Grounded Semantics acceptable set")
    print("=" * 60)

    # Case 1: No attacks -> all acceptable
    graph1 = ArgumentGraph()
    graph1.add_argument(make_arg("a1", ArgumentStance.PASS, [], 0.8))
    graph1.add_argument(make_arg("a2", ArgumentStance.PASS, [], 0.7))
    acceptable1 = graph1.compute_acceptable_set()
    print(f"  No attacks: acceptable={acceptable1}")
    assert acceptable1 == {"a1", "a2"}
    print("  [OK] All acceptable when no attacks")

    # Case 2: a1 attacks a2, a1 has no attacker -> a1 acceptable, a2 defeated
    graph2 = ArgumentGraph()
    graph2.add_argument(make_arg("a1", ArgumentStance.PASS, ["ev_R001"], 0.8))
    graph2.add_argument(make_arg("a2", ArgumentStance.REJECT, ["ev_R002"], 0.5))
    graph2.add_attack(AttackRelation(
        attacker_id="a1", target_id="a2",
        attack_type=AttackType.DEFEATER,
        evidence="stance conflict", weight=0.7,
    ))
    acceptable2 = graph2.compute_acceptable_set()
    print(f"  a1 attacks a2: acceptable={acceptable2}")
    assert "a1" in acceptable2
    assert "a2" not in acceptable2
    print("  [OK] Attacker accepted, target defeated")

    # Case 3: Mutual attack -> stronger one wins
    graph3 = ArgumentGraph()
    graph3.add_argument(make_arg("a1", ArgumentStance.PASS, [], 0.8))
    graph3.add_argument(make_arg("a2", ArgumentStance.REJECT, [], 0.4))
    graph3.add_attack(AttackRelation(
        attacker_id="a1", target_id="a2",
        attack_type=AttackType.REBUTTAL, evidence="conflict", weight=0.9,
    ))
    graph3.add_attack(AttackRelation(
        attacker_id="a2", target_id="a1",
        attack_type=AttackType.UNDERCUT, evidence="flaw", weight=0.5,
    ))
    acceptable3 = graph3.compute_acceptable_set()
    print(f"  Mutual attack: acceptable={acceptable3}")
    # a1 (0.8 conf) attacks a2 with 0.9 weight -> a2 defeated
    # a2 (0.4 conf) attacks a1 with 0.5 weight -> 0.5 < 0.8, not strong enough
    assert "a1" in acceptable3
    print("  [OK] Stronger argument survives")
    print()


# ── Test 3: Finalize arguments ───────────────────────────────────────────
def test_finalize_arguments():
    print("=" * 60)
    print("TEST 3: Finalize arguments (UNDECIDED mapping)")
    print("=" * 60)

    graph = ArgumentGraph()
    graph.add_argument(make_arg("a1", ArgumentStance.PASS, [], 0.8))
    graph.add_argument(make_arg("a2", ArgumentStance.REJECT, [], 0.7))
    # Mutual attack with similar weights -> both might end up undecided
    graph.add_attack(AttackRelation(
        attacker_id="a1", target_id="a2",
        attack_type=AttackType.REBUTTAL, evidence="conflict", weight=0.9,
    ))
    graph.add_attack(AttackRelation(
        attacker_id="a2", target_id="a1",
        attack_type=AttackType.REBUTTAL, evidence="conflict", weight=0.9,
    ))

    statuses = graph.finalize_arguments()
    print(f"  Final statuses: {statuses}")

    for arg_id, status in statuses.items():
        assert status in ("accepted", "defeated", "undecided"), f"Invalid status: {status}"
    print("  [OK] All statuses are valid (accepted/defeated/undecided)")

    # Check serialization includes counts
    d = graph.to_dict()
    print(f"  Counts: accepted={d['acceptable_count']}, defeated={d['defeated_count']}, undecided={d['undecided_count']}")
    print("  [OK] Serialization includes counts")
    print()


# ── Test 4: AttackDetector ───────────────────────────────────────────────
def test_attack_detector():
    print("=" * 60)
    print("TEST 4: AttackDetector")
    print("=" * 60)

    detector = AttackDetector()

    # Evidence conflict: same ref, opposite stance
    a1 = make_arg("a1", ArgumentStance.PASS, ["ev_R001"], 0.7)
    a2 = make_arg("a2", ArgumentStance.REJECT, ["ev_R001"], 0.6)
    attacks = detector.detect([a1, a2])
    print(f"  Evidence conflict: {len(attacks)} attacks")
    assert any(t.attack_type == AttackType.REBUTTAL for t in attacks)
    print("  [OK] Detected evidence conflict")

    # Stance conflict: PASS vs REJECT
    a3 = make_arg("a3", ArgumentStance.PASS, ["ev_R003"], 0.8)
    a4 = make_arg("a4", ArgumentStance.REJECT, ["ev_R004"], 0.5)
    attacks2 = detector.detect([a3, a4])
    print(f"  Stance conflict: {len(attacks2)} attacks")
    assert any(t.attack_type == AttackType.DEFEATER for t in attacks2)
    print("  [OK] Detected stance/rule conflict")

    # No attack when same stance
    a5 = make_arg("a5", ArgumentStance.PASS, ["ev_R005"], 0.7)
    a6 = make_arg("a6", ArgumentStance.PASS, ["ev_R006"], 0.8)
    attacks3 = detector.detect([a5, a6])
    # Should have no evidence_conflict or rule_conflict (same stance, different refs)
    conflict_attacks = [t for t in attacks3 if t.attack_type in (AttackType.REBUTTAL, AttackType.DEFEATER)]
    assert len(conflict_attacks) == 0
    print("  [OK] No conflict attack for same stance")
    print()


# ── Test 5: Missing data attack ──────────────────────────────────────────
def test_missing_data_attack():
    print("=" * 60)
    print("TEST 5: Missing data attack with projection")
    print("=" * 60)

    detector = AttackDetector()
    projection = EvidenceProjection(
        task_header="test",
        target_person="test",
        policy_scope="test",
        cards=[
            EvidenceSummaryCard(
                card_id="card_R001", question="q", finding="f",
                status="missing", confidence=0.0,
            ),
            EvidenceSummaryCard(
                card_id="card_R002", question="q", finding="f",
                status="supports", confidence=0.9,
            ),
        ],
    )

    # a1 relies on missing evidence R001, a2 relies on good evidence R002
    a1 = make_arg("a1", ArgumentStance.PASS, ["R001"], 0.5)
    a2 = make_arg("a2", ArgumentStance.REJECT, ["R002"], 0.8)

    attacks = detector.detect([a1, a2], projection)
    missing_attacks = [t for t in attacks if t.attack_type == AttackType.UNDERMINING]
    print(f"  Missing data attacks: {len(missing_attacks)}")
    assert len(missing_attacks) > 0
    print("  [OK] Detected missing data attack")
    print()


# ── Test 6: compute_argument_confidence ──────────────────────────────────
def test_argument_confidence():
    print("=" * 60)
    print("TEST 6: compute_argument_confidence")
    print("=" * 60)

    projection = EvidenceProjection(
        task_header="test",
        target_person="test",
        policy_scope="test",
        cards=[
            EvidenceSummaryCard(
                card_id="card_R001", question="q", finding="f",
                status="supports", confidence=0.9,
                evidence_score=85.0,
            ),
        ],
    )
    evidence_scores = {"R001": 85.0}

    arg = make_arg("a1", ArgumentStance.PASS, ["R001"], 0.5)
    conf = compute_argument_confidence(arg, projection, evidence_scores)
    print(f"  Good evidence arg confidence: {conf}")
    assert conf > 0.5
    print("  [OK] Good evidence -> higher confidence")

    arg_bad = make_arg("a2", ArgumentStance.PASS, [], 0.5)
    conf_bad = compute_argument_confidence(arg_bad, projection, evidence_scores)
    print(f"  No evidence arg confidence: {conf_bad}")
    assert conf_bad < conf
    print("  [OK] No evidence -> lower confidence")
    print()


# ── Test 7: AgentJudgment arguments field ────────────────────────────────
def test_judgment_arguments():
    print("=" * 60)
    print("TEST 7: AgentJudgment arguments field")
    print("=" * 60)
    from agents.base_agent import AgentJudgment

    j = AgentJudgment(
        agent_id="test",
        agent_role="TestAgent",
        conclusion="符合",
        stance="支持通过",
        confidence=0.8,
        evidence_refs=["ev_R001"],
        reasoning="test reasoning " * 5,
        arguments=[
            {
                "arg_text": "Evidence supports approval",
                "evidence_refs": ["ev_R001"],
                "stance": "pass",
                "attacks": [],
                "supported_by": [],
            }
        ],
    )
    assert len(j.arguments) == 1
    assert j.arguments[0]["stance"] == "pass"
    print("  [OK] AgentJudgment accepts arguments field")

    # Default empty
    j2 = AgentJudgment(
        agent_id="test2",
        agent_role="TestAgent2",
        conclusion="符合",
        stance="支持通过",
        confidence=0.8,
        reasoning="test reasoning " * 5,
    )
    assert j2.arguments == []
    print("  [OK] Default arguments is empty list")
    print()


def test_fallback_argument_stance_from_conclusion():
    print("=" * 60)
    print("TEST 8: Fallback argument stance uses conclusion first")
    print("=" * 60)

    from typing import get_args

    from agents.base_agent import AgentJudgment
    from agents.debate_orchestrator import DebateOrchestrator

    conclusions = get_args(AgentJudgment.model_fields["conclusion"].annotation)
    stances = get_args(AgentJudgment.model_fields["stance"].annotation)
    judgment = AgentJudgment(
        agent_id="agent_test",
        agent_role="TestAgent",
        conclusion=conclusions[0],
        stance=stances[2],
        confidence=0.8,
        reasoning="test reasoning " * 5,
        key_finding="fallback should follow conclusion",
    )

    orchestrator = DebateOrchestrator.__new__(DebateOrchestrator)
    inferred = orchestrator._infer_argument_stance(judgment, judgment.key_finding)

    assert inferred == ArgumentStance.PASS
    print("  [OK] Conclusion overrides pending vote stance for fallback arguments")
    print()


def test_argumentation_consensus_updates_record_conclusion():
    print("=" * 60)
    print("TEST 9: Argumentation consensus updates DebateRecord")
    print("=" * 60)

    from typing import get_args

    from agents.base_agent import AgentJudgment
    from agents.debate_orchestrator import DebateOrchestrator, DebateRecord

    conclusions = get_args(AgentJudgment.model_fields["conclusion"].annotation)
    stances = get_args(AgentJudgment.model_fields["stance"].annotation)
    judgment = AgentJudgment(
        agent_id="agent_test",
        agent_role="TestAgent",
        conclusion=conclusions[2],
        stance=stances[2],
        confidence=0.5,
        reasoning="test reasoning " * 5,
        key_finding="initial record is pending",
    )
    record = DebateRecord([judgment], 0)

    graph = ArgumentGraph()
    graph.add_argument(make_arg("a1", ArgumentStance.PASS, [], 0.95))
    graph.add_argument(make_arg("a2", ArgumentStance.PASS, [], 0.9))

    orchestrator = DebateOrchestrator.__new__(DebateOrchestrator)
    orchestrator._update_record_argumentation(record, graph)

    assert record.argumentation_consensus_reached
    assert record.argumentation_stance == "pass"
    assert record.get_final_conclusion() == conclusions[0]
    print("  [OK] Accepted arguments can drive final conclusion")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("THIRD BATCH VERIFICATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_argument_graph_basic,
        test_acceptable_set,
        test_finalize_arguments,
        test_attack_detector,
        test_missing_data_attack,
        test_argument_confidence,
        test_judgment_arguments,
        test_fallback_argument_stance_from_conclusion,
        test_argumentation_consensus_updates_record_conclusion,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    print("\nAll tests passed!")
