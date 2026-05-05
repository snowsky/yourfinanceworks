"""CLI bridge to the same AI Assistant MCP path used by the web UI."""

from __future__ import annotations

from typing import Any

from .api_client import InvestmentAPIClient
from .config import Profile


class CliChatAgent:
    """Sends chat messages to /ai/chat so backend MCP tools stay centralized."""

    def __init__(self, client: InvestmentAPIClient, profile: Profile):
        self.client = client
        self.profile = profile

    def handle(
        self,
        message: str,
        *,
        config_id: int = 0,
        page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.client.ai_chat(
            message,
            config_id=config_id,
            page_context=page_context,
        )
