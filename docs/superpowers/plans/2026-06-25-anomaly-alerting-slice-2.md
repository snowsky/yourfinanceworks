# Anomaly Proactive Alerting (Slice 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notify tenant admins of new high/critical open anomalies via immediate in-app alerts (normal audit path) and a daily email digest (catches bulk reprocess), each gated by a per-user preference and de-duplicated.

**Architecture:** Two additive columns (`Anomaly.alerted_at`, `EmailNotificationSettings.anomaly_alert`) through the existing idempotent per-tenant ensure paths (no alembic). A new `AnomalyAlertService` fires immediate in-app alerts from the Kafka audit worker by writing system `ReminderNotification` rows (the real bell feed). A new `AnomalyDigestService` (mirroring `ExpenseDigestService`) runs daily from the existing background loop, batching open high/critical anomalies into one email per admin. Frontend adds one notification-routing branch and one settings toggle.

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant DBs), Jinja2 email templates, Kafka audit worker, React/TypeScript + vitest.

## Global Constraints

- Severity threshold is **fixed** at `risk_level in ("high", "critical")` this slice — do NOT add a configurable threshold (that is Slice 3).
- Only `status == "open"` anomalies alert. Resolved (confirmed/dismissed) anomalies never alert.
- Recipients for both channels are tenant admins only: `User.role == "admin"` (values are `admin`/`user`/`viewer`).
- Both channels are gated per-user by `NotificationService(db).should_send_notification(user_id, "anomaly_alert", channel)` with `channel` = `"in_app"` or `"email"`.
- Immediate in-app alerts fire ONLY when `reprocess_mode is False`. Bulk reprocess (`reprocess_mode=True`) never produces immediate in-app alerts — those anomalies are caught by the daily digest only.
- The `anomalies` table is NOT alembic-managed: schema changes go in `api/db_init.py::ensure_tenant_required_columns` (idempotent `ADD COLUMN`). The `email_notification_settings` table is patched via `api/core/services/expense_digest_service.py::ensure_expense_digest_preference_columns`.
- The in-app bell feed is the `reminder_notifications` table (model `ReminderNotification`), NOT `NotificationService.create_in_app_notification` (a logging stub). Deliver in-app by writing a `ReminderNotification` with `reminder_id=None`, `channel="in_app"`, `notification_type="anomaly_alert"`, and `#<anomaly_id>` embedded in `subject`.
- Digest is email-only. Digest emails render with Jinja2 autoescape ON (use `_HTML_ENV` in `notification_templates.py`).
- Feature gate for the digest: `FeatureConfigService.is_enabled("anomaly_detection", db=db)`.
- Deep-link target (Slice 1 drawer): `/anomalies?selected=<id>`; email absolute URL base is `config.UI_BASE_URL`.
- Backend tests run in-container: `docker compose exec -T api python -m pytest tests/<file> -v` (workdir `api/`, so test paths drop the `api/` prefix). Frontend: `docker compose exec -T ui npx vitest run src/<path>`.

---

### Task 1: `Anomaly.alerted_at` column + per-tenant schema patch

**Files:**
- Modify: `api/core/models/models_per_tenant.py` (the `Anomaly` class — find it via the existing `status`/`resolution_note` columns added in Slice 1)
- Modify: `api/db_init.py:243-265` (the existing `anomalies` block inside `ensure_tenant_required_columns`)
- Test: `api/tests/test_anomaly_status_model.py`

**Interfaces:**
- Produces: `Anomaly.alerted_at` — `Optional[datetime]`, nullable, defaults to `None`. Set by `AnomalyAlertService` (Task 3) when the immediate in-app alert fires.

- [ ] **Step 1: Write the failing test**

Append to `api/tests/test_anomaly_status_model.py`:

```python
def test_new_anomaly_alerted_at_defaults_to_none(db_session):
    a = Anomaly(entity_type="invoice", entity_id=99, risk_score=80.0,
                risk_level="high", reason="x")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    assert a.alerted_at is None
    db_session.delete(a)
    db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_status_model.py::test_new_anomaly_alerted_at_defaults_to_none -v`
Expected: FAIL with `AttributeError: 'Anomaly' object has no attribute 'alerted_at'`

- [ ] **Step 3: Add the model column**

In `api/core/models/models_per_tenant.py`, in the `Anomaly` class, immediately after the `resolution_note` column (added in Slice 1), add:

```python
    # Slice 2 (alerting): set when an immediate in-app alert has been fired for
    # this anomaly, so a Kafka redelivery (at-least-once) does not re-alert.
    alerted_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_status_model.py::test_new_anomaly_alerted_at_defaults_to_none -v`
