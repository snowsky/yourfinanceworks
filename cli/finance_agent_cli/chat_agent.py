"""Small conversational bridge for common YFW/MCP-style CLI operations."""

from __future__ import annotations

import json
import re
from typing import Any

from .api_client import InvestmentAPIClient
from .config import Profile


class CliChatAgent:
    """Maps plain-language requests to a narrow set of YFW API tool calls."""

    TOOL_NAMES = {"create_tenant", "get_tenant_info", "list_tenant_users", "list_portfolios"}

    def __init__(self, client: InvestmentAPIClient, profile: Profile):
        self.client = client
        self.profile = profile

    def handle(self, message: str) -> dict[str, Any]:
        tool_call = self._plan_with_llm(message) or self._plan_with_rules(message)
        if not tool_call:
            return {
                "success": False,
                "error": "I can handle create organization, tenant info, list tenant users, and list portfolios right now.",
            }
        return self._execute(tool_call["tool"], tool_call.get("args") or {})

    def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool == "create_tenant":
            required = {"name", "domain"}
            missing = sorted(required - set(args))
            if missing:
                return {"success": False, "error": f"Missing required fields: {', '.join(missing)}"}
            payload = {key: value for key, value in args.items() if value is not None}
            return {"success": True, "tool": tool, "data": self.client.create_tenant(payload)}
        if tool == "get_tenant_info":
            return {"success": True, "tool": tool, "data": self.client.get_tenant_info()}
        if tool == "list_tenant_users":
            tenant_id = int(args["tenant_id"])
            return {
                "success": True,
                "tool": tool,
                "data": self.client.list_tenant_users(
                    tenant_id,
                    skip=int(args.get("skip", 0)),
                    limit=int(args.get("limit", 100)),
                ),
            }
        if tool == "list_portfolios":
            return {"success": True, "tool": tool, "data": self.client.list_portfolios(limit=int(args.get("limit", 50)))}
        return {"success": False, "error": f"Unsupported tool: {tool}"}

    def _plan_with_rules(self, message: str) -> dict[str, Any] | None:
        text = message.strip()
        lower = text.lower()
        if "portfolio" in lower and ("list" in lower or "show" in lower):
            return {"tool": "list_portfolios", "args": {}}
        if "tenant info" in lower or "organization info" in lower or "current organization" in lower:
            return {"tool": "get_tenant_info", "args": {}}
        if "user" in lower and ("tenant" in lower or "organization" in lower):
            tenant_id = self._extract_int(lower, "tenant") or self._extract_int(lower, "organization")
            if tenant_id:
                return {"tool": "list_tenant_users", "args": {"tenant_id": tenant_id}}
        if ("create" in lower or "add" in lower) and ("organization" in lower or "tenant" in lower):
            name = self._extract_quoted(text) or self._extract_after(text, "named") or self._extract_after(text, "called")
            domain = self._extract_domain(text) or self._slug_domain(name)
            if name:
                return {"tool": "create_tenant", "args": {"name": name, "domain": domain, "company_name": name, "is_active": True}}
        return None

    def _plan_with_llm(self, message: str) -> dict[str, Any] | None:
        if not self.profile.llm_model:
            return None
        try:
            from litellm import completion
        except ImportError:
            return None

        prompt = (
            "Convert the user request into JSON with keys tool and args. "
            f"Allowed tools: {', '.join(sorted(self.TOOL_NAMES))}. "
            "For create_tenant, args require name and domain and may include company_name, is_active, max_users, subscription_plan. "
            "Return only JSON. If no tool fits, return null.\n\n"
            f"User: {message}"
        )
        kwargs = {
            "model": self._model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0,
        }
        if self.profile.llm_api_key:
            kwargs["api_key"] = self.profile.llm_api_key
        if self.profile.llm_base_url:
            kwargs["api_base"] = self.profile.llm_base_url

        response = completion(**kwargs)
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.removeprefix("json").strip()
        if content == "null":
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict) or payload.get("tool") not in self.TOOL_NAMES:
            return None
        return payload

    def _model_name(self) -> str:
        provider = (self.profile.llm_provider or "").strip().lower()
        model = str(self.profile.llm_model)
        if not provider or provider == "openai" or "/" in model:
            return model
        return f"{provider}/{model}"

    def _extract_int(self, text: str, label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\s+#?(\d+)|#?(\d+)\s+{re.escape(label)}", text)
        if not match:
            return None
        return int(next(group for group in match.groups() if group))

    def _extract_quoted(self, text: str) -> str | None:
        match = re.search(r"['\"]([^'\"]+)['\"]", text)
        return match.group(1).strip() if match else None

    def _extract_after(self, text: str, marker: str) -> str | None:
        match = re.search(rf"\b{re.escape(marker)}\s+(.+?)(?:\s+with\s+domain|\s+domain|$)", text, re.IGNORECASE)
        return match.group(1).strip(" .") if match else None

    def _extract_domain(self, text: str) -> str | None:
        match = re.search(r"\bdomain\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        return match.group(1).lower() if match else None

    def _slug_domain(self, name: str | None) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "organization").lower()).strip("-")
        return f"{slug or 'organization'}.local"
