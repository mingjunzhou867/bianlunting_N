"""Tests for pluggable Policy Pack loading."""
from __future__ import annotations

import unittest

from policy.policy_pack_loader import (
    DEFAULT_POLICY_PACKS_DIR,
    list_policy_pack_summaries,
    load_policy_configs_from_packs,
    load_policy_packs,
    resolve_policy_id,
)


class PolicyPackLoaderTests(unittest.TestCase):
    def test_loads_flexible_employment_policy_pack(self) -> None:
        packs = load_policy_packs(DEFAULT_POLICY_PACKS_DIR)

        self.assertIn("POLICY_001", packs)
        pack = packs["POLICY_001"]
        self.assertEqual(pack.manifest.pack_id, "flexible_employment_subsidy")
        self.assertEqual(pack.manifest.policy_name, "灵活就业社保补贴资格认定")
        self.assertEqual(len(pack.structured_rules.basic_conditions), 3)
        self.assertEqual(len(pack.structured_rules.exclusion_conditions), 3)
        self.assertEqual(len(pack.structured_rules.calculation_rules), 5)
        self.assertGreaterEqual(len(pack.evidence_requirements), 7)

    def test_loads_enterprise_social_insurance_active_service_pack(self) -> None:
        packs = load_policy_packs(DEFAULT_POLICY_PACKS_DIR)

        self.assertIn("POLICY_003", packs)
        pack = packs["POLICY_003"]
        self.assertEqual(pack.manifest.pack_id, "enterprise_social_insurance_active_service")
        self.assertEqual(pack.manifest.policy_name, "企业社会保险补贴主动服务（增员筛查）")
        self.assertEqual(pack.manifest.default_data_source_id, "local_mysql_demo")
        self.assertEqual(len(pack.structured_rules.basic_conditions), 3)
        self.assertEqual(len(pack.structured_rules.exclusion_conditions), 0)
        self.assertEqual(len(pack.structured_rules.inference_rules), 6)
        self.assertEqual(len(pack.structured_rules.calculation_rules), 1)
        self.assertGreaterEqual(len(pack.evidence_requirements), 10)

    def test_policy_pack_converts_to_legacy_policy_config(self) -> None:
        configs = load_policy_configs_from_packs(DEFAULT_POLICY_PACKS_DIR)

        config = configs["POLICY_001"]
        self.assertEqual(config.policy_id, "POLICY_001")
        self.assertEqual(config.policy_type, "资格认定")
        self.assertEqual(config.structured_rules.basic_conditions[0].rule_id, "P001_MUST_001")
        self.assertIn("life_status", config.evidence_plan_template)
        self.assertIn("policy_pack_id=flexible_employment_subsidy", config.notes)

    def test_resolve_policy_id_accepts_policy_id_or_pack_id(self) -> None:
        self.assertEqual(resolve_policy_id("POLICY_001", DEFAULT_POLICY_PACKS_DIR), "POLICY_001")
        self.assertEqual(resolve_policy_id("flexible_employment_subsidy", DEFAULT_POLICY_PACKS_DIR), "POLICY_001")
        self.assertEqual(resolve_policy_id("unknown", DEFAULT_POLICY_PACKS_DIR), "unknown")

    def test_policy_pack_summaries_are_lightweight(self) -> None:
        summaries = list_policy_pack_summaries(DEFAULT_POLICY_PACKS_DIR)
        summary_by_pack_id = {
            summary["pack_id"]: summary
            for summary in summaries
        }

        flexible_summary = summary_by_pack_id["flexible_employment_subsidy"]
        self.assertEqual(flexible_summary["policy_id"], "POLICY_001")
        self.assertGreaterEqual(flexible_summary["evidence_requirement_count"], 7)

        enterprise_summary = summary_by_pack_id["enterprise_social_insurance_active_service"]
        self.assertEqual(enterprise_summary["policy_id"], "POLICY_003")
        self.assertEqual(enterprise_summary["default_data_source_id"], "local_mysql_demo")
        self.assertGreaterEqual(enterprise_summary["evidence_requirement_count"], 10)


if __name__ == "__main__":
    unittest.main()