Expected: PASS

- [ ] **Step 5: Add the idempotent per-tenant ALTER**

In `api/db_init.py`, inside the `if "anomalies" in inspector.get_table_names():` block, after the `resolution_note` block (around line 265), add:

```python
                if "alerted_at" not in existing:
                    logger.info(f"[tenant {tenant_id}] Adding anomalies.alerted_at")
                    conn.execute(
                        text("ALTER TABLE anomalies ADD COLUMN alerted_at TIMESTAMP WITH TIME ZONE")
                    )
                    conn.commit()
```

- [ ] **Step 6: Verify the file imports/compiles**

Run: `docker compose exec -T api python -c "import db_init; import core.models.models_per_tenant"`
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add api/core/models/models_per_tenant.py api/db_init.py api/tests/test_anomaly_status_model.py
git commit -m "feat(anomaly-alerting): add Anomaly.alerted_at de-dup column"
```

---

### Task 2: `anomaly_alert` notification preference

**Files:**
- Modify: `api/core/models/email_notifications.py` (the `EmailNotificationSettings` model)
- Modify: `api/core/schemas/email_notifications.py:5-156` (the `EmailNotificationSettingsBase` Pydantic model)
- Modify: `api/core/services/expense_digest_service.py:43-70` (the `ensure_expense_digest_preference_columns` function and its docstring)
- Test: `api/tests/test_anomaly_alert_preference.py` (new)

**Interfaces:**
- Produces: `EmailNotificationSettings.anomaly_alert` — `bool`, default `True`. Read by `NotificationService.should_send_notification(user_id, "anomaly_alert", channel)` via its existing `getattr(settings, event_type, False)` (works for both `"email"` and `"in_app"` because `"anomaly_alert"` is not an `expense_`/`approval_` prefix).

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_anomaly_alert_preference.py`:

```python
"""should_send_notification honours the anomaly_alert preference (Slice 2)."""
from core.models.models_per_tenant import User
from core.models import EmailNotificationSettings
from core.services.notification_service import NotificationService


def _admin(db):
    u = User(email="admin@example.com", hashed_password="x", is_active=True,
             role="admin", first_name="A", last_name="D")
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_anomaly_alert_defaults_on_for_both_channels(db_session):
    user = _admin(db_session)
    svc = NotificationService(db_session)
    assert svc.should_send_notification(user.id, "anomaly_alert", "in_app") is True
    assert svc.should_send_notification(user.id, "anomaly_alert", "email") is True


def test_anomaly_alert_off_suppresses_both_channels(db_session):
    user = _admin(db_session)
    settings = EmailNotificationSettings(user_id=user.id, anomaly_alert=False)
    db_session.add(settings); db_session.commit()
    svc = NotificationService(db_session)
    assert svc.should_send_notification(user.id, "anomaly_alert", "in_app") is False
    assert svc.should_send_notification(user.id, "anomaly_alert", "email") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_alert_preference.py -v`
Expected: FAIL — `TypeError` (unexpected keyword `anomaly_alert`) or the default-on assertion fails because the attribute does not exist (`getattr(..., False)`).

- [ ] **Step 3: Add the model column**

In `api/core/models/email_notifications.py`, in the `EmailNotificationSettings` class, after the inventory columns block (around line 62), add a new section:

```python
    # Anomaly / fraud alerts (Slice 2) — gates both in-app and email channels
    anomaly_alert = Column(Boolean, default=True)
```

- [ ] **Step 4: Add the schema field**

In `api/core/schemas/email_notifications.py`, in `EmailNotificationSettingsBase`, after `expense_analysis_failed: bool = True` (line 39), add:

```python
    # Anomaly / fraud alerts (Slice 2)
    anomaly_alert: bool = True
```

- [ ] **Step 5: Add the per-tenant column patch**

In `api/core/services/expense_digest_service.py`, update `ensure_expense_digest_preference_columns`: change the docstring to `"""Backfill per-user digest + anomaly-alert columns for tenant DBs that have not run migrations yet."""` and add to the `column_defs` dict:

```python
        "anomaly_alert": (
            "BOOLEAN NOT NULL DEFAULT TRUE"
            if dialect == "postgresql"
            else "BOOLEAN NOT NULL DEFAULT 1"
        ),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_alert_preference.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add api/core/models/email_notifications.py api/core/schemas/email_notifications.py api/core/services/expense_digest_service.py api/tests/test_anomaly_alert_preference.py
git commit -m "feat(anomaly-alerting): add anomaly_alert notification preference"
```

---

### Task 3: `AnomalyAlertService` (immediate in-app) + worker wiring

