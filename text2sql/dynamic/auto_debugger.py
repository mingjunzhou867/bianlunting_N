import re
import time
from typing import Any
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from data_sources.session import get_session_for_data_source
from cognition.evidence_planner import EvidencePlanItem
from text2sql.dynamic.text2sql_agent import Text2SQLAgent
from privacy.sanitizer import prepare_sql_for_execution, sanitize_for_llm


class AutoDebugger:
    """
    自动执行 SQL 并根据报错自我修复的高级执行引擎。
    拦截语法错误并让 LLM 闭环重写，保护系统免受动态 SQL 炸弹影响。
    """
    
    def __init__(self, agent: Text2SQLAgent | None = None, max_retries: int = 3, detail_query_rule_ids: set[str] | None = None):
        self.agent = agent or Text2SQLAgent()
        self.max_retries = max_retries
        self._detail_query_rule_ids = detail_query_rule_ids or set()

    def _enforce_detail_query(self, plan_item: EvidencePlanItem, sql: str) -> None:
        rule_text = f"{plan_item.rule_name} {plan_item.rule_description}"
        is_detail_query = any(token in rule_text for token in ("调查详情", "详情查询", "明细", "复合表", "联合查询")) or plan_item.rule_id in self._detail_query_rule_ids
        if not is_detail_query:
            return
        lowered = sql.lower()
        if "count(" in lowered or "exists" in lowered:
            raise RuntimeError(
                f"Detail query guardrail rejected aggregate SQL for {plan_item.rule_id}; expected field-level or composite-table facts."
            )
        forbidden_candidates = [
            "hc.valid_from",
            "hc.valid_to",
            "hc.status",
            "hc_category_type",
            "hc_policy_code",
            "hc_data_source",
        ]
        if any(token in lowered for token in forbidden_candidates):
            raise RuntimeError(
                f"Detail query guardrail rejected hallucinated columns for {plan_item.rule_id}; use only schema-backed fields."
            )
        if plan_item.allowed_fields:
            allowed = {field.split('.')[-1].lower() for field in plan_item.allowed_fields}
            tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", lowered)
            excluded = {"select", "from", "where", "and", "or", "join", "left", "right", "inner", "outer", "on", "as", "order", "by", "desc", "asc", "limit", "distinct", "group", "having", "case", "when", "then", "else", "end", "with", "count", "exists", "sum", "min", "max", "avg", "lag", "lead", "over", "partition", "current_date", "date_format", "date_sub", "now"}
            suspicious = sorted({token for token in tokens if token not in allowed and token not in excluded and len(token) > 2})
            if any(name.endswith("_from") or name.endswith("_to") for name in suspicious):
                raise RuntimeError(
                    f"Detail query guardrail rejected non-whitelisted field names for {plan_item.rule_id}: {', '.join(suspicious[:5])}"
                )

    def execute_with_auto_fix(
        self,
        plan_item: EvidencePlanItem,
        person_id: str,
        data_source_id: str = "local_mysql_demo",
    ) -> tuple[str, list[dict[str, Any]]]:
        error_feedback = ""
        last_sql = ""
        
        for attempt in range(self.max_retries):
            # 1. 动态生成 SQL (若有报错则回传供模型修订)
            sql = self.agent.generate_sql(plan_item, person_id, error_feedback, data_source_id=data_source_id)
            
            # 2. 安全替换第一阶段规划的占位符
            executable_sql = prepare_sql_for_execution(sql, person_id)
            last_sql = executable_sql
            self._enforce_detail_query(plan_item, executable_sql)
            
            logger.info(
                "[AutoDebugger] executing SQL attempt {}/{}:\n{}",
                attempt + 1,
                self.max_retries,
                sanitize_for_llm(executable_sql, person_id),
            )
            
            try:
                # 3. 尝试带压测执行
                with get_session_for_data_source(data_source_id) as session:
                    result = session.execute(text(executable_sql))
                    columns = result.keys()
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
                    
                    logger.success("[AutoDebugger] SQL executed successfully, rows={}", len(rows))
                    return last_sql, rows
                    
            except SQLAlchemyError as exc:
                # 4. 异常拦截与智能反思机制
                error_msg = sanitize_for_llm(str(exc), person_id)
                logger.warning("[AutoDebugger] SQL execution failed, retrying with feedback: {}", error_msg)
                error_feedback = error_msg
                time.sleep(1)  # 防 LLM 速率限制
                
        # 兜底：所有补救措施全失败
        logger.error("[AutoDebugger] SQL execution failed after {} attempt(s)", self.max_retries)
        raise RuntimeError(f"AutoDebugger failed after {self.max_retries} attempts. Last DB error: {error_feedback}")
