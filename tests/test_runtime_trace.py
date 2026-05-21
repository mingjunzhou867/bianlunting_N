"""Tests for structured runtime trace helpers."""
from __future__ import annotations

import unittest

from runtime.trace import TraceContext, current_trace, use_trace
from tools.tool_registry import ToolRegistry


class DummyTool:
    def to_schema(self) -> dict:
        return {"type": "function", "function": {"name": "dummy"}}

    def execute(self, value: str) -> str:
        return f"ok:{value}"


class RuntimeTraceTests(unittest.TestCase):
    def test_trace_context_keeps_ordered_events(self) -> None:
        trace = TraceContext("session-1", "42090219760310000D", "POLICY_001")

        trace.info("session", "start", "started")
        trace.success("session", "done", "finished")

        events = trace.to_list()
        self.assertEqual([event["event_id"] for event in events], ["trace_0001", "trace_0002"])
        self.assertEqual(events[0]["stage"], "session")
        self.assertEqual(events[1]["status"], "success")
        self.assertEqual(events[1]["policy_id"], "POLICY_001")

    def test_use_trace_scopes_current_trace(self) -> None:
        trace = TraceContext("session-1", "42090219760310000D", "POLICY_001")

        self.assertIsNone(current_trace())
        with use_trace(trace):
            self.assertIs(current_trace(), trace)
        self.assertIsNone(current_trace())

    def test_tool_registry_appends_tool_trace_events(self) -> None:
        trace = TraceContext("session-1", "42090219760310000D", "POLICY_001")
        registry = ToolRegistry()
        registry.tools = {"dummy": DummyTool()}

        with use_trace(trace):
            result = registry.execute("dummy", {"value": "x"})

        self.assertEqual(result, "ok:x")
        events = trace.to_list()
        self.assertEqual([event["action"] for event in events], ["tool_call_started", "tool_call_finished"])
        self.assertEqual(events[0]["payload"]["tool_name"], "dummy")


if __name__ == "__main__":
    unittest.main()