**Files:**
- Create: `api/commercial/anomaly_detection/alert_service.py`
- Modify: `api/workers/audit_consumer.py:167-171` (the `analyze_entity` call site in `_process_message`)
- Test: `api/tests/test_anomaly_alert_service.py` (new)

**Interfaces:**
- Consumes: `Anomaly` (with `alerted_at` from Task 1), `EmailNotificationSettings.anomaly_alert` (Task 2), `ReminderNotification` (`api/core/models/models_per_tenant.py`), `User.role`.
- Produces: `AnomalyAlertService(db).notify_new_anomalies(anomalies: list[Anomaly], reprocess_mode: bool) -> dict` returning `{"alerted": int, "skipped": int}`. Writes one `ReminderNotification(reminder_id=None, notification_type="anomaly_alert", channel="in_app")` per opted-in admin per alertable anomaly and sets `anomaly.alerted_at`.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_anomaly_alert_service.py`:

```python
"""AnomalyAlertService immediate in-app alerts (Slice 2)."""
from core.models.models_per_tenant import User, Anomaly, ReminderNotification
from core.models import EmailNotificationSettings
from commercial.anomaly_detection.alert_service import AnomalyAlertService


def _admin(db, email="admin@example.com"):
    u = User(email=email, hashed_password="x", is_active=True, role="admin",
             first_name="A", last_name="D")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _user(db, role="user", email="reg@example.com"):
    u = User(email=email, hashed_password="x", is_active=True, role=role,
             first_name="R", last_name="U")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _anomaly(db, *, risk_level="high", status="open"):
    a = Anomaly(entity_type="invoice", entity_id=1, risk_score=80.0,
                risk_level=risk_level, reason="dup billing", rule_id="duplicate_billing",
                status=status)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _notifs(db):
    return db.query(ReminderNotification).filter(
        ReminderNotification.notification_type == "anomaly_alert").all()


def test_high_risk_open_anomaly_alerts_admin_and_sets_alerted_at(db_session):
    admin = _admin(db_session)
    a = _anomaly(db_session, risk_level="high")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert result["alerted"] == 1
    rows = _notifs(db_session)
    assert len(rows) == 1
    assert rows[0].user_id == admin.id
    assert rows[0].channel == "in_app"
    assert rows[0].reminder_id is None
    assert f"#{a.id}" in rows[0].subject
    db_session.refresh(a)
    assert a.alerted_at is not None


def test_critical_risk_alerts(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="critical")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert len(_notifs(db_session)) == 1


def test_low_and_medium_risk_do_not_alert(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="medium")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert result["alerted"] == 0
    assert _notifs(db_session) == []


def test_resolved_anomaly_does_not_alert(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="high", status="confirmed")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert _notifs(db_session) == []


def test_reprocess_mode_suppresses_all_alerts(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="critical")
    result = AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=True)
    assert result["alerted"] == 0
    assert _notifs(db_session) == []
    db_session.refresh(a)
    assert a.alerted_at is None


def test_already_alerted_anomaly_is_skipped(db_session):
    _admin(db_session)
    a = _anomaly(db_session, risk_level="high")
    svc = AnomalyAlertService(db_session)
    svc.notify_new_anomalies([a], reprocess_mode=False)
    svc.notify_new_anomalies([a], reprocess_mode=False)  # second pass
    assert len(_notifs(db_session)) == 1  # not doubled


def test_only_admins_receive_alerts(db_session):
    _admin(db_session, email="a@x.com")
    _user(db_session, role="user", email="u@x.com")
    _user(db_session, role="viewer", email="v@x.com")
    a = _anomaly(db_session, risk_level="high")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert len(_notifs(db_session)) == 1  # only the admin


