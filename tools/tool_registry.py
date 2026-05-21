"""Tool registry for agent tool calling with MCP security enforcement."""
import json
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from runtime.trace import current_trace
from privacy.sanitizer import sanitize_for_llm


class ToolRegistry:
    """统一的工具注册中心，支持 MCP 进程隔离和策略执行。"""

    def __init__(
        self,
        tool_policy: Any | None = None,
        mcp_client: Any | None = None,
    ):
        self.tools: dict[str, Any] = {}
        self.tool_policy = tool_policy
        self.mcp_client = mcp_client
        self._call_counts: dict[str, int] = {}
        self._evidence_collected: bool = False
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        from tools.text2sql_tool import Text2SQLTool
        from tools.dict_tool import DictTool

        self.register("text_to_sql", Text2SQLTool())
        self.register("get_dict", DictTool())

    def register(self, name: str, tool: Any):
        self.tools[name] = tool

    def get_tool_schemas(self) -> list[dict]:
        """返回 OpenAI Tool Calling 格式的工具描述"""
        return [tool.to_schema() for tool in self.tools.values()]

    def mark_evidence_collected(self) -> None:
        """标记证据已收集，解除 evidence-first 门控。"""
        self._evidence_collected = True

    def reset_turn(self, agent_id: str) -> None:
        """重置指定 agent 的每轮调用计数。"""
        self._call_counts[agent_id] = 0

    def execute(
        self,
        tool_name: str,
        arguments: dict,
        agent_id: str = "",
    ) -> str:
        """执行工具调用，经过策略检查 + MCP/直接分发。"""
        trace = current_trace()
        start_time = time.monotonic()
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "tool_name": tool_name,
            "arguments": {k: sanitize_for_llm(str(v))[:100] for k, v in (arguments or {}).items()},
        }

        # ── 策略检查 ──────────────────────────────────────────────────
        deny_reason = self._check_policy(tool_name, agent_id)
        if deny_reason:
            audit["policy_decision"] = f"denied: {deny_reason}"
            audit["dispatch_mode"] = "none"
            audit["result_status"] = "denied"
            if trace:
                trace.danger(
                    "tool", "tool_policy_denied",
                    f"[Tool] {tool_name} 被策略拒绝：{deny_reason}",
                    tool_name=tool_name, agent_id=agent_id,
                )
            logger.warning("[Tool] 策略拒绝 {} 调用 {}: {}", agent_id, tool_name, deny_reason)
            return json.dumps(
                {"status": "error", "error": f"工具调用被安全策略拒绝：{deny_reason}"},
                ensure_ascii=False,
            )

        if trace:
            trace.info(
                "tool", "tool_call_started",
                f"[Tool] 调用 {tool_name}",
                tool_name=tool_name,
                agent_id=agent_id,
                argument_keys=sorted((arguments or {}).keys()),
            )

        # ── 分发：MCP 优先，回退直接调用 ──────────────────────────────
        dispatch_mode = "direct"
        try:
            if self.mcp_client and self.mcp_client.available:
                dispatch_mode = "mcp"
                result = self.mcp_client.call_tool(tool_name, arguments or {})
            else:
                tool = self.tools.get(tool_name)
                if not tool:
                    if trace:
                        trace.danger("tool", "tool_missing", f"[Tool] 工具不存在：{tool_name}", tool_name=tool_name)
                    return json.dumps({"status": "error", "error": f"工具 {tool_name} 不存在"}, ensure_ascii=False)
                result = tool.execute(**(arguments or {}))
        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            audit["dispatch_mode"] = dispatch_mode
            audit["policy_decision"] = "allowed"
            audit["result_status"] = "error"
            audit["duration_ms"] = round(elapsed, 1)
            if trace:
                trace.danger("tool", "tool_call_failed", f"[Tool] {tool_name} 执行失败：{exc}", tool_name=tool_name)
            logger.error("[Tool] {} 执行失败 ({}): {}", tool_name, dispatch_mode, exc)
            raise

        elapsed = (time.monotonic() - start_time) * 1000
        audit["dispatch_mode"] = dispatch_mode
        audit["policy_decision"] = "allowed"
        audit["result_status"] = "success"
        audit["duration_ms"] = round(elapsed, 1)

        if trace:
            trace.success(
                "tool", "tool_call_finished",
                f"[Tool] {tool_name} 执行完成 ({dispatch_mode}, {elapsed:.0f}ms)",
                tool_name=tool_name, dispatch_mode=dispatch_mode, duration_ms=round(elapsed, 1),
            )

        logger.debug(
            "[Tool] {} 完成 agent={} mode={} {:.0f}ms",
            tool_name, agent_id or "?", dispatch_mode, elapsed,
        )
        return sanitize_for_llm(result)

    def _check_policy(self, tool_name: str, agent_id: str) -> str | None:
        """执行策略检查，返回拒绝原因或 None（允许）。"""
        policy = self.tool_policy
        if not policy:
            return None

        # 1. 工具名白名单
        allowed = getattr(policy, "allowed_tool_names", None)
        if allowed and tool_name not in allowed:
            return f"工具 {tool_name} 不在允许列表中"

        # 2. 每轮调用次数限制
        max_calls = getattr(policy, "max_tool_calls_per_turn", 0)
        if max_calls and agent_id:
            current_count = self._call_counts.get(agent_id, 0)
            if current_count >= max_calls:
                return f"超出每轮调用上限 ({max_calls})"
            self._call_counts[agent_id] = current_count + 1

        # 3. 证据优先门控
        require_evidence = getattr(policy, "require_existing_evidence_first", False)
        if require_evidence and tool_name == "text_to_sql" and not self._evidence_collected:
            return "需要先收集证据才能调用 text_to_sql"

        return None
