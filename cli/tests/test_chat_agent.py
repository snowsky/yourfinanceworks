from cli.finance_agent_cli.chat_agent import CliChatAgent
from cli.tests.test_api_client import _profile


class StubClient:
    def __init__(self):
        self.called = []

    def ai_chat(self, message, *, config_id=0, page_context=None):
        self.called.append(("ai_chat", message, config_id, page_context))
        return {"success": True, "data": {"response": "ok", "source": "mcp_tools"}}


def test_chat_agent_uses_ai_assistant_chat_endpoint(tmp_path):
    client = StubClient()
    result = CliChatAgent(client, _profile(tmp_path)).handle(
        "list statements",
        config_id=3,
        page_context={"route": "/statements"},
    )

    assert result["success"] is True
    assert result["data"]["source"] == "mcp_tools"
    assert client.called == [("ai_chat", "list statements", 3, {"route": "/statements"})]
