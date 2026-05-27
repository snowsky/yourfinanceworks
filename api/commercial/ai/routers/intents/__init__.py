# Copyright (c) 2026 YourFinanceWORKS
# This file is part of the Commercial module of YourFinanceWORKS.
"""Per-intent handlers for the AI chat dispatcher.

Importing this package populates ``intent_registry.default_registry`` with
every migrated handler. New handlers register themselves here so the import
side effect is the single source of truth.
"""

from commercial.ai.routers.intent_registry import default_registry
from commercial.ai.routers.intents import (
    analyze_patterns,
    cashflow,
    clients,
    currencies,
    expenses,
    investments,
    invoices,
    outstanding,
    overdue,
    payments,
    statements,
    statistics,
    suggest_actions,
)

for module in (
    investments,
    analyze_patterns,
    suggest_actions,
    currencies,
    outstanding,
    overdue,
    statements,
    statistics,
    payments,
    invoices,
    expenses,
    cashflow,
    clients,
):
    module.register(default_registry)

__all__ = ["default_registry"]
