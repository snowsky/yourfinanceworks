import importlib.util
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[2] / "api"
HANDLERS_PATH = API_DIR / "commercial" / "ai" / "routers" / "intent_handlers.py"
spec = importlib.util.spec_from_file_location("intent_handlers", HANDLERS_PATH)
intent_handlers = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(intent_handlers)

requested_limit_from_options = intent_handlers._requested_limit_from_options


def test_requested_limit_reads_agent_tool_options():
    assert requested_limit_from_options({"limit": 4}, default=20) == 4


def test_requested_limit_caps_agent_tool_options():
    assert requested_limit_from_options({"limit": 500}, default=20, maximum=100) == 100


def test_requested_limit_uses_default_when_absent():
    assert requested_limit_from_options({}, default=20) == 20
