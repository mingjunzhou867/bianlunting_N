"""
Persistence helpers for completed debate sessions.

This module defines the canonical storage contract used by the runtime and the
MySQL DDL. Only successfully completed sessions are persisted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import text

from agents.decision_semantics import build_item_semantics, conclusion_tag_type
from config.database import get_session
from evidence.evidence_model import EvidenceBundle, EvidenceItem
from reports.official_report_generator import build_official_report_metadata
from runtime.memory import build_session_memory_snapshot


class DebatePersistenceError(RuntimeError):
    """Raised when a completed debate session cannot be persisted."""


class DebateSessionNotFoundError(LookupError):
    """Raised when a saved debate session cannot be found."""


@dataclass(frozen=True)
class PersistedDebateSession:
    """Canonical persisted payload for one completed debate session."""

    session_row: dict[str, Any]
    log_rows: list[dict[str, Any]]
    snapshot: dict[str, Any]


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _isoformat(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_evidence_item(item: EvidenceItem) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "rule_id": item.rule_id,
        "target_id_card": item.target_id_card,
        "target": item.target,
        "category": item.category,
        "sql": item.sql,
        "result_raw": item.result_raw,
        "result_summary": item.result_summary,
        "time_range": item.time_range,
        "supports_conclusion": item.supports_conclusion,
        "confidence": item.confidence,
        "exec_status": item.exec_status,
        "diagnostic_code": item.diagnostic_code,
        "diagnostic_label": item.diagnostic_label,
        "diagnostic_detail": item.diagnostic_detail,
        "diagnostic_hint": item.diagnostic_hint,
        "manual_verified": item.manual_verified,
        "manual_stance": item.manual_stance,
        "created_at": _isoformat(item.created_at),
        **build_item_semantics(item),
    }


def serialize_evidence_bundle(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    return [serialize_evidence_item(item) for item in bundle.items]


def serialize_history(history: Sequence[Any]) -> list[dict[str, Any]]:
    serialized_history: list[dict[str, Any]] = []
    for record in history:
        entry = {
            "round_num": record.round_num,
            "judgments": [_model_dump(judgment) for judgment in record.judgments],
            "total": record.total,
            "majority_stance": record.majority_stance,
            "majority_count": record.majority_count,
            "consensus_rate": record.consensus_rate,
            "is_consensus_reached": record.is_consensus_reached,
        }
        # Include argumentation graph if present
        if getattr(record, "argument_graph", None) is not None:
            entry["argument_graph"] = record.argument_graph
        # Include weighted fields if present
        if getattr(record, "weighted_confidence", None) is not None:
            entry["weighted_confidence"] = record.weighted_confidence
            entry["weighted_stance"] = record.weighted_stance
            entry["weighted_scores"] = record.weighted_scores
            entry["agent_weights"] = record.agent_weights
        serialized_history.append(entry)
    return serialized_history


def build_debate_result(
    session_id: str,
    bundle: EvidenceBundle,
    history: Sequence[Any],
    final_record: Any,
    arbiter_result: dict[str, Any] | None = None,
    adjudication_report: dict[str, Any] | None = None,
    manual_supplements: list[dict[str, Any]] | None = None,
    persona: dict[str, Any] | None = None,
    system_traces: list[dict[str, Any]] | None = None,
    memory_snapshot: dict[str, Any] | None = None,
    policy_id: str = "",
    data_source_id: str = "",
) -> dict[str, Any]:
    final_conclusion = final_record.get_final_conclusion()
    resolved_memory_snapshot = memory_snapshot or build_session_memory_snapshot(
        session_id=session_id,
        policy_id=policy_id,
        bundle=bundle,
        history=history,
        final_record=final_record,
        manual_supplements=manual_supplements,
        system_traces=system_traces,
    )
    return {
        "session_id": session_id,
        "id_card": bundle.id_card,
        "data_source_id": data_source_id,
        "evidence_count": len(bundle.items),
        "rounds_taken": final_record.round_num,
        "final_conclusion": final_conclusion,
        "final_conclusion_tag_type": conclusion_tag_type(final_conclusion),
        "final_stance": final_record.majority_stance,
        "consensus_rate": final_record.consensus_rate,
        "is_consensus_reached": final_record.is_consensus_reached,
        "history": serialize_history(history),
        "arbiter_result": arbiter_result or {},
        "adjudication_report": adjudication_report or {},
        "manual_supplements": manual_supplements or [],
        "manual_review_confirmed": False,
        "manual_review": {
            "confirmed": False,
            "confirmed_at": None,
            "supplement_count": len(manual_supplements or []),
            "updated_clause_count": 0,
            "has_manual_supplement": bool(manual_supplements),
        },
        "persona": persona or {},
        "system_traces": system_traces or [],
        "memory_snapshot": resolved_memory_snapshot,
        "official_report": {
            **build_official_report_metadata(session_id),
            "available": False,
            "confirmed_required": True,
        },
    }


def build_completed_session_records(
    session_id: str,
    source_endpoint: str,
    bundle: EvidenceBundle,
    history: Sequence[Any],
    final_record: Any,
    started_at: datetime,
    completed_at: datetime,
    policy_id: str = "POLICY_001",
    arbiter_result: dict[str, Any] | None = None,
    adjudication_report: dict[str, Any] | None = None,
    manual_supplements: list[dict[str, Any]] | None = None,
    persona: dict[str, Any] | None = None,
    system_traces: list[dict[str, Any]] | None = None,
    data_source_id: str = "",
) -> PersistedDebateSession:
    history_payload = serialize_history(history)
    evidence_payload = serialize_evidence_bundle(bundle)
    memory_snapshot = build_session_memory_snapshot(
        session_id=session_id,
        policy_id=policy_id,
        bundle=bundle,
        history=history,
        final_record=final_record,
        manual_supplements=manual_supplements,
        system_traces=system_traces,
    )
    result_payload = build_debate_result(
        session_id,
        bundle,
        history,
        final_record,
        arbiter_result=arbiter_result,
        adjudication_report=adjudication_report,
        manual_supplements=manual_supplements,
        persona=persona,
        system_traces=system_traces,
        memory_snapshot=memory_snapshot,
        policy_id=policy_id,
        data_source_id=data_source_id,
    )
    agent_count = len(history[0].judgments) if history else 0

    session_row = {
        "session_id": session_id,
        "id_card": bundle.id_card,
        "policy_id": policy_id,
        "status": "completed",
        "source_endpoint": source_endpoint,
        "final_conclusion": result_payload["final_conclusion"],
        "final_stance": result_payload["final_stance"],
        "consensus_rate": final_record.consensus_rate,
        "is_consensus_reached": int(final_record.is_consensus_reached),
        "rounds_taken": final_record.round_num,
        "evidence_count": len(bundle.items),
        "agent_count": agent_count,
        "started_at": started_at,
        "completed_at": completed_at,
    }

    snapshot = {
        **result_payload,
        "policy_id": policy_id,
        "data_source_id": data_source_id,
        "status": session_row["status"],
        "source_endpoint": source_endpoint,
        "started_at": _isoformat(started_at),
        "completed_at": _isoformat(completed_at),
        "summary": {
            "status": session_row["status"],
            "policy_id": policy_id,
            "data_source_id": data_source_id,
            "source_endpoint": source_endpoint,
            "final_conclusion": session_row["final_conclusion"],
            "final_stance": session_row["final_stance"],
            "consensus_rate": session_row["consensus_rate"],
            "is_consensus_reached": bool(session_row["is_consensus_reached"]),
            "rounds_taken": session_row["rounds_taken"],
            "evidence_count": session_row["evidence_count"],
            "agent_count": session_row["agent_count"],
        },
        "evidence": evidence_payload,
    }

    session_row["snapshot_payload"] = _json_dumps(snapshot)

    log_rows: list[dict[str, Any]] = []
    for record in history:
        for judgment in record.judgments:
            log_rows.append(
                {
                    "session_id": session_id,
                    "id_card": bundle.id_card,
                    "debate_round": record.round_num,
                    "agent_id": judgment.agent_id,
                    "agent_role": judgment.agent_role,
                    "conclusion": judgment.conclusion,
                    "stance": judgment.stance,
                    "confidence": judgment.confidence,
                    "evidence_refs": _json_dumps(judgment.evidence_refs),
                    "reasoning": judgment.reasoning,
                    "dissent_points": _json_dumps(judgment.dissent_points),
                    "key_finding": judgment.key_finding,
                    "round_majority_stance": record.majority_stance,
                    "round_consensus_rate": record.consensus_rate,
                    "round_is_consensus_reached": int(record.is_consensus_reached),
                }
            )

    return PersistedDebateSession(
        session_row=session_row,
        log_rows=log_rows,
        snapshot=snapshot,
    )


def _build_history_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    summary_fields = [
        "session_id",
        "id_card",
        "policy_id",
        "status",
        "source_endpoint",
        "final_conclusion",
        "final_stance",
        "consensus_rate",
        "is_consensus_reached",
        "rounds_taken",
        "evidence_count",
        "completed_at",
    ]
    summary = {
        field: _normalize_value(row[field])
        for field in summary_fields
        if field in row
    }
    if "is_consensus_reached" in summary:
        summary["is_consensus_reached"] = bool(summary["is_consensus_reached"])
    return summary


def list_saved_sessions(id_card: str = None) -> list[dict[str, Any]]:
    where_clause = "WHERE id_card = :id_card" if id_card else ""
    query_sql = text(
        f"""
        SELECT
            session_id,
            id_card,
            policy_id,
            status,
            source_endpoint,
            final_conclusion,
            final_stance,
            consensus_rate,
            is_consensus_reached,
            rounds_taken,
            evidence_count,
            completed_at
        FROM debate_session
        {where_clause}
        ORDER BY completed_at DESC, created_at DESC
        """
    )

    with get_session() as session:
        params = {"id_card": id_card} if id_card else {}
        rows = session.execute(query_sql, params).mappings().all()

    return [_build_history_summary_row(dict(row)) for row in rows]


def _mask_id_card(id_card: Any) -> str:
    text_value = str(id_card or "").strip()
    if len(text_value) <= 8:
        return "*" * len(text_value)
    return f"{text_value[:4]}{'*' * (len(text_value) - 8)}{text_value[-4:]}"


def _memory_record_matches(
    record: dict[str, Any],
    *,
    query: str,
    trust_level: str,
    source_type: str,
) -> bool:
    if trust_level and str(record.get("trust_level") or "") != trust_level:
        return False
    if source_type and str(record.get("source_type") or "") != source_type:
        return False
    if not query:
        return True

    searchable = " ".join(
        [
            str(record.get("memory_id") or ""),
            str(record.get("trust_level") or ""),
            str(record.get("source_type") or ""),
            str(record.get("source_id") or ""),
            str(record.get("summary") or ""),
            _json_dumps(record.get("payload") or {}),
        ]
    ).lower()
    return query.lower() in searchable


def search_saved_memory(
    *,
    query: str | None = None,
    policy_id: str | None = None,
    trust_level: str | None = None,
    source_type: str | None = None,
    limit: int = 20,
    session_limit: int = 100,
) -> dict[str, Any]:
    """Search structured memory records extracted from completed sessions."""
    resolved_limit = max(1, min(int(limit or 20), 100))
    resolved_session_limit = max(resolved_limit, min(int(session_limit or 100), 500))
    normalized_policy_id = str(policy_id or "").strip()
    normalized_query = str(query or "").strip()
    normalized_trust_level = str(trust_level or "").strip()
    normalized_source_type = str(source_type or "").strip()
    where_clause = "WHERE policy_id = :policy_id" if normalized_policy_id else ""
    query_sql = text(
        f"""
        SELECT
            session_id,
            id_card,
            policy_id,
            completed_at,
            snapshot_payload
        FROM debate_session
        {where_clause}
        ORDER BY completed_at DESC, created_at DESC
        LIMIT {resolved_session_limit}
        """
    )

    with get_session() as session:
        params = {"policy_id": normalized_policy_id} if normalized_policy_id else {}
        rows = session.execute(query_sql, params).mappings().all()

    matches: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        try:
            snapshot = json.loads(row.get("snapshot_payload") or "{}")
        except json.JSONDecodeError:
            continue
        memory_snapshot = snapshot.get("memory_snapshot") if isinstance(snapshot, dict) else None
        records = memory_snapshot.get("records") if isinstance(memory_snapshot, dict) else None
        if not isinstance(records, list):
            continue

        for raw_record in records:
            if not isinstance(raw_record, dict):
                continue
            if not _memory_record_matches(
                raw_record,
                query=normalized_query,
                trust_level=normalized_trust_level,
                source_type=normalized_source_type,
            ):
                continue
            matches.append(
                {
                    "session_id": row.get("session_id"),
                    "policy_id": row.get("policy_id") or memory_snapshot.get("policy_id") or "",
                    "completed_at": _normalize_value(row.get("completed_at")),
                    "masked_id_card": _mask_id_card(row.get("id_card")),
                    "record": dict(raw_record),
                }
            )
            if len(matches) >= resolved_limit:
                return {
                    "query": normalized_query,
                    "policy_id": normalized_policy_id,
                    "trust_level": normalized_trust_level,
                    "source_type": normalized_source_type,
                    "limit": resolved_limit,
                    "matches": matches,
                }

    return {
        "query": normalized_query,
        "policy_id": normalized_policy_id,
        "trust_level": normalized_trust_level,
        "source_type": normalized_source_type,
        "limit": resolved_limit,
        "matches": matches,
    }


def _apply_detail_defaults(row: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    detail = dict(snapshot)
    detail.setdefault("session_id", row["session_id"])
    detail.setdefault("id_card", row["id_card"])
    detail.setdefault("status", row["status"])
    detail.setdefault("source_endpoint", row["source_endpoint"])
    detail.setdefault("completed_at", _normalize_value(row["completed_at"]))
    return detail


def _manual_stance_to_effect(stance: Any) -> tuple[str, str, str]:
    text_value = str(stance or "").strip().lower()
    if text_value in {"refute", "oppose", "reject", "fail", "不符合", "反驳"}:
        return "不符合", "oppose", "danger"
    return "符合", "support", "success"


def _manual_stance_text(stance: Any) -> str:
    label, _, _ = _manual_stance_to_effect(stance)
    return "支持该条款（人工确认满足）" if label == "符合" else "反驳该条款（人工确认不满足）"


def _normalize_manual_supplements_for_confirm(
    manual_supplements: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not manual_supplements:
        return []
    reviewed_at = _isoformat(datetime.now())
    resolved: list[dict[str, Any]] = []
    for raw in manual_supplements:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        clause_id = str(row.get("clause_id") or "").strip()
        if not clause_id:
            continue
        if str(row.get("status") or "").strip() != "not_adopted":
            row["status"] = "adopted"
            row["reviewed_at"] = row.get("reviewed_at") or reviewed_at
            row["review_reason"] = row.get("review_reason") or f"人工补证复核确认完成，{_manual_stance_text(row.get('stance'))}，已用于 PDF 裁决报告。"
        resolved.append(row)
    return resolved


def _build_manual_evidence_payload(snapshot: dict[str, Any], supplement: dict[str, Any]) -> dict[str, Any]:
    label, effect, tag_type = _manual_stance_to_effect(supplement.get("stance"))
    clause_id = str(supplement.get("clause_id") or "").strip()
    supplement_id = str(supplement.get("supplement_id") or f"confirm_{clause_id}")
    detail = str(supplement.get("detail") or "人工确认完成补证复核。")
    return {
        "evidence_id": str(supplement.get("evidence_id") or f"manual_{supplement_id}"),
        "rule_id": clause_id,
        "target_id_card": snapshot.get("id_card") or "",
        "target": f"人工核验证据({clause_id})",
        "category": "manual_supplement",
        "sql": "-- manual review confirmation",
        "result_raw": [{"source": "manual", "supplement_id": supplement_id, "clause_id": clause_id}],
        "result_summary": f"[人工复核][{_manual_stance_text(supplement.get('stance'))}] {detail}",
        "time_range": None,
        "supports_conclusion": effect == "support",
        "confidence": 1.0,
        "exec_status": "success",
        "diagnostic_code": "ok",
        "diagnostic_label": "人工补证复核",
        "diagnostic_detail": "人工补证复核已确认，人工结论优先级最高。",
        "diagnostic_hint": "该条款已按人工补证复核结果覆盖系统原始判断。",
        "manual_verified": True,
        "manual_stance": str(supplement.get("stance") or "support"),
        "semantic_decision_effect": effect,
        "semantic_display_label": label,
        "semantic_tag_type": tag_type,
        "created_at": supplement.get("reviewed_at") or supplement.get("submitted_at") or _isoformat(datetime.now()),
    }


def _apply_manual_review_to_snapshot(
    snapshot: dict[str, Any],
    manual_supplements: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    next_snapshot = dict(snapshot)
    resolved_supplements = _normalize_manual_supplements_for_confirm(manual_supplements)
    if not resolved_supplements and isinstance(next_snapshot.get("manual_supplements"), list):
        resolved_supplements = _normalize_manual_supplements_for_confirm(next_snapshot.get("manual_supplements"))

    confirmed_at = _isoformat(datetime.now())
    latest_by_clause: dict[str, dict[str, Any]] = {}
    for row in resolved_supplements:
        clause_id = str(row.get("clause_id") or "").strip()
        if clause_id and str(row.get("status") or "") != "not_adopted":
            latest_by_clause[clause_id] = row

    next_snapshot["manual_supplements"] = resolved_supplements
    next_snapshot["manual_review_confirmed"] = True
    next_snapshot["manual_review"] = {
        "confirmed": True,
        "confirmed_at": confirmed_at,
        "supplement_count": len(resolved_supplements),
        "updated_clause_count": len(latest_by_clause),
        "has_manual_supplement": bool(resolved_supplements),
    }
    if isinstance(next_snapshot.get("official_report"), dict):
        official_report = dict(next_snapshot["official_report"])
    else:
        official_report = build_official_report_metadata(str(next_snapshot.get("session_id") or ""))
    official_report["available"] = True
    official_report["confirmed_required"] = False
    next_snapshot["official_report"] = official_report

    adjudication = dict(next_snapshot.get("adjudication_report") or {})
    clause_rows = adjudication.get("clause_results")
    if isinstance(clause_rows, list) and latest_by_clause:
        updated_rows = []
        for raw in clause_rows:
            if not isinstance(raw, dict):
                updated_rows.append(raw)
                continue
            row = dict(raw)
            clause_id = str(row.get("clause_id") or "").strip()
            manual = latest_by_clause.get(clause_id)
            if manual:
                label, effect, tag_type = _manual_stance_to_effect(manual.get("stance"))
                detail = str(manual.get("detail") or "人工补证复核确认完成。")
                row["status"] = label
                row["semantic_display_label"] = label
                row["semantic_decision_effect"] = effect
                row["semantic_tag_type"] = tag_type
                row["semantic_is_missing_data"] = False
                row["reason"] = f"【人工复核】{detail}"
                row["action_hint"] = "该条款已由人工补证复核确认，PDF 报告按人工结论出具。"
                row["manual_verified"] = True
                row["manual_stance"] = manual.get("stance") or "support"
            updated_rows.append(row)
        adjudication["clause_results"] = updated_rows
        next_snapshot["adjudication_report"] = adjudication

    if latest_by_clause:
        evidence_rows = next_snapshot.get("evidence") if isinstance(next_snapshot.get("evidence"), list) else []
        overridden = set(latest_by_clause.keys())
        retained = [row for row in evidence_rows if not (isinstance(row, dict) and str(row.get("rule_id") or "").strip() in overridden)]
        manual_evidence = [_build_manual_evidence_payload(next_snapshot, row) for row in latest_by_clause.values()]
        next_snapshot["evidence"] = retained + manual_evidence
        next_snapshot["evidence_count"] = len(next_snapshot["evidence"])
        if isinstance(next_snapshot.get("summary"), dict):
            summary = dict(next_snapshot["summary"])
            summary["evidence_count"] = len(next_snapshot["evidence"])
            next_snapshot["summary"] = summary

    arbiter = dict(next_snapshot.get("arbiter_result") or {})
    risks = arbiter.get("remaining_risks")
    if isinstance(risks, list) and latest_by_clause:
        support_clause_ids = {
            clause_id
            for clause_id, manual in latest_by_clause.items()
            if _manual_stance_to_effect(manual.get("stance"))[1] == "support"
        }
        next_risks = []
        for risk in risks:
            risk_text = str(risk)
            if any(clause_id and clause_id in risk_text for clause_id in support_clause_ids):
                continue
            next_risks.append(risk)
        arbiter["remaining_risks"] = next_risks
        next_snapshot["arbiter_result"] = arbiter

    return next_snapshot


def get_saved_session_detail(session_id: str) -> dict[str, Any]:
    query_sql = text(
        """
        SELECT
            session_id,
            id_card,
            status,
            source_endpoint,
            completed_at,
            snapshot_payload
        FROM debate_session
        WHERE session_id = :session_id
        """
    )

    with get_session() as session:
        row = session.execute(query_sql, {"session_id": session_id}).mappings().first()

    if row is None:
        raise DebateSessionNotFoundError(f"Saved debate session not found: {session_id}")

    row_dict = dict(row)
    snapshot = json.loads(row_dict["snapshot_payload"])
    return _apply_detail_defaults(row_dict, snapshot)


def persist_completed_session(
    session_id: str,
    source_endpoint: str,
    bundle: EvidenceBundle,
    history: Sequence[Any],
    final_record: Any,
    started_at: datetime,
    completed_at: datetime,
    policy_id: str = "POLICY_001",
    arbiter_result: dict[str, Any] | None = None,
    adjudication_report: dict[str, Any] | None = None,
    manual_supplements: list[dict[str, Any]] | None = None,
    persona: dict[str, Any] | None = None,
    system_traces: list[dict[str, Any]] | None = None,
    data_source_id: str = "",
) -> PersistedDebateSession:
    persisted = build_completed_session_records(
        session_id=session_id,
        source_endpoint=source_endpoint,
        bundle=bundle,
        history=history,
        final_record=final_record,
        started_at=started_at,
        completed_at=completed_at,
        policy_id=policy_id,
        arbiter_result=arbiter_result,
        adjudication_report=adjudication_report,
        manual_supplements=manual_supplements,
        persona=persona,
        system_traces=system_traces,
        data_source_id=data_source_id,
    )

    insert_session_sql = text(
        """
        INSERT INTO debate_session (
            session_id,
            id_card,
            policy_id,
            status,
            source_endpoint,
            final_conclusion,
            final_stance,
            consensus_rate,
            is_consensus_reached,
            rounds_taken,
            evidence_count,
            agent_count,
            started_at,
            completed_at,
            snapshot_payload
        ) VALUES (
            :session_id,
            :id_card,
            :policy_id,
            :status,
            :source_endpoint,
            :final_conclusion,
            :final_stance,
            :consensus_rate,
            :is_consensus_reached,
            :rounds_taken,
            :evidence_count,
            :agent_count,
            :started_at,
            :completed_at,
            :snapshot_payload
        )
        """
    )

    insert_log_sql = text(
        """
        INSERT INTO agent_debate_log (
            session_id,
            id_card,
            debate_round,
            agent_id,
            agent_role,
            conclusion,
            stance,
            confidence,
            evidence_refs,
            reasoning,
            dissent_points,
            key_finding,
            round_majority_stance,
            round_consensus_rate,
            round_is_consensus_reached
        ) VALUES (
            :session_id,
            :id_card,
            :debate_round,
            :agent_id,
            :agent_role,
            :conclusion,
            :stance,
            :confidence,
            :evidence_refs,
            :reasoning,
            :dissent_points,
            :key_finding,
            :round_majority_stance,
            :round_consensus_rate,
            :round_is_consensus_reached
        )
        """
    )

    try:
        with get_session() as session:
            session.execute(insert_session_sql, persisted.session_row)
            for row in persisted.log_rows:
                session.execute(insert_log_sql, row)
    except Exception as exc:
        raise DebatePersistenceError(
            f"Failed to persist completed debate session {session_id}"
        ) from exc

    return persisted


def confirm_manual_review(
    session_id: str,
    manual_supplements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mark manual review as complete and persist a PDF-ready snapshot."""
    query_sql = text(
        """
        SELECT
            session_id,
            id_card,
            status,
            source_endpoint,
            completed_at,
            snapshot_payload
        FROM debate_session
        WHERE session_id = :session_id
        """
    )
    update_sql = text(
        """
        UPDATE debate_session
        SET snapshot_payload = :snapshot_payload
        WHERE session_id = :session_id
        """
    )

    with get_session() as session:
        row = session.execute(query_sql, {"session_id": session_id}).mappings().first()
        if row is None:
            raise DebateSessionNotFoundError(f"Saved debate session not found: {session_id}")
        row_dict = dict(row)
        snapshot = json.loads(row_dict["snapshot_payload"])
        next_snapshot = _apply_manual_review_to_snapshot(snapshot, manual_supplements)
        session.execute(
            update_sql,
            {
                "session_id": session_id,
                "snapshot_payload": _json_dumps(next_snapshot),
            },
        )

    return _apply_detail_defaults(row_dict, next_snapshot)
