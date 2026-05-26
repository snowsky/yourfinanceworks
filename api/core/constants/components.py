"""Catalog of components that support per-user permission grants.

The tenant role on `User.role` is the ceiling. Grants only restrict further;
they cannot elevate a user above their role.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ComponentDefinition:
    key: str
    label: str
    category: str  # core_financial | secondary | plugins | admin
    description: str


COMPONENTS: Tuple[ComponentDefinition, ...] = (
    # Core financial CRUD
    ComponentDefinition(
        "invoices",
        "Invoices",
        "core_financial",
        "Create and manage customer invoices",
    ),
    ComponentDefinition(
        "expenses",
        "Expenses",
        "core_financial",
        "Track business expenses",
    ),
    ComponentDefinition(
        "customers",
        "Customers",
        "core_financial",
        "Customer / client records",
    ),
    ComponentDefinition(
        "vendors",
        "Vendors",
        "core_financial",
        "Vendor records",
    ),
    # Secondary financial views
    ComponentDefinition(
        "bank_statements",
        "Bank Statements",
        "secondary",
        "Bank statement import & reconciliation",
    ),
    ComponentDefinition(
        "subscriptions",
        "Subscriptions",
        "secondary",
        "Recurring subscription tracking",
    ),
    ComponentDefinition(
        "net_worth",
        "Net Worth",
        "secondary",
        "Personal and commercial net worth",
    ),
    ComponentDefinition(
        "reports",
        "Reports",
        "secondary",
        "Financial reports and dashboards",
    ),
    # Plugins
    ComponentDefinition(
        "plugin_currency_rates",
        "Currency Rates Plugin",
        "plugins",
        "Currency rates plugin",
    ),
    ComponentDefinition(
        "plugin_investments",
        "Investments Plugin",
        "plugins",
        "Investments plugin",
    ),
    ComponentDefinition(
        "plugin_time_tracking",
        "Time Tracking Plugin",
        "plugins",
        "Time tracking plugin",
    ),
    # Admin areas
    ComponentDefinition(
        "users",
        "Users",
        "admin",
        "User management",
    ),
    ComponentDefinition(
        "settings",
        "Settings",
        "admin",
        "Tenant settings",
    ),
    ComponentDefinition(
        "integrations",
        "Integrations",
        "admin",
        "Third-party integrations",
    ),
    ComponentDefinition(
        "audit_log",
        "Audit Log",
        "admin",
        "Audit log access",
    ),
)


COMPONENT_KEYS = frozenset(c.key for c in COMPONENTS)

PERMISSION_LEVELS: Tuple[str, ...] = ("viewer", "user", "admin")

_LEVEL_RANK = {"viewer": 1, "user": 2, "admin": 3}


def level_rank(level: str) -> int:
    """Return ordinal rank for a permission level (viewer=1 < user=2 < admin=3).

    Unknown levels return 0 so any real level outranks them.
    """
    return _LEVEL_RANK.get(level, 0)


def is_valid_component(component: str) -> bool:
    return component in COMPONENT_KEYS


def is_valid_level(level: str) -> bool:
    return level in PERMISSION_LEVELS