def test_admin_opted_out_gets_no_alert(db_session):
    admin = _admin(db_session)
    db_session.add(EmailNotificationSettings(user_id=admin.id, anomaly_alert=False))
    db_session.commit()
    a = _anomaly(db_session, risk_level="high")
    AnomalyAlertService(db_session).notify_new_anomalies([a], reprocess_mode=False)
    assert _notifs(db_session) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_alert_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'commercial.anomaly_detection.alert_service'`

- [ ] **Step 3: Implement the service**

Create `api/commercial/anomaly_detection/alert_service.py`:

```python
"""Immediate in-app alerting for newly detected anomalies (Slice 2).

Writes system ReminderNotification rows (the in-app bell feed) for tenant
admins when the audit worker saves a new high/critical open anomaly on the
normal (non-reprocess) path. The NotificationService.create_in_app_notification
method is a logging stub and does NOT reach the bell, so we write the row here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from core.models.models_per_tenant import Anomaly, ReminderNotification, User
from core.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

ALERT_LEVELS = {"high", "critical"}

_ENTITY_LABELS = {
    "invoice": "invoice",
    "expense": "expense",
    "bank_transaction": "transaction",
    "bank_statement_transaction": "transaction",
}


class AnomalyAlertService:
    def __init__(self, db: Session):
        self.db = db
        self._notifier = NotificationService(db)

    def notify_new_anomalies(self, anomalies: List[Anomaly], reprocess_mode: bool) -> dict:
        """Fire immediate in-app alerts for new high/critical open anomalies."""
        alerted = 0
        skipped = 0
        if reprocess_mode:
            # Bulk reprocess never alerts in-app; the daily digest catches these.
            return {"alerted": 0, "skipped": len(anomalies)}

        admins = self.db.query(User).filter(User.role == "admin", User.is_active == True).all()  # noqa: E712
        now = datetime.now(timezone.utc)

        for anomaly in anomalies:
            if (anomaly.risk_level not in ALERT_LEVELS
                    or anomaly.status != "open"
                    or anomaly.alerted_at is not None):
                skipped += 1
                continue

            label = _ENTITY_LABELS.get(anomaly.entity_type, anomaly.entity_type)
            subject = (
                f"{anomaly.risk_level.title()}-risk anomaly on "
                f"{label} #{anomaly.id}"
            )
            message = (anomaly.reason or "An anomaly was detected.")[:500]

            fired = False
            for admin in admins:
                if not self._notifier.should_send_notification(admin.id, "anomaly_alert", "in_app"):
                    continue
                self.db.add(ReminderNotification(
                    reminder_id=None,
                    user_id=admin.id,
                    notification_type="anomaly_alert",
                    channel="in_app",
                    scheduled_for=now,
                    sent_at=now,
                    is_sent=True,
                    subject=subject,
                    message=message,
                ))
                fired = True

            anomaly.alerted_at = now
            if fired:
                alerted += 1
            else:
                skipped += 1

        self.db.commit()
        logger.info(f"Anomaly in-app alerts: {alerted} alerted, {skipped} skipped")
        return {"alerted": alerted, "skipped": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_alert_service.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Wire the service into the audit worker**

In `api/workers/audit_consumer.py`, in `_process_message`, replace the existing `analyze_entity` call (around lines 168-171):

```python
                    # Run Anomaly Detection
                    service = AnomalyDetectionService(tenant_session)
                    await service.analyze_entity(entity, entity_type, reprocess_mode=reprocess_mode)
                    logger.info(f"Completed audit for {entity_type} {entity_id}")
```

with:

```python
                    # Run Anomaly Detection
                    service = AnomalyDetectionService(tenant_session)
                    created = await service.analyze_entity(
                        entity, entity_type, reprocess_mode=reprocess_mode
                    )
                    logger.info(f"Completed audit for {entity_type} {entity_id}")
                    # Slice 2: immediate in-app alerts for new high/critical anomalies
                    # (suppressed for bulk reprocess; digest catches those).
                    from commercial.anomaly_detection.alert_service import AnomalyAlertService
                    AnomalyAlertService(tenant_session).notify_new_anomalies(
                        created or [], reprocess_mode=reprocess_mode
                    )
```

- [ ] **Step 6: Verify the worker imports/compiles**

Run: `docker compose exec -T api python -c "import workers.audit_consumer"`
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add api/commercial/anomaly_detection/alert_service.py api/workers/audit_consumer.py api/tests/test_anomaly_alert_service.py
git commit -m "feat(anomaly-alerting): immediate in-app alerts via AnomalyAlertService"
```

---

### Task 4: Daily email digest — templates + `AnomalyDigestService`

**Files:**
- Modify: `api/core/services/notification_templates.py` (append two templates near `APPROVAL_DIGEST_HTML_TEMPLATE`, ~line 549)
- Create: `api/core/services/anomaly_digest_service.py`
- Test: `api/tests/test_anomaly_digest_service.py` (new)

**Interfaces:**
- Consumes: `Anomaly` (with `alerted_at`, `status`, `risk_level`, `created_at`), `User.role`, `Settings` (`api/core/models/models_per_tenant.py`), `FeatureConfigService.is_enabled("anomaly_detection", db=db)`, `EmailService`/`EmailMessage` (`api/core/services/email_service.py`), `NotificationService.should_send_notification`, `config.UI_BASE_URL`.
- Produces: `AnomalyDigestService(db, email_service).process_due_digest(force: bool=False) -> dict` returning `{"status": "skipped"|"empty"|"sent", ...}`; uses Settings key `"anomaly_digest_runtime"` holding `{"last_run_at": iso}`.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_anomaly_digest_service.py`:

```python
"""AnomalyDigestService daily email digest (Slice 2)."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from core.models.models_per_tenant import User, Anomaly, Settings
from core.services.feature_config_service import FeatureConfigService
from core.services.anomaly_digest_service import AnomalyDigestService


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_digest_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.services.anomaly_digest_service'`

