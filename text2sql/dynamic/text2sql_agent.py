import re
from loguru import logger
from typing import Optional

from config.llm_client import llm_chat
from text2sql.dynamic.prompt_builder import QueryPromptBuilder
from text2sql.dynamic.sql_postprocessor import postprocess_generated_sql
from cognition.evidence_planner import EvidencePlanItem
from privacy.sanitizer import sanitize_for_llm


class Text2SQLAgent:
    """
    动态 SQL 生成智能体。
    依据 Layer 1 产生的规划，通过 LLM 生成精确的 SQL，自带提取能力。
    """

    def __init__(self, prompt_builder: QueryPromptBuilder | None = None, model: str = ""):
        self.prompt_builder = prompt_builder or QueryPromptBuilder()
        self.model = model  # 如果为空，llm_chat 内部会走 settings.default_llm_model
        self._current_ds: str | None = None

    def generate_sql(self, plan_item: EvidencePlanItem, person_id: str, error_feedback: str = "", data_source_id: str | None = None) -> str:
        """
        调用 LLM 生成 SQL。
        如果是报错后的重试调用，会把错误信息通过 error_feedback 传给模型。
        如果 plan_item 已有 sql_template，直接返回，跳过 LLM 调用。
        """
        # Template-first: 有模板直接用，跳过 LLM + auto_debugger
        if plan_item.sql_template and not error_feedback:
            logger.debug(f"[Text2SQL Agent] 使用预置模板，跳过 LLM：{plan_item.rule_id}")
            return plan_item.sql_template

        # 当 data_source_id 变化时，重建 prompt_builder 以使用对应的 schema
        if data_source_id and data_source_id != self._current_ds:
            self.prompt_builder = QueryPromptBuilder(data_source_id=data_source_id)
            self._current_ds = data_source_id

        system_prompt = self.prompt_builder.build_system_prompt(plan_item, person_id)
        user_prompt = self.prompt_builder.build_user_prompt(
            plan_item,
            person_id,
            error_msg=sanitize_for_llm(error_feedback, person_id),
        )

        logger.debug(f"[Text2SQL Agent] 准备生成 SQL，目标：{plan_item.rule_id} ({plan_item.rule_name})")
        
        response = llm_chat(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.1  # SQL 生成需要极高的确定性
        )
        
        return self._extract_sql(response)

    def _extract_sql(self, text: str) -> str:
        """
        从大模型返回的文本中提取被 markdown 包裹的 sql 代码。
        """
        match = re.search(r"```[sS][qQ][lL]\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return postprocess_generated_sql(match.group(1).strip())
            
        # 如果模型没有遵守 markdown 格式，尝试退化处理
        logger.warning("模型未输出 markdown sql 块，尝试直接清理并返回原文")
        return postprocess_generated_sql(text.strip("` \n"))
