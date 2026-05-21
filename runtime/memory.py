"""Session memory extraction for evidence-grounded agent workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from evidence.evidence_model import EvidenceBundle, EvidenceItem


TRUST_LEVELS = {
    "P0_DATA": "database facts and system observations",
    "P1_MANUAL": "manual review and supplements",
    "P2_DECISION": "completed adjudication decisions",
    "P3_AGENT": "agent judgments and arguments",
    "P4_INFERRED": "low-trust inferred operational experience",
}


@dataclass(frozen=True)
class MemoryRecord:
    """One structured memory item extracted from a review session."""

    memory_id: str
    trust_level: str
    source_type: str
    source_id: str
    summary: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "trust_level": self.trust_level,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "summary": self.summary,
            "payload": self.payload,
        }


class SessionMemoryStore:
    """Append-only memory collector for a single completed session."""

    def __init__(self, session_id: str, policy_id: str):
        self.session_id = session_id
        self.policy_id = policy_id
        self._records: list[MemoryRecord] = []

    def add(
        self,
        trust_level: str,
        source_type: str,
        source_id: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if trust_level not in TRUST_LEVELS:
            raise ValueError(f"Unknown memory trust level: {trust_level}")
        memory_id = f"mem_{len(self._records) + 1:04d}"
        self._records.append(
            MemoryRecord(
                memory_id=memory_id,
                trust_level=trust_level,
                source_type=source_type,
                source_id=source_id,
                summary=summary,
                payload=payload or {},
            )
        )

    def to_snapshot(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self._records]
        counts: dict[str, int] = {level: 0 for level in TRUST_LEVELS}
        for record in records:
            counts[record["trust_level"]] = counts.get(record["trust_level"], 0) + 1
        return {
            "session_id": self.session_id,
            "policy_id": self.policy_id,
            "trust_levels": dict(TRUST_LEVELS),
            "counts_by_trust_level": counts,
            "records": records,
        }


def build_session_memory_snapshot(
    *,
    session_id: str,
    policy_id: str,
    bundle: EvidenceBundle,
    history: Sequence[Any],
    final_record: Any,
    manual_supplements: list[dict[str, Any]] | None = None,
    system_traces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a structured memory snapshot from a completed review session."""

    store = SessionMemoryStore(session_id=session_id, policy_id=policy_id)
    _add_evidence_memories(store, bundle.items)
    _add_manual_memories(store, manual_supplements or [])
    _add_decision_memory(store, final_record)
    _add_agent_memories(store, history)
    _add_operational_memories(store, system_traces or [])
    return store.to_snapshot()


def _add_evidence_memories(store: SessionMemoryStore, items: Sequence[EvidenceItem]) -> None:
    for item in items:
        trust_level = "P1_MANUAL" if item.manual_verified else "P0_DATA"
        summary = f"{item.rule_id}: {item.result_summary}"
        store.add(
            trust_level,
            "evidence",
            item.evidence_id,
            summary,
            {
                "rule_id": item.rule_id,
                "category": item.category,
                "exec_status": item.exec_status,
                "supports_conclusion": item.supports_conclusion,
                "confidence": item.confidence,
                "diagnostic_code": item.diagnostic_code,
                "manual_verified": item.manual_verified,
                "manual_stance": item.manual_stance,
            },
        )


def _add_manual_memories(store: SessionMemoryStore, supplements: list[dict[str, Any]]) -> None:
    for index, supplement in enumerate(supplements, start=1):
        supplement_id = str(supplement.get("supplement_id") or supplement.get("evidence_id") or index)
        clause_id = str(supplement.get("clause_id") or "")
        detail = str(supplement.get("detail") or supplement.get("result_summary") or "")
        store.add(
            "P1_MANUAL",
            "manual_supplement",
            supplement_id,
            f"{clause_id}: {detail}".strip(": "),
            {
                "clause_id": clause_id,
                "stance": supplement.get("stance") or supplement.get("manual_stance"),
                "submitted_at": supplement.get("submitted_at"),
            },
        )


def _add_decision_memory(store: SessionMemoryStore, final_record: Any) -> None:
    final_conclusion = final_record.get_final_conclusion()
    store.add(
        "P2_DECISION",
        "final_decision",
        "final_record",
        f"Final conclusion: {final_conclusion}",
        {
            "final_conclusion": final_conclusion,
            "majority_stance": getattr(final_record, "majority_stance", None),
            "consensus_rate": getattr(final_record, "consensus_rate", None),
            "round_num": getattr(final_record, "round_num", None),
            "is_consensus_reached": getattr(final_record, "is_consensus_reached", None),
        },
    )


def _add_agent_memories(store: SessionMemoryStore, history: Sequence[Any]) -> None:
    for record in history:
        round_num = getattr(record, "round_num", 0)
        for judgment in getattr(record, "judgments", []):
            agent_id = str(getattr(judgment, "agent_id", "agent"))
            source_id = f"{agent_id}_round_{round_num}"
            summary = str(getattr(judgment, "key_finding", "") or getattr(judgment, "reasoning", ""))
            store.add(
                "P3_AGENT",
                "agent_judgment",
                source_id,
                summary,
                {
                    "round_num": round_num,
                    "agent_id": agent_id,
                    "agent_role": getattr(judgment, "agent_role", ""),
                    "conclusion": getattr(judgment, "conclusion", ""),
                    "stance": getattr(judgment, "stance", ""),
                    "confidence": getattr(judgment, "confidence", 0.0),
                    "evidence_refs": list(getattr(judgment, "evidence_refs", []) or []),
                },
            )


def _add_operational_memories(store: SessionMemoryStore, traces: list[dict[str, Any]]) -> None:
    for trace in traces:
        status = str(trace.get("status") or "")
        stage = str(trace.get("stage") or "")
        if status not in {"warning", "danger"}:
            continue
        if stage not in {"tool", "evidence", "planning"}:
            continue
        source_id = str(trace.get("event_id") or trace.get("action") or "trace")
        store.add(
            "P4_INFERRED",
            "operational_trace",
            source_id,
            str(trace.get("log") or ""),
            {
                "stage": stage,
                "action": trace.get("action"),
                "status": status,
                "payload": trace.get("payload") or {},
            },
        )
