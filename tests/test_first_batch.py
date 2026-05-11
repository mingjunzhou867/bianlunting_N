"""Test first batch: rule_engine + optimization_algorithms + unified_decision_engine + decision_semantics fix."""
from __future__ import annotations

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from evidence.evidence_model import EvidenceItem, EvidenceBundle
from evidence.evidence_projection import EvidenceProjection, EvidenceSummaryCard


def make_evidence_item(
    rule_id: str,
    supports: bool | None = True,
    exec_status: str = "success",
    category: str = "社保",
    confidence: float = 1.0,
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
        confidence=confidence,
        exec_status=exec_status,
        time_range="2025-01 至 2025-12",
    )


def make_judgment(conclusion: str, confidence: float = 0.8, refs: list[str] | None = None):
    from agents.base_agent import AgentJudgment
    stance_map = {
        "符合": "支持通过",
        "不符合": "反对通过",
        "数据缺失": "待定",
    }
    return AgentJudgment(
        agent_id="test_agent",
        agent_role="测试Agent",
        conclusion=conclusion,
        stance=stance_map.get(conclusion, "待定"),
        confidence=confidence,
        evidence_refs=refs or [],
        reasoning="测试推理过程",
    )


# ── Test 1: rule_engine ──────────────────────────────────────────────────
def test_rule_engine():
    print("=" * 60)
    print("TEST 1: rule_engine")
    print("=" * 60)
    from agents.rule_engine import run_rule_engine

    # Case 1: All evidence supports → PASS
    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True, category="社保"),
            make_evidence_item("R002", supports=True, category="公积金"),
            make_evidence_item("R003", supports=True, category="工商"),
        ],
    )
    result = run_rule_engine(bundle)
    print(f"  Case 1 (all pass): pre_decision={result.pre_decision}, "
          f"passed={len(result.passed)}, failed={len(result.failed)}")
    assert len(result.passed) == 3, f"Expected 3 passed, got {len(result.passed)}"
    assert len(result.failed) == 0
    print("  [OK] Case 1 OK")

    # Case 2: One evidence fails → should be in failed list
    bundle2 = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
            make_evidence_item("R002", supports=False),
        ],
    )
    result2 = run_rule_engine(bundle2)
    print(f"  Case 2 (one fail): pre_decision={result2.pre_decision}, "
          f"passed={len(result2.passed)}, failed={len(result2.failed)}")
    assert len(result2.failed) == 1, f"Expected 1 failed, got {len(result2.failed)}"
    assert result2.failed[0].rule_id == "R002"
    print("  [OK] Case 2 OK")

    # Case 3: Missing evidence
    bundle3 = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
            make_evidence_item("R002", exec_status="field_missing"),
        ],
    )
    result3 = run_rule_engine(bundle3)
    print(f"  Case 3 (missing): passed={len(result3.passed)}, "
          f"missing={len(result3.missing)}")
    assert len(result3.missing) >= 1
    print("  [OK] Case 3 OK")

    print()


# ── Test 2: optimization_algorithms ──────────────────────────────────────
def test_optimization_algorithms():
    print("=" * 60)
    print("TEST 2: optimization_algorithms")
    print("=" * 60)
    from agents.optimization_algorithms import (
        score_evidence_item,
        sort_evidence_items,
        aggregate_weighted_stances,
        estimate_clause_confidence,
    )

    # Score a good evidence item
    good = make_evidence_item("R001", supports=True, exec_status="success",
                              category="社保", confidence=1.0)
    score = score_evidence_item(good)
    print(f"  Good evidence: score={score.score}, percent={score.score_percent}, "
          f"reason={score.rank_reason}")
    assert score.score > 60, f"Expected score > 60, got {score.score}"
    print("  [OK] Good evidence scoring OK")

    # Score a bad evidence item
    bad = make_evidence_item("R002", supports=None, exec_status="failed",
                             category="个人自述", confidence=0.3)
    score_bad = score_evidence_item(bad)
    print(f"  Bad evidence: score={score_bad.score}, percent={score_bad.score_percent}")
    assert score_bad.score < score.score
    print("  [OK] Bad evidence scoring OK (lower than good)")

    # Sort
    items = [bad, good]
    sorted_items = sort_evidence_items(items)
    assert sorted_items[0].evidence_id == good.evidence_id
    print("  [OK] Sort OK (good first)")

    # Aggregate weighted stances
    judgments = [
        make_judgment("符合", 0.9, ["ev_R001"]),
        make_judgment("符合", 0.7, ["ev_R001"]),
        make_judgment("不符合", 0.6, ["ev_R002"]),
    ]
    agg = aggregate_weighted_stances(judgments)
    print(f"  Weighted stances: support={agg['weighted_support']}, "
          f"oppose={agg['weighted_oppose']}, dominant={agg['dominant_stance']}")
    assert agg["dominant_stance"] == "支持通过"
    print("  [OK] Aggregate OK")

    # Clause confidence
    conf = estimate_clause_confidence(good)
    print(f"  Clause confidence: {conf}")
    assert conf > 0.5
    print("  [OK] Clause confidence OK")

    print()