- [ ] **Step 3: Add the email templates**

In `api/core/services/notification_templates.py`, after the `APPROVAL_DIGEST_TEXT_TEMPLATE` definition (search for it), append:

```python
ANOMALY_DIGEST_HTML_TEMPLATE = _HTML_ENV.from_string("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{{ subject }}</title></head>
<body style="font-family: Arial, sans-serif; background:#f5f5f5; padding:20px;">
  <div style="max-width:600px; margin:0 auto; background:#fff; padding:30px; border-radius:10px;">
    <h2 style="color:#333;">{{ subject }}</h2>
    <p style="color:#666;">{{ count }} high/critical anomal{{ 'y' if count == 1 else 'ies' }} need review.</p>
    <ul style="color:#444; line-height:1.6;">
      {% for item in items %}
      <li>
        <strong>[{{ item.risk_level | upper }}]</strong>
        {{ item.entity_label }} #{{ item.entity_id }} — {{ item.reason }}
        — <a href="{{ item.url }}">Review</a>
      </li>
      {% endfor %}
    </ul>
    <p style="color:#999; font-size:12px;">{{ company_name }}</p>
  </div>
</body>
</html>
""")

ANOMALY_DIGEST_TEXT_TEMPLATE = _TEXT_ENV.from_string("""{{ subject }}

{{ count }} high/critical anomalies need review.

{% for item in items %}- [{{ item.risk_level | upper }}] {{ item.entity_label }} #{{ item.entity_id }} — {{ item.reason }}
  Review: {{ item.url }}
{% endfor %}
{{ company_name }}
""")
```

- [ ] **Step 4: Implement the digest service**

Create `api/core/services/anomaly_digest_service.py`:

```python
"""Daily anomaly digest emails to tenant admins (Slice 2).

Mirrors ExpenseDigestService: a tenant-level digest gated by a Settings-row
watermark. Selects open high/critical anomalies created since the last run and
emails one summary per opted-in admin, then advances the watermark.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config import APP_NAME, config as app_config
from core.models.models_per_tenant import Anomaly, Settings, User
from core.services.email_service import EmailService, EmailMessage
from core.services.feature_config_service import FeatureConfigService
from core.services.notification_service import NotificationService
from core.services.notification_templates import (
    ANOMALY_DIGEST_HTML_TEMPLATE,
    ANOMALY_DIGEST_TEXT_TEMPLATE,
)

logger = logging.getLogger(__name__)

ALERT_LEVELS = ("high", "critical")
_ENTITY_LABELS = {
    "invoice": "Invoice",
    "expense": "Expense",
    "bank_transaction": "Transaction",
    "bank_statement_transaction": "Transaction",
}


class AnomalyDigestService:
    RUNTIME_KEY = "anomaly_digest_runtime"

    def __init__(self, db: Session, email_service: Optional[EmailService] = None):
        self.db = db
        self.email_service = email_service
        self._notifier = NotificationService(db, email_service)

    def process_due_digest(self, force: bool = False) -> Dict[str, Any]:
        if not FeatureConfigService.is_enabled("anomaly_detection", db=self.db):
            return {"status": "skipped", "reason": "feature_disabled"}

        now = datetime.now(timezone.utc)
        last_run_at = self._load_last_run_at()

        if not force and last_run_at is not None and (now - last_run_at) < timedelta(hours=24):
            return {"status": "skipped", "reason": "not_due"}

        # Window start: the watermark, or the last 24h for a first-ever run.
        window_start = last_run_at if last_run_at is not None else (now - timedelta(hours=24))

        anomalies = (
            self.db.query(Anomaly)
            .filter(
                Anomaly.status == "open",
                Anomaly.risk_level.in_(ALERT_LEVELS),
                Anomaly.created_at > window_start,
            )
            .order_by(Anomaly.created_at.desc())
            .all()
        )

        if not anomalies:
            self._save_last_run_at(now)
            return {"status": "empty"}

        items = [self._serialize(a) for a in anomalies]
        admins = self.db.query(User).filter(User.role == "admin", User.is_active == True).all()  # noqa: E712
        emailed = 0
        for admin in admins:
            if not self._notifier.should_send_notification(admin.id, "anomaly_alert", "email"):
                continue
            if self._send_to_admin(admin, items):
                emailed += 1

        self._save_last_run_at(now)
        return {"status": "sent", "anomaly_count": len(items), "emailed": emailed}

    def _serialize(self, a: Anomaly) -> Dict[str, Any]:
        label = _ENTITY_LABELS.get(a.entity_type, a.entity_type)
        base = app_config.UI_BASE_URL.rstrip("/")
        return {
            "risk_level": a.risk_level,
            "entity_label": label,
            "entity_id": a.entity_id,
            "reason": a.reason or "Anomaly detected",
            "url": f"{base}/anomalies?selected={a.id}",
        }

    def _send_to_admin(self, admin: User, items: List[Dict[str, Any]]) -> bool:
        if not self.email_service:
            return False
        recipient_name = f"{admin.first_name or ''} {admin.last_name or ''}".strip() or admin.email
        subject = f"{len(items)} fraud/anomaly alert(s) need review"
        context = {
            "subject": subject,
            "count": len(items),
            "items": items,
            "company_name": APP_NAME,
        }
        from_email = self.email_service.config.from_email or "noreply@invoiceapp.com"
        from_name = self.email_service.config.from_name or APP_NAME
        message = EmailMessage(
            to_email=admin.email,
            to_name=recipient_name,
            subject=subject,
            html_body=ANOMALY_DIGEST_HTML_TEMPLATE.render(**context),
            text_body=ANOMALY_DIGEST_TEXT_TEMPLATE.render(**context),
            from_email=from_email,
            from_name=from_name,
        )
        return self.email_service.send_email(message)

    def _load_last_run_at(self) -> Optional[datetime]:
        record = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if not record or not isinstance(record.value, dict):
            return None
        raw = record.value.get("last_run_at")
        if not raw:
            return None
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def _save_last_run_at(self, now: datetime) -> None:
        value = {"last_run_at": now.isoformat()}
        record = self.db.query(Settings).filter(Settings.key == self.RUNTIME_KEY).first()
        if record:
            record.value = value
            record.updated_at = now
        else:
            self.db.add(Settings(key=self.RUNTIME_KEY, value=value))
        self.db.commit()
```

