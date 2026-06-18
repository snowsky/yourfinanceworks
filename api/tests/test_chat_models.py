from commercial.ai.routers.chat_models import ChatRequest


def test_chat_request_defaults_have_no_onboarding_fields():
    req = ChatRequest(message="hi")
    assert req.mode is None
    assert req.confirmed_action is None


def test_chat_request_accepts_onboarding_mode_and_confirmed_action():
    req = ChatRequest(
        message="create my first client",
        mode="onboarding",
        confirmed_action={"action": "create_client", "params": {"name": "Acme", "email": "ap@acme.com"}},
    )
    assert req.mode == "onboarding"
    assert req.confirmed_action["action"] == "create_client"
    assert req.confirmed_action["params"]["name"] == "Acme"
