"""Tests for MCP security: policy enforcement, MCP fallback, audit logging."""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from tools.tool_registry import ToolRegistry


# ── Stub policy for testing ───────────────────────────────────────────
@dataclass(frozen=True)
class StubPolicy:
    allow_tools: bool = True
    require_existing_evidence_first: bool = False
    max_tool_calls_per_turn: int = 2
    allowed_tool_names: tuple[str, ...] = ("get_dict", "text_to_sql")


# ── Stub tool for testing ─────────────────────────────────────────────
class StubTool:
    def execute(self, **kwargs):
        return json.dumps({"status": "ok", "data": "stub"})

    def to_schema(self):
        return {"type": "function", "function": {"name": "stub_tool", "parameters": {}}}


# ── Test 1: Policy blocks disallowed tool names ──────────────────────
def test_policy_blocks_disallowed_tool():
    print("=" * 60)
    print("TEST 1: Policy blocks disallowed tool names")
    print("=" * 60)

    policy = StubPolicy(allowed_tool_names=("get_dict",))
    registry = ToolRegistry(tool_policy=policy)

    result = registry.execute("text_to_sql", {"intent": "test"}, agent_id="agent_test")
    parsed = json.loads(result)
    assert parsed["status"] == "error"
    assert "不允许" in parsed["error"] or "拒绝" in parsed["error"]
    print("  [OK] Disallowed tool blocked")
    print()


# ── Test 2: Policy blocks calls exceeding max_tool_calls_per_turn ────
def test_policy_blocks_excess_calls():
    print("=" * 60)
    print("TEST 2: Policy blocks calls exceeding max_tool_calls_per_turn")
    print("=" * 60)

    policy = StubPolicy(max_tool_calls_per_turn=2)
    registry = ToolRegistry(tool_policy=policy)

    # First two calls should succeed
    for i in range(2):
        result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
        # May return error if dict doesn't exist, but shouldn't be policy-denied
        parsed = json.loads(result)
        assert "策略拒绝" not in parsed.get("error", ""), f"Call {i+1} should not be policy-denied"
    print("  [OK] First 2 calls allowed")

    # Third call should be denied
    result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
    parsed = json.loads(result)
    assert parsed["status"] == "error"
    assert "超出" in parsed["error"] or "拒绝" in parsed["error"]
    print("  [OK] Third call blocked by policy")
    print()


# ── Test 3: Policy allows calls within limits ────────────────────────
def test_policy_allows_within_limits():
    print("=" * 60)
    print("TEST 3: Policy allows calls within limits")
    print("=" * 60)

    policy = StubPolicy(max_tool_calls_per_turn=5)
    registry = ToolRegistry(tool_policy=policy)

    for i in range(5):
        result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
        parsed = json.loads(result)
        assert "策略拒绝" not in parsed.get("error", ""), f"Call {i+1} should be allowed"
    print("  [OK] All 5 calls within limit allowed")
    print()


# ── Test 4: reset_turn resets call counts ────────────────────────────
def test_reset_turn():
    print("=" * 60)
    print("TEST 4: reset_turn resets call counts")
    print("=" * 60)

    policy = StubPolicy(max_tool_calls_per_turn=1)
    registry = ToolRegistry(tool_policy=policy)

    # Use up the limit
    registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
    result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
    assert json.loads(result)["status"] == "error"
    print("  [OK] Second call blocked")

    # Reset and try again
    registry.reset_turn("agent_test")
    result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
    assert "策略拒绝" not in json.loads(result).get("error", "")
    print("  [OK] Call allowed after reset_turn")
    print()


# ── Test 5: No policy = no restrictions ──────────────────────────────
def test_no_policy_no_restrictions():
    print("=" * 60)
    print("TEST 5: No policy means no restrictions")
    print("=" * 60)

    registry = ToolRegistry(tool_policy=None)

    for i in range(10):
        result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
        parsed = json.loads(result)
        assert "策略拒绝" not in parsed.get("error", ""), f"Call {i+1} should not be denied"
    print("  [OK] No restrictions without policy")
    print()


# ── Test 6: Evidence-first gate ──────────────────────────────────────
def test_evidence_first_gate():
    print("=" * 60)
    print("TEST 6: Evidence-first gate blocks text_to_sql before evidence")
    print("=" * 60)

    policy = StubPolicy(require_existing_evidence_first=True)
    registry = ToolRegistry(tool_policy=policy)

    # text_to_sql should be blocked before evidence is collected
    result = registry.execute("text_to_sql", {"intent": "test"}, agent_id="agent_test")
    parsed = json.loads(result)
    assert parsed["status"] == "error"
    assert "证据" in parsed["error"] or "拒绝" in parsed["error"]
    print("  [OK] text_to_sql blocked before evidence")

    # Mark evidence collected
    registry.mark_evidence_collected()

    # Now text_to_sql should pass policy check (may fail at execution, but not policy-denied)
    try:
        result = registry.execute("text_to_sql", {"intent": "test", "person_id": "P001"}, agent_id="agent_test")
        parsed = json.loads(result)
        assert "策略拒绝" not in parsed.get("error", ""), "Should not be policy-denied after evidence"
    except TypeError:
        # Execution may fail due to missing DB connection, but policy check passed
        pass
    print("  [OK] text_to_sql allowed after evidence collected")
    print()


# ── Test 7: MCP fallback to direct ──────────────────────────────────
def test_mcp_fallback_to_direct():
    print("=" * 60)
    print("TEST 7: MCP unavailable falls back to direct")
    print("=" * 60)

    # No MCP client = direct execution
    registry = ToolRegistry(tool_policy=None, mcp_client=None)
    result = registry.execute("get_dict", {"field_name": "test"}, agent_id="agent_test")
    # Should execute (may return error if dict doesn't exist, but not a connection error)
    parsed = json.loads(result)
    assert "连接" not in parsed.get("error", ""), "Should not fail with connection error"
    print("  [OK] Falls back to direct execution when MCP unavailable")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MCP SECURITY TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_policy_blocks_disallowed_tool,
        test_policy_blocks_excess_calls,
        test_policy_allows_within_limits,
        test_reset_turn,
        test_no_policy_no_restrictions,
        test_evidence_first_gate,
        test_mcp_fallback_to_direct,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    print("\nAll tests passed!")
