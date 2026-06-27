import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from core.models.models_per_tenant import Expense, BankStatementTransaction, Anomaly
from commercial.anomaly_detection.service import AnomalyDetectionService
from core.models.database import set_tenant_context

@pytest.mark.asyncio
async def test_anomaly_detection_integration(db_session: Session, monkeypatch):
    """Test that multiple rules can detect anomalies on a single expense.

    Uses monkeypatch to bypass the commercial feature-flag check so the rule
    engine actually runs in the test environment (absent-row regression guard:
    with no Settings row the config returns all-enabled + min_risk_score 0).
    """
    monkeypatch.setattr(
        AnomalyDetectionService, "_is_super_admin_context", lambda self: True
    )
    # 1. Setup - Create an expense that triggers multiple rules
    # Round number + duplicate-ish + Sunday (Temporal)
    expense = Expense(
        user_id=None,
        vendor="PHANTOM VENDOR INC",
        amount=500.00,  # Round number
        currency="USD",
        expense_date=datetime(2023, 10, 1, 14, 0, tzinfo=timezone.utc),  # A Sunday
        category="Consulting",
        notes="Software consulting for phantom project",
        status="recorded"
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)

    # 2. Run Anomaly Detection
    service = AnomalyDetectionService(db_session)
    await service.analyze_entity(expense, "expense")

    # 3. Verify Anomalies were created
    anomalies = db_session.query(Anomaly).filter(Anomaly.entity_id == expense.id).all()

    # We expect at least: Rounding + Temporal (Sunday).
    # phantom_vendor requires an AI call which is unavailable in the test env.
    rule_ids = [a.rule_id for a in anomalies]
    assert "rounding_anomaly" in rule_ids
    assert "temporal_anomaly" in rule_ids

    print(f"Successfully detected {len(anomalies)} anomalies (absent-row regression guard).")

from core.models.models_per_tenant import Settings
from core.services.anomaly_rule_config import ANOMALY_RULE_CONFIG_KEY


def _set_rule_config(db, value):
    # Delete any pre-existing row first to avoid UniqueViolation when a
    # prior test's teardown failed and left its Settings row behind.
    db.query(Settings).filter(Settings.key == ANOMALY_RULE_CONFIG_KEY).delete()
    db.add(Settings(key=ANOMALY_RULE_CONFIG_KEY, value=value))
    db.commit()


@pytest.mark.asyncio
async def test_disabled_rule_produces_no_anomaly(db_session, sample_user, monkeypatch):
    # Force the engine to run despite no licensed feature / master superuser in the test env.
    monkeypatch.setattr(
        AnomalyDetectionService, "_is_super_admin_context", lambda self: True
    )
    _set_rule_config(db_session, {"rules": {"rounding_anomaly": {"enabled": False}}})
    # $500 round amount on a Sunday: rounding_anomaly WOULD fire (disabled here);
    # temporal_anomaly fires on the weekend regardless (positive control: proves engine ran).
    expense = Expense(
        user_id=sample_user.id, vendor="Acme Co", amount=500.00, currency="USD",
        expense_date=datetime(2023, 10, 1, 14, 0, tzinfo=timezone.utc),  # a Sunday
        category="Office", notes="Office chairs", status="recorded",
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)

    service = AnomalyDetectionService(db_session)
    await service.analyze_entity(expense, "expense")

    rule_ids = [
        a.rule_id for a in
        db_session.query(Anomaly).filter(Anomaly.entity_id == expense.id).all()
    ]
    assert "temporal_anomaly" in rule_ids      # positive control: engine actually ran
    assert "rounding_anomaly" not in rule_ids  # the disabled rule produced nothing


@pytest.mark.asyncio
async def test_min_risk_score_floor_drops_low_results(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(
        AnomalyDetectionService, "_is_super_admin_context", lambda self: True
    )
    # Floor at 35: rounding_anomaly (score 40) survives; temporal_anomaly (score 30) is dropped.
    _set_rule_config(db_session, {"min_risk_score": 35})
    expense = Expense(
        user_id=sample_user.id, vendor="Acme Co", amount=500.00, currency="USD",
        expense_date=datetime(2023, 10, 1, 14, 0, tzinfo=timezone.utc),  # a Sunday
        category="Office", notes="Office chairs", status="recorded",
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)

    service = AnomalyDetectionService(db_session)
    await service.analyze_entity(expense, "expense")

    saved_rule_ids = [
        a.rule_id for a in
        db_session.query(Anomaly).filter(Anomaly.entity_id == expense.id).all()
    ]
    assert "rounding_anomaly" in saved_rule_ids      # 40 >= 35 survives
    assert "temporal_anomaly" not in saved_rule_ids  # 30 < 35 dropped by the floor


from commercial.anomaly_detection.rules.rounding_anomaly import RoundingAnomalyRule
from commercial.anomaly_detection.rules.temporal_anomaly import TemporalAnomalyRule


@pytest.mark.asyncio
async def test_rounding_rule_respects_min_amount(db_session):
    rule = RoundingAnomalyRule()
    expense = Expense(
        user_id=None, vendor="Acme", amount=500.00, currency="USD",
        expense_date=datetime(2023, 10, 3, 14, 0, tzinfo=timezone.utc),
        category="Office", status="recorded",
    )
    # Raise the floor above 500 -> no flag.
    ctx = {"rule_config": {"rules": {"rounding_anomaly": {"min_amount": 1000}}}}
    assert await rule.analyze(db_session, expense, "expense", ctx) is None
    # Default behavior (no config) still flags it.
    assert await rule.analyze(db_session, expense, "expense", {}) is not None


@pytest.mark.asyncio
async def test_temporal_rule_respects_custom_hours(db_session):
    rule = TemporalAnomalyRule()
    expense = Expense(
        user_id=None, vendor="Acme", amount=10.0, currency="USD",
        expense_date=datetime(2023, 10, 3, 22, 0, tzinfo=timezone.utc),  # 22:00 Tuesday
        category="Office", status="recorded",
    )
    # Default hours (7-20) flag 22:00.
    assert await rule.analyze(db_session, expense, "expense", {}) is not None
    # Widen end_hour to 23 and drop weekend flag -> 22:00 Tuesday no longer odd.
    ctx = {"rule_config": {"rules": {"temporal_anomaly": {"end_hour": 23, "flag_weekend": False}}}}
    assert await rule.analyze(db_session, expense, "expense", ctx) is None


if __name__ == "__main__":
    # For manual runs if needed
    pass