Note: `from config import APP_NAME, config as app_config` and `app_config.UI_BASE_URL` match the project's existing pattern (`api/core/services/email_service.py` uses `from config import APP_NAME, config` then `config.UI_BASE_URL`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_digest_service.py -v`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add api/core/services/notification_templates.py api/core/services/anomaly_digest_service.py api/tests/test_anomaly_digest_service.py
git commit -m "feat(anomaly-alerting): daily anomaly digest service + email templates"
```

---

### Task 5: Scheduler wiring — `_process_anomaly_digest`

**Files:**
- Modify: `api/core/services/reminder_background_service.py:138-155` (the per-tenant loop) and add a `_process_anomaly_digest` method next to `_process_expense_digest` (~line 168)
- Test: `api/tests/test_anomaly_digest_scheduler.py` (new)

**Interfaces:**
- Consumes: `AnomalyDigestService.process_due_digest` (Task 4), `Settings` key `"email_config"`, `EmailService`/`EmailProviderConfig`.
- Produces: `ReminderBackgroundService._process_anomaly_digest(db, tenant_id) -> dict` — returns `{"status": "skipped", "reason": "email_config_missing"}` when email is unconfigured, else the digest result.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_anomaly_digest_scheduler.py`:

```python
"""Scheduler wiring for the anomaly digest (Slice 2)."""
from core.services.reminder_background_service import ReminderBackgroundService


def test_anomaly_digest_skipped_when_email_unconfigured(db_session):
    svc = ReminderBackgroundService()
    out = svc._process_anomaly_digest(db_session, tenant_id=1)
    assert out["status"] == "skipped"
    assert out["reason"] == "email_config_missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_digest_scheduler.py -v`
Expected: FAIL — `AttributeError: 'ReminderBackgroundService' object has no attribute '_process_anomaly_digest'`

(If `ReminderBackgroundService()` needs constructor args, inspect the class header in `reminder_background_service.py` and adjust the test instantiation to match — match how the existing code constructs it.)

- [ ] **Step 3: Add the method**

In `api/core/services/reminder_background_service.py`, after the `_process_expense_digest` method, add a sibling method that mirrors its email-config build:

