"""Tests for pluggable pack contract validation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.pack_validator import (
    validate_all_packs,
    validate_data_source_packs,
    validate_policy_packs,
)


class PackValidatorTests(unittest.TestCase):
    def test_repository_pack_contracts_are_valid(self) -> None:
        issues = validate_all_packs()

        self.assertEqual([], [issue for issue in issues if issue.level == "error"])

    def test_rejects_unregistered_collector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pack_dir = root / "custom_source"
            pack_dir.mkdir()
            (pack_dir / "manifest.yaml").write_text(
                "\n".join(
                    [
                        "data_source_id: custom_source",
                        "display_name: Custom Source",
                        "type: custom",
                        "version: 1.0.0",
                    ]
                ),
                encoding="utf-8",
            )
            (pack_dir / "schema_map.yaml").write_text(
                "\n".join(
                    [
                        "entities:",
                        "  applicant:",
                        "    table: applicants",
                        "    id_field: id_card",
                    ]
                ),
                encoding="utf-8",
            )
            (pack_dir / "collectors.yaml").write_text(
                "\n".join(
                    [
                        "collectors:",
                        "  - collector_id: missing_collector",
                        "    type: custom",
                        "    entities:",
                        "      - applicant",
                    ]
                ),
                encoding="utf-8",
            )

            issues = validate_data_source_packs(root)

        messages = [issue.message for issue in issues]
        self.assertTrue(any("collector is not registered" in message for message in messages))

    def test_rejects_policy_requirement_with_unknown_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pack_dir = root / "broken_policy"
            pack_dir.mkdir()
            (pack_dir / "manifest.yaml").write_text(
                "\n".join(
                    [
                        "pack_id: broken_policy",
                        "policy_id: POLICY_BROKEN",
                        "policy_name: Broken Policy",
                        "policy_type: test",
                        "version: 1.0.0",
                        "default_data_source_id: local_mysql_demo",
                    ]
                ),
                encoding="utf-8",
            )
            (pack_dir / "rules.yaml").write_text(
                "\n".join(
                    [
                        "basic_conditions: []",
                        "exclusion_conditions: []",
                        "inference_rules: []",
                        "calculation_rules: []",
                    ]
                ),
                encoding="utf-8",
            )
            (pack_dir / "evidence_requirements.yaml").write_text(
                "\n".join(
                    [
                        "requirements:",
                        "  - requirement_id: missing_rule_req",
                        "    rule_id: RULE_MISSING",
                        "    description: Missing rule reference",
                        "    entity: applicant",
                    ]
                ),
                encoding="utf-8",
            )
            (pack_dir / "prompts.yaml").write_text("review_scope: test\n", encoding="utf-8")
            (pack_dir / "report_template.yaml").write_text("report_title: test\n", encoding="utf-8")

            issues = validate_policy_packs(root)

        messages = [issue.message for issue in issues]
        self.assertTrue(any("unknown rule_id" in message for message in messages))

    def test_rejects_policy_requirement_not_supported_by_default_data_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_root = Path(tmpdir) / "policies"
            data_root = Path(tmpdir) / "sources"
            policy_dir = policy_root / "field_mismatch_policy"
            data_dir = data_root / "minimal_source"
            policy_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            (data_dir / "manifest.yaml").write_text(
                "\n".join(
                    [
                        "data_source_id: minimal_source",
                        "display_name: Minimal Source",
                        "type: mysql",
                    ]
                ),
                encoding="utf-8",
            )
            (data_dir / "schema_map.yaml").write_text(
                "\n".join(
                    [
                        "entities:",
                        "  applicant:",
                        "    table: person",
                        "    id_field: id_card",
                        "    fields:",
                        "      applicant_id: id_card",
                    ]
                ),
                encoding="utf-8",
            )
            (data_dir / "collectors.yaml").write_text(
                "\n".join(
                    [
                        "collectors:",
                        "  - collector_id: dynamic_mysql_text2sql",
                        "    type: mysql",
                        "    entities:",
                        "      - applicant",
                    ]
                ),
                encoding="utf-8",
            )
            (policy_dir / "manifest.yaml").write_text(
                "\n".join(
                    [
                        "pack_id: field_mismatch_policy",
                        "policy_id: POLICY_FIELD_MISMATCH",
                        "policy_name: Field Mismatch Policy",
                        "policy_type: test",
                        "default_data_source_id: minimal_source",
                    ]
                ),
                encoding="utf-8",
            )
            (policy_dir / "rules.yaml").write_text(
                "\n".join(
                    [
                        "basic_conditions:",
                        "  - rule_id: RULE_001",
                        "    description: Check applicant",
                        "exclusion_conditions: []",
                        "inference_rules: []",
                        "calculation_rules: []",
                    ]
                ),
                encoding="utf-8",
            )
            (policy_dir / "evidence_requirements.yaml").write_text(
                "\n".join(
                    [
                        "requirements:",
                        "  - requirement_id: missing_field_req",
                        "    rule_id: RULE_001",
                        "    description: Missing field reference",
                        "    entity: applicant",
                        "    required_fields:",
                        "      - unmapped_field",
                    ]
                ),
                encoding="utf-8",
            )
            (policy_dir / "prompts.yaml").write_text("review_scope: test\n", encoding="utf-8")
            (policy_dir / "report_template.yaml").write_text("report_title: test\n", encoding="utf-8")

            issues = validate_policy_packs(policy_root, data_root)

        messages = [issue.message for issue in issues]
        self.assertTrue(any("fields not mapped" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
