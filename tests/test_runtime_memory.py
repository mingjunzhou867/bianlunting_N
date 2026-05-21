"""Tests for session memory extraction."""
from __future__ import annotations

import unittest

from agents.base_agent import AgentJudgment
from agents.debate_orchestrator import DebateRecord
from evidence.evidence_model import EvidenceBundle, EvidenceItem
from runtime.memory import SessionMemoryStore, build_session_memory_snapshot


PASS = "符合"
SUPPORT = "支持通过"


def build_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        id_card="42090219760310000D",
        items=[
            EvidenceItem(
                evidence_id="EV_001",
                rule_id="RULE_001",
                target_id_card="42090219760310000D",
                target="basic check",
                category="qualification",
                sql="SELECT 1",
                result_raw=[{"ok": 1}],
                result_summary="basic evidence exists",
                supports_conclusion=True,
                confidence=1.0,
                exec_status="success",
            )
        ],
    )


def build_history() -> list[DebateRecord]:
    judgment = AgentJudgment(
        agent_id="agent_1",
        agent_role="strict",
        debate_round=0,
        conclusion=PASS,
        stance=SUPPORT,
        confidence=0.9,
        evidence_refs=["EV_001"],
        reasoning="evidence supports approval",
        dissent_points=[],
        key_finding="basic evidence supports approval",
    )
    return [DebateRecord([judgment], 0)]


class RuntimeMemoryTests(unittest.TestCase):
    def test_session_memory_store_counts_trust_levels(self) -> None:
        store = SessionMemoryStore("session-1", "POLICY_001")
        store.add("P0_DATA", "evidence", "EV_001", "fact")
        store.add("P3_AGENT", "agent_judgment", "agent_1", "view")

        snapshot = store.to_snapshot()

        self.assertEqual(snapshot["counts_by_trust_level"]["P0_DATA"], 1)
        self.assertEqual(snapshot["counts_by_trust_level"]["P3_AGENT"], 1)
        self.assertEqual(snapshot["records"][0]["memory_id"], "mem_0001")

    def test_build_session_memory_snapshot_layers_sources(self) -> None:
        bundle = build_bundle()
        history = build_history()
        traces = [
            {
                "event_id": "trace_0001",
                "stage": "tool",
                "action": "tool_call_failed",
                "status": "danger",
                "log": "tool failed",
                "payload": {"tool_name": "text_to_sql"},
            }
        ]

        snapshot = build_session_memory_snapshot(
            session_id="session-1",
            policy_id="POLICY_001",
            bundle=bundle,
            history=history,
            final_record=history[-1],
            manual_supplements=[{"supplement_id": "SUP_001", "clause_id": "RULE_001", "detail": "manual proof"}],
            system_traces=traces,
        )

        self.assertEqual(snapshot["policy_id"], "POLICY_001")
        self.assertEqual(snapshot["counts_by_trust_level"]["P0_DATA"], 1)
        self.assertEqual(snapshot["counts_by_trust_level"]["P1_MANUAL"], 1)
        self.assertEqual(snapshot["counts_by_trust_level"]["P2_DECISION"], 1)
        self.assertEqual(snapshot["counts_by_trust_level"]["P3_AGENT"], 1)
        self.assertEqual(snapshot["counts_by_trust_level"]["P4_INFERRED"], 1)


if __name__ == "__main__":
    unittest.main()
