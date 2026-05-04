"""
InvoiceTools package — assembled from domain mixin classes.
"""
import logging
from ..api_client import InvoiceAPIClient

from .clients import ClientToolsMixin
from .invoices import InvoiceToolsMixin
from .expenses import ExpenseToolsMixin
from .bank_statements import BankStatementToolsMixin
from .approvals import ApprovalToolsMixin
from .reporting import ReportingToolsMixin
from .search import SearchToolsMixin
from .payments import PaymentToolsMixin
from .cashflow import CashFlowToolsMixin
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
    CashFlowToolsMixin,
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
