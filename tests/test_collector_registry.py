"""Tests for data-source-specific collector registry."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.debate_orchestrator import DebateOrchestrator
from collectors.registry import CollectorRegistry, CollectorResolutionError, build_default_collector_registry
from collectors.table_payload_collector import TablePayloadCollector
from evidence.evidence_model import EvidenceBundle, EvidenceItem
from text2sql.dynamic.dynamic_collector import DynamicEvidenceCollector


def build_pack(source_type: str = "mysql", collector_id: str = "dynamic_mysql_text2sql"):
    return SimpleNamespace(
        manifest=SimpleNamespace(data_source_id="local_mysql_demo", type=source_type),
        collectors=[SimpleNamespace(collector_id=collector_id)],
    )


class StubCollector:
    def collect_all(self, id_card, policy_id="POLICY_001", data_source_id="custom_source", trace=None):
        return EvidenceBundle(
            id_card=id_card,
            items=[
                EvidenceItem(
                    evidence_id="stub-1",
                    rule_id="RULE_STUB",
                    target_id_card=id_card,
                    target="stub",
                    category="stub",
                    sql="SELECT 1",
                    result_raw=[{"ok": 1}],
                    result_summary="stub evidence",
                    supports_conclusion=True,
                    confidence=1.0,
                    exec_status="success",
                )
            ],
        )

    def collect_stream(self, id_card, policy_id="POLICY_001", data_source_id="custom_source", trace=None):
        return iter(self.collect_all(id_card, policy_id, data_source_id, trace).items)


class CollectorRegistryTests(unittest.TestCase):
    def test_default_registry_resolves_mysql_dynamic_collector(self) -> None:
        registry = build_default_collector_registry()

        with patch("collectors.registry.get_data_source_pack", return_value=build_pack()):
            collector = registry.create_for_data_source("local_mysql_demo")

        self.assertIsInstance(collector, DynamicEvidenceCollector)

    def test_default_registry_resolves_table_payload_collector(self) -> None:
        registry = build_default_collector_registry()

        with patch("collectors.registry.get_data_source_pack", return_value=build_pack(source_type="table_payload", collector_id="table_payload")):
            collector = registry.create_for_data_source("table_payload_demo")

        self.assertIsInstance(collector, TablePayloadCollector)

    def test_registry_can_resolve_custom_collector_by_type(self) -> None:
        registry = CollectorRegistry()
        registry.register_type("excel", StubCollector)

        with patch("collectors.registry.get_data_source_pack", return_value=build_pack(source_type="excel", collector_id="missing")):
            collector = registry.create_for_data_source("excel_demo")

        self.assertIsInstance(collector, StubCollector)

    def test_registry_rejects_unknown_data_source(self) -> None:
        registry = CollectorRegistry()

        with patch("collectors.registry.get_data_source_pack", return_value=None):
            with self.assertRaises(CollectorResolutionError):
                registry.create_for_data_source("missing_source")

    def test_orchestrator_uses_registry_for_non_default_data_source(self) -> None:
        orchestrator = DebateOrchestrator()
        orchestrator.collector_registry = CollectorRegistry()
        orchestrator.collector_registry.register_type("excel", StubCollector)

        with patch("collectors.registry.get_data_source_pack", return_value=build_pack(source_type="excel", collector_id="missing")):
            bundle = orchestrator._collect_all_evidence(
                "42090219760310000D",
                "POLICY_001",
                "excel_demo",
                None,
                trace=None,
            )

        self.assertEqual(bundle.items[0].rule_id, "RULE_STUB")


if __name__ == "__main__":
    unittest.main()
