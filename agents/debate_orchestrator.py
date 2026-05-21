"""Debate orchestration and completed-session persistence."""
from __future__ import annotations

import json
import uuid
import time
from datetime import UTC, datetime
from typing import Any, Generator

from loguru import logger

from agents import create_all_agents
from agents.adjudication_report import build_adjudication_report
from agents.agent_arbiter import ConservativeArbiter
from agents.base_agent import (
    AgentJudgment,
    CONCLUSION_FAIL,
    CONCLUSION_MISSING,
    CONCLUSION_PASS,
    DebateToolPolicy,
    STANCE_OPPOSE,
    STANCE_PENDING,
    STANCE_SUPPORT,
)
from agents.decision_semantics import (
    aggregate_final_conclusion_from_judgments,
    build_item_semantics,
)
from agents.optimization_algorithms import (
    aggregate_weighted_stances,
    score_evidence_item,
    sort_evidence_items,
)
from agents.debate_memory import (
    Argument,
    ArgumentGraph,
    ArgumentStance,
    AttackType,
)
from agents.attack_detector import AttackDetector
from agents.optimization_algorithms import compute_argument_confidence
from portrait import PersonaBuilder
from agents.empirical_case_retriever import retrieve_empirical_cases
from agents.debate_persistence import (
    DebatePersistenceError,
    build_debate_result,
    persist_completed_session,
)
from collectors.registry import CollectorRegistry, build_default_collector_registry
from config.settings import settings
from evidence.evidence_model import EvidenceBundle
from evidence.evidence_projection import EvidenceProjection, EvidenceSummaryCard
from cognition.evidence_planner import EvidencePlanner
from text2sql.dynamic.dynamic_collector import DynamicEvidenceCollector
from tools.tool_registry import ToolRegistry
from runtime.trace import TraceContext, use_trace


DEFAULT_TASK_HEADER = "灵活就业社保补贴资格认定"
DEFAULT_POLICY_SCOPE = "灵活就业补贴政策规则"


def project_evidence(bundle: EvidenceBundle, task_header: str = DEFAULT_TASK_HEADER, policy_scope: str = DEFAULT_POLICY_SCOPE) -> EvidenceProjection:
    """Reshape retrieved evidence into the summary-first debate format."""

    # Sort evidence by quality score before building cards
    sorted_items = sort_evidence_items(bundle.items)

    cards: list[EvidenceSummaryCard] = []
    uncertainty_markers: list[str] = []

    for item in sorted_items:
        semantic = build_item_semantics(item)
        if semantic["semantic_decision_effect"] == "support":
            status = "supports"
        elif semantic["semantic_decision_effect"] == "oppose":
            status = "contradicts"
        elif semantic["semantic_is_missing_data"]:
            status = "missing"
        else:
            status = "unresolved"

        # Compute evidence quality score
        ev_score = score_evidence_item(item)

        cards.append(
            EvidenceSummaryCard(
                card_id=f"card_{item.rule_id}",
                question=item.target,
                finding=item.result_summary,
                status=status,
                confidence=item.confidence,
                artifact_refs=[item.evidence_id],
                evidence_score=ev_score.score,
                evidence_score_percent=ev_score.score_percent,
                score_breakdown=ev_score.breakdown,
                rank_reason=ev_score.rank_reason,
            )
        )

        if status == "unresolved":
            uncertainty_markers.append(f"[{item.rule_id}] {item.target}: 需 Agent 进一步判定")
        elif status == "missing":
            uncertainty_markers.append(f"[{item.rule_id}] {item.target}: 数据缺失({item.exec_status})")

    resolved_count = sum(1 for card in cards if card.status in ("supports", "contradicts"))
    unresolved_count = sum(1 for card in cards if card.status in ("unresolved", "missing"))

    return EvidenceProjection(
        task_header=task_header,
        target_person=bundle.id_card,
        policy_scope=policy_scope,
        cards=cards,
        uncertainty_markers=uncertainty_markers,
        total_cards=len(cards),
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
    )


class DebateRecord:
    """Internal round record shared by API responses and persistence."""

    _STANCE_BY_CONCLUSION = {
        CONCLUSION_PASS: STANCE_SUPPORT,
        CONCLUSION_FAIL: STANCE_OPPOSE,
        CONCLUSION_MISSING: STANCE_PENDING,
    }
    _FINAL_CONCLUSION_PRIORITY = {
        CONCLUSION_PASS: 2,
        CONCLUSION_FAIL: 1,
        CONCLUSION_MISSING: 0,
    }

    def __init__(
        self,
        judgments: list[AgentJudgment],
        round_num: int,
        projection: EvidenceProjection | None = None,
        evidence_items: list | None = None,
    ):
        self.round_num = round_num
        self.judgments = judgments

        stances = [self._effective_stance(judgment) for judgment in judgments]
        self.total = len(stances)
        counts = {stance: stances.count(stance) for stance in set(stances)}

        if counts:
            self.majority_count = max(counts.values())
            leaders = [
                stance
                for stance in (STANCE_SUPPORT, STANCE_OPPOSE, STANCE_PENDING)
                if counts.get(stance, 0) == self.majority_count
            ]
            self.majority_stance = leaders[0] if len(leaders) == 1 else STANCE_PENDING
            self.consensus_rate = self.majority_count / self.total
        else:
            self.majority_stance = STANCE_PENDING
            self.majority_count = 0
            self.consensus_rate = 0.0

        # Weighted stance aggregation
        weighted = aggregate_weighted_stances(judgments, projection)
        self.weighted_stance = weighted["dominant_stance"]
        self.weighted_confidence = weighted["weighted_confidence"]
        self.weighted_scores = {
            "support": weighted["weighted_support"],
            "oppose": weighted["weighted_oppose"],
            "pending": weighted["weighted_pending"],
        }
        self.agent_weights = {}  # agent_id → weight, computed per-judgment
        evidence_score_map: dict[str, float] = {}
        if projection:
            for card in projection.cards:
                eid = card.card_id.replace("card_", "")
                evidence_score_map[eid] = card.evidence_score
        for j in judgments:
            refs = getattr(j, "evidence_refs", [])
            avg_ev = sum(evidence_score_map.get(r, 0) for r in refs) / max(len(refs), 1)
            self.agent_weights[j.agent_id] = round(j.confidence * 0.6 + (avg_ev / 100) * 0.4, 3)

        # Dual consensus: consensus_rate AND weighted_confidence
        self.is_consensus_reached = (
            self.consensus_rate >= settings.consensus_threshold
            and self.weighted_confidence >= settings.consensus_threshold
        )

        # Store references for get_final_conclusion
        self._projection = projection
        self._evidence_items = evidence_items

        # Argumentation graph (populated by orchestrator after construction)
        self.argument_graph: dict[str, Any] | None = None
        self.argumentation_stance: str | None = None
        self.argumentation_conclusion: str | None = None
        self.argumentation_confidence: float = 0.0
        self.argumentation_consensus_rate: float = 0.0
        self.argumentation_consensus_reached: bool = False

        # Round summary (populated by orchestrator after argumentation update)
        self.round_summary: str = ""

    def get_final_conclusion(self) -> str:
        if self.argumentation_consensus_reached and self.argumentation_conclusion:
            return self.argumentation_conclusion
        return aggregate_final_conclusion_from_judgments(
            self.judgments,
            projection=getattr(self, "_projection", None),
            evidence_items=getattr(self, "_evidence_items", None),
        )

    @classmethod
    def _effective_stance(cls, judgment: AgentJudgment) -> str:
        expected_stance = cls._STANCE_BY_CONCLUSION.get(judgment.conclusion)
        if expected_stance and judgment.stance != expected_stance:
            logger.warning(
                "Normalize mismatched stance: agent={} conclusion={} stance={} -> {}",
                judgment.agent_id,
                judgment.conclusion,
                judgment.stance,
                expected_stance,
            )
            return expected_stance
        return judgment.stance

    def to_dict(self) -> dict[str, object]:
        result = {
            "round_num": self.round_num,
            "judgments": [judgment.model_dump() for judgment in self.judgments],
            "total": self.total,
            "majority_stance": self.majority_stance,
            "majority_count": self.majority_count,
            "consensus_rate": self.consensus_rate,
            "is_consensus_reached": self.is_consensus_reached,
            "weighted_stance": self.weighted_stance,
            "weighted_confidence": self.weighted_confidence,
            "weighted_scores": self.weighted_scores,
            "agent_weights": self.agent_weights,
            "argumentation_stance": self.argumentation_stance,
            "argumentation_conclusion": self.argumentation_conclusion,
            "argumentation_confidence": self.argumentation_confidence,
            "argumentation_consensus_rate": self.argumentation_consensus_rate,
            "argumentation_consensus_reached": self.argumentation_consensus_reached,
        }
        if self.argument_graph is not None:
            result["argument_graph"] = self.argument_graph
        return result


