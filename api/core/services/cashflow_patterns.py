"""Bank statement pattern detection helpers for the cash flow service.

Pure functions that classify and group ``BankStatementTransaction`` rows into
recurring cash flow patterns. Split out of :mod:`cashflow_service` so the main
forecast pipeline isn't interleaved with the pattern-matching heuristics.
"""

import re
from datetime import date
from statistics import median
from typing import List, Optional, Tuple

from core.models.models_per_tenant import BankStatementTransaction
from core.schemas.cashflow import CashFlowReference, CashFlowThresholdSettings
from core.services.cashflow_references import bank_statement_transaction_reference

# Statement statuses whose transactions are usable for cash flow projection.
BANK_STATEMENT_READY_STATUSES = ("processed", "uploaded", "done")

# Labels that are usually scheduled household or operating bills even when the
# lookback window only contains one statement.
LIKELY_MONTHLY_BILL_KEYWORDS = (
    "mortgage",
    "mtge",
    "rent",
    "lease",
    "insurance",
    "ins",
    "hydro",
    "utility",
    "utilities",
    "electric",
    "water",
    "gas",
    "internet",
    "telecom",
    "phone",
)


def normalize_transaction_description(description: Optional[str]) -> str:
    """Collapse noisy transaction descriptions into a recurring-pattern key."""
    if not description:
        return "Bank statement transaction"

    normalized = description.lower()
    normalized = re.sub(r"\b\d{2,}\b", " ", normalized)
    normalized = re.sub(r"[^a-z\s]", " ", normalized)
    words = [
        word
        for word in normalized.split()
        if word not in {"pos", "debit", "credit", "payment", "transfer", "online"}
    ]
    if not words:
        return description.strip()[:60] or "Bank statement transaction"

    return " ".join(words[:4]).title()


def bank_statement_pattern_label(txn: BankStatementTransaction) -> str:
    """Choose a stable user-facing label for a statement transaction pattern."""
    category = (txn.category or "").strip()
    if category and category.lower() not in {"other", "uncategorized", "unknown"}:
        return category
    return normalize_transaction_description(txn.description)


def is_bank_statement_category_enabled(
    transaction_type: str,
    label: str,
    settings: CashFlowThresholdSettings,
) -> bool:
    configured = (
        settings.bank_statement_inflow_categories
        if transaction_type == "credit"
        else settings.bank_statement_outflow_categories
    )
    if not configured:
        return True
    label_lower = label.lower()
    return any(
        item_lower in label_lower or label_lower in item_lower
        for item_lower in (item.lower() for item in configured)
    )


def classify_bank_statement_interval(
    observed_days: int,
    enabled_intervals: Optional[List[int]] = None,
) -> Optional[int]:
    """Map observed transaction spacing to a conservative recurring interval."""
    enabled = set(enabled_intervals or [7, 14, 30, 90])
    if 7 in enabled and 6 <= observed_days <= 8:
        return 7
    if 14 in enabled and 12 <= observed_days <= 16:
        return 14
    if 30 in enabled and 25 <= observed_days <= 35:
        return 30
    if 90 in enabled and 85 <= observed_days <= 95:
        return 90
    return None


def build_bank_statement_pattern(
    transactions: List[BankStatementTransaction],
    settings: CashFlowThresholdSettings,
) -> Optional[Tuple[float, int, str, date, int, int, List[CashFlowReference]]]:
    """Return amount/interval metadata if transactions look recurring enough."""
    ordered = sorted(transactions, key=lambda txn: txn.date)
    unique_dates = sorted({txn.date for txn in ordered})
    if len(unique_dates) < settings.bank_statement_min_occurrences:
        return None

    intervals = [
        (unique_dates[index] - unique_dates[index - 1]).days
        for index in range(1, len(unique_dates))
        if (unique_dates[index] - unique_dates[index - 1]).days > 0
    ]
    if not intervals:
        return None

    interval_days = classify_bank_statement_interval(
        int(round(median(intervals))),
        settings.bank_statement_intervals,
    )
    if interval_days is None:
        return None

    amounts = [abs(float(txn.amount or 0.0)) for txn in ordered]
    avg_amount = sum(amounts) / len(amounts)
    if avg_amount <= 0:
        return None

    label = bank_statement_pattern_label(ordered[-1])
    references = [bank_statement_transaction_reference(txn) for txn in ordered[-5:]]
    return avg_amount, interval_days, label, unique_dates[-1], len(ordered), ordered[-1].id, references


def build_single_observation_bank_statement_pattern(
    transactions: List[BankStatementTransaction],
    settings: CashFlowThresholdSettings,
) -> Optional[Tuple[float, int, str, date, int, int, List[CashFlowReference]]]:
    """Project obvious monthly bills from a single statement observation."""
    if 30 not in set(settings.bank_statement_intervals or []):
        return None

    ordered = sorted(transactions, key=lambda txn: (txn.date, txn.id or 0))
    if not ordered:
        return None

    txn = ordered[-1]
    label = bank_statement_pattern_label(txn)
    text = f"{label} {txn.description or ''}".lower()
    if not any(keyword in text for keyword in LIKELY_MONTHLY_BILL_KEYWORDS):
        return None

    amount = abs(float(txn.amount or 0.0))
    if amount <= 0:
        return None

    references = [bank_statement_transaction_reference(txn)]
    return amount, 30, label, txn.date, 1, txn.id, references
