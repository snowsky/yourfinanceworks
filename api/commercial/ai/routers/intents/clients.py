# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""clients intent handler — create / search / list with regex-driven argument extraction.

Three sub-paths keyed off the chat message:

  * "create" / "add" / "new"  -> regex-extract name (+optional email/phone),
                                 call create_client, render a confirmation.
  * "search" / "find"         -> regex-extract a query term, call
                                 search_clients (or list_clients(limit=10)
                                 if no query was captured).
  * default                   -> list_clients with a planner-friendly page:
                                 limit=1000 for a count request,
                                 limit=20 otherwise.

Count-intent detection (``how many``, ``count``, ``total number``, ``number of``)
also switches the render path to a short "you have N clients" line instead
of the full dashboard.

A latent bug in the legacy branch caused the create-path response to never
reach the user (the post-create render gate excluded create-keyword messages
but the create branch didn't return on its own). This handler fixes that:
the create path returns its envelope directly from ``_handle_create``.
Documented in the PR that introduces this module.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from commercial.ai.routers.intent_registry import (
    IntentContext,
    IntentRegistry,
    mcp_envelope,
)
from commercial.ai.routers.intents._helpers import detect_search_intent


logger = logging.getLogger(__name__)


NO_CLIENTS_MESSAGE = "No clients found matching your query."
NAME_REQUIRED_MESSAGE = (
    "I understood you want to create a client, but I couldn't extract the "
    "client name. Please specify the name, e.g., 'Create a client named "
    "John Doe'."
)

_CREATE_KEYWORDS = ("create", "add", "new")
_COUNT_KEYWORDS = ("how many", "count", "total number", "number of")

_NAME_RE = re.compile(
    r"""(?:create|add|new)\s+(?:a\s+)?client\s+(?:named\s+|called\s+)?["']?([^"',]+)["']?""",
    re.IGNORECASE,
)
_NAME_FALLBACK_RE = re.compile(
    r"""(?:create|add|new)\s+(?:a\s+)?client\s+([a-zA-Z0-9\s]+?)(?:\s+with|\s*$)""",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(
    r"""email\s+["']?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)["']?""",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"""phone\s+["']?([0-9+\-\s()]{7,})["']?""", re.IGNORECASE)


def is_create_intent(lower_message: str) -> bool:
    return any(keyword in lower_message for keyword in _CREATE_KEYWORDS)


def is_count_intent(lower_message: str) -> bool:
    return any(keyword in lower_message for keyword in _COUNT_KEYWORDS)


def extract_create_client_args(
    lower_message: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Pull (name, email, phone) out of a 'create client ...' message."""
    name: Optional[str] = None
    match = _NAME_RE.search(lower_message)
    if match:
        name = match.group(1).strip()
    else:
        fallback = _NAME_FALLBACK_RE.search(lower_message)
        if fallback:
            name = fallback.group(1).strip()

    email_match = _EMAIL_RE.search(lower_message)
    email = email_match.group(1) if email_match else None

    phone_match = _PHONE_RE.search(lower_message)
    phone = phone_match.group(1) if phone_match else None

    return name, email, phone


class ClientsHandler:
    intent = "clients"
    license_feature: Optional[str] = None
    license_denied_message = ""

    async def execute(self, ctx: IntentContext) -> Optional[dict]:
        lower = ctx.lower_message

        if is_create_intent(lower):
            return await self._handle_create(ctx, lower)

        is_search, query = detect_search_intent(lower)
        if is_search and query:
            result = await ctx.tools.search_clients(query=query)
        elif is_search:
            result = await ctx.tools.list_clients(limit=10)
        else:
            count_request = is_count_intent(lower)
            try:
                result = await ctx.tools.list_clients(
                    limit=1000 if count_request else 20
                )
            except Exception as exc:
                logger.warning("clients list_clients raised: %s", exc)
                result = {"success": False, "error": str(exc)}
            if count_request and result.get("success"):
                clients = result.get("data") or []
                return mcp_envelope(ctx, format_count_response(len(clients)))

        if not result.get("success"):
            # Legacy behavior: don't fall back to the LLM on a list/search
            # failure; surface the underlying error in our envelope.
            return mcp_envelope(
                ctx,
                f"Error retrieving clients: {result.get('error', 'Unknown error')}",
            )

        clients = result.get("data") or []
        if not clients:
            return mcp_envelope(ctx, NO_CLIENTS_MESSAGE)
        return mcp_envelope(ctx, format_clients_response(clients))

    async def _handle_create(self, ctx: IntentContext, lower: str) -> Optional[dict]:
        name, email, phone = extract_create_client_args(lower)
        if not name:
            return mcp_envelope(ctx, NAME_REQUIRED_MESSAGE)

        result = await ctx.tools.create_client(name=name, email=email, phone=phone)
        if not result.get("success"):
            return mcp_envelope(
                ctx,
                f"Failed to create client: {result.get('error', 'Unknown error')}",
            )

        return mcp_envelope(
            ctx,
            format_create_client_response(result.get("data") or {}, fallback_name=name),
        )


def format_count_response(count: int) -> str:
    return (
        f"You have **{count} client{'s' if count != 1 else ''}** managed in YourFinanceWORKS."
    )


def format_create_client_response(client: dict[str, Any], *, fallback_name: str) -> str:
    lines = [
        "✅ **Client Created Successfully**",
        "",
        "👤 **Client Details:**",
        f"• **Name:** {client.get('name', fallback_name)}",
        f"• **ID:** {client.get('id', 'N/A')}",
    ]
    if client.get("email"):
        lines.append(f"• **Email:** {client['email']}")
    if client.get("phone"):
        lines.append(f"• **Phone:** {client['phone']}")
    lines.append("")
    lines.append("You can now create invoices for this client.")
    return "\n".join(lines)


def format_clients_response(clients: list[dict[str, Any]]) -> str:
    total = sum(client.get("outstanding_balance", 0) or 0 for client in clients)
    average = total / len(clients) if clients else 0
    detail_lines = "\n".join(
        _format_client_block(client) for client in clients
    )
    return (
        "👥 **Client Management Dashboard**\n\n"
        "📊 **📈 Client Overview:**\n"
        f"• **Total Clients:** {len(clients):,}\n"
        f"• **Total Outstanding Balance:** ${total:,.2f}\n"
        f"• **Average Balance per Client:** ${average:,.2f}\n\n"
        "👤 **💼 Client Details:**\n"
        f"{detail_lines}\n\n"
        "📋 **📊 Data Source:**\n"
        "This comprehensive client information was retrieved using your actual "
        "client data through our advanced MCP tools."
    )


def _format_client_block(client: dict[str, Any]) -> str:
    parts = [f"• **{client.get('name', 'Unknown')}** (ID: {client.get('id', 'N/A')})\n"]
    if client.get("email"):
        parts.append(f"  📧 Email: {client.get('email', 'N/A')}\n")
    if client.get("phone"):
        parts.append(f"  📞 Phone: {client.get('phone', 'N/A')}\n")
    if client.get("outstanding_balance"):
        parts.append(
            f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n"
        )
    parts.append("  -----------------------------------------\n")
    return "".join(parts)


def register(registry: IntentRegistry) -> None:
    registry.register(ClientsHandler())
