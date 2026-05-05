import importlib.util
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[2] / "api"
ROUTING_PATH = API_DIR / "commercial" / "ai" / "routers" / "intent_routing.py"
spec = importlib.util.spec_from_file_location("intent_routing", ROUTING_PATH)
intent_routing = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(intent_routing)

normalize_tool_intent = intent_routing.normalize_tool_intent
parse_agent_tool_plan = intent_routing.parse_agent_tool_plan


def test_model_tool_answer_routes_to_payments_tools():
    assert normalize_tool_intent("payments") == "payments"


def test_model_tool_answer_handles_short_explanation():
    assert normalize_tool_intent("Use the payments tool.") == "payments"


def test_model_none_answer_does_not_force_tool_routing():
    assert normalize_tool_intent("none") is None


def test_agent_tool_plan_parses_json_tools():
    assert parse_agent_tool_plan('{"tools":["payments"],"reason":"payment total"}') == ["payments"]


def test_agent_tool_plan_parses_multiple_tools():
    assert parse_agent_tool_plan('{"tools":["payments","expenses"],"reason":"net income"}') == ["payments", "expenses"]


def test_agent_tool_plan_empty_tools_means_no_mcp_tool():
    assert parse_agent_tool_plan('{"tools":[],"reason":"no business data"}') == []
