from loguru import logger
from sqlalchemy import text

from cognition.evidence_planner import EvidencePlanner
from data_sources.session import get_session_for_data_source
from evidence.evidence_model import EvidenceBundle, EvidenceItem, classify_evidence_diagnostic
from text2sql.dynamic.auto_debugger import AutoDebugger
from text2sql.dynamic.evidence_assembler import EvidenceAssembler
from runtime.trace import TraceContext


class DynamicEvidenceCollector:
    """
    破除静态脚本边界的终极武器 —— 全自动动态取证大满贯引擎。
    它完美替代了旧版本的静态 EvidenceCollector，串联了规划层、打字机生成层、抗压执行层，和转译装配层。
    """
    def __init__(self):
        self.planner = EvidencePlanner()
        self.assembler = EvidenceAssembler()
        self.auto_debugger = AutoDebugger()
        self._pack = None
        self._overrides = None
        self._rule_type_cache: dict[str, str] | None = None
        self._loaded_policy_id: str | None = None

    def _ensure_pack(self, policy_id: str):
        """惰性加载 policy pack，仅在 policy_id 变化时重新加载。"""
        if self._loaded_policy_id == policy_id:
            return
        from policy.policy_pack_loader import load_policy_packs
        from policy.policy_models import CollectorOverrides
        packs = load_policy_packs()
        self._pack = packs.get(policy_id)
        self._overrides = self._pack.collector_overrides if self._pack else CollectorOverrides()
        self._loaded_policy_id = policy_id
        self._rule_type_cache = None
        # 重建 assembler guidance_map
        guidance_map: dict[str, str] = {}
        if self._pack:
            for bucket in (
                self._pack.structured_rules.basic_conditions,
                self._pack.structured_rules.exclusion_conditions,
                self._pack.structured_rules.inference_rules,
                self._pack.structured_rules.calculation_rules,
            ):
                for r in bucket:
                    if r.assembler_guidance:
                        guidance_map[r.rule_id] = r.assembler_guidance
        self.assembler = EvidenceAssembler(guidance_map=guidance_map)
        # 重建 auto_debugger detail_query_rule_ids
        detail_ids: set[str] = set()
        if self._pack:
            for bucket in (
                self._pack.structured_rules.basic_conditions,
                self._pack.structured_rules.exclusion_conditions,
                self._pack.structured_rules.inference_rules,
                self._pack.structured_rules.calculation_rules,
            ):
                for r in bucket:
                    if r.requires_detail_query:
                        detail_ids.add(r.rule_id)
        self.auto_debugger = AutoDebugger(detail_query_rule_ids=detail_ids)

    def _rule_type_map(self) -> dict[str, str]:
        """构建 rule_id -> bucket_type ('must'/'exclude'/'flex') 映射。"""
        if self._rule_type_cache is not None:
            return self._rule_type_cache
        m: dict[str, str] = {}
        if self._pack:
            for r in self._pack.structured_rules.basic_conditions:
                m[r.rule_id] = "must"
            for r in self._pack.structured_rules.exclusion_conditions:
                m[r.rule_id] = "exclude"
            for r in self._pack.structured_rules.inference_rules:
                m[r.rule_id] = "flex"
            for r in self._pack.structured_rules.calculation_rules:
                m[r.rule_id] = "flex"
        self._rule_type_cache = m
        return m

    def _is_must_rule(self, rule_id: str) -> bool:
        return self._rule_type_map().get(rule_id) == "must"

    def _is_exclude_rule(self, rule_id: str) -> bool:
        return self._rule_type_map().get(rule_id) == "exclude"

    def _is_effective_hit(self, raw_data) -> bool:
        """
        Determine whether a query truly hit business facts.
        COUNT-style queries return one row even when count=0, so row presence alone is not enough.
        """
        if not raw_data:
            return False
        if len(raw_data) == 1 and isinstance(raw_data[0], dict):
            row = raw_data[0]
            if "cnt" in row:
                try:
                    return float(row.get("cnt") or 0) > 0
                except (TypeError, ValueError):
                    return False
            if "count" in row:
                try:
                    return float(row.get("count") or 0) > 0
                except (TypeError, ValueError):
                    return False
        return True

    def _apply_hard_rule_semantics(self, item, exec_status, raw_data, assembled):
        """
        Hard-rule deterministic semantics:
        - MUST: effective hit => support True; otherwise support False
        - EXCLUDE: effective hit => support False; otherwise support True
        """
        has_hit = self._is_effective_hit(raw_data)

        if self._is_must_rule(item.rule_id):
            if exec_status == "success" and has_hit:
                assembled.supports_conclusion = True
                return
            if exec_status in {"success", "no_data"} and not has_hit:
                assembled.supports_conclusion = False
                assembled.result_summary = assembled.result_summary or "未查询到满足该必须条件的有效记录。"
                return

        if self._is_exclude_rule(item.rule_id):
            if exec_status == "success" and has_hit:
                assembled.supports_conclusion = False
                return
            if exec_status in {"success", "no_data"} and not has_hit:
                assembled.supports_conclusion = True
                assembled.result_summary = assembled.result_summary or "未命中该排除条件记录。"
                return

    def _is_category_in_policy_scope(self, row: dict, validator_name: str = "hardship_category_scope") -> bool | None:
        """根据 policy pack 的 scope_validators 配置判断类别是否在政策范围内。"""
        validator = (self._overrides.scope_validators or {}).get(validator_name) if self._overrides else None
        if not validator:
            return None

        match_field = validator.match_field or "hardship_policy_match"
        policy_match = row.get(match_field)
        if policy_match in (1, "1", True):
            return True
        if policy_match in (0, "0", False):
            return False

        code_field = validator.code_field or "hardship_category_code"
        code = (row.get(code_field) or "").strip().upper()
        if code and validator.in_scope_codes:
            return code in set(validator.in_scope_codes)

        label_field = validator.label_field or "hardship_category"
        category = (row.get(label_field) or "").strip()
        if category and validator.in_scope_labels:
            return category in set(validator.in_scope_labels)
        return None

    def _execute_recovery(self, rule_id: str, id_card: str, data_source_id: str = "local_mysql_demo"):
        """
        通用回退取证：从 policy pack 的 recovery_strategies 配置驱动。
        返回 (raw_data, summary, supports) 或 None。
        """
        strategy = (self._overrides.recovery_strategies or {}).get(rule_id) if self._overrides else None
        if not strategy or not strategy.sql:
            return None
        try:
            with get_session_for_data_source(data_source_id) as session:
                rows = session.execute(text(strategy.sql), {"id_card": id_card}).mappings().all()
            if not rows:
                return None
            raw_data = [dict(row) for row in rows]
            first_row = raw_data[0]

            # 使用 scope_validator 判断 supports_conclusion
            supports: bool | None = None
            if strategy.scope_validator:
                supports = self._is_category_in_policy_scope(first_row, strategy.scope_validator)

            # 生成摘要
            if strategy.summary_template:
                try:
                    summary = strategy.summary_template.format(**first_row)
                except KeyError:
                    summary = strategy.summary_template
            elif strategy.success_summary_template:
                try:
                    summary = strategy.success_summary_template.format(row_count=len(raw_data))
                except KeyError:
                    summary = strategy.success_summary_template
            else:
                summary = f"回退取证成功：共查询到 {len(raw_data)} 条记录。"
            return raw_data, summary, supports
        except Exception as exc:
            logger.warning("[DynamicCollector] {} fallback recovery failed: {}", rule_id, exc)
            return None

    def _resolve_volatility_semantics(self, item, raw_data):
        """通用波动分析：从 policy pack 的 volatility_analyzers 配置驱动。"""
        analyzer = (self._overrides.volatility_analyzers or {}).get(item.rule_id) if self._overrides else None
        if not analyzer:
            return None

        value_field = analyzer.value_field
        values: list[float] = []
        for row in raw_data or []:
            raw_value = row.get(value_field)
            if raw_value in (None, ""):
                continue
            try:
                v = float(raw_value)
            except (TypeError, ValueError):
                continue
            if v > 0:
                values.append(v)

        if len(values) < analyzer.min_samples:
            return (analyzer.insufficient_samples_summary, analyzer.insufficient_samples_supports)

        relative_changes: list[float] = []
        for previous, current in zip(values, values[1:]):
            if previous <= 0:
                continue
            relative_changes.append(abs(current - previous) / previous)

        if not relative_changes:
            return (analyzer.insufficient_samples_summary, analyzer.insufficient_samples_supports)

        max_change = max(relative_changes)
        # thresholds 按 max_change 升序排列，找第一个匹配的
        for threshold in analyzer.thresholds:
            if max_change < threshold.max_change:
                return (threshold.summary, threshold.supports)
        # 超过最大阈值，用最后一个
        if analyzer.thresholds:
            last = analyzer.thresholds[-1]
            return (last.summary, last.supports)
        return None

    def _resolve_no_data_semantics(self, item):
        """从 policy pack 的 rule 元数据读取无数据语义。"""
        if not self._pack:
            return None
        # 在 pack 的四个 bucket 中查找匹配的 rule
        for bucket in (
            self._pack.structured_rules.basic_conditions,
            self._pack.structured_rules.exclusion_conditions,
            self._pack.structured_rules.inference_rules,
            self._pack.structured_rules.calculation_rules,
        ):
            for r in bucket:
                if r.rule_id == item.rule_id and r.no_data_summary:
                    return (r.no_data_summary, r.no_data_supports)
        return None

    def collect_all(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        trace: TraceContext | None = None,
    ) -> EvidenceBundle:
        """为非流式接口保留的遗留打包方法"""
        bundle = EvidenceBundle(id_card=id_card)
        for item in self.collect_stream(id_card, policy_id=policy_id, data_source_id=data_source_id, trace=trace):
            bundle.items.append(item)
        return bundle
        
    def collect_stream(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        trace: TraceContext | None = None,
    ):
        logger.info(
            "[DynamicCollector] 开启全境动态取证，目标人员：{} policy={} data_source={}",
            id_card,
            policy_id,
            data_source_id,
        )
        if trace:
            trace.info(
                "evidence",
                "collection_started",
                "[Evidence] 动态取证启动",
                policy_id=policy_id,
                data_source_id=data_source_id,
            )
        
        # 1. 启动第一层：智能规划网络
        plan = self.planner.plan(person_id=id_card, policy_id=policy_id)
        if trace:
            trace.success(
                "evidence",
                "plan_created",
                f"[Evidence] 取证计划生成：{len(plan.items)} 个断点",
                plan_item_count=len(plan.items),
            )
        
        # 确保 policy pack 已加载
        self._ensure_pack(policy_id)

        # 2. 深入第二层：执行与转储
        for item in plan.items:
            evidence_id = item.plan_item_id
            if trace:
                trace.info(
                    "evidence",
                    "rule_collection_started",
                    f"[Evidence] 开始取证 {item.rule_id}: {item.rule_name}",
                    rule_id=item.rule_id,
                    rule_type=item.rule_type,
                )
            
            try:
                # 2.1 浴火执行：撰写 SQL -> 防爆拦截重试 -> 获取原始数据
                sql, raw_data = self.auto_debugger.execute_with_auto_fix(
                    item,
                    id_card,
                    data_source_id=data_source_id,
                )
                exec_status = "success" if raw_data else "no_data"
                
                # 2.2 升维装配：将黑客数据翻译成符合裁决规则的结论总结
                assembled = self.assembler.assemble(item, raw_data)
                rule_resolution = self._resolve_volatility_semantics(item, raw_data)
                if rule_resolution:
                    assembled.result_summary, assembled.supports_conclusion = rule_resolution

                # 通用 no_data 回退：检查 recovery_strategies 中 trigger=no_data 的规则
                recovery_strategy = (self._overrides.recovery_strategies or {}).get(item.rule_id) if self._overrides else None
                if recovery_strategy and recovery_strategy.trigger == "no_data" and exec_status == "no_data":
                    recovered = self._execute_recovery(item.rule_id, id_card, data_source_id=data_source_id)
                    if recovered:
                        raw_data, recovered_summary, recovered_supports = recovered
                        exec_status = "success"
                        assembled.result_summary = recovered_summary
                        assembled.supports_conclusion = recovered_supports
                        sql = f"/* fallback: recovered via recovery_strategy for {item.rule_id} */\n{recovery_strategy.sql}"
                        if trace:
                            trace.warning(
                                "evidence",
                                "fallback_recovered",
                                f"[Evidence] {item.rule_id} 使用回退策略取证成功",
                                rule_id=item.rule_id,
                                row_count=len(raw_data),
                            )

                if exec_status == "no_data":
                    no_data_resolution = self._resolve_no_data_semantics(item)
                    if no_data_resolution:
                        assembled.result_summary, assembled.supports_conclusion = no_data_resolution

                self._apply_hard_rule_semantics(item, exec_status, raw_data, assembled)
                
                diagnostic = classify_evidence_diagnostic(exec_status)
                evidence = EvidenceItem(
                    evidence_id=evidence_id,
                    rule_id=item.rule_id,
                    target_id_card=id_card,
                    target=item.rule_name,
                    category=item.rule_type,
                    sql=sql.strip(),
                    result_raw=raw_data,
                    result_summary=assembled.result_summary,
                    supports_conclusion=assembled.supports_conclusion,
                    confidence=1.0 if exec_status == "success" else 0.5,
                    exec_status=exec_status,
                    diagnostic_code=diagnostic[0],
                    diagnostic_label=diagnostic[1],
                    diagnostic_detail=diagnostic[2],
                    diagnostic_hint=diagnostic[3],
                )
                if trace:
                    trace.success(
                        "evidence",
                        "rule_collection_finished",
                        f"[Evidence] {item.rule_id} 取证完成：{exec_status}",
                        rule_id=item.rule_id,
                        exec_status=exec_status,
                        row_count=len(raw_data),
                        supports_conclusion=assembled.supports_conclusion,
                    )
            except Exception as exc:
                # 通用 exception 回退：检查 recovery_strategies 中 trigger=exception 的规则
                exception_recovery = (self._overrides.recovery_strategies or {}).get(item.rule_id) if self._overrides else None
                if exception_recovery and exception_recovery.trigger == "exception":
                    recovered = self._execute_recovery(item.rule_id, id_card, data_source_id=data_source_id)
                    if recovered:
                        raw_data, recovered_summary, recovered_supports = recovered
                        exec_status = "success"
                        diagnostic = classify_evidence_diagnostic(exec_status)
                        evidence = EvidenceItem(
                            evidence_id=evidence_id,
                            rule_id=item.rule_id,
                            target_id_card=id_card,
                            target=item.rule_name,
                            category=item.rule_type,
                            sql=f"/* fallback: recovered via exception recovery for {item.rule_id} */\n{exception_recovery.sql}",
                            result_raw=raw_data,
                            result_summary=recovered_summary,
                            supports_conclusion=recovered_supports,
                            confidence=1.0,
                            exec_status=exec_status,
                            diagnostic_code=diagnostic[0],
                            diagnostic_label=diagnostic[1],
                            diagnostic_detail=diagnostic[2],
                            diagnostic_hint=diagnostic[3],
                        )
                        if trace:
                            trace.warning(
                                "evidence",
                                "fallback_recovered",
                                f"[Evidence] {item.rule_id} 异常后使用回退策略取证成功",
                                rule_id=item.rule_id,
                                row_count=len(raw_data),
                            )
                        yield evidence
                        continue
                    # 回退也无数据：使用 no_data 语义
                    no_data_resolution = self._resolve_no_data_semantics(item)
                    summary = (
                        no_data_resolution[0]
                        if no_data_resolution
                        else exception_recovery.no_data_summary or "未查询到相关记录。"
                    )
                    supports = (
                        no_data_resolution[1]
                        if no_data_resolution
                        else exception_recovery.no_data_supports
                    )
                    diagnostic = classify_evidence_diagnostic("no_data")
                    evidence = EvidenceItem(
                        evidence_id=evidence_id,
                        rule_id=item.rule_id,
                        target_id_card=id_card,
                        target=item.rule_name,
                        category=item.rule_type,
                        sql=f"/* fallback: no data after exception recovery for {item.rule_id} */\n{exception_recovery.sql}",
                        result_raw=[],
                        result_summary=summary,
                        supports_conclusion=supports,
                        confidence=0.8,
                        exec_status="no_data",
                        diagnostic_code=diagnostic[0],
                        diagnostic_label=diagnostic[1],
                        diagnostic_detail=diagnostic[2],
                        diagnostic_hint=diagnostic[3],
                    )
                    if trace:
                        trace.warning(
                            "evidence",
                            "fallback_no_data",
                            f"[Evidence] {item.rule_id} 异常后回退为无数据记录",
                            rule_id=item.rule_id,
                        )
                    yield evidence
                    continue

                logger.error(f"[DynamicCollector] 取证线 {item.rule_id} 执行全线崩溃: {exc}")
                if trace:
                    trace.danger(
                        "evidence",
                        "rule_collection_failed",
                        f"[Evidence] {item.rule_id} 取证失败：{exc}",
                        rule_id=item.rule_id,
                    )
                diagnostic = classify_evidence_diagnostic("failed", str(exc))
                evidence = EvidenceItem(
                    evidence_id=evidence_id,
                    rule_id=item.rule_id,
                    target_id_card=id_card,
                    target=item.rule_name,
                    category=item.rule_type,
                    sql="SQL 生成与执行链路遭受毁灭性破坏",
                    result_raw=[],
                    result_summary=f"系统保护性拦截异常: {exc}",
                    supports_conclusion=None,
                    confidence=0.0,
                    exec_status="failed",
                    diagnostic_code=diagnostic[0],
                    diagnostic_label=diagnostic[1],
                    diagnostic_detail=diagnostic[2],
                    diagnostic_hint=diagnostic[3],
                )
            
            
            yield evidence
            
        logger.info(f"[DynamicCollector] 动态取证落幕。")
        if trace:
            trace.success("evidence", "collection_finished", "[Evidence] 动态取证完成")