class DebateOrchestrator:
    """Run synchronous and streaming debate flows using Dynamic Evidence collection."""

    def __init__(self):
        self.collector_registry: CollectorRegistry = build_default_collector_registry()
        self.collector = DynamicEvidenceCollector()
        self._current_policy_name = "政策资格认定"
        self._current_policy_id: str | None = None
        self.agents = create_all_agents(self._current_policy_name)
        self.arbiter = ConservativeArbiter()
        self.max_rounds = settings.debate_max_rounds
        # Debate agents judge from projected evidence first. Supplemental query is allowed,
        # but only as a bounded follow-up when a specific gap or challenge point needs verification.
        self.debate_tool_policy = DebateToolPolicy(
            allow_tools=True,
            require_existing_evidence_first=True,
            max_tool_calls_per_turn=1,
            allowed_tool_names=("get_dict", "text_to_sql"),
        )
        # MCP client for process-isolated tool execution
        try:
            from mcp_server.client import MCPToolClient
            self.mcp_client = MCPToolClient()
        except Exception as exc:
            logger.warning("MCP Client 初始化失败，回退到直接调用: {}", exc)
            self.mcp_client = None
        self.tool_registry = ToolRegistry(
            tool_policy=self.debate_tool_policy,
            mcp_client=self.mcp_client,
        )
        self.tools = self.tool_registry.get_tool_schemas()

    def close(self) -> None:
        """清理 MCP 子进程等资源。"""
        if hasattr(self, "mcp_client") and self.mcp_client:
            self.mcp_client.close()

    def _empirical_case_context(self, agent, projection: EvidenceProjection) -> list[dict] | None:
        if getattr(agent, "AGENT_ID", "") != "agent_empirical":
            return None
        return [case.to_prompt_dict() for case in retrieve_empirical_cases(projection)]

    def _policy_display(self, policy_id: str) -> tuple[str, str]:
        """根据 policy_id 解析 (task_header, policy_scope) 显示名称，并刷新 agent 上下文。"""
        self._current_policy_id = policy_id
        from policy.policy_pack_loader import load_policy_packs
        pack = load_policy_packs().get(policy_id)
        if pack and pack.manifest.task_header:
            task_header = pack.manifest.task_header
            policy_scope = pack.manifest.policy_scope or pack.manifest.policy_name
            policy_name = pack.manifest.policy_name
        else:
            from policy.policy_router import get_policy
            cfg = get_policy(policy_id)
            if cfg:
                task_header = f"{cfg.policy_name}{cfg.policy_type}"
                policy_scope = cfg.policy_name
                policy_name = cfg.policy_name
            else:
                return DEFAULT_TASK_HEADER, DEFAULT_POLICY_SCOPE
        # 当 policy_name 变化时刷新 agents
        if policy_name != self._current_policy_name:
            self._current_policy_name = policy_name
            self.agents = create_all_agents(policy_name)
        return task_header, policy_scope

    def run_debate(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
    ) -> dict[str, object]:
        session_id = str(uuid.uuid4())
        started_at = self._utcnow()
        trace = TraceContext(session_id=session_id, id_card=id_card, policy_id=policy_id)
        trace.info("session", "session_started", "[Session] 非流式审查会话启动", data_source_id=data_source_id)

        bundle = self._collect_all_evidence(id_card, policy_id, data_source_id, collection_context, trace)
        task_header, policy_scope = self._policy_display(policy_id)
        persona = self._build_persona(bundle, policy_id, None, data_source_id=data_source_id)
        trace.success("persona", "persona_ready", "[Persona] 申请人画像构建完成")
        history, final_record = self._execute_debate(
            bundle,
            task_header,
            policy_scope,
            persona_context=persona,
            trace=trace,
        )
        arbiter_result = self._build_arbiter_result(bundle, history, final_record, task_header, policy_scope)
        adjudication_report = self._build_adjudication_report(
            policy_id,
            bundle,
            history,
            final_record,
            arbiter_result,
        )
        trace.success("arbitration", "report_ready", "[Arbitration] 仲裁与条款级报告生成完成")
        trace.success("session", "session_completed", "[Session] 审查会话完成")
        result = build_debate_result(
            session_id,
            bundle,
            history,
            final_record,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            persona=persona,
            system_traces=trace.to_list(),
            policy_id=policy_id,
            data_source_id=data_source_id,
        )
        result["policy_id"] = policy_id
        result["data_source_id"] = data_source_id
        self._persist_completed_session(
            session_id=session_id,
            source_endpoint="/api/debate",
            bundle=bundle,
            history=history,
            final_record=final_record,
            started_at=started_at,
            policy_id=policy_id,
            data_source_id=data_source_id,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            persona=persona,
            system_traces=trace.to_list(),
        )
        return result

    def run_debate_with_bundle(
        self,
        bundle: EvidenceBundle,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        source_endpoint: str = "/api/debate",
        manual_supplements: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        bundle = self._prioritize_manual_evidence(bundle)
        session_id = str(uuid.uuid4())
        started_at = self._utcnow()
        trace = TraceContext(session_id=session_id, id_card=bundle.id_card, policy_id=policy_id)
        trace.info("session", "session_started", "[Session] 复用证据审查会话启动", data_source_id=data_source_id)
        trace.success("evidence", "evidence_reused", f"[Evidence] 复用现有证据：{len(bundle.items)} 条")
        task_header, policy_scope = self._policy_display(policy_id)
        persona = self._build_persona(bundle, policy_id, None, data_source_id=data_source_id)
        trace.success("persona", "persona_ready", "[Persona] 申请人画像构建完成")
        history, final_record = self._execute_debate(
            bundle,
            task_header,
            policy_scope,
            persona_context=persona,
            trace=trace,
        )
        arbiter_result = self._build_arbiter_result(bundle, history, final_record, task_header, policy_scope)
        adjudication_report = self._build_adjudication_report(
            policy_id,
            bundle,
            history,
            final_record,
            arbiter_result,
        )
        resolved_manual_supplements = self._resolve_manual_supplements(manual_supplements, adjudication_report)
        trace.success("arbitration", "report_ready", "[Arbitration] 仲裁与条款级报告生成完成")
        trace.success("session", "session_completed", "[Session] 审查会话完成")
        result = build_debate_result(
            session_id,
            bundle,
            history,
            final_record,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            manual_supplements=resolved_manual_supplements,
            persona=persona,
            system_traces=trace.to_list(),
            policy_id=policy_id,
            data_source_id=data_source_id,
        )
        result["policy_id"] = policy_id
        result["data_source_id"] = data_source_id
        self._persist_completed_session(
            session_id=session_id,
            source_endpoint=source_endpoint,
            bundle=bundle,
            history=history,
            final_record=final_record,
            started_at=started_at,
            policy_id=policy_id,
            data_source_id=data_source_id,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            manual_supplements=resolved_manual_supplements,
            persona=persona,
            system_traces=trace.to_list(),
        )
        return result

    def run_debate_stream(
        self,
        id_card: str,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        collection_context: dict | None = None,
    ) -> Generator[str, None, None]:
        session_id = str(uuid.uuid4())
        started_at = self._utcnow()
        trace = TraceContext(session_id=session_id, id_card=id_card, policy_id=policy_id)
        trace.info("session", "session_started", "[Session] 流式审查会话启动", data_source_id=data_source_id)
        task_header, policy_scope = self._policy_display(policy_id)

        try:
            planner = EvidencePlanner()
            plan = planner.plan(person_id=id_card, policy_id=policy_id)
            
            yield self._build_sse_event("system_trace", trace.info("planning", "goal_loaded", f"[Sys] 成功加载系统目标：{plan.packet_summary}"))
            time.sleep(0.3)
            yield self._build_sse_event("system_trace", trace.success("planning", "plan_created", f"[Plan] Evidence Planner 已完成拆解，共生成 {len(plan.items)} 个侦查断点。", plan_item_count=len(plan.items)))
            time.sleep(0.4)
            # 逐条输出取证任务，避免前端只看到聚合摘要。
            for item in plan.items:
                yield self._build_sse_event(
                    "system_trace",
                    trace.warning(
                        "planning",
                        "plan_item_ready",
                        f"  - [Rule: {item.rule_type}] {item.rule_name}",
                        rule_id=item.rule_id,
                        rule_type=item.rule_type,
                    ),
                )
                time.sleep(0.15)
            yield self._build_sse_event("system_trace", trace.info("evidence", "collector_handoff", "[Agent: Text2SQL] Agent 接管取证据队列，多路动态代码生成中..."))
            time.sleep(0.5)
            yield self._build_sse_event("system_trace", trace.success("evidence", "evidence_bus_ready", "[Sys] 底层证据矩阵构建完毕，数据总线已对齐，进入仲裁阶段..."))
            time.sleep(0.4)
        except Exception as e:
            logger.error(f"Trace generation failed: {e}")
            yield self._build_sse_event(
                "system_trace",
                trace.danger("planning", "plan_failed", f"[Plan] 取证规划阶段异常：{e}"),
            )

        # 真正开始流式收集证据：
        bundle = EvidenceBundle(id_card=id_card)
        for evidence_item in self._collect_stream_evidence(id_card, policy_id, data_source_id, collection_context, trace):
            bundle.items.append(evidence_item)
            # 实时推送取证结果到前端 EvidenceBoard
            yield self._build_sse_event("evidence", self._build_stream_evidence(bundle))

        history: list[DebateRecord] = []
        projection = project_evidence(bundle, task_header, policy_scope)
        persona = self._build_persona(bundle, policy_id, None, data_source_id=data_source_id)
        trace.success("persona", "persona_ready", "[Persona] 申请人画像构建完成")
        yield self._build_sse_event("persona_ready", persona)

        # Initialize argumentation framework
        arg_graph = ArgumentGraph()
        attack_detector = AttackDetector()
        previous_acceptable: set[str] = set()
        arg_seq_counter = 0

        from concurrent.futures import ThreadPoolExecutor, as_completed

        r0_judgments: list[AgentJudgment] = []

        def _judge_agent(agent):
            try:
                case_summaries = self._empirical_case_context(agent, projection)
                with use_trace(trace):
                    judgment = agent.judge(
                        projection,
                        debate_round=0,
                        case_summaries=case_summaries,
                        persona_context=persona,
                        tools=self.tools,
                        tool_registry=self.tool_registry,
                        tool_policy=self.debate_tool_policy,
                    )
                trace.success("debate", "agent_judgment", f"[Debate] {agent.AGENT_ROLE} 初判完成", agent_id=agent.AGENT_ID, round=0)
                return judgment
            except Exception as exc:
                logger.error("{} round-0 judgment failed: {}", agent.AGENT_ROLE, exc)
                trace.danger("debate", "agent_judgment_failed", f"[Debate] {agent.AGENT_ROLE} 初判失败：{exc}", agent_id=agent.AGENT_ID, round=0)
                return self._create_fallback_judgment(agent, 0, str(exc))

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_judge_agent, agent): agent for agent in self.agents}
            for future in as_completed(futures):
                judgment = future.result()
                r0_judgments.append(judgment)
                yield self._build_sse_event("agent_judgment", self._judgment_to_payload(judgment))

        last_record = DebateRecord(
            r0_judgments, 0,
            projection=projection,
            evidence_items=bundle.items,
        )

        # Extract arguments from round 0
        arg_seq_counter = self._extract_arguments_to_graph(
            last_record.judgments, 0, arg_graph, projection,
            attack_detector, arg_seq_counter,
        )
        self._update_record_argumentation(last_record, arg_graph)
        history.append(last_record)

        for round_idx in range(1, self.max_rounds + 1):
            if last_record.is_consensus_reached:
                break

            # Build conflict summary from previous round's argument graph
            conflict_summary = arg_graph.summarize_conflicts()
            round_summaries = "\n".join(
                r.round_summary for r in history if r.round_summary
            )

            yield self._build_sse_event("round_start", round_idx)
            current_judgments: list[AgentJudgment] = []

            def _respond_agent(agent):
                try:
                    case_summaries = self._empirical_case_context(agent, projection)
                    with use_trace(trace):
                        judgment = agent.debate_respond(
                            projection,
                            last_record.judgments,
                            debate_round=round_idx,
                            case_summaries=case_summaries,
                            persona_context=persona,
                            tools=self.tools,
                            tool_registry=self.tool_registry,
                            tool_policy=self.debate_tool_policy,
                            conflict_summary=conflict_summary,
                            round_summaries=round_summaries,
                        )
                    trace.success("debate", "agent_response", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应完成", agent_id=agent.AGENT_ID, round=round_idx)
                    return judgment
                except Exception as exc:
                    logger.error("{} debate response failed: {}", agent.AGENT_ROLE, exc)
                    trace.danger("debate", "agent_response_failed", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应失败：{exc}", agent_id=agent.AGENT_ID, round=round_idx)
                    return self._create_fallback_judgment(agent, round_idx, str(exc))

            with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
                futures = {pool.submit(_respond_agent, agent): agent for agent in self.agents}
                for future in as_completed(futures):
                    judgment = future.result()
                    current_judgments.append(judgment)
                    yield self._build_sse_event("agent_judgment", self._judgment_to_payload(judgment))

            last_record = DebateRecord(
                current_judgments, round_idx,
                projection=projection,
                evidence_items=bundle.items,
            )

            # Extract arguments from this round
            arg_seq_counter = self._extract_arguments_to_graph(
                last_record.judgments, round_idx, arg_graph, projection,
                attack_detector, arg_seq_counter,
            )
            self._update_record_argumentation(last_record, arg_graph)

            # Dynamic termination: check argumentation convergence
            current_acceptable = arg_graph.compute_acceptable_set()
            if current_acceptable == previous_acceptable and len(current_acceptable) > 0:
                logger.info("Argumentation converged: acceptable set stable at round {}", round_idx)
                break
            previous_acceptable = current_acceptable

            history.append(last_record)

        # Finalize argument statuses
        arg_graph.finalize_arguments()
        self._update_record_argumentation(last_record, arg_graph)

        arbiter_result = self._build_arbiter_result(bundle, history, last_record, task_header, policy_scope)
        adjudication_report = self._build_adjudication_report(
            policy_id,
            bundle,
            history,
            last_record,
            arbiter_result,
        )
        trace.success("arbitration", "report_ready", "[Arbitration] 仲裁与条款级报告生成完成")
        trace.success("session", "session_completed", "[Session] 审查会话完成")
        result = build_debate_result(
            session_id,
            bundle,
            history,
            last_record,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            persona=persona,
            system_traces=trace.to_list(),
            policy_id=policy_id,
            data_source_id=data_source_id,
        )
        result["policy_id"] = policy_id
        result["data_source_id"] = data_source_id
        self._persist_completed_session(
            session_id=session_id,
            source_endpoint="/api/debate_stream",
            bundle=bundle,
            history=history,
            final_record=last_record,
            started_at=started_at,
            policy_id=policy_id,
            data_source_id=data_source_id,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            persona=persona,
            system_traces=trace.to_list(),
        )
        yield self._build_sse_event("debate_final", result)

    def run_debate_stream_with_bundle(
        self,
        bundle: EvidenceBundle,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        manual_supplements: list[dict[str, object]] | None = None,
    ) -> Generator[str, None, None]:
        bundle = self._prioritize_manual_evidence(bundle)
        session_id = str(uuid.uuid4())
        started_at = self._utcnow()
        trace = TraceContext(session_id=session_id, id_card=bundle.id_card, policy_id=policy_id)
        trace.info("session", "session_started", "[Session] 流式复用证据审查会话启动", data_source_id=data_source_id)
        task_header, policy_scope = self._policy_display(policy_id)

        yield self._build_sse_event(
            "system_trace",
            trace.success("evidence", "evidence_reused", f"[Plan] 复用现有证据，跳过取证阶段（共 {len(bundle.items)} 条）。"),
        )
        yield self._build_sse_event(
            "system_trace",
            trace.warning("evidence", "manual_priority_enabled", "[Plan] 人工核验补证已启用最高优先级：同条款将覆盖系统证据。"),
        )

        history: list[DebateRecord] = []
        projection = project_evidence(bundle, task_header, policy_scope)
        persona = self._build_persona(bundle, policy_id, None, data_source_id=data_source_id)
        trace.success("persona", "persona_ready", "[Persona] 申请人画像构建完成")
        yield self._build_sse_event("persona_ready", persona)

        # Initialize argumentation framework
        arg_graph = ArgumentGraph()
        attack_detector = AttackDetector()
        previous_acceptable: set[str] = set()
        arg_seq_counter = 0

        from concurrent.futures import ThreadPoolExecutor, as_completed

        r0_judgments: list[AgentJudgment] = []

        def _judge_agent(agent):
            try:
                case_summaries = self._empirical_case_context(agent, projection)
                with use_trace(trace):
                    judgment = agent.judge(
                        projection,
                        debate_round=0,
                        case_summaries=case_summaries,
                        persona_context=persona,
                        tools=self.tools,
                        tool_registry=self.tool_registry,
                        tool_policy=self.debate_tool_policy,
                    )
                trace.success("debate", "agent_judgment", f"[Debate] {agent.AGENT_ROLE} 初判完成", agent_id=agent.AGENT_ID, round=0)
                return judgment
            except Exception as exc:
                logger.error("{} round-0 judgment failed: {}", agent.AGENT_ROLE, exc)
                trace.danger("debate", "agent_judgment_failed", f"[Debate] {agent.AGENT_ROLE} 初判失败：{exc}", agent_id=agent.AGENT_ID, round=0)
                return self._create_fallback_judgment(agent, 0, str(exc))

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_judge_agent, agent): agent for agent in self.agents}
            for future in as_completed(futures):
                judgment = future.result()
                r0_judgments.append(judgment)
                yield self._build_sse_event("agent_judgment", self._judgment_to_payload(judgment))

        last_record = DebateRecord(
            r0_judgments, 0,
            projection=projection,
            evidence_items=bundle.items,
        )

        # Extract arguments from round 0
        arg_seq_counter = self._extract_arguments_to_graph(
            last_record.judgments, 0, arg_graph, projection,
            attack_detector, arg_seq_counter,
        )
        self._update_record_argumentation(last_record, arg_graph)
        history.append(last_record)

        for round_idx in range(1, self.max_rounds + 1):
            if last_record.is_consensus_reached:
                break

            # Build conflict summary from previous round's argument graph
            conflict_summary = arg_graph.summarize_conflicts()
            round_summaries = "\n".join(
                r.round_summary for r in history if r.round_summary
            )

            yield self._build_sse_event("round_start", round_idx)
            current_judgments: list[AgentJudgment] = []

            def _respond_agent(agent):
                try:
                    case_summaries = self._empirical_case_context(agent, projection)
                    with use_trace(trace):
                        judgment = agent.debate_respond(
                            projection,
                            last_record.judgments,
                            debate_round=round_idx,
                            case_summaries=case_summaries,
                            persona_context=persona,
                            tools=self.tools,
                            tool_registry=self.tool_registry,
                            tool_policy=self.debate_tool_policy,
                            conflict_summary=conflict_summary,
                            round_summaries=round_summaries,
                        )
                    trace.success("debate", "agent_response", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应完成", agent_id=agent.AGENT_ID, round=round_idx)
                    return judgment
                except Exception as exc:
                    logger.error("{} debate response failed: {}", agent.AGENT_ROLE, exc)
                    trace.danger("debate", "agent_response_failed", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应失败：{exc}", agent_id=agent.AGENT_ID, round=round_idx)
                    return self._create_fallback_judgment(agent, round_idx, str(exc))

            with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
                futures = {pool.submit(_respond_agent, agent): agent for agent in self.agents}
                for future in as_completed(futures):
                    judgment = future.result()
                    current_judgments.append(judgment)
                    yield self._build_sse_event("agent_judgment", self._judgment_to_payload(judgment))

            last_record = DebateRecord(
                current_judgments, round_idx,
                projection=projection,
                evidence_items=bundle.items,
            )

            # Extract arguments from this round
            arg_seq_counter = self._extract_arguments_to_graph(
                last_record.judgments, round_idx, arg_graph, projection,
                attack_detector, arg_seq_counter,
            )
            self._update_record_argumentation(last_record, arg_graph)

            # Dynamic termination: check argumentation convergence
            current_acceptable = arg_graph.compute_acceptable_set()
            if current_acceptable == previous_acceptable and len(current_acceptable) > 0:
                logger.info("Argumentation converged: acceptable set stable at round {}", round_idx)
                break
            previous_acceptable = current_acceptable

            history.append(last_record)

        # Finalize argument statuses
        arg_graph.finalize_arguments()
        self._update_record_argumentation(last_record, arg_graph)

        arbiter_result = self._build_arbiter_result(bundle, history, last_record, task_header, policy_scope)
        adjudication_report = self._build_adjudication_report(
            policy_id,
            bundle,
            history,
            last_record,
            arbiter_result,
        )
        resolved_manual_supplements = self._resolve_manual_supplements(manual_supplements, adjudication_report)
        trace.success("arbitration", "report_ready", "[Arbitration] 仲裁与条款级报告生成完成")
        trace.success("session", "session_completed", "[Session] 审查会话完成")
        result = build_debate_result(
            session_id,
            bundle,
            history,
            last_record,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            manual_supplements=resolved_manual_supplements,
            persona=persona,
            system_traces=trace.to_list(),
            policy_id=policy_id,
            data_source_id=data_source_id,
        )
        result["policy_id"] = policy_id
        result["data_source_id"] = data_source_id
        self._persist_completed_session(
            session_id=session_id,
            source_endpoint="/api/debate_stream",
            bundle=bundle,
            history=history,
            final_record=last_record,
            started_at=started_at,
            policy_id=policy_id,
            data_source_id=data_source_id,
            arbiter_result=arbiter_result,
            adjudication_report=adjudication_report,
            manual_supplements=resolved_manual_supplements,
            persona=persona,
            system_traces=trace.to_list(),
        )
        yield self._build_sse_event("debate_final", result)

    def _execute_debate(
        self,
        bundle: EvidenceBundle,
        task_header: str = DEFAULT_TASK_HEADER,
        policy_scope: str = DEFAULT_POLICY_SCOPE,
        persona_context: dict | None = None,
        trace: TraceContext | None = None,
    ) -> tuple[list[DebateRecord], DebateRecord]:
        history: list[DebateRecord] = []

        # Cache projection to avoid recomputing each round
        cached_projection = project_evidence(bundle, task_header, policy_scope)

        # Initialize argumentation framework
        arg_graph = ArgumentGraph()
        attack_detector = AttackDetector()
        previous_acceptable: set[str] = set()
        arg_seq_counter = 0

        current_record = self._run_round_zero(
            bundle, task_header, policy_scope,
            persona_context=persona_context,
            cached_projection=cached_projection,
            trace=trace,
        )

        # Extract arguments from round 0 judgments
        arg_seq_counter = self._extract_arguments_to_graph(
            current_record.judgments, 0, arg_graph, cached_projection,
            attack_detector, arg_seq_counter,
        )
        self._update_record_argumentation(current_record, arg_graph)
        history.append(current_record)

        if current_record.is_consensus_reached:
            return history, current_record

        for round_idx in range(1, self.max_rounds + 1):
            # Build conflict summary from previous round's argument graph
            conflict_summary = arg_graph.summarize_conflicts()
            # Collect round summaries from history
            round_summaries = "\n".join(
                r.round_summary for r in history if r.round_summary
            )

            current_record = self._run_debate_round(
                bundle,
                current_record,
                round_idx,
                task_header,
                policy_scope,
                persona_context=persona_context,
                cached_projection=cached_projection,
                trace=trace,
                conflict_summary=conflict_summary,
                round_summaries=round_summaries,
            )

            # Extract arguments from this round
            arg_seq_counter = self._extract_arguments_to_graph(
                current_record.judgments, round_idx, arg_graph, cached_projection,
                attack_detector, arg_seq_counter,
            )
            self._update_record_argumentation(current_record, arg_graph)

            history.append(current_record)

            # Dynamic termination: check argumentation convergence
            current_acceptable = arg_graph.compute_acceptable_set()
            if current_acceptable == previous_acceptable and len(current_acceptable) > 0:
                logger.info("Argumentation converged: acceptable set stable at round {}", round_idx)
                break
            previous_acceptable = current_acceptable

            if current_record.is_consensus_reached:
                break

        # Finalize argument statuses
        arg_graph.finalize_arguments()
        # Store final graph on last record
        self._update_record_argumentation(current_record, arg_graph)

        return history, current_record

    def _update_record_argumentation(
        self,
        record: DebateRecord,
        arg_graph: ArgumentGraph,
    ) -> None:
        record.argument_graph = arg_graph.to_dict()
        consensus = self._compute_argumentation_consensus(arg_graph)
        record.argumentation_stance = consensus["stance"]
        record.argumentation_conclusion = consensus["conclusion"]
        record.argumentation_confidence = consensus["confidence"]
        record.argumentation_consensus_rate = consensus["rate"]
        record.argumentation_consensus_reached = consensus["reached"]
        record.is_consensus_reached = record.is_consensus_reached or consensus["reached"]
        record.round_summary = self._build_round_summary(record, arg_graph)

    def _build_round_summary(self, record: DebateRecord, arg_graph: ArgumentGraph) -> str:
        """生成本轮摘要：立场分布 + 关键冲突 + 收敛趋势。纯数据格式化，无 LLM。"""
        parts: list[str] = []

        # 立场分布
        stance_counts: dict[str, int] = {}
        for j in record.judgments:
            stance_counts[j.stance] = stance_counts.get(j.stance, 0) + 1
        stance_str = "、".join(f"{v}{'支持' if k == '支持通过' else '反对' if k == '反对通过' else '待定'}" for k, v in stance_counts.items())
        parts.append(f"Round {record.round_num}：{stance_str}")

        # 关键冲突
        conflict_summary = arg_graph.summarize_conflicts(max_items=3)
        if conflict_summary:
            # 只取冲突行，不带标题
            conflict_lines = [l for l in conflict_summary.split("\n") if l.startswith(("1.", "2.", "3."))]
            if conflict_lines:
                parts.append("核心分歧：" + "；".join(conflict_lines))

        # 共识状态
        if record.is_consensus_reached:
            parts.append("已达共识。")
        else:
            parts.append(f"共识率 {record.consensus_rate:.0%}，尚未达成共识。")

        return " | ".join(parts)

    def _compute_argumentation_consensus(self, arg_graph: ArgumentGraph) -> dict[str, Any]:
        acceptable_ids = arg_graph.compute_acceptable_set()
        accepted_args = [
            arg_graph.arguments[arg_id]
            for arg_id in acceptable_ids
            if arg_id in arg_graph.arguments
        ]
        if not accepted_args:
            return {
                "stance": None,
                "conclusion": None,
                "confidence": 0.0,
                "rate": 0.0,
                "reached": False,
            }

        stance_groups: dict[ArgumentStance, list[Argument]] = {}
        for arg in accepted_args:
            stance_groups.setdefault(arg.stance, []).append(arg)

        dominant_stance, dominant_args = max(
            stance_groups.items(),
            key=lambda item: (len(item[1]), sum(arg.confidence for arg in item[1])),
        )
        rate = len(dominant_args) / len(accepted_args)
        confidence = sum(arg.confidence for arg in dominant_args) / max(len(dominant_args), 1)
        conclusion = {
            ArgumentStance.PASS: CONCLUSION_PASS,
            ArgumentStance.REJECT: CONCLUSION_FAIL,
            ArgumentStance.INSUFFICIENT: CONCLUSION_MISSING,
        }[dominant_stance]
        reached = (
            rate >= settings.consensus_threshold
            and confidence >= settings.consensus_threshold
        )
        return {
            "stance": dominant_stance.value,
            "conclusion": conclusion,
            "confidence": round(confidence, 3),
            "rate": round(rate, 3),
            "reached": reached,
        }

    def _infer_argument_stance(
        self,
        judgment: AgentJudgment,
        text: str = "",
    ) -> ArgumentStance:
        conclusion_map = {
            CONCLUSION_PASS: ArgumentStance.PASS,
            CONCLUSION_FAIL: ArgumentStance.REJECT,
            CONCLUSION_MISSING: ArgumentStance.INSUFFICIENT,
        }
        conclusion = getattr(judgment, "conclusion", None)
        if conclusion in conclusion_map:
            return conclusion_map[conclusion]

        stance_map = {
            STANCE_SUPPORT: ArgumentStance.PASS,
            STANCE_OPPOSE: ArgumentStance.REJECT,
            STANCE_PENDING: ArgumentStance.INSUFFICIENT,
        }
        stance = getattr(judgment, "stance", None)
        if stance in stance_map:
            return stance_map[stance]

        lowered = (text or "").lower()
        compact = (text or "").replace(" ", "")
        reject_markers = ("reject", "fail", "oppose", "不符合", "反对", "驳回", "不通过")
        pass_markers = ("pass", "approve", "support", "符合", "支持", "通过")
        missing_markers = ("insufficient", "missing", "pending", "数据缺失", "待定", "未证实", "无法确认")
        if any(marker in lowered or marker in compact for marker in reject_markers):
            return ArgumentStance.REJECT
        if any(marker in lowered or marker in compact for marker in pass_markers):
            return ArgumentStance.PASS
        if any(marker in lowered or marker in compact for marker in missing_markers):
            return ArgumentStance.INSUFFICIENT
        return ArgumentStance.INSUFFICIENT

    @staticmethod
    def _infer_proof_standard(
        evidence_refs: list[str],
        rule_proof_map: dict[str, "ProofStandard"],
        card_proof_map: dict[str, "ProofStandard"],
    ) -> "ProofStandard":
        """Infer the highest proof standard from an argument's evidence references."""
        from agents.proof_standards import ProofStandard
        standards = [
            ProofStandard.PREPONDERANCE,
            ProofStandard.CLEAR_AND_CONVINCING,
            ProofStandard.BEYOND_REASONABLE_DOUBT,
        ]
        best_idx = 0
        for ref in evidence_refs:
            card_id = f"card_{ref}"
            ps = card_proof_map.get(card_id)
            if ps is None:
                # Try matching evidence_id to rule_id (case-insensitive)
                ref_upper = ref.upper().replace("PLAN_", "")
                for rule_id, rps in rule_proof_map.items():
                    if rule_id.lower() == ref_upper.lower():
                        ps = rps
                        break
            if ps is not None:
                idx = standards.index(ps)
                if idx > best_idx:
                    best_idx = idx
        return standards[best_idx]

    def _extract_arguments_to_graph(
        self,
        judgments: list[AgentJudgment],
        round_num: int,
        arg_graph: ArgumentGraph,
        projection: EvidenceProjection,
        attack_detector: AttackDetector,
        seq_counter: int,
    ) -> int:
        """Extract structured arguments from judgments into the argument graph."""
        from agents.proof_standards import proof_standard_for_rule_type

        # Build evidence score map for confidence computation
        evidence_scores: dict[str, float] = {}
        for card in projection.cards:
            eid = card.card_id.replace("card_", "")
            evidence_scores[eid] = card.evidence_score

        # Build rule_id → proof_standard map from policy pack
        rule_proof_map: dict[str, ProofStandard] = {}
        if self._current_policy_id:
            from policy.policy_pack_loader import load_policy_packs
            pack = load_policy_packs().get(self._current_policy_id)
            if pack:
                for bucket_name, bucket in [
                    ("必须满足", pack.structured_rules.basic_conditions),
                    ("必须排除", pack.structured_rules.exclusion_conditions),
                    ("灵活评判", pack.structured_rules.inference_rules),
                    ("额度计算", pack.structured_rules.calculation_rules),
                ]:
                    for rule in bucket:
                        rule_proof_map[rule.rule_id] = proof_standard_for_rule_type(bucket_name)

        # Build card_id → proof_standard map for quick lookup
        card_proof_map: dict[str, ProofStandard] = {}
        for card in projection.cards:
            rule_id = card.card_id.replace("card_", "")
            if rule_id in rule_proof_map:
                card_proof_map[card.card_id] = rule_proof_map[rule_id]

        new_args: list[Argument] = []

        for judgment in judgments:
            raw_args = getattr(judgment, "arguments", []) or []
            if not raw_args:
                # If agent didn't produce structured arguments, create one from judgment
                fallback_text = (
                    getattr(judgment, "key_finding", "")
                    or getattr(judgment, "reasoning", "")[:100]
                )
                raw_args = [{
                    "arg_text": fallback_text,
                    "evidence_refs": getattr(judgment, "evidence_refs", []),
                    "stance": self._infer_argument_stance(judgment, fallback_text).value,
                    "attacks": [],
                    "supported_by": [],
                }]

            for raw_arg in raw_args:
                seq_counter += 1
                arg_id = f"arg_{judgment.agent_id}_{round_num}_{seq_counter}"

                # Parse stance
                raw_stance = raw_arg.get("stance", "insufficient")
                if isinstance(raw_stance, ArgumentStance):
                    stance = raw_stance
                else:
                    stance = {
                        "pass": ArgumentStance.PASS,
                        "reject": ArgumentStance.REJECT,
                        "insufficient": ArgumentStance.INSUFFICIENT,
                        STANCE_SUPPORT: ArgumentStance.PASS,
                        STANCE_OPPOSE: ArgumentStance.REJECT,
                        STANCE_PENDING: ArgumentStance.INSUFFICIENT,
                        CONCLUSION_PASS: ArgumentStance.PASS,
                        CONCLUSION_FAIL: ArgumentStance.REJECT,
                        CONCLUSION_MISSING: ArgumentStance.INSUFFICIENT,
                    }.get(str(raw_stance).strip().lower(), ArgumentStance.INSUFFICIENT)

                # Determine proof_standard from evidence_refs
                arg_evidence_refs = raw_arg.get("evidence_refs", [])
                proof_standard = self._infer_proof_standard(
                    arg_evidence_refs, rule_proof_map, card_proof_map,
                )

                arg = Argument(
                    arg_id=arg_id,
                    text=raw_arg.get("arg_text", ""),
                    source_agent=judgment.agent_id,
                    round_num=round_num,
                    evidence_refs=arg_evidence_refs,
                    stance=stance,
                    confidence=0.0,  # will be computed objectively
                    attacks=raw_arg.get("attacks", []),
                    supported_by=raw_arg.get("supported_by", []),
                    proof_standard=proof_standard,
                )

                # Compute objective confidence
                arg.confidence = compute_argument_confidence(arg, projection, evidence_scores)
                arg_graph.add_argument(arg)
                new_args.append(arg)

        # Detect attack relations
        all_args = list(arg_graph.arguments.values())
        detected_attacks = attack_detector.detect(all_args, projection)
        for attack in detected_attacks:
            arg_graph.add_attack(attack)

        return seq_counter

    def _run_round_zero(
        self,
        bundle: EvidenceBundle,
        task_header: str = DEFAULT_TASK_HEADER,
        policy_scope: str = DEFAULT_POLICY_SCOPE,
        persona_context: dict | None = None,
        cached_projection: EvidenceProjection | None = None,
        trace: TraceContext | None = None,
    ) -> DebateRecord:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        projection = cached_projection or project_evidence(bundle, task_header, policy_scope)
        judgments: list[AgentJudgment] = []
        lock = threading.Lock()

        def _judge_agent(agent):
            try:
                with use_trace(trace):
                    judgment = agent.judge(
                        projection,
                        debate_round=0,
                        case_summaries=self._empirical_case_context(agent, projection),
                        persona_context=persona_context,
                        tools=self.tools,
                        tool_registry=self.tool_registry,
                        tool_policy=self.debate_tool_policy,
                    )
                if trace:
                    trace.success("debate", "agent_judgment", f"[Debate] {agent.AGENT_ROLE} 初判完成", agent_id=agent.AGENT_ID, round=0)
                return judgment
            except Exception as exc:
                logger.error("{} round-0 judgment failed: {}", agent.AGENT_ROLE, exc)
                if trace:
                    trace.danger("debate", "agent_judgment_failed", f"[Debate] {agent.AGENT_ROLE} 初判失败：{exc}", agent_id=agent.AGENT_ID, round=0)
                return self._create_fallback_judgment(agent, 0, str(exc))

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_judge_agent, agent): agent for agent in self.agents}
            for future in as_completed(futures):
                with lock:
                    judgments.append(future.result())

        return DebateRecord(
            judgments, 0,
            projection=projection,
            evidence_items=bundle.items,
        )

    def _run_debate_round(
        self,
        bundle: EvidenceBundle,
        previous_record: DebateRecord,
        round_idx: int,
        task_header: str = DEFAULT_TASK_HEADER,
        policy_scope: str = DEFAULT_POLICY_SCOPE,
        persona_context: dict | None = None,
        cached_projection: EvidenceProjection | None = None,
        trace: TraceContext | None = None,
        conflict_summary: str = "",
        round_summaries: str = "",
    ) -> DebateRecord:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        projection = cached_projection or project_evidence(bundle, task_header, policy_scope)
        judgments: list[AgentJudgment] = []
        lock = threading.Lock()

        def _respond_agent(agent):
            try:
                with use_trace(trace):
                    judgment = agent.debate_respond(
                        projection,
                        previous_record.judgments,
                        debate_round=round_idx,
                        case_summaries=self._empirical_case_context(agent, projection),
                        persona_context=persona_context,
                        tools=self.tools,
                        tool_registry=self.tool_registry,
                        tool_policy=self.debate_tool_policy,
                        conflict_summary=conflict_summary,
                        round_summaries=round_summaries,
                    )
                if trace:
                    trace.success("debate", "agent_response", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应完成", agent_id=agent.AGENT_ID, round=round_idx)
                return judgment
            except Exception as exc:
                logger.error("{} debate response failed: {}", agent.AGENT_ROLE, exc)
                if trace:
                    trace.danger("debate", "agent_response_failed", f"[Debate] {agent.AGENT_ROLE} 第 {round_idx} 轮回应失败：{exc}", agent_id=agent.AGENT_ID, round=round_idx)
                return self._create_fallback_judgment(agent, round_idx, str(exc))

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {pool.submit(_respond_agent, agent): agent for agent in self.agents}
            for future in as_completed(futures):
                with lock:
                    judgments.append(future.result())

        return DebateRecord(
            judgments, round_idx,
            projection=projection,
            evidence_items=bundle.items,
        )

    def _create_fallback_judgment(self, agent, round_idx: int, err_msg: str) -> AgentJudgment:
        return AgentJudgment(
            agent_id=agent.AGENT_ID,
            agent_role=agent.AGENT_ROLE,
            debate_round=round_idx,
            conclusion=CONCLUSION_MISSING,
            stance=STANCE_PENDING,
            confidence=0.0,
            evidence_refs=[],
            reasoning=f"Agent 执行异常，兜底判定生效：{err_msg}",
            dissent_points=[],
            key_finding="兜底判定：Agent 执行异常，结论降级为待定。",
        )

    def _build_stream_evidence(self, bundle: EvidenceBundle) -> list[dict[str, object]]:
        result = []
        for item in bundle.items:
            ev_score = score_evidence_item(item)
            result.append({
                "rule_id": item.rule_id,
                "target": item.target,
                "category": item.category,
                "exec_status": item.exec_status,
                "diagnostic_code": item.diagnostic_code,
                "diagnostic_label": item.diagnostic_label,
                "diagnostic_detail": item.diagnostic_detail,
                "diagnostic_hint": item.diagnostic_hint,
                "supports_conclusion": item.supports_conclusion,
                "result_summary": item.result_summary,
                "sql": item.sql,
                "result_raw": item.result_raw,
                "evidence_score": ev_score.score,
                "evidence_score_percent": ev_score.score_percent,
                "score_breakdown": ev_score.breakdown,
                "rank_reason": ev_score.rank_reason,
                **build_item_semantics(item),
            })
        return result

    def _build_sse_event(self, event: str, data: object) -> str:
        return f"data: {json.dumps({'event': event, 'data': data}, ensure_ascii=False, default=str)}\n\n"

    def _judgment_to_payload(self, judgment: AgentJudgment) -> dict[str, object]:
        return judgment.model_dump()

    def _build_arbiter_result(
        self,
        bundle: EvidenceBundle,
        history: list[DebateRecord],
        final_record: DebateRecord,
        task_header: str,
        policy_scope: str,
    ) -> dict[str, object]:
        projection = project_evidence(bundle, task_header, policy_scope)
        arbiter_result = self.arbiter.explain(projection, history, final_record)
        result_dict = arbiter_result.to_dict()
        # 反事实推演：不符合/待定时生成 what-if 场景
        conclusion = final_record.get_final_conclusion()
        if conclusion in ("不符合", "待定"):
            result_dict["counterfactuals"] = self.arbiter.build_counterfactuals(
                projection, arbiter_result, final_record,
            )
        else:
            result_dict["counterfactuals"] = []
        return result_dict

    def _build_adjudication_report(
        self,
        policy_id: str,
        bundle: EvidenceBundle,
        history: list[DebateRecord],
        final_record: DebateRecord,
        arbiter_result: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return build_adjudication_report(
            policy_id=policy_id,
            bundle=bundle,
            history=history,
            final_record=final_record,
            arbiter_result=arbiter_result or {},
        )

    def _build_persona(
        self,
        bundle: EvidenceBundle,
        policy_id: str,
        final_conclusion: str | None,
        data_source_id: str = "local_mysql_demo",
    ) -> dict[str, object]:
        try:
            builder = PersonaBuilder()
            return builder.build(
                id_card=bundle.id_card,
                policy_id=policy_id,
                evidence_bundle=bundle,
                final_conclusion=final_conclusion,
                data_source_id=data_source_id,
            )
        except Exception as exc:
            logger.exception("Persona build failed: id_card={} policy_id={}", bundle.id_card, policy_id)
            return {
                "error": str(exc),
                "title": f"{bundle.id_card} 画像构建失败",
                "archetype": "画像构建失败",
            }

    def _persist_completed_session(
        self,
        session_id: str,
        source_endpoint: str,
        bundle: EvidenceBundle,
        history: list[DebateRecord],
        final_record: DebateRecord,
        started_at: datetime,
        policy_id: str = "POLICY_001",
        data_source_id: str = "local_mysql_demo",
        arbiter_result: dict[str, object] | None = None,
        adjudication_report: dict[str, object] | None = None,
        manual_supplements: list[dict[str, object]] | None = None,
        persona: dict[str, object] | None = None,
        system_traces: list[dict[str, object]] | None = None,
    ) -> None:
        completed_at = self._utcnow()
        try:
            persist_completed_session(
                session_id=session_id,
                source_endpoint=source_endpoint,
                bundle=bundle,
                history=history,
                final_record=final_record,
                started_at=started_at,
                completed_at=completed_at,
                policy_id=policy_id,
                data_source_id=data_source_id,
                arbiter_result=arbiter_result,
                adjudication_report=adjudication_report,
                manual_supplements=manual_supplements,
                persona=persona,
                system_traces=system_traces,
            )
        except DebatePersistenceError:
            logger.exception(
                "Completed debate session persistence failed: session={} endpoint={}",
                session_id,
                source_endpoint,
            )
            raise

    def _collect_all_evidence(
        self,
        id_card: str,
        policy_id: str,
        data_source_id: str,
        collection_context: dict | None,
        trace: TraceContext | None,
    ) -> EvidenceBundle:
        collector = self._collector_for_data_source(data_source_id)
        try:
            return collector.collect_all(
                id_card,
                policy_id=policy_id,
                data_source_id=data_source_id,
                collection_context=collection_context,
                trace=trace,
            )
        except TypeError as exc:
            if "trace" not in str(exc) and "data_source_id" not in str(exc) and "collection_context" not in str(exc):
                raise
            try:
                return collector.collect_all(
                    id_card,
                    policy_id=policy_id,
                    data_source_id=data_source_id,
                    trace=trace,
                )
            except TypeError as retry_exc:
                if "trace" not in str(retry_exc) and "data_source_id" not in str(retry_exc):
                    raise
                try:
                    return collector.collect_all(id_card, policy_id=policy_id, trace=trace)
                except TypeError as final_exc:
                    if "trace" not in str(final_exc):
                        raise
                    return collector.collect_all(id_card, policy_id=policy_id)

    def _collect_stream_evidence(
        self,
        id_card: str,
        policy_id: str,
        data_source_id: str,
        collection_context: dict | None,
        trace: TraceContext | None,
    ):
        collector = self._collector_for_data_source(data_source_id)
        try:
            return collector.collect_stream(
                id_card,
                policy_id=policy_id,
                data_source_id=data_source_id,
                collection_context=collection_context,
                trace=trace,
            )
        except TypeError as exc:
            if "trace" not in str(exc) and "data_source_id" not in str(exc) and "collection_context" not in str(exc):
                raise
            try:
                return collector.collect_stream(
                    id_card,
                    policy_id=policy_id,
                    data_source_id=data_source_id,
                    trace=trace,
                )
            except TypeError as retry_exc:
                if "trace" not in str(retry_exc) and "data_source_id" not in str(retry_exc):
                    raise
                try:
                    return collector.collect_stream(id_card, policy_id=policy_id, trace=trace)
                except TypeError as final_exc:
                    if "trace" not in str(final_exc):
                        raise
                    return collector.collect_stream(id_card, policy_id=policy_id)

    def _collector_for_data_source(self, data_source_id: str):
        if data_source_id == "local_mysql_demo":
            return self.collector
        return self.collector_registry.create_for_data_source(data_source_id)

    def _utcnow(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def _is_manual_evidence(self, item) -> bool:
        if bool(getattr(item, "manual_verified", False)):
            return True
        return str(getattr(item, "category", "") or "") == "manual_supplement"

    def _prioritize_manual_evidence(self, bundle: EvidenceBundle) -> EvidenceBundle:
        chosen: dict[str, object] = {}
        manual_locked: dict[str, bool] = {}

        for item in bundle.items:
            rule_id = str(getattr(item, "rule_id", "") or "").strip()
            if not rule_id:
                continue

            is_manual = self._is_manual_evidence(item)
            if rule_id not in chosen:
                chosen[rule_id] = item
                manual_locked[rule_id] = is_manual
                continue

            if manual_locked.get(rule_id, False):
                if is_manual:
                    chosen[rule_id] = item
                continue

            if is_manual:
                chosen[rule_id] = item
                manual_locked[rule_id] = True
            else:
                chosen[rule_id] = item

        prioritized_items = list(chosen.values())
        if len(prioritized_items) == len(bundle.items):
            return bundle
        return EvidenceBundle(
            id_card=bundle.id_card,
            collected_at=bundle.collected_at,
            items=prioritized_items,
        )

    def _resolve_manual_supplements(
        self,
        manual_supplements: list[dict[str, object]] | None,
        adjudication_report: dict[str, object] | None,
    ) -> list[dict[str, object]]:
        if not manual_supplements:
            return []

        clause_rows = (
            adjudication_report.get("clause_results", [])
            if isinstance(adjudication_report, dict)
            else []
        )
        clause_by_id = {
            str(row.get("clause_id", "")).strip(): row
            for row in clause_rows
            if isinstance(row, dict) and row.get("clause_id")
        }

        reviewed_at = self._utcnow().isoformat()
        resolved: list[dict[str, object]] = []

        for raw in manual_supplements:
            if not isinstance(raw, dict):
                continue

            row = dict(raw)
            status = str(row.get("status") or "pending_review")
            clause_id = str(row.get("clause_id") or "").strip()
            if status != "pending_review" or not clause_id:
                resolved.append(row)
                continue

            clause = clause_by_id.get(clause_id)
            stance = str(row.get("stance") or "support").strip().lower()

            review_status = ""
            review_effect = ""
            review_reason = "人工核验补证为最高优先级，已直接采纳。"
            adopted = True

            if isinstance(clause, dict):
                review_status = str(clause.get("semantic_display_label") or clause.get("status") or "")
                review_effect = str(clause.get("semantic_decision_effect") or "")
                if stance == "support":
                    review_reason = "人工核验补证（支持）为最高优先级，已直接采纳。"
                elif stance == "refute":
                    review_reason = "人工核验补证（反驳）为最高优先级，已直接采纳。"
                else:
                    review_reason = "人工核验补证为最高优先级，已直接采纳。"

            row["status"] = "adopted" if adopted else "not_adopted"
            row["reviewed_at"] = reviewed_at
            row["review_status"] = review_status
            row["review_effect"] = review_effect
            row["review_reason"] = review_reason
            resolved.append(row)

        return resolved