```python
    def _process_anomaly_digest(self, db, tenant_id: int) -> Dict[str, Any]:
        """Process the due anomaly digest for a tenant if email is configured."""
        try:
            from core.models.models_per_tenant import Settings
            from core.services.email_service import EmailProvider, EmailProviderConfig, EmailService
            from core.services.anomaly_digest_service import AnomalyDigestService

            email_settings = db.query(Settings).filter(Settings.key == "email_config").first()
            if not email_settings or not email_settings.value:
                return {"status": "skipped", "reason": "email_config_missing"}

            email_config_data = email_settings.value
            if not email_config_data.get("enabled", False):
                return {"status": "skipped", "reason": "email_disabled"}

            config = EmailProviderConfig(
                provider=EmailProvider(email_config_data["provider"]),
                from_email=email_config_data.get("from_email"),
                from_name=email_config_data.get("from_name"),
                aws_access_key_id=email_config_data.get("aws_access_key_id"),
                aws_secret_access_key=email_config_data.get("aws_secret_access_key"),
                aws_region=email_config_data.get("aws_region"),
                azure_connection_string=email_config_data.get("azure_connection_string"),
                mailgun_api_key=email_config_data.get("mailgun_api_key"),
                mailgun_domain=email_config_data.get("mailgun_domain"),
            )
            email_service = EmailService(config)
            return AnomalyDigestService(db, email_service).process_due_digest(force=False)
        except Exception as e:
            logger.error(f"Anomaly digest pass failed for tenant {tenant_id}: {e}")
            return {"status": "failed", "error": str(e)}
```

- [ ] **Step 4: Call it in the per-tenant loop**

In the same file, in the per-tenant processing block, right after the expense-digest block (after line ~141) and before the cleanup block, add:

```python
                # Process anomaly digest schedule (Slice 2)
                anomaly_digest_stats = self._process_anomaly_digest(db, tenant_id)
                if anomaly_digest_stats.get("status") not in {"skipped", "failed"}:
                    logger.info(f"Processed anomaly digest for tenant {tenant_id}: {anomaly_digest_stats}")
```

And add `"anomaly_digest": anomaly_digest_stats,` to the returned dict (next to `"expense_digest": expense_digest_stats,`).

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/test_anomaly_digest_scheduler.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add api/core/services/reminder_background_service.py api/tests/test_anomaly_digest_scheduler.py
git commit -m "feat(anomaly-alerting): run daily anomaly digest from background loop"
```

---

### Task 6: Frontend — in-app notification routing

**Files:**
- Modify: `ui/src/components/reminders/InAppNotifications.tsx:204-236` (the `handleNotificationClick` function)
- Test: `ui/src/components/reminders/__tests__/InAppNotifications.routing.test.tsx` (new — confirm the `__tests__` dir convention by checking sibling test locations; if the project colocates tests, place it next to the component instead)

**Interfaces:**
- Consumes: notification objects with `notification_type: "anomaly_alert"` and `subject` containing `#<id>` (produced by Task 3). Uses the existing `extractResourceId(subject)` helper (regex `/#(\d+)/`).

- [ ] **Step 1: Write the failing test**

First inspect the component to mirror its existing test setup (props, the notification shape, how `markAsRead` is provided). Then create `ui/src/components/reminders/__tests__/InAppNotifications.routing.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InAppNotifications } from '../InAppNotifications';

// Mock the API the component fetches from so we can inject a notification.
vi.mock('@/lib/api', () => ({
  reminderApi: {
    getUnreadNotificationCount: vi.fn().mockResolvedValue({ count: 1 }),
    getRecentNotifications: vi.fn().mockResolvedValue([
      {
        id: 1,
        notification_type: 'anomaly_alert',
        subject: 'High-risk anomaly on invoice #42',
        message: 'duplicate billing',
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ]),
    markNotificationAsRead: vi.fn().mockResolvedValue({}),
    markAllNotificationsAsRead: vi.fn().mockResolvedValue({}),
    dismissNotification: vi.fn().mockResolvedValue({}),
  },
}));

describe('InAppNotifications anomaly routing', () => {
  beforeEach(() => {
    // jsdom: make window.location.href assignable and observable
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' },
    });
  });

  it('routes an anomaly_alert notification to the Slice-1 drawer', async () => {
    render(<InAppNotifications />);
    // Open the popover, then click the notification.
    fireEvent.click(await screen.findByRole('button'));
    const item = await screen.findByText(/High-risk anomaly on invoice #42/i);
    fireEvent.click(item);
    await waitFor(() => {
      expect(window.location.href).toBe('/anomalies?selected=42');
    });
  });
});
```

> The exact API method names (`getRecentNotifications`, `getUnreadNotificationCount`, etc.) and the notification field names MUST match what the component actually imports/uses — read `InAppNotifications.tsx` and `ui/src/lib/api/reminders.ts` first and align the mock to reality. Adjust the queries (`getByRole`, text matchers) to the component's real markup.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/reminders/__tests__/InAppNotifications.routing.test.tsx`
Expected: FAIL — clicking does nothing, `window.location.href` stays `''`.

