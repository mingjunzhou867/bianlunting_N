from __future__ import annotations

import unittest

from evidence.evidence_model import EvidenceBundle, EvidenceItem
from portrait.persona_builder import PersonContext, PersonaBuilder


def _mock_context(life_status: str = "死亡") -> PersonContext:
    return PersonContext(
        person={
            "id_card": "42090219700505000I",
            "name": "测试用户",
            "gender": "男",
            "birth_date": "1970-05-05",
            "hukou_region": "湖北",
            "life_status": life_status,
            "system_status": "有效",
            "business_role": "",
        },
        unemployment=None,
        hardship=None,
        active_employment=None,
        employment_history=[],
        personal_payments=[],
        unit_payments=[],
        change_logs=[],
        subsidy_rows=[],
        shareholder_rows=[],
        legal_person_rows=[],
        inactive_self_business_rows=[],
    )


def _read_life_status_card(profile: dict) -> dict:
    cards = profile.get("fact_cards") or []
    for card in cards:
        if card.get("label") == "生存状态":
            return card
    return {}


class PersonaBuilderEvidenceOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PersonaBuilder()
        self.builder._load_context = self._fail_if_database_context_is_loaded  # type: ignore[method-assign]

    def _fail_if_database_context_is_loaded(self, _id_card, _ds_id="local_mysql_demo") -> PersonContext:
        raise AssertionError("evidence-first persona should not load database context")

    def test_manual_support_overrides_death_status_for_persona(self) -> None:
        raw_id = "42090219700505000I"
        bundle = EvidenceBundle(
            id_card=raw_id,
            items=[
                EvidenceItem(
                    evidence_id="manual_1",
                    rule_id="P001_MUST_001",
                    target_id_card=raw_id,
                    target="person.life_status",
                    category="manual_supplement",
                    sql="",
                    result_raw=[],
                    result_summary="人工核验支持该条款：该人确认存活",
                    supports_conclusion=True,
                    confidence=1.0,
                    exec_status="success",
                    manual_verified=True,
                    manual_stance="support",
                )
            ],
        )

        profile = self.builder.build(id_card=raw_id, evidence_bundle=bundle)
        card = _read_life_status_card(profile)
        self.assertEqual(profile["source"], "evidence")
        self.assertNotIn(raw_id, profile["title"])
        self.assertIn("420902********000I", profile["title"])
        self.assertEqual((profile.get("fact_cards") or [])[0].get("value"), "420902********000I")
        self.assertEqual(card.get("source"), "evidence")
        self.assertEqual(card.get("evidence_refs"), ["manual_1"])
        self.assertIn("确认存活", card.get("value", ""))

    def test_manual_refute_keeps_death_status_for_persona(self) -> None:
        bundle = EvidenceBundle(
            id_card="42090219700505000I",
            items=[
                EvidenceItem(
                    evidence_id="manual_2",
                    rule_id="P001_MUST_001",
                    target_id_card="42090219700505000I",
                    target="person.life_status",
                    category="manual_supplement",
                    sql="",
                    result_raw=[],
                    result_summary="人工核验反驳该条款：生命状态异常",
                    supports_conclusion=False,
                    confidence=1.0,
                    exec_status="success",
                    manual_verified=True,
                    manual_stance="refute",
                )
            ],
        )

        profile = self.builder.build(id_card="42090219700505000I", evidence_bundle=bundle)
        card = _read_life_status_card(profile)
        self.assertEqual(profile["source"], "evidence")
        self.assertEqual(card.get("source"), "evidence")
        self.assertEqual(card.get("evidence_refs"), ["manual_2"])
        self.assertIn("生命状态异常", card.get("value", ""))

    def test_database_context_is_fallback_when_no_evidence_exists(self) -> None:
        self.builder._load_context = lambda _id_card, _ds_id="local_mysql_demo": _mock_context("生存")  # type: ignore[method-assign]

        profile = self.builder.build(id_card="42090219700505000I", evidence_bundle=None)
        cards = profile.get("fact_cards") or []

        self.assertTrue(cards)
        self.assertEqual(cards[0].get("source"), "database_fallback")


if __name__ == "__main__":
    unittest.main()
