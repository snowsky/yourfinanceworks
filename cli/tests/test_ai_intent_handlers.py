import importlib.util
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[2] / "api"
HANDLERS_PATH = API_DIR / "commercial" / "ai" / "routers" / "intent_handlers.py"
spec = importlib.util.spec_from_file_location("intent_handlers", HANDLERS_PATH)
intent_handlers = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(intent_handlers)

extract_requested_limit = intent_handlers._extract_requested_limit


def test_extract_requested_limit_from_last_numeric_phrase():
    assert extract_requested_limit("how much did I spend in last 4 expenses?", default=20) == 4


def test_extract_requested_limit_from_recent_word_phrase():
    assert extract_requested_limit("show recent four expenses", default=20) == 4


def test_extract_requested_limit_uses_default_when_absent():
    assert extract_requested_limit("show expenses", default=20) == 20
