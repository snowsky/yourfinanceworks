"""
InvoiceTools package — assembled from domain mixin classes.
"""
from typing import Any, Dict, List, Optional
import json
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from ..api_client import InvoiceAPIClient
from ..auth_client import AuthenticationError
from core.schemas.client import ClientBase

from .clients import ClientToolsMixin
from .invoices import InvoiceToolsMixin
from .expenses import ExpenseToolsMixin
from .bank_statements import BankStatementToolsMixin
from .approvals import ApprovalToolsMixin
from .reporting import ReportingToolsMixin
from .search import SearchToolsMixin
from .payments import PaymentToolsMixin
from .currencies import CurrencyToolsMixin
from .settings import SettingsToolsMixin
from .ai import AIToolsMixin
from .audit import AuditToolsMixin
from .tenant import TenantToolsMixin
from .inventory import InventoryToolsMixin
from .reminders import ReminderToolsMixin
from .investments import InvestmentToolsMixin
from .communications import CommunicationsToolsMixin
from ._helpers import ToolHelpersMixin


class InvoiceTools(
    ClientToolsMixin,
    InvoiceToolsMixin,
    ExpenseToolsMixin,
    BankStatementToolsMixin,
    ApprovalToolsMixin,
    ReportingToolsMixin,
    SearchToolsMixin,
    PaymentToolsMixin,
    CurrencyToolsMixin,
    SettingsToolsMixin,
    AIToolsMixin,
    AuditToolsMixin,
    TenantToolsMixin,
    InventoryToolsMixin,
    ReminderToolsMixin,
    InvestmentToolsMixin,
    CommunicationsToolsMixin,
    ToolHelpersMixin,
):
    def __init__(self, api_client: InvoiceAPIClient):
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
