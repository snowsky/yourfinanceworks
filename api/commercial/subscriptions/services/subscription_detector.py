"""Subscription detection service.

Scans a tenant's bank statement transactions, identifies recurring debit
patterns by wrapping ``core.services.cashflow_patterns``, and upserts
``DetectedSubscription`` rows.

State transitions trigger notifications:
- new active subscription      -> ``subscription_detected``
- existing active row whose
  amount drifts > 5%           -> ``subscription_price_changed``

User decisions (dismissed / canceled_by_user / not_a_subscription) are
preserved across re-scans by upserting keyed on ``merchant_key``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from commercial.subscriptions.models import DetectedSubscription, SubscriptionStatus
from commercial.subscriptions.services.subscription_notifications import (
    notify_price_change,
    notify_subscription_detected,
)
from core.models.models_per_tenant import BankStatementTransaction
from core.schemas.cashflow import CashFlowThresholdSettings
from core.services.cashflow_patterns import (
    BANK_STATEMENT_READY_STATUSES,
    bank_statement_pattern_label,
    build_bank_statement_pattern,
    normalize_transaction_description,
)

logger = logging.getLogger(__name__)


# Categories that look like recurring debits but aren't subscriptions users
# would consider "cancellable". Compared case-insensitively against the
# transaction's category and normalized label.
EXCLUDED_CATEGORY_KEYWORDS = (
    "rent",
    "mortgage",
    "payroll",
    "salary",
    "income",
    "transfer",
    "loan payment",
    "tax",
    "refund",
)

# Default lookback covers slightly over a year so quarterly cadences land
# inside the window even if the most recent charge is near the boundary.
DEFAULT_LOOKBACK_DAYS = 365

# Above this fractional drift between the new median and stored amount we
# emit a price-change notification. Below it we silently update.
PRICE_CHANGE_THRESHOLD = 0.05


@dataclass
class ScanResult:
    """Summary of a detector run, returned to API callers."""

    scanned_transactions: int = 0
    candidate_groups: int = 0
    new_subscriptions: int = 0
    updated_subscriptions: int = 0
    price_changed_subscriptions: int = 0
    skipped_excluded: int = 0
    new_subscription_ids: List[int] = field(default_factory=list)
    price_changed_subscription_ids: List[int] = field(default_factory=list)


def scan_tenant(
    db: Session,
    *,
    user_id: Optional[int] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    settings: Optional[CashFlowThresholdSettings] = None,
    emit_notifications: bool = True,
) -> ScanResult:
    """Detect recurring debits for the current tenant and persist results.

    ``user_id`` is only used as the recipient for notifications; detection
    itself is tenant-wide. ``settings`` defaults to subscription-friendly
    thresholds (lookback = 365d, min 2 occurrences, all supported intervals
    enabled, no category filter).
    """
    if settings is None:
        settings = _default_settings(lookback_days)

    result = ScanResult()

    today = date.today()
    window_start = today - timedelta(days=lookback_days)
    transactions = _load_candidate_transactions(db, window_start, today)
    result.scanned_transactions = len(transactions)

    grouped = _group_by_merchant(transactions)
    result.candidate_groups = len(grouped)

    existing_by_key = _load_existing_by_merchant_key(db, list(grouped.keys()))

    for merchant_key, group in grouped.items():
        if _is_excluded(group):
            result.skipped_excluded += 1
            continue

        pattern = build_bank_statement_pattern(group, settings)
        if pattern is None:
            continue

        avg_amount, interval_days, label, last_date, sample_count, _last_id, _refs = pattern

        existing = existing_by_key.get(merchant_key)
        if existing is None:
            new_sub = _create_subscription(
                db,
                merchant_key=merchant_key,
                label=label,
                amount=avg_amount,
                cadence_days=interval_days,
                sample=group,
                last_date=last_date,
            )
            db.flush()
            result.new_subscriptions += 1
            result.new_subscription_ids.append(new_sub.id)
            if emit_notifications and user_id is not None:
                notify_subscription_detected(db, user_id=user_id, subscription=new_sub)
            continue

        # Don't resurrect a row the user has dismissed or marked
        # not_a_subscription. We still update charge_count / last_seen so
        # the user can see the merchant is still active.
        updated, price_changed, old_amount = _update_subscription(
            existing,
            label=label,
            amount=avg_amount,
            cadence_days=interval_days,
            sample=group,
            last_date=last_date,
        )

        if updated:
            result.updated_subscriptions += 1

        if (
            price_changed
            and existing.status == SubscriptionStatus.ACTIVE.value
        ):
            result.price_changed_subscriptions += 1
            result.price_changed_subscription_ids.append(existing.id)
            if emit_notifications and user_id is not None:
                notify_price_change(
                    db,
                    user_id=user_id,
                    subscription=existing,
                    old_amount=old_amount,
                    new_amount=avg_amount,
                )

    db.commit()
    return result


def _default_settings(lookback_days: int) -> CashFlowThresholdSettings:
    return CashFlowThresholdSettings(
        bank_statement_lookback_days=min(max(lookback_days, 30), 365),
        bank_statement_min_occurrences=2,
        bank_statement_intervals=[7, 14, 30, 90],
        bank_statement_inflow_categories=[],
        bank_statement_outflow_categories=[],
    )


def _load_candidate_transactions(
    db: Session, start: date, end: date
) -> List[BankStatementTransaction]:
    """Load debit transactions in the window, ignoring zero amounts and
    transactions whose owning statement isn't fully processed yet."""
    from core.models.models_per_tenant import BankStatement

    rows = (
        db.query(BankStatementTransaction)
        .join(BankStatement, BankStatement.id == BankStatementTransaction.statement_id)
        .filter(
            BankStatementTransaction.transaction_type == "debit",
            BankStatementTransaction.date >= start,
            BankStatementTransaction.date <= end,
            BankStatement.status.in_(BANK_STATEMENT_READY_STATUSES),
        )
        .all()
    )
    return [r for r in rows if r.amount and abs(float(r.amount)) > 0]


