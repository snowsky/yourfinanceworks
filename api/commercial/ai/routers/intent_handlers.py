# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
# This code is NOT licensed under AGPLv3.
# Usage requires a valid YourFinanceWORKS Commercial License.
# See LICENSE-COMMERCIAL.txt for details.

import logging
import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def dispatch_intent(
    intent: str,
    tools: Any,
    message: str,
    lower_message: str,
    ai_config: Any,
    page_context: Optional[Dict[str, Any]],
    db: Session,
    tool_options: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    # First, consult the intent registry. Handlers migrated to the registry
    # return their MCP envelope here (or None if the handler errored).
    # Unmigrated intents fall through to the legacy if/elif chain below.
    from commercial.ai.routers.intent_registry import IntentContext
    from commercial.ai.routers.intents import default_registry

    ctx = IntentContext(
        intent=intent,
        message=message,
        lower_message=lower_message,
        tools=tools,
        ai_config=ai_config,
        page_context=page_context,
        db=db,
        tool_options=tool_options,
    )
    registry_result = await default_registry.dispatch(ctx)
    if registry_result is not None:
        return registry_result
    if default_registry.is_registered(intent):
        # Handler ran but returned None (tool failure or exception). Don't
        # fall through to a legacy branch for the same intent.
        return None

    # Legacy: intents not yet migrated to the registry
    if intent == "clients":
        lower_message = message.lower()
        is_count_request = any(token in lower_message for token in ["how many", "count", "total number", "number of"])
        print(f"MCP Integration: Detected client management pattern in message: '{message}'")
        print(f"MCP Integration: lower_message: '{lower_message}'")
        print(f"MCP Integration: Checking patterns: {[phrase for phrase in ['client', 'customer', 'list clients', 'search client', 'find client', 'show clients', 'get clients'] if phrase in lower_message]}")
        try:
            if "create" in lower_message or "add" in lower_message or "new" in lower_message:
                # Client creation intent
                print(f"MCP Integration: Detected client creation intent in message: '{message}'")

                # Extract client details using regex
                # Extract name (required)
                # Patterns: "create client named X", "create client X", "add client X", "new client X"
                name = None
                name_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+(?:named\s+|called\s+)?["\']?([^"\',]+)["\']?', lower_message, re.IGNORECASE)
                if name_match:
                    name = name_match.group(1).strip()
                else:
                    # Fallback: try to find a name after "client" if no quotes
                    simple_match = re.search(r'(?:create|add|new)\s+(?:a\s+)?client\s+([a-zA-Z0-9\s]+?)(?:\s+with|\s*$)', lower_message, re.IGNORECASE)
                    if simple_match:
                        name = simple_match.group(1).strip()

                # Extract email (optional)
                email = None
                email_match = re.search(r'email\s+["\']?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)["\']?', lower_message, re.IGNORECASE)
                if email_match:
                    email = email_match.group(1)

                # Extract phone (optional)
                phone = None
                phone_match = re.search(r'phone\s+["\']?([0-9+\-\s()]{7,})["\']?', lower_message, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(1)

                if name:
                    print(f"MCP Integration: Creating client: name='{name}', email='{email}', phone='{phone}'")
                    result = await tools.create_client(name=name, email=email, phone=phone)

                    if result.get("success"):
                        client = result.get("data", {})
                        mcp_response = f"""
✅ **Client Created Successfully**

👤 **Client Details:**
• **Name:** {client.get('name', name)}
• **ID:** {client.get('id', 'N/A')}
{f"• **Email:** {client.get('email')}" if client.get('email') else ""}
{f"• **Phone:** {client.get('phone')}" if client.get('phone') else ""}

You can now create invoices for this client.
                        """.strip()
                    else:
                        mcp_response = f"Failed to create client: {result.get('error', 'Unknown error')}"
                else:
                    mcp_response = "I understood you want to create a client, but I couldn't extract the client name. Please specify the name, e.g., 'Create a client named John Doe'."

            elif "search" in lower_message or "find" in lower_message:
                # Extract search query from message
                search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                if search_match:
                    search_query = search_match.group(1)
                    print(f"MCP Integration: Searching clients with query: '{search_query}'")
                    result = await tools.search_clients(query=search_query)
                else:
                    # Default search
                    result = await tools.list_clients(limit=10)
            else:
                # List all clients
                print("MCP Integration: Listing clients...")
                try:
                    result = await tools.list_clients(limit=1000 if is_count_request else 20)
                    print(f"MCP Integration: list_clients result: {result}")
                except Exception as e:
                    print(f"MCP Integration: Error calling list_clients: {e}")
                    result = {"success": False, "error": str(e)}

            if "create" not in lower_message and "add" not in lower_message and "new" not in lower_message:
                # Only process list/search results here, creation is handled above
                if result.get("success"):
                    clients = result.get("data", [])
                    if clients:
                        if is_count_request:
                            mcp_response = f"You have **{len(clients)} client{'s' if len(clients) != 1 else ''}** managed in YourFinanceWORKS."
                            return {
                                "success": True,
                                "data": {
                                    "response": mcp_response,
                                    "provider": ai_config.provider_name,
                                    "model": ai_config.model_name,
                                    "source": "mcp_tools"
                                }
                            }

                        # Calculate total outstanding balance
                        total_balance = sum(client.get('outstanding_balance', 0) for client in clients)

                        # Format client details for f-string
                        client_lines = '\n'.join([f"• **{client.get('name', 'Unknown')}** (ID: {client.get('id', 'N/A')})\n" +
                                        (f"  📧 Email: {client.get('email', 'N/A')}\n" if client.get('email') else "") +
                                        (f"  📞 Phone: {client.get('phone', 'N/A')}\n" if client.get('phone') else "") +
                                        (f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n" if client.get('outstanding_balance') else "") +
                                        "  -----------------------------------------\n"
                                        for client in clients])
                        mcp_response = f"""
👥 **Client Management Dashboard**

📊 **📈 Client Overview:**
• **Total Clients:** {len(clients):,}
• **Total Outstanding Balance:** ${total_balance:,.2f}
• **Average Balance per Client:** ${(total_balance / len(clients)) if len(clients) > 0 else 0:,.2f}

👤 **💼 Client Details:**
{client_lines}

📋 **📊 Data Source:**
This comprehensive client information was retrieved using your actual client data through our advanced MCP tools.
                        """.strip()
                    else:
                        mcp_response = "No clients found matching your query."
                else:
                    # Fallback for search/list errors
                    mcp_response = f"Error retrieving clients: {result.get('error', 'Unknown error')}"

                return {
                    "success": True,
                    "data": {
                        "response": mcp_response,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }
            else:
                print(f"MCP Integration: Tool execution failed: {result}")
                # Fallback to LLM if MCP fails
                pass
        except Exception as e:
            print(f"MCP Integration: Exception during tool execution: {e}")
            # Fallback to LLM
            pass

    # For general queries or unmatched intents, use the regular LLM
    else:
        print(f"MCP Integration: Intent '{intent}' - falling back to LLM")

    return None
