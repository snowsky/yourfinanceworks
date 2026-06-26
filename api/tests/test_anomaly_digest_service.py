"""AnomalyDigestService daily email digest (Slice 2)."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from core.models.models_per_tenant import User, Anomaly, Settings
from core.services.feature_config_service import FeatureConfigService
from core.services.anomaly_digest_service import AnomalyDigestService


@pytest.fixture(autouse=True)
def _cleanup(db_session):
    yield
    from core.models import EmailNotificationSettings
    db_session.query(EmailNotificationSettings).delete()
    db_session.query(Anomaly).delete()
    db_session.query(Settings).delete()
    db_session.query(User).delete()
    db_session.commit()


class _FakeEmail:
    def __init__(self):
        self.sent = []
        self.config = SimpleNamespace(from_email="noreply@x.com", from_name="App")

    def send_email(self, message):
        self.sent.append(message)
        return True


@pytest.fixture
def feature_on(monkeypatch):
    monkeypatch.setattr(FeatureConfigService, "is_enabled",
                        staticmethod(lambda *a, **k: True))


@pytest.fixture
def feature_off(monkeypatch):
    monkeypatch.setattr(FeatureConfigService, "is_enabled",
                        staticmethod(lambda *a, **k: False))


def _admin(db, email="admin@example.com"):
    u = User(email=email, hashed_password="x", is_active=True, role="admin",
             first_name="A", last_name="D")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _anomaly(db, *, risk_level="high", status="open", created_at=None):
    a = Anomaly(entity_type="invoice", entity_id=1, risk_score=80.0,
                risk_level=risk_level, reason="dup", rule_id="duplicate_billing",
                status=status)
    db.add(a); db.commit(); db.refresh(a)
    if created_at is not None:
        a.created_at = created_at
        db.commit()
    return a


def test_feature_disabled_skips(db_session, feature_off):
    _admin(db_session)
    _anomaly(db_session)
    out = AnomalyDigestService(db_session, _FakeEmail()).process_due_digest(force=True)
    assert out["status"] == "skipped"
    assert out["reason"] == "feature_disabled"


def test_empty_window_advances_watermark(db_session, feature_on):
    _admin(db_session)
    email = _FakeEmail()
    out = AnomalyDigestService(db_session, email).process_due_digest(force=True)
    assert out["status"] == "empty"
    assert email.sent == []
    rt = db_session.query(Settings).filter(Settings.key == "anomaly_digest_runtime").first()
    assert rt is not None and "last_run_at" in rt.value


def test_sends_one_email_per_admin_for_open_high_critical(db_session, feature_on):
    _admin(db_session, email="a1@x.com")
    _admin(db_session, email="a2@x.com")
    _anomaly(db_session, risk_level="high")
    _anomaly(db_session, risk_level="critical")
    email = _FakeEmail()
    out = AnomalyDigestService(db_session, email).process_due_digest(force=True)
    assert out["status"] == "sent"
    assert out["anomaly_count"] == 2
    assert len(email.sent) == 2  # one per admin


def test_excludes_resolved_and_low_medium(db_session, feature_on):
    _admin(db_session)
    _anomaly(db_session, risk_level="medium")
    _anomaly(db_session, risk_level="high", status="dismissed")
    email = _FakeEmail()
    out = AnomalyDigestService(db_session, email).process_due_digest(force=True)
    assert out["status"] == "empty"
    assert email.sent == []


def test_watermark_prevents_re_email(db_session, feature_on):
    _admin(db_session)
    _anomaly(db_session, risk_level="high")
    svc = AnomalyDigestService(db_session, _FakeEmail())
    svc.process_due_digest(force=True)
    # second run, not forced: < 24h since last run -> not due
    out = svc.process_due_digest(force=False)
    assert out["status"] == "skipped"
    assert out["reason"] == "not_due"


def test_only_anomalies_after_watermark_are_included(db_session, feature_on):
    _admin(db_session)
    old = _anomaly(db_session, risk_level="high",
                   created_at=datetime.now(timezone.utc) - timedelta(days=3))
    # Seed a watermark 1 day ago so the 3-day-old anomaly is excluded.
    db_session.add(Settings(key="anomaly_digest_runtime",
                            value={"last_run_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}))
    db_session.commit()
    email = _FakeEmail()
    out = AnomalyDigestService(db_session, email).process_due_digest(force=True)
    assert out["status"] == "empty"


def test_admin_opted_out_receives_no_email(db_session, feature_on):
    from core.models import EmailNotificationSettings
    admin = _admin(db_session)
    db_session.add(EmailNotificationSettings(user_id=admin.id, anomaly_alert=False))
    db_session.commit()
    _anomaly(db_session, risk_level="high")
    email = _FakeEmail()
    out = AnomalyDigestService(db_session, email).process_due_digest(force=True)
    assert out["status"] == "sent"  # window had alertable anomalies
    assert email.sent == []  # but the only admin opted out