def _group_by_merchant(
    transactions: List[BankStatementTransaction],
) -> Dict[str, List[BankStatementTransaction]]:
    """Group transactions by normalized merchant key (description -> stable
    short string). Unlike the cashflow grouping we deliberately *don't*
    include amount in the key — we want different amounts for the same
    merchant to collapse together so we can detect price changes."""
    groups: Dict[str, List[BankStatementTransaction]] = defaultdict(list)
    for txn in transactions:
        key = normalize_transaction_description(txn.description) or "Unknown"
        groups[key].append(txn)
    return groups


def _load_existing_by_merchant_key(
    db: Session, keys: List[str]
) -> Dict[str, DetectedSubscription]:
    if not keys:
        return {}
    rows = (
        db.query(DetectedSubscription)
        .filter(DetectedSubscription.merchant_key.in_(keys))
        .all()
    )
    return {row.merchant_key: row for row in rows}


def _is_excluded(group: List[BankStatementTransaction]) -> bool:
    """Return True if this merchant looks like a non-subscription recurring
    expense (rent, payroll, transfer, etc)."""
    txn = group[-1]
    fields = [
        (txn.category or "").lower(),
        bank_statement_pattern_label(txn).lower(),
        (txn.description or "").lower(),
    ]
    return any(
        keyword in field for field in fields for keyword in EXCLUDED_CATEGORY_KEYWORDS
    )


def _create_subscription(
    db: Session,
    *,
    merchant_key: str,
    label: str,
    amount: float,
    cadence_days: int,
    sample: List[BankStatementTransaction],
    last_date: date,
) -> DetectedSubscription:
    ordered = sorted(sample, key=lambda t: t.date)
    sub = DetectedSubscription(
        merchant_key=merchant_key,
        label=label,
        category=_dominant_category(sample),
        amount=round(amount, 2),
        last_amount=round(abs(float(ordered[-1].amount or 0.0)), 2),
        cadence_days=cadence_days,
        confidence=_score_confidence(sample, cadence_days),
        first_seen_date=ordered[0].date,
        last_seen_date=last_date,
        next_expected_date=last_date + timedelta(days=cadence_days),
        charge_count=len(sample),
        status=SubscriptionStatus.ACTIVE.value,
        source_transaction_ids=[t.id for t in ordered[-10:]],
    )
    db.add(sub)
    return sub


