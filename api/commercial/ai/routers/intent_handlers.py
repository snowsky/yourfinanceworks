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


def _requested_limit_from_options(tool_options: Optional[Dict[str, Any]], *, default: int, maximum: int = 100) -> int:
    """Read planned result limits from the agent tool plan."""
    if not tool_options or tool_options.get("limit") is None:
        return default
    try:
        return max(1, min(maximum, int(tool_options["limit"])))
    except (TypeError, ValueError):
        return default


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
    if intent == "cashflow":
        print(f"MCP Integration: Detected cashflow intent in message: '{message}'")
        try:
            from core.utils.feature_gate import feature_enabled

            if not feature_enabled("cash_flow", db):
                mcp_response = "The Cash Flow Forecasting feature is not enabled for your account. Please contact your administrator or upgrade your license to access forecasts, runway analysis, and scenario planning."
                return {
                    "success": True,
                    "data": {
                        "response": mcp_response,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }

            if "runway" in lower_message or "burn rate" in lower_message:
                result = await tools.get_cashflow_runway()
                if result.get("success"):
                    data = result.get("data", {})
                    runway_days = data.get("runway_days")
                    runway_text = "net positive" if runway_days is None else f"{runway_days} days"
                    mcp_response = f"""
💵 **Cash Runway**

• **Current Balance:** ${data.get('current_balance', 0):,.2f}
• **Average Daily Burn:** ${data.get('average_daily_burn', 0):,.2f}
• **Average Daily Income:** ${data.get('average_daily_income', 0):,.2f}
• **Net Daily Burn:** ${data.get('net_daily_burn', 0):,.2f}
• **Runway:** {runway_text}
• **Monthly Burn Rate:** ${data.get('monthly_burn_rate', 0):,.2f}
• **Monthly Income Rate:** ${data.get('monthly_income_rate', 0):,.2f}
                    """.strip()
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

            if "alert" in lower_message or "threshold" in lower_message or "low cash" in lower_message:
                result = await tools.get_cashflow_alerts()
                if result.get("success"):
                    data = result.get("data", {})
                    alerts = data.get("alerts", [])
                    alert_lines = "\n".join([f"• {alert}" for alert in alerts]) if alerts else "No cash flow alerts are active."
                    mcp_response = f"""
💵 **Cash Flow Alerts**

• **Current Balance:** ${data.get('current_balance', 0):,.2f}
• **Safety Threshold:** ${data.get('safety_threshold', 0):,.2f}
• **Warning Threshold:** ${data.get('warning_threshold', 0):,.2f}

{alert_lines}
                    """.strip()
                    return {
                        "success": True,
                        "data": {
                            "response": mcp_response,
                            "provider": ai_config.provider_name,
                            "model": ai_config.model_name,
                            "source": "mcp_tools"
                        }
                    }

            period = (
                "90d" if any(token in lower_message for token in ["90", "quarter"])
                else "7d" if "7" in lower_message or "week" in lower_message
                else "365d" if any(token in lower_message for token in ["year", "annual", "365"])
                else "30d"
            )
            result = await tools.get_cashflow_forecast(period=period)
            if result.get("success"):
                data = result.get("data", {})
                alerts = data.get("alerts", [])
                alert_lines = "\n".join([f"• {alert}" for alert in alerts]) if alerts else "No forecast alerts."
                mcp_response = f"""
💵 **Cash Flow Forecast ({data.get('period', period)})**

• **Current Balance:** ${data.get('current_balance', 0):,.2f}
• **Projected End Balance:** ${data.get('projected_end_balance', 0):,.2f}
• **Projected Inflows:** ${data.get('total_projected_inflows', 0):,.2f}
• **Projected Outflows:** ${data.get('total_projected_outflows', 0):,.2f}
• **Net Change:** ${data.get('net_change', 0):,.2f}

{alert_lines}
                """.strip()
                return {
                    "success": True,
                    "data": {
                        "response": mcp_response,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }
        except Exception as e:
            print(f"MCP Integration: Exception during cashflow tool execution: {e}")
            # Fallback

    if intent == "payments":
        print(f"MCP Integration: Detected payment pattern in message: '{message}'")
        try:
            print("MCP Integration: Querying payments with natural language...")
            result = await tools.query_payments(query=message)

            if result.get("success"):
                payments = result.get("data", [])
                date_filter_applied = result.get("date_filter_applied", False)
                date_description = result.get("date_description", "")

                if payments:
                    # Format response based on whether date filtering was applied
                    if date_filter_applied:
                        response_title = f"💰 **Payment Report {date_description}**"
                    else:
                        response_title = "💰 **Payment Information Dashboard**"

                    # Calculate total amount
                    total_amount = sum(payment.get('amount', 0) for payment in payments)

                    # Format payment details for f-string
                    payment_lines = '\n'.join([f"• **Payment #{payment.get('id', 'N/A')}**\n  📄 Invoice: #{payment.get('invoice_number', 'N/A')}\n  💰 Amount: ${payment.get('amount', 0):,.2f}\n  💳 Method: {payment.get('payment_method', 'Unknown')}\n  📅 Date: {payment.get('payment_date', 'N/A')}\n" for payment in payments])
                    mcp_response = f"""
{response_title}

📊 **📈 Payment Summary:**
• **Total Payments:** {len(payments):,}
• **Total Amount:** ${total_amount:,.2f}
• **Date Range:** {date_description if date_filter_applied else "All Time"}

💳 **💵 Payment Details:**
{payment_lines}

📋 **📊 Data Source:**
This comprehensive payment information was retrieved using your actual payment data through our advanced MCP tools.
                    """.strip()
                else:
                    if date_filter_applied:
                        mcp_response = f"No payments found {date_description}."
                    else:
                        mcp_response = "No payments found."

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

    elif intent == "clients":
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

    elif intent == "invoices":
        lower_message = message.lower()
        print(f"MCP Integration: Detected invoice pattern in message: '{message}'")
        try:
            if "search" in lower_message or "find" in lower_message:
                # Extract search query from message
                search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                if search_match:
                    search_query = search_match.group(1)
                    print(f"MCP Integration: Searching invoices with query: '{search_query}'")
                    result = await tools.search_invoices(query=search_query)
                else:
                    # Default search
                    result = await tools.list_invoices(limit=10)
            else:
                # List all invoices
                print("MCP Integration: Listing invoices...")
                result = await tools.list_invoices(limit=20)

            if result.get("success"):
                invoices = result.get("data", [])
                if invoices:
                    # Calculate totals
                    total_amount = sum(inv.get('amount', 0) for inv in invoices)
                    status_counts = {}
                    for inv in invoices:
                        status = inv.get('status', 'Unknown')
                        status_counts[status] = status_counts.get(status, 0) + 1

                    # Format status breakdown for f-string
                    status_lines = '\n'.join([f"• **{status.title()}:** {count:,}" for status, count in status_counts.items()])
                    # Format invoice details for f-string
                    invoice_lines = '\n'.join([f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n" +
                                    f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n" +
                                    f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n" +
                                    f"  📊 Status: {inv.get('status', 'Unknown').title()}\n" +
                                    f"  📅 Due: {inv.get('due_date', 'N/A')}\n" +
                                    "  -----------------------------------------\n"
                                    for inv in invoices])
                    mcp_response = f"""
📄 **Invoice Management Dashboard**

📊 **📈 Invoice Overview:**
• **Total Invoices:** {len(invoices):,}
• **Total Amount:** ${total_amount:,.2f}
• **Average Invoice Amount:** ${(total_amount / len(invoices)) if len(invoices) > 0 else 0:,.2f}

📋 **📊 Status Breakdown:**
{status_lines}

📄 **💼 Invoice Details:**
{invoice_lines}

📋 **📊 Data Source:**
This comprehensive invoice information was retrieved using your actual invoice data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No invoices found matching your query."
            else:
                # Fallback for search/list errors
                mcp_response = f"Error retrieving invoices: {result.get('error', 'Unknown error')}"

            return {
                "success": True,
                "data": {
                    "response": mcp_response,
                    "provider": ai_config.provider_name,
                    "model": ai_config.model_name,
                    "source": "mcp_tools"
                }
            }
        except Exception as e:
            print(f"MCP Integration: Exception during tool execution: {e}")
            # Fallback to LLM
            pass

    elif intent == "expenses":
        lower_message = message.lower()
        requested_limit = _requested_limit_from_options(tool_options, default=20)
        print(f"MCP Integration: Detected expense management pattern in message: '{message}'")
        try:
            if "search" in lower_message or "find" in lower_message:
                # Extract search query from message
                search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                if search_match:
                    search_query = search_match.group(1)
                    print(f"MCP Integration: Searching expenses with query: '{search_query}'")
                    result = await tools.search_expenses(query=search_query, limit=requested_limit)
                else:
                    # Default search
                    result = await tools.list_expenses(limit=min(requested_limit, 10))
            else:
                # List all expenses
                print(f"MCP Integration: Listing expenses with limit={requested_limit}...")
                result = await tools.list_expenses(limit=requested_limit)

            if result.get("success"):
                expenses = result.get("data", [])
                if expenses:
                    # Calculate totals
                    total_amount = sum(exp.get('amount', 0) or 0 for exp in expenses)
                    total_tax = sum(exp.get('tax_amount', 0) or 0 for exp in expenses)
                    total_with_tax = sum((exp.get('total_amount') or exp.get('amount', 0) or 0) for exp in expenses)

                    # Format expense details for f-string
                    expense_lines = '\n'.join([f"• **Expense #{exp.get('id', 'N/A')}**\n" +
                                    f"  📝 Category: {exp.get('category', 'Unknown')}\n" +
                                    f"  🏪 Vendor: {exp.get('vendor', 'N/A')}\n" +
                                    f"  💰 Amount: ${(exp.get('amount') or 0):,.2f}\n" +
                                    f"  📊 Tax: ${(exp.get('tax_amount') or 0):,.2f}\n" +
                                    f"  💳 Total: ${(exp.get('total_amount') or exp.get('amount') or 0):,.2f}\n" +
                                    f"  📅 Date: {exp.get('expense_date', 'N/A')}\n" +
                                    "  -----------------------------------------\n"
                                    for exp in expenses])
                    mcp_response = f"""
💸 **Expense Management Dashboard**

📊 **📈 Expense Overview:**
• **Total Expenses:** {len(expenses):,}
• **Total Amount (Pre-Tax):** ${total_amount:,.2f}
• **Total Tax:** ${total_tax:,.2f}
• **Total Amount (With Tax):** ${total_with_tax:,.2f}
• **Average Expense:** ${(total_amount / len(expenses)) if len(expenses) > 0 else 0:,.2f}

💸 **💼 Expense Details:**
{expense_lines}

📋 **📊 Data Source:**
This comprehensive expense information was retrieved using your actual expense data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No expenses found matching your query."

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
