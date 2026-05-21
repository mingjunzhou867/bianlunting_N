"""Tests for the question-driven evidence planner."""
from __future__ import annotations

import unittest

from cognition.evidence_planner import (
    EvidencePlan,
    MissingEvidenceStrategy,
    PlannerPriority,
    plan_evidence,
)


class TestEvidencePlanner(unittest.TestCase):
    def test_plan_evidence_returns_question_driven_items(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY-FLEX")
        self.assertIsInstance(plan, EvidencePlan)
        self.assertGreater(len(plan.items), 0)
        self.assertTrue(all(item.question_id for item in plan.items))
        self.assertTrue(all(item.plan_item_id.startswith("plan_") for item in plan.items))

    def test_priority_order_places_basic_and_excl_first(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY-FLEX")
        priorities = [item.priority for item in plan.items]
        self.assertIn(PlannerPriority.HIGH, priorities[:2])

    def test_traceability_fields_are_present(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY-FLEX")
        first = plan.items[0]
        self.assertTrue(first.qualification_item_id)
        self.assertTrue(first.question_id)
        self.assertTrue(first.linked_policy_clauses is not None)

    def test_scope_filter_can_reduce_templates(self) -> None:
        plan = plan_evidence(
            "42090219760310000D",
            "POLICY-FLEX",
            qualification_scope="QI_BASIC_ACTIVE_PERSON",
        )
        self.assertEqual(len(plan.items), 1)
        self.assertEqual(plan.items[0].qualification_item_id, "QI_BASIC_ACTIVE_PERSON")

    def test_missing_strategy_and_sql_separation(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY-FLEX")
        first = plan.items[0]
        self.assertIsInstance(first.missing_evidence_strategy, MissingEvidenceStrategy)
        self.assertFalse(hasattr(first, "sql"))
        self.assertTrue(all("SELECT " not in note for note in first.notes_for_query_generation))

    def test_policy_pack_requirements_drive_runtime_plan(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY_001")

        self.assertGreaterEqual(len(plan.items), 7)
        life_status = next(item for item in plan.items if item.question_id == "life_status")
        self.assertEqual(life_status.rule_id, "P001_MUST_001")
        self.assertIn("person", life_status.evidence_targets)
        self.assertIn("person.life_status", life_status.allowed_fields)
        self.assertIn("policy_pack_id:flexible_employment_subsidy", life_status.notes_for_query_generation)
        self.assertIn("requirement_id:life_status", life_status.notes_for_query_generation)
        recent_unit_payment = next(item for item in plan.items if item.question_id == "recent_unit_payment")
        self.assertIn("social_insurance_payment.insurer_status", recent_unit_payment.allowed_fields)

    def test_policy_pack_plan_keeps_rules_without_explicit_requirement(self) -> None:
        plan = plan_evidence("42090219760310000D", "POLICY_001")

        rule_ids = {item.rule_id for item in plan.items}
        self.assertIn("P001_FLEX_005", rule_ids)
        historical_subsidy = next(item for item in plan.items if item.rule_id == "P001_FLEX_005")
        self.assertIn("subsidy_payment_history", historical_subsidy.evidence_targets)
        self.assertTrue(historical_subsidy.sql_template)


if __name__ == "__main__":
    unittest.main()
