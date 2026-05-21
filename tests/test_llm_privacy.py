from __future__ import annotations

from cognition.evidence_planner import EvidencePlanItem
from evidence.evidence_projection import EvidenceProjection, EvidenceSummaryCard
from agents.base_agent import format_projection
from privacy.sanitizer import TARGET_ID_CARD_PLACEHOLDER, prepare_sql_for_execution, sanitize_for_llm
from text2sql.dynamic.prompt_builder import QueryPromptBuilder


RAW_ID = "42090219850505000B"


def _plan_item() -> EvidencePlanItem:
    return EvidencePlanItem(
        plan_item_id="P001",
        rule_id="P001",
        rule_name=f"核查 {RAW_ID} 生存状态",
        rule_description=f"查询身份证号 {RAW_ID} 是否生存",
        rule_type="must",
        sql_template=f"SELECT * FROM person WHERE id_card = '{RAW_ID}'",
        priority=1,
        evidence_targets=["person"],
        allowed_fields=["person.id_card", "person.life_status"],
    )


def test_prompt_builder_never_exposes_raw_id_card_to_llm() -> None:
    prompt = QueryPromptBuilder().build_system_prompt(_plan_item(), RAW_ID)

    assert RAW_ID not in prompt
    assert TARGET_ID_CARD_PLACEHOLDER in prompt
    assert "id_card_replace" in prompt


def test_sql_placeholder_is_replaced_only_for_execution() -> None:
    sql = "SELECT * FROM person WHERE id_card = '<TARGET_ID_CARD>' OR id_card = 'id_card_replace'"

    executable = prepare_sql_for_execution(sql, RAW_ID)

    assert RAW_ID in executable
    assert TARGET_ID_CARD_PLACEHOLDER not in executable
    assert "id_card_replace" not in executable


def test_projection_prompt_masks_identity_fields() -> None:
    projection = EvidenceProjection(
        task_header="测试",
        target_person=RAW_ID,
        policy_scope="政策",
        cards=[
            EvidenceSummaryCard(
                card_id="card_1",
                question=f"查询 {RAW_ID} 的生存状态",
                finding=f"申请人 {RAW_ID} 生存。",
                status="supports",
                confidence=0.9,
                artifact_refs=["E1"],
            )
        ],
        uncertainty_markers=[f"{RAW_ID} 待人工核验"],
        total_cards=1,
        resolved_count=1,
        unresolved_count=0,
    )

    rendered = format_projection(projection)

    assert RAW_ID not in rendered
    assert rendered.count(TARGET_ID_CARD_PLACEHOLDER) >= 3


def test_sanitize_for_llm_replaces_any_id_like_value() -> None:
    assert sanitize_for_llm(f"SQL failed for {RAW_ID}") == f"SQL failed for {TARGET_ID_CARD_PLACEHOLDER}"
