"""Tests for table payload evidence collection."""
from __future__ import annotations

import unittest

from collectors.table_payload_collector import TablePayloadCollector


class TablePayloadCollectorTests(unittest.TestCase):
    def test_collects_direct_records_as_evidence_items(self) -> None:
        collector = TablePayloadCollector()

        bundle = collector.collect_all(
            "42090219760310000D",
            data_source_id="table_payload_demo",
            collection_context={
                "records": [
                    {
                        "rule_id": "UPLOAD_001",
                        "target": "就业登记材料",
                        "category": "uploaded_material",
                        "result_summary": "申请人提供了有效就业登记材料",
                        "supports_conclusion": True,
                        "confidence": 0.9,
                        "result_raw": {"employment_form": "灵活就业"},
                    }
                ]
            },
        )

        self.assertEqual(bundle.id_card, "42090219760310000D")
        self.assertEqual(len(bundle.items), 1)
        self.assertEqual(bundle.items[0].rule_id, "UPLOAD_001")
        self.assertTrue(bundle.items[0].supports_conclusion)
        self.assertEqual(bundle.items[0].result_raw[0]["employment_form"], "灵活就业")

    def test_collects_table_rows_as_generated_evidence_items(self) -> None:
        collector = TablePayloadCollector()

        bundle = collector.collect_all(
            "42090219760310000D",
            data_source_id="table_payload_demo",
            collection_context={
                "tables": {
                    "employment": [
                        {"employment_form": "灵活就业", "is_valid": "1"},
                        {"employment_form": "全日制用工", "is_valid": "0"},
                    ]
                }
            },
        )

        self.assertEqual(len(bundle.items), 2)
        self.assertEqual(bundle.items[0].rule_id, "TABLE_EMPLOYMENT_001")
        self.assertIn("employment_form=灵活就业", bundle.items[0].result_summary)

    def test_requires_non_empty_payload(self) -> None:
        collector = TablePayloadCollector()

        with self.assertRaises(ValueError):
            collector.collect_all("42090219760310000D", collection_context={})


if __name__ == "__main__":
    unittest.main()