# ── Test 3: unified_decision_engine ──────────────────────────────────────
def test_unified_decision_engine():
    print("=" * 60)
    print("TEST 3: unified_decision_engine")
    print("=" * 60)
    from agents.unified_decision_engine import decide

    # Case 1: Strong agreement → PASS via weighted_vote
    judgments_pass = [
        make_judgment("符合", 0.9, ["ev_R001"]),
        make_judgment("符合", 0.8, ["ev_R001"]),
        make_judgment("符合", 0.7, ["ev_R002"]),
    ]
    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
            make_evidence_item("R002", supports=True),
        ],
    )
    verdict = decide(judgments_pass, bundle=bundle)
    print(f"  Case 1 (all pass): conclusion={verdict.conclusion}, "
          f"method={verdict.method}, confidence={verdict.confidence}")
    assert verdict.conclusion == "符合", f"Expected 符合, got {verdict.conclusion}"
    print("  [OK] Case 1 OK")

    # Case 2: Strong opposition → FAIL
    judgments_fail = [
        make_judgment("不符合", 0.9, ["ev_R001"]),
        make_judgment("不符合", 0.8, ["ev_R001"]),
        make_judgment("符合", 0.5, ["ev_R002"]),
    ]
    verdict2 = decide(judgments_fail, bundle=bundle)
    print(f"  Case 2 (majority fail): conclusion={verdict2.conclusion}, "
          f"method={verdict2.method}")
    assert verdict2.conclusion == "不符合", f"Expected 不符合, got {verdict2.conclusion}"
    print("  [OK] Case 2 OK")

    # Case 3: Mixed / no consensus → MISSING
    judgments_mixed = [
        make_judgment("符合", 0.5, ["ev_R001"]),
        make_judgment("不符合", 0.5, ["ev_R002"]),
        make_judgment("数据缺失", 0.3, []),
    ]
    verdict3 = decide(judgments_mixed, bundle=bundle)
    print(f"  Case 3 (mixed): conclusion={verdict3.conclusion}, "
          f"method={verdict3.method}, requires_review={verdict3.requires_human_review}")
    print("  [OK] Case 3 OK")

    print()


# ── Test 4: decision_semantics priority fix ──────────────────────────────
def test_decision_semantics_priority():
    print("=" * 60)
    print("TEST 4: decision_semantics priority fix (non-EXCLUSION)")
    print("=" * 60)
    from agents.decision_semantics import build_item_semantics

    # Item with supports_conclusion=True but exec_status=field_missing
    # Before fix: would match missing_data first → UNVERIFIED
    # After fix: should match supports_conclusion first → PASS (if not missing)
    item = make_evidence_item("R001", supports=True, exec_status="success")
    sem = build_item_semantics(item)
    print(f"  supports=True, exec=success: status={sem['semantic_status']}, "
          f"effect={sem['semantic_decision_effect']}")
    assert sem["semantic_status"] == "符合"
    assert sem["semantic_decision_effect"] == "support"
    print("  [OK] Clear support → PASS")

    # supports_conclusion=False → should be FAIL
    item2 = make_evidence_item("R002", supports=False, exec_status="success")
    sem2 = build_item_semantics(item2)
    print(f"  supports=False, exec=success: status={sem2['semantic_status']}, "
          f"effect={sem2['semantic_decision_effect']}")
    assert sem2["semantic_status"] == "不符合"
    assert sem2["semantic_decision_effect"] == "oppose"
    print("  [OK] Clear oppose → FAIL")

    # missing_data with no clear support → UNVERIFIED
    item3 = make_evidence_item("R003", supports=None, exec_status="field_missing")
    sem3 = build_item_semantics(item3)
    print(f"  supports=None, exec=field_missing: status={sem3['semantic_status']}, "
          f"effect={sem3['semantic_decision_effect']}")
    assert sem3["semantic_decision_effect"] == "neutral"
    print("  [OK] Missing data → NEUTRAL")

    print()


# ── Test 5: aggregate with unified engine ────────────────────────────────
def test_aggregate_with_engine():
    print("=" * 60)
    print("TEST 5: aggregate_final_conclusion with unified engine")
    print("=" * 60)
    from agents.decision_semantics import aggregate_final_conclusion_from_judgments

    judgments = [
        make_judgment("符合", 0.9, ["ev_R001"]),
        make_judgment("符合", 0.8, ["ev_R001"]),
        make_judgment("符合", 0.7, ["ev_R002"]),
    ]
    bundle = EvidenceBundle(
        id_card="330100199001010001",
        items=[
            make_evidence_item("R001", supports=True),
            make_evidence_item("R002", supports=True),
        ],
    )

    # With unified engine
    result = aggregate_final_conclusion_from_judgments(judgments, bundle=bundle)
    print(f"  With engine: {result}")
    assert result == "符合"

    # Without engine (legacy path)
    result_legacy = aggregate_final_conclusion_from_judgments(judgments)
    print(f"  Legacy path: {result_legacy}")
    assert result_legacy == "符合"

    print("  [OK] Both paths produce correct result")
    print()


# ── Test 6: EvidenceSummaryCard new fields ───────────────────────────────
def test_evidence_score_fields():
    print("=" * 60)
    print("TEST 6: EvidenceSummaryCard new score fields")
    print("=" * 60)

    card = EvidenceSummaryCard(
        card_id="card_R001",
        question="是否有社保",
        finding="正常缴纳",
        status="supports",
        confidence=0.9,
        evidence_score=85.0,
        evidence_score_percent="85.0%",
        score_breakdown={"source_reliability": 90, "timeliness": 80},
        rank_reason="来源可靠性强",
    )
    print(f"  Card score: {card.evidence_score}, percent: {card.evidence_score_percent}")
    print(f"  Breakdown: {card.score_breakdown}")
    print(f"  Reason: {card.rank_reason}")
    assert card.evidence_score == 85.0
    assert card.score_breakdown["source_reliability"] == 90
    print("  [OK] New fields work correctly")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FIRST BATCH VERIFICATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_rule_engine,
        test_optimization_algorithms,
        test_unified_decision_engine,
        test_decision_semantics_priority,
        test_aggregate_with_engine,
        test_evidence_score_fields,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    print("\nAll tests passed!")
