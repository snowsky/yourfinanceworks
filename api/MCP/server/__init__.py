"""MCP server package.

Split from the original monolithic server.py (2,450 lines) into focused modules:
  - _shared.py      — ServerContext, FastMCP instance, lifespan, argument parsing, main/main_sync
  - clients.py      — Client Management tools (list, search, get, create)
  - invoices.py     — Invoice Management + Analytics tools
  - currencies.py   — Currency Management tools
  - payments.py     — Payment Management tools
  - inventory.py    — Inventory: categories, items, stock, analytics, import/export,
                      barcode, integration, bulk ops, search, attachments
  - bank_statements.py — Bank Statement Management tools
  - cashflow.py    — Cash flow forecast, runway, scenarios, alerts, settings
  - expenses.py     — Expense Management tools
  - statements.py   — Statement view/update + recycle bin, approval workflow,
                      report generation, advanced search, enhanced reports
  - settings.py     — Settings, discount rules, CRM, email, tenant, AI config tools
  - audit.py        — Page-view analytics, audit logs, notifications
  - documents.py    — PDF processing + accounting/tax export tools
  - super_admin.py  — Super Admin (tenants, users, system stats) tools
  - investments.py  — Investment portfolio tools
"""

# Import all domain modules to trigger @mcp.tool() registrations
from . import (
    audit,
    bank_statements,
    cashflow,
    clients,
    currencies,
    documents,
    expenses,
    inventory,
    investments,
    invoices,
    payments,
    settings,
    statements,
    super_admin,
)

# Re-export the public surface consumed by __main__.py and external callers
from ._shared import main, main_sync, mcp

__all__ = ["mcp", "main", "main_sync"]
