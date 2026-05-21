"""Collector for table-like payloads supplied by API clients."""
from __future__ import annotations

from typing import Any

from evidence.evidence_model import EvidenceBundle, EvidenceItem, classify_evidence_diagnostic
from runtime.trace import TraceContext


class TablePayloadCollector:
    """Convert uploaded table/material rows into normalized EvidenceItems."""

    def collect_all(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "table_payload_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ) -> EvidenceBundle:
        bundle = EvidenceBundle(id_card=id_card)
        for item in self.collect_stream(
            id_card,
            policy_id=policy_id,
            data_source_id=data_source_id,
            collection_context=collection_context,
            trace=trace,
        ):
            bundle.items.append(item)
        return bundle

    def collect_stream(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "table_payload_demo",
        collection_context: dict | None = None,
        trace: TraceContext | None = None,
    ):
        payload = collection_context or {}
        records = self._extract_records(payload)
        if not records:
            raise ValueError("table_payload requires non-empty records or tables")
        if trace:
            trace.info(
                "evidence",
                "table_payload_started",
                "[Evidence] table payload collection started",
                data_source_id=data_source_id,
                record_count=len(records),
            )

        for index, record in enumerate(records, start=1):
            item = self._record_to_evidence(id_card, record, index)
            if trace:
                trace.success(
                    "evidence",
                    "table_payload_record_ready",
                    f"[Evidence] table payload evidence ready: {item.rule_id}",
                    rule_id=item.rule_id,
                    exec_status=item.exec_status,
                )
            yield item

    def _extract_records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_records = payload.get("records") if isinstance(payload, dict) else None
        records: list[dict[str, Any]] = []
        if isinstance(raw_records, list):
            records.extend(row for row in raw_records if isinstance(row, dict))

        raw_tables = payload.get("tables") if isinstance(payload, dict) else None
        if isinstance(raw_tables, dict):
            for table_name, rows in raw_tables.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    records.append(
                        {
                            "source_table": str(table_name),
                            "result_raw": row,
                            "target": str(table_name),
                            "category": "table_payload",
                            "result_summary": self._summarize_row(str(table_name), row),
                        }
                    )
        return records

    def _record_to_evidence(self, id_card: str, record: dict[str, Any], index: int) -> EvidenceItem:
        rule_id = str(record.get("rule_id") or self._default_rule_id(record, index))
        evidence_id = str(record.get("evidence_id") or f"table_payload_{index:04d}")
        raw = record.get("result_raw")
        if isinstance(raw, dict):
            result_raw = [raw]
        elif isinstance(raw, list):
            result_raw = [row for row in raw if isinstance(row, dict)]
        else:
            result_raw = [dict(record)]

        exec_status = str(record.get("exec_status") or "success")
        if exec_status not in {"success", "no_data", "failed", "field_missing"}:
            exec_status = "success"
        diagnostic = classify_evidence_diagnostic(exec_status, str(record.get("diagnostic_detail") or ""))
        return EvidenceItem(
            evidence_id=evidence_id,
            rule_id=rule_id,
            target_id_card=str(record.get("target_id_card") or id_card),
            target=str(record.get("target") or rule_id),
            category=str(record.get("category") or "table_payload"),
            sql=str(record.get("sql") or "-- table payload evidence"),
            result_raw=result_raw,
            result_summary=str(record.get("result_summary") or self._summarize_row(rule_id, result_raw[0] if result_raw else {})),
            time_range=record.get("time_range"),
            supports_conclusion=self._normalize_support(record.get("supports_conclusion")),
            confidence=self._normalize_confidence(record.get("confidence")),
            exec_status=exec_status,
            diagnostic_code=str(record.get("diagnostic_code") or diagnostic[0]),
            diagnostic_label=str(record.get("diagnostic_label") or diagnostic[1]),
            diagnostic_detail=str(record.get("diagnostic_detail") or diagnostic[2]),
            diagnostic_hint=str(record.get("diagnostic_hint") or diagnostic[3]),
            manual_verified=bool(record.get("manual_verified") or False),
            manual_stance=record.get("manual_stance") or record.get("stance"),
        )

    def _default_rule_id(self, record: dict[str, Any], index: int) -> str:
        source_table = str(record.get("source_table") or "record").upper()
        safe_table = "".join(ch if ch.isalnum() else "_" for ch in source_table)
        return f"TABLE_{safe_table}_{index:03d}"

    def _summarize_row(self, label: str, row: dict[str, Any]) -> str:
        parts = []
        for key, value in list(row.items())[:5]:
            parts.append(f"{key}={value}")
        return f"{label}: " + "，".join(parts) if parts else f"{label}: 已提供表格材料"

    def _normalize_support(self, value: Any) -> bool | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "support", "pass", "符合"}:
            return True
        if text in {"false", "0", "no", "oppose", "fail", "不符合"}:
            return False
        return None

    def _normalize_confidence(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.8
        return max(0.0, min(1.0, number))