- [ ] **Step 3: Add the routing branch**

In `ui/src/components/reminders/InAppNotifications.tsx`, in `handleNotificationClick`, after the invoice-approval branch (around line 235) and before the closing `};`, add:

```tsx
    // Handle anomaly / fraud alerts (Slice 2) -> Slice-1 review drawer
    if (notification_type === 'anomaly_alert') {
      const anomalyId = extractResourceId(subject);
      if (anomalyId) {
        markAsRead(notification.id);
        setOpen(false);
        window.location.href = `/anomalies?selected=${anomalyId}`;
      }
      return;
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/reminders/__tests__/InAppNotifications.routing.test.tsx`
Expected: PASS

- [ ] **Step 5: Typecheck**

Run: `docker compose exec -T ui npx tsc --noEmit`
Expected: no new errors in `InAppNotifications.tsx` (pre-existing errors elsewhere are not introduced by this change).

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/reminders/InAppNotifications.tsx ui/src/components/reminders/__tests__/InAppNotifications.routing.test.tsx
git commit -m "feat(anomaly-alerting): route anomaly_alert notifications to review drawer"
```

---

### Task 7: Frontend — notification settings toggle

**Files:**
- Modify: `ui/src/components/settings/NotificationsTab.tsx`
- Modify: the TypeScript type for notification settings (find via `grep -rn "anomaly_alert\|expense_analysis_failed\|interface EmailNotificationSettings\|type EmailNotificationSettings" ui/src` — add `anomaly_alert: boolean;` wherever the settings shape is declared)
- Test: extend or create the NotificationsTab test (check for an existing `NotificationsTab.test.tsx`; if absent, create `ui/src/components/settings/__tests__/NotificationsTab.test.tsx` mirroring an existing settings-tab test's setup)

**Interfaces:**
- Consumes: the settings object round-tripped by the notifications settings GET/PUT (now including `anomaly_alert` from Task 2's schema change).

- [ ] **Step 1: Inspect the component**

Read `NotificationsTab.tsx` to find how other boolean toggles (e.g. `invoice_created`, `expense_approved`) are rendered and wired (the toggle component, the change handler, and the settings state shape). Mirror that exact pattern.

- [ ] **Step 2: Write the failing test**

Create/extend the test to assert the new toggle renders with an accessible label "Anomaly / fraud alerts" (or the label you use). Mirror the existing settings-tab test's provider/mock setup. Example (adapt mocks to the real ones the component uses):

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NotificationsTab } from '../NotificationsTab';

describe('NotificationsTab anomaly toggle', () => {
  it('renders the anomaly/fraud alerts toggle', async () => {
    render(<NotificationsTab />);
    expect(await screen.findByText(/anomaly.*alerts/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/settings/__tests__/NotificationsTab.test.tsx`
Expected: FAIL — the label is not found.

- [ ] **Step 4: Add the type field**

In the TS settings type (located in Step's grep), add:

```ts
  anomaly_alert: boolean;
```

- [ ] **Step 5: Add the toggle to the component**

In `NotificationsTab.tsx`, in the section that lists notification toggles (place it near the expense or a logical "security/alerts" group), add a toggle bound to `anomaly_alert` following the exact pattern used by neighbouring toggles. Use label "Anomaly / fraud alerts" and a helptext like "Notify admins when a high/critical anomaly is detected." Wire its change handler exactly like the sibling toggles so it persists on save.

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/settings/__tests__/NotificationsTab.test.tsx`
Expected: PASS

- [ ] **Step 7: Typecheck**

Run: `docker compose exec -T ui npx tsc --noEmit`
Expected: no new errors introduced by these files.

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/settings/NotificationsTab.tsx ui/src/components/settings/__tests__/NotificationsTab.test.tsx
git commit -m "feat(anomaly-alerting): add anomaly/fraud alerts notification toggle"
```

---

## Notes for the implementer

- Run the full backend slice suite after Task 5: `docker compose exec -T api python -m pytest tests/test_anomaly_alert_service.py tests/test_anomaly_digest_service.py tests/test_anomaly_alert_preference.py tests/test_anomaly_status_model.py tests/test_anomaly_digest_scheduler.py -v`.
- If `pytest` is missing in the api container (image was rebuilt), install test deps first: `docker compose exec -T api pip install -r requirements-test.txt`.
- The conftest `db_session` is in-memory SQLite with `create_all` from the model metadata, so the new columns exist for tests without running the `db_init`/ensure ALTER paths (those are exercised only against real postgres tenant DBs at startup).
- Do NOT add a configurable severity threshold or digest cadence — that is explicitly Slice 3.