def _update_subscription(
    sub: DetectedSubscription,
    *,
    label: str,
    amount: float,
    cadence_days: int,
    sample: List[BankStatementTransaction],
    last_date: date,
) -> Tuple[bool, bool, float]:
    """Mutate ``sub`` in place. Return (updated, price_changed, old_amount)."""
    old_amount = float(sub.amount or 0.0)
    new_amount = round(amount, 2)
    ordered = sorted(sample, key=lambda t: t.date)
    last_amount = round(abs(float(ordered[-1].amount or 0.0)), 2)

    price_changed = (
        old_amount > 0
        and abs(new_amount - old_amount) / old_amount > PRICE_CHANGE_THRESHOLD
    )

    updated = False
    if sub.last_seen_date != last_date:
        sub.last_seen_date = last_date
        sub.next_expected_date = last_date + timedelta(days=cadence_days)
        updated = True
    if sub.cadence_days != cadence_days:
        sub.cadence_days = cadence_days
        updated = True
    if sub.label != label:
        sub.label = label
        updated = True
    if sub.charge_count != len(sample):
        sub.charge_count = len(sample)
        updated = True
    if abs(new_amount - old_amount) > 0.001:
        sub.amount = new_amount
        updated = True
    if sub.last_amount != last_amount:
        sub.last_amount = last_amount
        updated = True
    if price_changed:
        sub.price_change_acknowledged = False

    new_ids = [t.id for t in ordered[-10:]]
    if sub.source_transaction_ids != new_ids:
        sub.source_transaction_ids = new_ids
        updated = True

    if updated:
        sub.confidence = _score_confidence(sample, cadence_days)

    return updated, price_changed, old_amount


def _dominant_category(sample: List[BankStatementTransaction]) -> Optional[str]:
    counts: Dict[str, int] = defaultdict(int)
    for txn in sample:
        cat = (txn.category or "").strip()
        if cat and cat.lower() not in {"other", "uncategorized", "unknown"}:
            counts[cat] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _score_confidence(
    sample: List[BankStatementTransaction], cadence_days: int
) -> float:
    """Compute a 0-1 confidence score for the detected pattern.

    Combines sample size (more charges -> higher confidence), amount
    stability (low coefficient of variation -> higher confidence) and
    interval stability (low spread in spacing -> higher confidence).
    """
    if len(sample) < 2:
        return 0.3

    amounts = [abs(float(t.amount or 0.0)) for t in sample]
    avg = sum(amounts) / len(amounts)
    amount_cv = (
        sum(abs(a - avg) for a in amounts) / (len(amounts) * avg)
        if avg > 0
        else 1.0
    )

    ordered = sorted({t.date for t in sample})
    if len(ordered) < 2:
        interval_score = 0.5
    else:
        spacings = [
            (ordered[i] - ordered[i - 1]).days for i in range(1, len(ordered))
        ]
        med = median(spacings) if spacings else cadence_days
        spread = (
            sum(abs(s - med) for s in spacings) / (len(spacings) * med)
            if med > 0
            else 1.0
        )
        interval_score = max(0.0, 1.0 - min(spread, 1.0))

    sample_score = min(len(sample) / 6.0, 1.0)
    amount_score = max(0.0, 1.0 - min(amount_cv, 1.0))

    return round(0.4 * sample_score + 0.3 * amount_score + 0.3 * interval_score, 3)


# Public helper for the auto-trigger on statement import.
def scan_after_statement_import(
    db: Session, *, user_id: Optional[int] = None
) -> ScanResult:
    """Run a scan after a bank statement has been imported.

    Catches exceptions because we don't want detection to break the
    statement-import flow.
    """
    try:
        return scan_tenant(db, user_id=user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Subscription auto-scan failed after statement import")
        return ScanResult()


# Re-export for unit tests that want to call the underlying primitives.
__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "PRICE_CHANGE_THRESHOLD",
    "ScanResult",
    "scan_after_statement_import",
    "scan_tenant",
]
