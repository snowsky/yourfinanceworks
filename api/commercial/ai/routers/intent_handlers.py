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
) -> Optional[Dict[str, Any]]:
    # Execute MCP tool based on AI-classified intent
    if intent == "investments":
        print(f"MCP Integration: Detected investments intent in message: '{message}'")
        try:
            # 1. Check Feature license
            from core.utils.feature_gate import feature_enabled
            if not feature_enabled("investments", db):
                mcp_response = "The Investment Management feature is not enabled for your account. Please contact your administrator or upgrade your license to access your investment data."
                return {
                    "success": True,
                    "data": {
                        "response": mcp_response,
                        "provider": ai_config.provider_name,
                        "model": ai_config.model_name,
                        "source": "mcp_tools"
                    }
                }

            # 2. List Portfolios
            print("MCP Integration: Listing portfolios...")
            result = await tools.list_portfolios()

            if result.get("success"):
                portfolios = result.get("data", [])
                if portfolios:
                    # If the user mentioned a specific portfolio name, we could try to get its summary
                    # For now, let's show the summary of all portfolios
                    portfolio_lines = []
                    total_market_value = 0

                    for p in portfolios:
                        val = p.get('total_value', 0)
                        total_market_value += val
                        perf = p.get('return_percentage', 0)
                        perf_str = f"{perf:+.2f}%" if perf != 0 else "0.00%"

                        line = (f"• **{p.get('name', 'Unnamed Portfolio')}** ({p.get('type', 'Unknown')})\n"
                               f"  💰 Value: ${val:,.2f} | 📈 Return: {perf_str}\n"
                               f"  📊 Holdings: {p.get('holdings_count', 0)}")
                        portfolio_lines.append(line)

                    portfolio_display = "\n".join(portfolio_lines)

                    mcp_response = f"""
📈 **Investment Portfolio Overview**

📊 **Business Summary:**
• **Total Portfolios:** {len(portfolios)}
• **Total Market Value:** ${total_market_value:,.2f}

💼 **Individual Portfolios:**
{portfolio_display}

📋 **Data Source:**
This information was retrieved from your investment management plugin via advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "You don't have any investment portfolios set up yet."

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
                # Fallback
        except Exception as e:
            print(f"MCP Integration: Exception during investments tool execution: {e}")
            # Fallback

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

    if intent == "analyze_patterns":
        print(f"MCP Integration: Detected analyze pattern in message: '{message}'")
        try:
            # Execute MCP tool directly
            print("MCP Integration: Executing analyze_invoice_patterns...")
            result = await tools.analyze_invoice_patterns()
            print(f"MCP Integration: Result: {result}")

            if result.get("success"):
                data = result.get("data", {})

                # Format revenue by currency for better display
                def format_revenue_by_currency(revenue_data):
                    if not revenue_data or not isinstance(revenue_data, dict):
                        return "None"
                    return ", ".join([f"{currency} ${amount:,.2f}" for currency, amount in revenue_data.items()])

                # Format recommendations for f-string
                recommendations_lines = '\n'.join([f"• {rec}" for rec in data.get('recommendations', [])])
                mcp_response = f"""
🎯 **Invoice Pattern Analysis Report**

📊 **📈 Business Overview:**
• **Total Invoices:** {data.get('total_invoices', 0):,}
• **Paid Invoices:** {data.get('paid_invoices', 0):,} ✅
• **Partially Paid:** {data.get('partially_paid_invoices', 0):,} ⚠️
• **Unpaid Invoices:** {data.get('unpaid_invoices', 0):,} ❌
• **Overdue Invoices:** {data.get('overdue_invoices', 0):,} 🚨

💰 **💵 Financial Summary:**
• **Total Revenue:** {format_revenue_by_currency(data.get('total_revenue_by_currency', {}))}
• **Outstanding Revenue:** {format_revenue_by_currency(data.get('outstanding_revenue_by_currency', {}))}

💡 **🎯 Strategic Recommendations:**
{recommendations_lines}

