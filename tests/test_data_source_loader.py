"""Tests for pluggable Data Source Pack loading."""
from __future__ import annotations

import unittest

from data_sources.loader import (
    DEFAULT_DATA_SOURCE_PACKS_DIR,
    get_data_source_pack,
    list_data_source_summaries,
    load_data_source_packs,
    resolve_data_source_id,
)
from data_sources.schema_mapper import resolve_entity_table, resolve_field


class DataSourceLoaderTests(unittest.TestCase):
    def test_loads_local_mysql_demo_pack(self) -> None:
        packs = load_data_source_packs(DEFAULT_DATA_SOURCE_PACKS_DIR)

        self.assertIn("local_mysql_demo", packs)
        pack = packs["local_mysql_demo"]
        self.assertEqual(pack.manifest.type, "mysql")
        self.assertEqual(pack.entities["person"].table, "person")
        self.assertEqual(pack.entities["employment"].table, "employment_registration")
        self.assertGreaterEqual(len(pack.entities), 9)
        self.assertEqual(pack.collectors[0].collector_id, "dynamic_mysql_text2sql")

    def test_schema_mapper_resolves_table_and_fields(self) -> None:
        self.assertEqual(resolve_entity_table("local_mysql_demo", "employment"), "employment_registration")
        self.assertEqual(resolve_field("local_mysql_demo", "person", "applicant_id"), "id_card")
        self.assertEqual(resolve_field("local_mysql_demo", "person", "life_status"), "life_status")

    def test_data_source_summaries_are_lightweight(self) -> None:
        summaries = list_data_source_summaries(DEFAULT_DATA_SOURCE_PACKS_DIR)

        self.assertEqual(summaries[0]["data_source_id"], "local_mysql_demo")
        self.assertEqual(summaries[0]["type"], "mysql")
        self.assertGreaterEqual(summaries[0]["entity_count"], 9)

    def test_resolve_data_source_id_uses_default(self) -> None:
        self.assertEqual(resolve_data_source_id(None), "local_mysql_demo")
        self.assertEqual(resolve_data_source_id("custom_source"), "custom_source")

    def test_get_data_source_pack_returns_none_for_unknown_pack(self) -> None:
        self.assertIsNone(get_data_source_pack("missing_source", DEFAULT_DATA_SOURCE_PACKS_DIR))


if __name__ == "__main__":
    unittest.main()
