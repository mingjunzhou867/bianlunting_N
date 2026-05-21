"""Question-driven evidence planning interfaces for cognition prep."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from cognition.policy_rule_loader import PolicyRule, PolicyRuleLoader
from cognition.question_templates import (
    QuestionTemplate,
    QuestionTemplateRegistry,
    QuestionType,
)
from cognition.semantic_packet import SemanticPacketBuilder
from data_sources.loader import get_data_source_pack
from data_sources.models import DataSourcePack
from policy.policy_models import EvidenceRequirement, PolicyRule as PackPolicyRule
from policy.policy_pack_loader import load_policy_packs


class PlannerPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MissingEvidenceStrategy(str, Enum):
    MARK_UNKNOWN = "mark_unknown"
    TREAT_AS_NOT_SATISFIED = "treat_as_not_satisfied"
    SEARCH_ADJACENT_SOURCE = "search_adjacent_source"


class EvidencePlanItem(BaseModel):
    plan_item_id: str
    rule_id: str
    rule_name: str
    rule_description: str
    rule_type: str
    sql_template: str
    priority: int | PlannerPriority
    scenario_category: str | None = None
    qualification_item_id: str | None = None
    question_id: str | None = None
    question_text: str | None = None
    question_type: QuestionType | None = None
    evidence_targets: list[str] = Field(default_factory=list)
    relevant_fields: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)
    entity_scope: list[str] = Field(default_factory=list)
    time_window_or_time_rule: str = ""
    expected_answer_shape: str = ""
    missing_evidence_strategy: MissingEvidenceStrategy = MissingEvidenceStrategy.MARK_UNKNOWN
    conflict_strategy: str = ""
    linked_policy_clauses: list[str] = Field(default_factory=list)
    notes_for_query_generation: list[str] = Field(default_factory=list)


class EvidencePlan(BaseModel):
    person_id: str
    policy_id: str
    qualification_scope: str | None = None
    packet_summary: str
    items: list[EvidencePlanItem] = Field(default_factory=list)


class EvidencePlanner:
    def __init__(
        self,
        packet_builder: SemanticPacketBuilder | None = None,
        rule_loader: PolicyRuleLoader | None = None,
        template_registry: QuestionTemplateRegistry | None = None,
    ):
        self.packet_builder = packet_builder or SemanticPacketBuilder()
        self.rule_loader = rule_loader or PolicyRuleLoader()
        self.template_registry = template_registry or QuestionTemplateRegistry.default()

    def plan(
        self,
        person_id: str,
        policy_id: str,
        qualification_scope: str | None = None,
    ) -> EvidencePlan:
        packet = self.packet_builder.build(person_id, policy_id, qualification_scope)
        pack_items = self._build_plan_items_from_policy_pack(policy_id, person_id)
        if pack_items:
            pack_items.sort(key=lambda item: (self._priority_rank(item.priority), item.rule_id))
            return EvidencePlan(
                person_id=person_id,
                policy_id=policy_id,
                qualification_scope=qualification_scope,
                packet_summary=packet.task.summary,
                items=pack_items,
            )

        rule_set = self.rule_loader.load_rules(policy_id)

        items: list[EvidencePlanItem] = [
            self._build_plan_item_from_rule(rule)
            for rule in rule_set.must_satisfy + rule_set.must_exclude + rule_set.flexible
        ]

        # Compatibility fallback for the earlier question-template planner.
        if not items:
            templates = self.template_registry.get_for_policy(policy_id, qualification_scope)
            items = [self._build_plan_item(packet, template, person_id) for template in templates]

        items.sort(key=lambda item: (self._priority_rank(item.priority), item.rule_id))

        return EvidencePlan(
            person_id=person_id,
            policy_id=policy_id,
            qualification_scope=qualification_scope,
            packet_summary=packet.task.summary,
            items=items,
        )

    def _build_plan_items_from_policy_pack(self, policy_id: str, person_id: str) -> list[EvidencePlanItem]:
        pack = load_policy_packs().get(policy_id)
        if pack is None:
            return []

        requirements_by_rule: dict[str, list[EvidenceRequirement]] = {}
        for requirement in pack.evidence_requirements:
            requirements_by_rule.setdefault(requirement.rule_id, []).append(requirement)
        data_source_pack = (
            get_data_source_pack(pack.manifest.default_data_source_id)
            if pack.manifest.default_data_source_id
            else None
        )

        items: list[EvidencePlanItem] = []
        rule_rows: list[tuple[PackPolicyRule, str, int]] = []
        rule_rows.extend((rule, "必须满足", 0) for rule in pack.structured_rules.basic_conditions)
        rule_rows.extend((rule, "必须排除", 1) for rule in pack.structured_rules.exclusion_conditions)
        rule_rows.extend((rule, "灵活评判", 2) for rule in pack.structured_rules.inference_rules)
        rule_rows.extend((rule, "额度计算", 3) for rule in pack.structured_rules.calculation_rules)

        seen_rule_ids: set[str] = set()
        for index, (rule, rule_type, bucket_rank) in enumerate(rule_rows, start=1):
            seen_rule_ids.add(rule.rule_id)
            requirements = requirements_by_rule.get(rule.rule_id) or [None]
            for requirement_index, requirement in enumerate(requirements, start=1):
                items.append(
                    self._build_pack_plan_item(
                        rule=rule,
                        rule_type=rule_type,
                        bucket_rank=bucket_rank,
                        priority=index,
                        person_id=person_id,
                        requirement=requirement,
                        requirement_index=requirement_index,
                        policy_pack_id=pack.manifest.pack_id,
                        data_source_pack=data_source_pack,
                    )
                )

        for requirement in pack.evidence_requirements:
            if requirement.rule_id in seen_rule_ids:
                continue
            items.append(
                self._build_requirement_only_plan_item(
                    requirement=requirement,
                    person_id=person_id,
                    policy_pack_id=pack.manifest.pack_id,
                    priority=900 + len(items),
                    data_source_pack=data_source_pack,
                )
            )

        return items

    def _build_pack_plan_item(
        self,
        rule: PackPolicyRule,
        rule_type: str,
        bucket_rank: int,
        priority: int,
        person_id: str,
        requirement: EvidenceRequirement | None,
        requirement_index: int,
        policy_pack_id: str,
        data_source_pack: DataSourcePack | None,
    ) -> EvidencePlanItem:
        rule_name = self._rule_name(rule)
        rule_description = rule.description or rule_name
        relevant_fields, allowed_fields, evidence_targets = self._requirement_hints(requirement, data_source_pack)
        specific_hints = self._rule_specific_hints(rule.rule_id, rule=rule)
        allowed_fields = self._merge_unique(allowed_fields, specific_hints["allowed_fields"])
        relevant_fields = self._merge_unique(relevant_fields, specific_hints["relevant_fields"] or allowed_fields)
        evidence_targets = self._merge_unique(evidence_targets, specific_hints["evidence_targets"])
        notes = self._pack_notes(policy_pack_id, requirement)
        notes.extend(specific_hints["notes_for_query_generation"])
        suffix = f"_{requirement_index}" if requirement and len(requirement.rule_id) > 0 and requirement_index > 1 else ""
        return EvidencePlanItem(
            plan_item_id=f"plan_{rule.rule_id.lower()}{suffix}",
            rule_id=rule.rule_id,
            rule_name=rule_name,
            rule_description=rule_description,
            rule_type=rule_type,
            sql_template=rule.normalize_sql_template or rule.sql_template_ref or "",
            priority=bucket_rank * 100 + priority,
            scenario_category=rule_type,
            qualification_item_id=requirement.requirement_id if requirement else rule.rule_id,
            question_id=requirement.requirement_id if requirement else rule.rule_id,
            question_text=requirement.description if requirement else rule_description,
            evidence_targets=evidence_targets,
            relevant_fields=relevant_fields,
            allowed_fields=allowed_fields,
            entity_scope=[person_id],
            expected_answer_shape=requirement.expected_signal if requirement and requirement.expected_signal else rule_description,
            missing_evidence_strategy=self._missing_strategy_for_requirement(requirement),
            conflict_strategy="preserve_trace_and_mark_for_review",
            linked_policy_clauses=[rule.rule_id],
            notes_for_query_generation=notes,
        )

    def _build_requirement_only_plan_item(
        self,
        requirement: EvidenceRequirement,
        person_id: str,
        policy_pack_id: str,
        priority: int,
        data_source_pack: DataSourcePack | None,
    ) -> EvidencePlanItem:
        relevant_fields, allowed_fields, evidence_targets = self._requirement_hints(requirement, data_source_pack)
        return EvidencePlanItem(
            plan_item_id=f"plan_{requirement.rule_id.lower()}_{requirement.requirement_id.lower()}",
            rule_id=requirement.rule_id,
            rule_name=requirement.description,
            rule_description=requirement.description,
            rule_type="证据需求",
            sql_template="",
            priority=priority,
            scenario_category="policy_pack_requirement",
            qualification_item_id=requirement.requirement_id,
            question_id=requirement.requirement_id,
            question_text=requirement.description,
            evidence_targets=evidence_targets,
            relevant_fields=relevant_fields,
            allowed_fields=allowed_fields,
            entity_scope=[person_id],
            expected_answer_shape=requirement.expected_signal or requirement.description,
            missing_evidence_strategy=self._missing_strategy_for_requirement(requirement),
            conflict_strategy="preserve_trace_and_mark_for_review",
            linked_policy_clauses=[requirement.rule_id],
            notes_for_query_generation=self._pack_notes(policy_pack_id, requirement),
        )

    def _rule_name(self, rule: PackPolicyRule) -> str:
        text = (rule.description or rule.rule_id).strip()
        for delimiter in ("：", ":", "。", "."):
            if delimiter in text:
                head = text.split(delimiter, 1)[0].strip()
                if head:
                    return head
        return text[:40] or rule.rule_id

    def _requirement_hints(
        self,
        requirement: EvidenceRequirement | None,
        data_source_pack: DataSourcePack | None = None,
    ) -> tuple[list[str], list[str], list[str]]:
        if requirement is None:
            return [], [], []
        entity_mapping = (
            data_source_pack.entities.get(requirement.entity)
            if data_source_pack is not None
            else None
        )
        table_name = entity_mapping.table if entity_mapping is not None else requirement.entity
        fields = []
        for field in requirement.required_fields:
            if "." in field:
                fields.append(field)
            else:
                physical_field = field
                if entity_mapping is not None:
                    physical_field = entity_mapping.fields.get(field) or field
                fields.append(f"{table_name}.{physical_field}")
        targets = [table_name] if table_name else []
        return list(fields), list(fields), targets

    def _missing_strategy_for_requirement(
        self,
        requirement: EvidenceRequirement | None,
    ) -> MissingEvidenceStrategy:
        if requirement is None:
            return MissingEvidenceStrategy.MARK_UNKNOWN
        fallback = (requirement.fallback or "").strip().lower()
        if fallback in {"not_satisfied", "treat_as_not_satisfied"}:
            return MissingEvidenceStrategy.TREAT_AS_NOT_SATISFIED
        if fallback in {"adjacent_source", "search_adjacent_source"}:
            return MissingEvidenceStrategy.SEARCH_ADJACENT_SOURCE
        return MissingEvidenceStrategy.MARK_UNKNOWN

    def _pack_notes(self, policy_pack_id: str, requirement: EvidenceRequirement | None) -> list[str]:
        notes = [f"policy_pack_id:{policy_pack_id}"]
        if requirement is not None:
            notes.extend(
                [
                    f"requirement_id:{requirement.requirement_id}",
                    f"entity:{requirement.entity}",
                    f"fallback:{requirement.fallback}",
                ]
            )
            if requirement.expected_signal:
                notes.append(f"expected_signal:{requirement.expected_signal}")
        return notes

    def _merge_unique(self, *groups: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for group in groups:
            for value in group:
                if value and value not in seen:
                    seen.add(value)
                    merged.append(value)
        return merged

    def _rule_specific_hints(
        self,
        rule_id: str,
        rule: PackPolicyRule | None = None,
    ) -> dict[str, list[str]]:
        # 优先从 policy pack rule 的元数据读取
        if rule is not None:
            if rule.allowed_fields or rule.evidence_targets or rule.notes_for_query_generation:
                return {
                    "allowed_fields": list(rule.allowed_fields),
                    "relevant_fields": list(rule.relevant_fields) if rule.relevant_fields else list(rule.allowed_fields),
                    "evidence_targets": list(rule.evidence_targets),
                    "notes_for_query_generation": list(rule.notes_for_query_generation),
                }

        # 向后兼容：无 pack rule 元数据时返回空（LLM 自行判断）
        return {
            "allowed_fields": [],
            "relevant_fields": [],
            "evidence_targets": [],
            "notes_for_query_generation": [],
        }

    def _build_plan_item_from_rule(self, rule: PolicyRule) -> EvidencePlanItem:
        hints = self._rule_specific_hints(rule.rule_id)

        return EvidencePlanItem(
            plan_item_id=f"plan_{rule.rule_id.lower()}",
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_description=rule.rule_description,
            rule_type=rule.rule_type,
            sql_template=rule.sql_template,
            priority=rule.priority,
            scenario_category=rule.scenario_category,
            relevant_fields=hints["relevant_fields"],
            allowed_fields=hints["allowed_fields"],
            evidence_targets=hints["evidence_targets"],
            notes_for_query_generation=hints["notes_for_query_generation"],
        )

    def _build_plan_item(
        self,
        packet: Any,
        template: QuestionTemplate,
        person_id: str,
    ) -> EvidencePlanItem:
        return EvidencePlanItem(
            plan_item_id=f"plan_{template.question_id.lower()}",
            rule_id=template.question_id,
            rule_name=template.question_id,
            rule_description=template.question_text,
            rule_type=self._rule_type_for(template.question_type),
            sql_template="",
            priority=self._priority_for(template.question_type),
            scenario_category=template.policy_scope,
            qualification_item_id=template.qualification_item_id,
            question_id=template.question_id,
            question_text=template.question_text,
            question_type=template.question_type,
            evidence_targets=list(template.suggested_evidence_targets),
            relevant_fields=self._select_relevant_fields(packet, template),
            entity_scope=[person_id],
            time_window_or_time_rule=self._time_rule_for(packet, template),
            expected_answer_shape=template.expected_answer_shape,
            missing_evidence_strategy=MissingEvidenceStrategy(
                template.default_missing_evidence_behavior
            ),
            conflict_strategy="preserve_trace_and_mark_for_review",
            linked_policy_clauses=list(template.linked_policy_clauses),
            notes_for_query_generation=[
                f"trace:{template.qualification_item_id}",
                f"question_type:{template.question_type.value}",
            ],
        )

    def _select_relevant_fields(self, packet: Any, template: QuestionTemplate) -> list[str]:
        packet_fields = {card.field_key for card in packet.fields}
        return [field for field in template.suggested_fields if field in packet_fields]

    def _time_rule_for(self, packet: Any, template: QuestionTemplate) -> str:
        for semantic in packet.time_semantics:
            if any(field in template.suggested_fields for field in semantic.related_fields):
                return semantic.rule
        return template.time_semantics_hint or "Use current task time semantics."

    def _priority_for(self, question_type: QuestionType) -> PlannerPriority:
        mapping = {
            QuestionType.BASIC: PlannerPriority.HIGH,
            QuestionType.EXCL: PlannerPriority.HIGH,
            QuestionType.INFER: PlannerPriority.MEDIUM,
            QuestionType.CALC: PlannerPriority.LOW,
        }
        return mapping[question_type]

    def _priority_rank(self, priority: int | PlannerPriority) -> int:
        if isinstance(priority, int):
            return priority
        return {
            PlannerPriority.HIGH: 0,
            PlannerPriority.MEDIUM: 1,
            PlannerPriority.LOW: 2,
        }[priority]

    def _rule_type_for(self, question_type: QuestionType) -> str:
        mapping = {
            QuestionType.BASIC: "必须满足",
            QuestionType.EXCL: "必须排除",
            QuestionType.INFER: "灵活判断",
            QuestionType.CALC: "灵活判断",
        }
        return mapping[question_type]


def plan_evidence(
    person_id: str,
    policy_id: str,
    qualification_scope: str | None = None,
    packet_builder: SemanticPacketBuilder | None = None,
    rule_loader: PolicyRuleLoader | None = None,
) -> EvidencePlan:
    planner = EvidencePlanner(
        packet_builder=packet_builder,
        rule_loader=rule_loader,
    )
    return planner.plan(
        person_id=person_id,
        policy_id=policy_id,
        qualification_scope=qualification_scope,
    )
