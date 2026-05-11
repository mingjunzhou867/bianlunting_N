"""Test second batch: DebateRecord weighted fields, project_evidence scoring,
adjudication_report score fields, base_agent projection check."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evidence.evidence_model import EvidenceItem, EvidenceBundle
from evidence.evidence_projection import EvidenceProjection, EvidenceSummaryCard


def make_evidence_item(
    rule_id: str,
    supports: bool | None = True,
    exec_status: str = "success",
    category: str = "社保",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{rule_id}",
        rule_id=rule_id,
        target_id_card="330100199001010001",
        target="测试人",
        category=category,
        sql=f"SELECT * FROM t WHERE rule='{rule_id}'",
        result_raw=[{"result": "ok"}] if exec_status == "success" else [],
        result_summary=f"{rule_id} 查询结果" if exec_status == "success" else "",
        supports_conclusion=supports,
        confidence=0.9 if exec_status == "success" else 0.3,
        exec_status=exec_status,
        time_range="2025-01 至 2025-12",
    )


def make_judgment(conclusion: str, confidence: float = 0.8, refs=None, agent_id="test"):
    from agents.base_agent import AgentJudgment
    stance_map = {"符合": "支持通过", "不符合": "反对通过", "数据缺失": "待定"}
    return AgentJudgment(
        agent_id=agent_id,
        agent_role=f"Test_{agent_id}",
        conclusion=conclusion,
        stance=stance_map.get(conclusion, "待定"),
        confidence=confidence,
        evidence_refs=refs or [],
        reasoning="test reasoning " * 5,
    )


# ── Test 1: project_evidence with scoring ────────────────────────────────
def test_project_evidence_scoring():
    print("=" * 60)
    print("TEST 1: project_evidence with evidence scoring")
    print("=" * 60)
    from agents.debate_orchestrator import project_evidence

    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True, category="社保"),
            make_evidence_item("R002", supports=False, category="个人自述"),
        ],
    )
    projection = project_evidence(bundle)

    card0 = projection.cards[0]
    print(f"  Card 0: score={card0.evidence_score}, percent={card0.evidence_score_percent}")
    print(f"    breakdown={card0.score_breakdown}")
    print(f"    reason={card0.rank_reason}")
    assert card0.evidence_score > 0, "Expected score > 0"
    assert card0.score_breakdown, "Expected non-empty breakdown"
    print("  [OK] Cards have score fields")

    # Higher quality card should come first (sorted)
    assert projection.cards[0].evidence_score >= projection.cards[1].evidence_score
    print("  [OK] Cards sorted by score descending")
    print()


# ── Test 2: DebateRecord weighted fields ─────────────────────────────────
def test_debate_record_weighted():
    print("=" * 60)
    print("TEST 2: DebateRecord weighted fields")
    print("=" * 60)
    from agents.debate_orchestrator import DebateRecord, project_evidence

    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
        ],
    )
    projection = project_evidence(bundle)

    judgments = [
        make_judgment("符合", 0.9, ["ev_R001"], "a1"),
        make_judgment("符合", 0.8, ["ev_R001"], "a2"),
        make_judgment("符合", 0.7, ["ev_R001"], "a3"),
    ]
    record = DebateRecord(judgments, 0, projection=projection, evidence_items=bundle.items)

    print(f"  weighted_stance: {record.weighted_stance}")
    print(f"  weighted_confidence: {record.weighted_confidence}")
    print(f"  weighted_scores: {record.weighted_scores}")
    print(f"  agent_weights: {record.agent_weights}")

    assert record.weighted_stance == "支持通过"
    assert record.weighted_confidence > 0
    assert len(record.agent_weights) == 3
    print("  [OK] Weighted fields computed correctly")

    # to_dict includes new fields
    d = record.to_dict()
    assert "weighted_stance" in d
    assert "weighted_confidence" in d
    assert "weighted_scores" in d
    assert "agent_weights" in d
    print("  [OK] to_dict includes weighted fields")
    print()


# ── Test 3: adjudication_report score fields ─────────────────────────────
def test_adjudication_report_scoring():
    print("=" * 60)
    print("TEST 3: adjudication_report score fields")
    print("=" * 60)
    from agents.debate_orchestrator import DebateRecord, project_evidence
    from agents.adjudication_report import build_adjudication_report

    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
        ],
    )
    projection = project_evidence(bundle)
    judgments = [
        make_judgment("符合", 0.9, ["ev_R001"], "a1"),
        make_judgment("符合", 0.8, ["ev_R001"], "a2"),
    ]
    record = DebateRecord(judgments, 0, projection=projection, evidence_items=bundle.items)

    report = build_adjudication_report(
        policy_id="test",
        bundle=bundle,
        history=[record],
        final_record=record,
    )

    summary = report["summary"]
    print(f"  summary.avg_clause_confidence: {summary.get('avg_clause_confidence')}")
    print(f"  summary.weighted_stance: {summary.get('weighted_stance')}")
    print(f"  summary.weighted_confidence: {summary.get('weighted_confidence')}")
    print(f"  summary.algorithm_version: {summary.get('algorithm_version')}")

    assert "avg_clause_confidence" in summary
    assert "weighted_stance" in summary
    assert "weighted_confidence" in summary
    assert summary["algorithm_version"] == "backend_optimization_v1"
    print("  [OK] Summary has new fields")

    # Check clause-level score fields
    if report["clause_results"]:
        clause = report["clause_results"][0]
        print(f"  clause[0].evidence_score: {clause.get('evidence_score')}")
        print(f"  clause[0].clause_confidence: {clause.get('clause_confidence')}")
        assert "evidence_score" in clause
        assert "clause_confidence" in clause
        print("  [OK] Clause has score fields")
    print()


# ── Test 4: base_agent projection check ──────────────────────────────────
def test_projection_check():
    print("=" * 60)
    print("TEST 4: base_agent projection check method")
    print("=" * 60)
    from agents.base_agent import BaseAgent

    # All supportive
    proj_support = EvidenceProjection(
        task_header="test",
        target_person="test",
        policy_scope="test",
        cards=[
            EvidenceSummaryCard(card_id="c1", question="q", finding="f",
                                status="supports", confidence=0.9),
            EvidenceSummaryCard(card_id="c2", question="q", finding="f",
                                status="missing", confidence=0.0),
        ],
    )
    assert BaseAgent._projection_has_only_supportive_or_missing_evidence(proj_support)
    print("  [OK] supports + missing -> True")

    # Has contradicts
    proj_contra = EvidenceProjection(
        task_header="test",
        target_person="test",
        policy_scope="test",
        cards=[
            EvidenceSummaryCard(card_id="c1", question="q", finding="f",
                                status="supports", confidence=0.9),
            EvidenceSummaryCard(card_id="c2", question="q", finding="f",
                                status="contradicts", confidence=0.8),
        ],
    )
    assert not BaseAgent._projection_has_only_supportive_or_missing_evidence(proj_contra)
    print("  [OK] has contradicts -> False")
    print()


# ── Test 5: dual consensus ───────────────────────────────────────────────
def test_dual_consensus():
    print("=" * 60)
    print("TEST 5: dual consensus condition")
    print("=" * 60)
    from agents.debate_orchestrator import DebateRecord, project_evidence
    from config.settings import settings

    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[make_evidence_item("R001", supports=True)],
    )
    projection = project_evidence(bundle)

    # All agree with high confidence -> consensus
    judgments_high = [
        make_judgment("符合", 0.95, ["ev_R001"], "a1"),
        make_judgment("符合", 0.95, ["ev_R001"], "a2"),
        make_judgment("符合", 0.95, ["ev_R001"], "a3"),
    ]
    record_high = DebateRecord(judgments_high, 0, projection=projection, evidence_items=bundle.items)
    print(f"  High conf: consensus_rate={record_high.consensus_rate:.2f}, "
          f"weighted_conf={record_high.weighted_confidence:.2f}, "
          f"reached={record_high.is_consensus_reached}")
    assert record_high.is_consensus_reached
    print("  [OK] High confidence consensus reached")

    # All agree but low confidence -> should NOT reach consensus
    judgments_low = [
        make_judgment("符合", 0.3, ["ev_R001"], "a1"),
        make_judgment("符合", 0.3, ["ev_R001"], "a2"),
        make_judgment("符合", 0.3, ["ev_R001"], "a3"),
    ]
    record_low = DebateRecord(judgments_low, 0, projection=projection, evidence_items=bundle.items)
    print(f"  Low conf: consensus_rate={record_low.consensus_rate:.2f}, "
          f"weighted_conf={record_low.weighted_confidence:.2f}, "
          f"reached={record_low.is_consensus_reached}")
    # With dual consensus, low weighted_confidence should prevent consensus
    assert not record_low.is_consensus_reached
    print("  [OK] Low confidence prevents consensus")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SECOND BATCH VERIFICATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_project_evidence_scoring,
        test_debate_record_weighted,
        test_adjudication_report_scoring,
        test_projection_check,
        test_dual_consensus,
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
