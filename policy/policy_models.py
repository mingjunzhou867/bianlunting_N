"""
政策相关数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PolicyRule(BaseModel):
    """单条政策规则"""
    rule_id: str = Field(..., description="规则ID")
    description: str = Field(..., description="规则描述")
    check_fields: Optional[List[str]] = Field(None, description="检查字段")
    pass_condition: Optional[str] = Field(None, description="通过条件")
    fail_condition: Optional[str] = Field(None, description="失败条件")
    check_logic: Optional[str] = Field(None, description="检查逻辑")
    formula: Optional[str] = Field(None, description="计算公式")
    sql_template_ref: Optional[str] = Field(None, description="SQL模板引用")
    # -- 泛用性扩展字段（可选，有默认值） --
    requires_detail_query: bool = Field(False, description="是否要求详情级查询（禁止聚合SQL）")
    allowed_fields: List[str] = Field(default_factory=list, description="允许查询的字段白名单")
    relevant_fields: List[str] = Field(default_factory=list, description="相关字段列表")
    evidence_targets: List[str] = Field(default_factory=list, description="证据目标表")
    notes_for_query_generation: List[str] = Field(default_factory=list, description="SQL生成提示")
    no_data_summary: str = Field("", description="无数据时的摘要文本")
    no_data_supports: Optional[bool] = Field(None, description="无数据时是否视为支持结论")
    assembler_guidance: str = Field("", description="证据装配器的规则特定约束")
    normalize_sql_template: str = Field("", description="DB规则加载时的SQL模板覆盖")
    normalize_description: str = Field("", description="DB规则加载时的描述覆盖")
    normalize_rule_name: str = Field("", description="DB规则加载时的名称覆盖")


class StructuredRules(BaseModel):
    """结构化规则集"""
    basic_conditions: List[PolicyRule] = Field(default_factory=list, description="基础条件")
    exclusion_conditions: List[PolicyRule] = Field(default_factory=list, description="排斥条件")
    inference_rules: List[PolicyRule] = Field(default_factory=list, description="合理推断规则")
    calculation_rules: List[PolicyRule] = Field(default_factory=list, description="计算规则")


class PolicyConfig(BaseModel):
    """政策完整配置"""
    policy_id: str = Field(..., description="政策ID")
    policy_name: str = Field(..., description="政策名称")
    policy_type: str = Field(..., description="政策类型")
    effective_date: Optional[str] = Field(None, description="生效日期")
    expiry_date: Optional[str] = Field(None, description="失效日期")
    description: str = Field(..., description="政策描述")
    
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    aliases: List[str] = Field(default_factory=list, description="别名列表")
    intent_patterns: List[str] = Field(default_factory=list, description="意图匹配模式")
    
    policy_source_files: List[str] = Field(default_factory=list, description="政策原文件路径")
    policy_text: str = Field("", description="政策原文")
    
    structured_rules: StructuredRules = Field(default_factory=StructuredRules, description="结构化规则")
    
    evidence_plan_template: Dict[str, List[str]] = Field(default_factory=dict, description="取证计划模板")
    
    notes: List[str] = Field(default_factory=list, description="备注")


class DecisionLabels(BaseModel):
    """政策包内的通用裁决标签。"""

    passed: str = Field("符合", description="通过标签")
    failed: str = Field("不符合", description="不通过标签")
    uncertain: str = Field("数据缺失", description="无法自动判定标签")


class PolicyPackManifest(BaseModel):
    """可插拔政策包清单。"""

    pack_id: str = Field(..., description="政策包ID")
    policy_id: str = Field(..., description="兼容旧链路的政策ID")
    policy_name: str = Field(..., description="政策名称")
    policy_type: str = Field(..., description="政策类型")
    version: str = Field("1.0.0", description="政策包版本")
    applicant_type: str = Field("person", description="申请主体类型")
    description: str = Field("", description="政策描述")
    effective_date: Optional[str] = Field(None, description="生效日期")
    expiry_date: Optional[str] = Field(None, description="失效日期")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    aliases: List[str] = Field(default_factory=list, description="别名列表")
    intent_patterns: List[str] = Field(default_factory=list, description="意图匹配模式")
    decision_labels: DecisionLabels = Field(default_factory=DecisionLabels, description="裁决标签")
    default_data_source_id: Optional[str] = Field(None, description="默认数据源包ID")
    task_header: str = Field("", description="辩论任务标题（如'灵活就业社保补贴资格认定'）")
    policy_scope: str = Field("", description="政策范围描述（如'灵活就业补贴政策规则'）")


class EvidenceRequirement(BaseModel):
    """政策包声明的证据需求。"""

    requirement_id: str = Field(..., description="证据需求ID")
    rule_id: str = Field(..., description="关联规则ID")
    description: str = Field(..., description="证据需求描述")
    entity: str = Field(..., description="业务实体")
    required_fields: List[str] = Field(default_factory=list, description="所需字段")
    expected_signal: Optional[str] = Field(None, description="期望信号")
    fallback: str = Field("manual_review", description="无法自动取证时的兜底方式")


class PromptPack(BaseModel):
    """政策包提供的 Agent 提示词约束。"""

    review_scope: str = Field("", description="审核范围")
    agent_instructions: List[str] = Field(default_factory=list, description="Agent 审核口径")
    manual_review_items: List[str] = Field(default_factory=list, description="人工复核建议项")


class ReportTemplate(BaseModel):
    """政策包报告模板声明。"""

    report_title: str = Field("政策资格审核辅助报告", description="报告标题")
    sections: List[str] = Field(default_factory=list, description="报告章节")


class ScopeValidator(BaseModel):
    """困难类别范围校验配置。"""
    match_field: str = Field("", description="政策匹配标记字段名")
    code_field: str = Field("", description="类别编码字段名")
    label_field: str = Field("", description="类别标签字段名")
    in_scope_codes: List[str] = Field(default_factory=list, description="政策范围内的类别编码")
    in_scope_labels: List[str] = Field(default_factory=list, description="政策范围内的类别标签")


class RecoveryStrategy(BaseModel):
    """取证回退策略配置。"""
    trigger: str = Field("no_data", description="触发条件：no_data 或 exception")
    sql: str = Field("", description="回退SQL模板")
    scope_validator: Optional[str] = Field(None, description="引用的ScopeValidator名称")
    summary_template: str = Field("", description="成功摘要模板（支持{field}占位符）")
    success_summary_template: str = Field("", description="成功摘要模板（备选）")
    no_data_summary: str = Field("", description="回退也无数据时的摘要")
    no_data_supports: Optional[bool] = Field(None, description="回退也无数据时是否支持结论")


class VolatilityThreshold(BaseModel):
    """波动分析阈值。"""
    max_change: float = Field(..., description="最大相对变化阈值")
    summary: str = Field("", description="匹配时的摘要")
    supports: Optional[bool] = Field(None, description="匹配时的结论支持值")


class VolatilityAnalyzer(BaseModel):
    """波动分析器配置。"""
    value_field: str = Field("", description="要分析的数值字段名")
    min_samples: int = Field(2, description="最少样本数")
    thresholds: List[VolatilityThreshold] = Field(default_factory=list, description="阈值列表（按max_change升序）")
    insufficient_samples_summary: str = Field("", description="样本不足时的摘要")
    insufficient_samples_supports: Optional[bool] = Field(None, description="样本不足时的结论支持值")


class CollectorOverrides(BaseModel):
    """动态取证器的策略覆盖配置。"""
    scope_validators: Dict[str, ScopeValidator] = Field(default_factory=dict, description="范围校验器")
    recovery_strategies: Dict[str, RecoveryStrategy] = Field(default_factory=dict, description="回退策略")
    volatility_analyzers: Dict[str, VolatilityAnalyzer] = Field(default_factory=dict, description="波动分析器")


class PolicyPack(BaseModel):
    """完整政策包。"""

    manifest: PolicyPackManifest
    structured_rules: StructuredRules = Field(default_factory=StructuredRules, description="结构化规则")
    evidence_requirements: List[EvidenceRequirement] = Field(default_factory=list, description="证据需求")
    prompts: PromptPack = Field(default_factory=PromptPack, description="提示词约束")
    report_template: ReportTemplate = Field(default_factory=ReportTemplate, description="报告模板")
    collector_overrides: CollectorOverrides = Field(default_factory=CollectorOverrides, description="取证器策略覆盖")
    source_dir: str = Field("", description="政策包目录")

    def to_policy_config(self) -> PolicyConfig:
        """Convert the pack into the legacy PolicyConfig runtime contract."""
        manifest = self.manifest
        return PolicyConfig(
            policy_id=manifest.policy_id,
            policy_name=manifest.policy_name,
            policy_type=manifest.policy_type,
            effective_date=manifest.effective_date,
            expiry_date=manifest.expiry_date,
            description=manifest.description,
            keywords=manifest.keywords,
            aliases=manifest.aliases,
            intent_patterns=manifest.intent_patterns,
            structured_rules=self.structured_rules,
            evidence_plan_template={
                requirement.requirement_id: requirement.required_fields
                for requirement in self.evidence_requirements
            },
            notes=[
                f"policy_pack_id={manifest.pack_id}",
                f"policy_pack_version={manifest.version}",
            ],
        )