📋 **📊 Analysis Details:**
This comprehensive analysis was performed using your actual invoice data through our advanced MCP tools, providing real-time insights into your business performance and cash flow patterns.
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
            else:
                print(f"MCP Integration: Tool execution failed: {result}")
                # Fallback to LLM if MCP fails
                pass
        except Exception as e:
            print(f"MCP Integration: Exception during tool execution: {e}")
            # Fallback to LLM
            pass

    elif intent == "suggest_actions":
        print(f"MCP Integration: Detected suggest pattern in message: '{message}'")
        try:
            # Execute MCP tool directly
            print("MCP Integration: Executing suggest_invoice_actions...")
            result = await tools.suggest_invoice_actions()
            print(f"MCP Integration: Result: {result}")

            if result.get("success"):
                data = result.get("data", {})
                actions = data.get("suggested_actions", [])

                # Helper function to get priority emoji
                def get_priority_emoji(priority):
                    # Ensure priority is a string
                    if not isinstance(priority, str):
                        priority = str(priority)
                    return {
                        'high': '🔴',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(priority.lower(), '⚪')

                # Format actions for f-string
                actions_lines = '\n'.join([f"• {get_priority_emoji(action.get('priority', 'medium'))} **{action.get('action', 'Unknown').replace('_', ' ').title()}**\n  📝 {action.get('description', 'No description')}\n  🏷️ Priority: {action.get('priority', 'medium').title()}\n" for action in actions])
                mcp_response = f"""
🎯 **Strategic Action Plan**

🚀 **🎯 Priority Actions:**
{actions_lines}

📊 **📈 Quick Metrics:**
• **Overdue Invoices:** {data.get('overdue_count', 0):,} 🚨
• **Clients with Balance:** {data.get('clients_with_balance', 0):,} 💰
• **Recent Invoices:** {data.get('recent_invoices_count', 0):,} 📄

💡 **💼 Action Insights:**
These strategic recommendations are based on your actual invoice data and business patterns, designed to optimize your cash flow and improve client relationships.
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
            else:
                print(f"MCP Integration: Tool execution failed: {result}")
                # Fallback to LLM if MCP fails
                pass
        except Exception as e:
            print(f"MCP Integration: Exception during tool execution: {e}")
            # Fallback to LLM
            pass

    elif intent == "payments":
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
                    result = await tools.list_clients(limit=20)
                    print(f"MCP Integration: list_clients result: {result}")
                except Exception as e:
                    print(f"MCP Integration: Error calling list_clients: {e}")
                    result = {"success": False, "error": str(e)}

            if "create" not in lower_message and "add" not in lower_message and "new" not in lower_message:
                # Only process list/search results here, creation is handled above
                if result.get("success"):
                    clients = result.get("data", [])
                    if clients:
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

    elif intent == "currencies":
        print(f"MCP Integration: Detected currency pattern in message: '{message}'")
        try:
            print("MCP Integration: Listing currencies...")
            result = await tools.list_currencies(active_only=True)

            if result.get("success"):
                currencies = result.get("data", [])
                if currencies:
                    # Format currency details for f-string
                    currency_lines = '\n'.join([f"• **{currency.get('code', 'N/A')}** ({currency.get('symbol', '')})\n" +
                                    f"  📝 Name: {currency.get('name', 'Unknown')}\n" +
                                    f"  📊 Status: {'Active' if currency.get('is_active', True) else 'Inactive'}\n" +
                                    "  -----------------------------------------\n"
                                    for currency in currencies])
                    mcp_response = f"""
💱 **Currency Management Dashboard**

📊 **📈 Currency Overview:**
• **Active Currencies:** {len(currencies):,}
• **Supported Currencies:** {len(currencies):,}

💱 **💵 Currency Details:**
{currency_lines}

📋 **📊 Data Source:**
This comprehensive currency information was retrieved using your actual currency data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No active currencies found."

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

    elif intent == "outstanding":
        print(f"MCP Integration: Detected outstanding balance pattern in message: '{message}'")
        try:
            print("MCP Integration: Getting clients with outstanding balance...")
            result = await tools.get_clients_with_outstanding_balance()

            if result.get("success"):
                clients = result.get("data", [])
                if clients:
                    # Calculate total outstanding balance
                    total_outstanding = sum(client.get('outstanding_balance', 0) for client in clients)

                    # Format outstanding details for f-string
                    outstanding_lines = '\n'.join([f"• **{client.get('name', 'Unknown')}**\n" +
                                    f"  💰 Outstanding Balance: ${client.get('outstanding_balance', 0):,.2f}\n" +
                                    f"  📧 Email: {client.get('email', 'N/A')}\n" +
                                    f"  📞 Phone: {client.get('phone', 'N/A')}\n" +
                                    "  -----------------------------------------\n"
                                    for client in clients])
                    mcp_response = f"""
⚠️ **Outstanding Balance Report**

📊 **📈 Outstanding Overview:**
• **Clients with Balances:** {len(clients):,}
• **Total Outstanding Amount:** ${total_outstanding:,.2f}
• **Average Outstanding per Client:** ${(total_outstanding / len(clients)) if len(clients) > 0 else 0:,.2f}

💰 **💵 Outstanding Details:**
{outstanding_lines}

📋 **📊 Data Source:**
This comprehensive outstanding balance information was retrieved using your actual client data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No clients with outstanding balances found."

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

    elif intent == "overdue":
        print(f"MCP Integration: Detected overdue invoice pattern in message: '{message}'")
        try:
            print("MCP Integration: Getting overdue invoices...")
            result = await tools.get_overdue_invoices()

            if result.get("success"):
                invoices = result.get("data", [])
                if invoices:
                    # Calculate total overdue amount
                    total_overdue = sum(inv.get('amount', 0) for inv in invoices)
                    avg_days_overdue = sum(inv.get('days_overdue', 0) for inv in invoices) / len(invoices) if invoices else 0

                    # Format overdue details for f-string
                    overdue_lines = '\n'.join([f"• **Invoice #{inv.get('invoice_number', inv.get('id', 'N/A'))}**\n" +
                                    f"  👤 Client: {inv.get('client_name', 'Unknown Client')}\n" +
                                    f"  💰 Amount: ${inv.get('amount', 0):,.2f}\n" +
                                    f"  📅 Due Date: {inv.get('due_date', 'N/A')}\n" +
                                    f"  ⏰ Days Overdue: {inv.get('days_overdue', 'N/A')}\n" +
                                    "  -----------------------------------------\n"
                                    for inv in invoices])
                    mcp_response = f"""
🚨 **Overdue Invoice Alert Report**

📊 **📈 Overdue Overview:**
• **Overdue Invoices:** {len(invoices):,}
• **Total Overdue Amount:** ${total_overdue:,.2f}
• **Average Days Overdue:** {avg_days_overdue:.1f} days
• **Average Overdue Amount:** ${(total_overdue / len(invoices)) if len(invoices) > 0 else 0:,.2f}

🚨 **💸 Overdue Details:**
{overdue_lines}

📋 **📊 Data Source:**
This comprehensive overdue invoice information was retrieved using your actual invoice data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No overdue invoices found."

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
        print(f"MCP Integration: Detected expense management pattern in message: '{message}'")
        try:
            if "search" in lower_message or "find" in lower_message:
                # Extract search query from message
                search_match = re.search(r'(?:search|find)\s+(?:for\s+)?["\']?([^"\']+)["\']?', lower_message)
                if search_match:
                    search_query = search_match.group(1)
                    print(f"MCP Integration: Searching expenses with query: '{search_query}'")
                    result = await tools.search_expenses(query=search_query)
                else:
                    # Default search
                    result = await tools.list_expenses(limit=10)
            else:
                # List all expenses
                print("MCP Integration: Listing expenses...")
                result = await tools.list_expenses(limit=20)

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

    elif intent == "statements":
        print(f"MCP Integration: Detected statement pattern in message: '{message}'")
        logger.info(f"MCP Integration: Detected statement pattern in message: '{message}'")
        try:
            print("MCP Integration: Listing statements...")
            logger.info("MCP Integration: Listing statements...")
            result = await tools.list_statements()
            print(f"MCP Integration: Statements result: {result}")
            logger.info(f"MCP Integration: Statements result: {result}")

            if result.get("success"):
                statements = result.get("data", [])
                print(f"MCP Integration: Retrieved {len(statements)} statements")
                logger.info(f"MCP Integration: Retrieved {len(statements)} statements")
                if statements:
                    # Format statement details for f-string
                    statement_lines = '\n'.join([f"• **Statement #{stmt.get('id', 'N/A')}**\n" +
                                    f"  🏦 Account: {stmt.get('account_name', 'Unknown')}\n" +
                                    f"  📅 Period: {stmt.get('statement_period', 'N/A')}\n" +
                                    f"  📊 Status: {stmt.get('status', 'Unknown').title()}\n" +
                                    f"  📄 Transactions: {stmt.get('transaction_count', 'N/A')}\n" +
                                    f"  📅 Imported: {stmt.get('created_at', 'N/A')}\n" +
                                    "  -----------------------------------------\n"
                                    for stmt in statements])
                    mcp_response = f"""
🏦 **Statement Management Dashboard**

📊 **📈 Statement Overview:**
• **Total Statements:** {len(statements):,}
• **Processed Statements:** {len([s for s in statements if s.get('status') == 'processed']):,}
• **Pending Statements:** {len([s for s in statements if s.get('status') == 'pending']):,}

🏦 **💼 Statement Details:**
{statement_lines}

📋 **📊 Data Source:**
This comprehensive bank statement information was retrieved using your actual bank statement data through our advanced MCP tools.
                    """.strip()
                else:
                    mcp_response = "No bank statements found."

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

    elif intent == "statistics":
        print(f"MCP Integration: Detected statistics pattern in message: '{message}'")
        try:
            print("MCP Integration: Getting invoice statistics...")
            result = await tools.get_invoice_stats()

            if result.get("success"):
                stats = result.get("data", {})
                mcp_response = f"""
📊 **Invoice Statistics Dashboard**

📈 **📊 Business Metrics:**
• **Total Invoices:** {stats.get('total_invoices', 0):,}
• **Total Revenue:** ${stats.get('total_revenue', 0):,.2f}
• **Average Invoice Amount:** ${stats.get('average_invoice_amount', 0):,.2f}

📋 **📊 Status Breakdown:**
• **Paid Invoices:** {stats.get('paid_invoices', 0):,} ✅
• **Unpaid Invoices:** {stats.get('unpaid_invoices', 0):,} ❌
• **Overdue Invoices:** {stats.get('overdue_invoices', 0):,} 🚨

📊 **📈 Performance Insights:**
• **Payment Rate:** {((stats.get('paid_invoices', 0) / stats.get('total_invoices', 1) * 100) if stats.get('total_invoices', 0) > 0 else 0):.1f}%
• **Overdue Rate:** {((stats.get('overdue_invoices', 0) / stats.get('total_invoices', 1) * 100) if stats.get('total_invoices', 0) > 0 else 0):.1f}%

📋 **📊 Data Source:**
This comprehensive statistical analysis was performed using your actual invoice data through our advanced MCP tools.
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
