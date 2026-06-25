# Anomaly / Fraud Detection — Proactive Alerting (Slice 2) Design Spec

**Date:** 2026-06-25
**Status:** Approved design → ready for implementation planning
**Scope:** Slice 2 of competitor feature #4 (AI anomaly / fraud detection). The detection **engine + Kafka pipeline are already built**, and **Slice 1** (PR #423) added the triage workflow (`Anomaly.status` open/confirmed/dismissed, a detail drawer, `GET /anomalies/{id}`, `?selected=<id>` deep-link). This slice adds **proactive alerting**: tenant admins are notified — immediately in-app and via a daily email digest — when the engine writes a new **high/critical** anomaly, so fraud surfaces without anyone hunting for it. **Per-tenant rule config (Slice 3)** is out of scope — see `docs/todos/anomaly-fraud-detection-slices.md`.

---

## Problem

The fraud engine silently writes `Anomaly` rows. Today nothing tells a human a high-risk flag exists — the only way to find one is to open the `/anomalies` page and look. A fraud signal that no one sees is worthless. We need to push high/critical anomalies to the people who can act on them (tenant admins), deep-linked into the Slice-1 review drawer, without flooding inboxes or the notification bell.

Two delivery constraints shape the design:

- **Immediacy for the normal path.** When a single invoice/expense is audited and flagged high/critical, an admin should see it in-app right away.
- **Flood control for bulk reprocess.** Super-admin "reprocess all" (`reprocess_mode=True`) can produce hundreds of anomalies in one pass. Per-anomaly immediate alerts would bury the bell. Those must be caught by the **daily email digest** instead — one batched email — never by immediate in-app.

## Goal

Notify tenant admins of new **high/critical, open** anomalies through two channels — **immediate in-app** (normal audit path) and a **daily email digest** (catches everything, including bulk reprocess) — each gated by a per-user preference, de-duplicated so the same anomaly never alerts twice, and respecting Slice-1 resolution state (resolved items never alert).

**Non-goals (Slice 2):** per-tenant rule enable/disable + threshold tuning (Slice 3); per-anomaly email (digest only); SMS / push / Slack channels; escalation chains; configurable severity threshold (fixed at high+critical this slice); new alert UI beyond reusing the Slice-1 drawer.

---

## Architecture

### Delivery model (the two channels)

| Channel | Trigger | Audience | Flood control |
|---|---|---|---|
| **Immediate in-app** | audit worker, per new high/critical open anomaly, **`reprocess_mode=False` only** | tenant admins (per-user pref) | `Anomaly.alerted_at` de-dup; reprocess suppressed |
| **Daily email digest** | scheduled per-tenant job (existing background loop) | tenant admins (per-user pref) | per-tenant watermark — each anomaly emailed once |

**Recipients** for both channels are tenant **admins** (`User.role == "admin"`), each independently gated by `should_send_notification(user_id, "anomaly_alert", channel)`.

**Severity threshold** is fixed at `risk_level in {"high", "critical"}` this slice (Slice 3 makes it configurable). Only `status == "open"` anomalies alert.

**Commercial gating:** alerting belongs to the `anomaly_detection` commercial module. The immediate path fires only inside the audit worker (which runs only when an audit was triggered — already gated upstream). The digest checks the tenant's `anomaly_detection` feature and skips when disabled.

### 1. Notification preference — `EmailNotificationSettings` (`api/core/models/email_notifications.py`)

Add one boolean column:

- `anomaly_alert = Column(Boolean, default=True)` — admin opt-out for both channels.

`should_send_notification(user_id, "anomaly_alert", channel)` already does `getattr(settings, event_type, False)` and only special-cases `expense_*` / `approval_*` prefixes — so `anomaly_alert` works for both `"email"` and `"in_app"` with no special handling. The column is additive on the per-tenant `email_notification_settings` table; add it through the existing idempotent per-tenant column-ensure path (the same mechanism as `ensure_expense_digest_preference_columns`), **not** alembic. `EmailNotificationSettingsSchema` (the Pydantic response/update model) gains the field so the settings UI can toggle it.

### 2. De-dup marker — `Anomaly` (`api/core/models/models_per_tenant.py`)

Add one nullable timestamp:

- `alerted_at = Column(DateTime(timezone=True), nullable=True)` — set when the **immediate in-app** alert fires for this row; guards against double-firing (Kafka is at-least-once, so a redelivered audit message must not re-alert).

Added through the existing **`db_init.py::ensure_tenant_required_columns` anomalies block** (idempotent `ADD COLUMN`, same path Slice 1 used for `status`/`resolution_note`) — the `anomalies` table is **not** alembic-managed.

The daily digest does **not** need a per-row flag: it uses a per-tenant watermark (below), so re-scoring or new rows are emailed exactly once by time window.

### 3. Immediate in-app — `AnomalyAlertService` (`api/commercial/anomaly_detection/alert_service.py`, new)

A small, testable service that turns a batch of freshly-created anomalies into in-app notifications:

```python
class AnomalyAlertService:
    def __init__(self, db: Session): ...

    def notify_new_anomalies(
        self, anomalies: list[Anomaly], reprocess_mode: bool
    ) -> dict:
        """Fire immediate in-app alerts for new high/critical open anomalies.
        Returns {"alerted": int, "skipped": int}."""
```

Logic, per anomaly:
- Skip if `reprocess_mode` is True (digest will catch it).
- Skip unless `risk_level in {"high","critical"}` and `status == "open"` and `alerted_at is None`.
- Resolve tenant admins (`User.role == "admin"`). For each admin, if `NotificationService(db).should_send_notification(admin.id, "anomaly_alert", "in_app")`, write a **system** `ReminderNotification`:
  - `reminder_id=None` (the model already allows null for system notifications), `user_id=admin.id`, `notification_type="anomaly_alert"`, `channel="in_app"`, `is_sent=True`, `sent_at=now`, `scheduled_for=now`,
  - `subject = f"{risk_level.title()}-risk anomaly on {entity_label} #{anomaly.id}"` — the `#{anomaly.id}` is what the UI's `extractResourceId` parses to build the deep-link,
  - `message` = the anomaly's `reason` (truncated).
- After fanning out, set `anomaly.alerted_at = now`.
- One `db.commit()` for the batch.

**Wiring (`api/workers/audit_consumer.py::_process_message`):** `analyze_entity` already returns `created_anomalies: list[Anomaly]`. Capture that return value and call `AnomalyAlertService(tenant_session).notify_new_anomalies(created_anomalies, reprocess_mode=reprocess_mode)` before the session closes. The worker stays thin; all logic and tests live in the service.

> **Why `ReminderNotification`, not `create_in_app_notification`:** the bell feed (`InAppNotifications.tsx` via `reminderApi`) reads `ReminderNotification` rows. `NotificationService.create_in_app_notification` is currently a logging stub that writes nothing — so it would not reach the bell. We write the row directly, following the existing system-notification pattern in `reminders.py`.

### 4. Daily email digest — `AnomalyDigestService` (`api/core/services/anomaly_digest_service.py`, new)

Mirrors `ExpenseDigestService` (tenant-level digest with a `Settings`-row runtime watermark):

```python
class AnomalyDigestService:
    RUNTIME_KEY = "anomaly_digest_runtime"   # Settings row holding {"last_run_at": iso}

    def __init__(self, db: Session, email_service: Optional[EmailService] = None): ...

    def process_due_digest(self, force: bool = False) -> dict:
        """Send the daily anomaly digest to admins if due.
        Returns {"status": "skipped"|"sent"|"empty", ...}."""
```

Logic:
1. **Feature gate:** if the tenant's `anomaly_detection` feature is disabled → `{"status":"skipped","reason":"feature_disabled"}`.
2. **Due check:** load `last_run_at` from the runtime Settings row; if `not force` and `< 24h` since `last_run_at` → `{"status":"skipped","reason":"not_due"}`. (Fixed daily cadence this slice — no per-interval config; Slice 3 territory.)
3. **Select:** `Anomaly` where `status == "open"` AND `risk_level in ("high","critical")` AND `created_at > last_run_at` (first ever run: `created_at` within the last 24h), newest first.
4. If empty → advance watermark to `now`, return `{"status":"empty"}`.
5. **Send:** recipients = admins (`User.role == "admin"`). For each, if `should_send_notification(admin.id, "anomaly_alert", "email")`, send **one** digest email summarizing the batch (count by severity + a row per anomaly: risk, reason, entity label, deep-link to `/anomalies?selected=<id>`).
6. **Advance** the watermark to `now` regardless of per-user opt-outs (the window was processed), then commit.

Digest is **email-only** — the immediate channel owns in-app; bulk-reprocess items deliberately have no in-app entry (flood control) and the digest email is their catch-all.

**Email template (`api/core/services/notification_templates.py`):** add `ANOMALY_DIGEST_HTML_TEMPLATE` + `ANOMALY_DIGEST_TEXT_TEMPLATE`, rendered with **Jinja2 autoescape on** (consistent with the stored-XSS hardening already applied to this module) since `reason`/entity labels are user/AI-influenced text. The digest email is composed and sent via the existing `EmailService`.

**Scheduler wiring (`api/core/services/reminder_background_service.py`):** add `_process_anomaly_digest(db, tenant_id)` mirroring the existing `_process_expense_digest` (reuse the `email_config` Settings → `EmailService` build), call it in the per-tenant loop right after the expense digest, and include its stats in the returned dict. No new scheduler — the loop already started at `main.py:278` drives it.

### 5. Frontend

**`ui/src/components/reminders/InAppNotifications.tsx`:** add one branch to `handleNotificationClick` for `notification_type === "anomaly_alert"` → parse the id via the existing `extractResourceId(subject)` and `window.location.href = '/anomalies?selected=' + id` (the Slice-1 drawer opens on that param). Mark-as-read + close, matching the existing branches.

**`ui/src/components/settings/NotificationsTab.tsx`:** add an **"Anomaly / fraud alerts"** toggle bound to the new `anomaly_alert` field (the settings GET/PUT already round-trip the whole `EmailNotificationSettings` object; the field appears once it's in the schema).

No new pages or components — the alert deep-links into the Slice-1 drawer; the bell already renders `ReminderNotification` rows.

### Data flow

```
NORMAL PATH
audit worker → analyze_entity() → [Anomaly(open, high/critical)]
  → AnomalyAlertService.notify_new_anomalies(anomalies, reprocess_mode=False)
     → per admin (pref on): ReminderNotification(type="anomaly_alert", "#<id>" in subject)
     → anomaly.alerted_at = now
  → bell shows it → click → /anomalies?selected=<id> → Slice-1 drawer

BULK REPROCESS (reprocess_mode=True)
audit worker → [many Anomaly] → notify_new_anomalies(..., reprocess_mode=True) → NO in-app

DAILY (background loop, per tenant)
AnomalyDigestService.process_due_digest()
  → open high/critical since watermark → one email per admin (pref on) w/ deep-links
  → advance watermark
```

---

## Testing

**`AnomalyAlertService` (in-container, `db_session`):**
- Fires for a new **high** and **critical** open anomaly; writes one `ReminderNotification` (`notification_type="anomaly_alert"`, `channel="in_app"`, `subject` contains `#<id>`) per admin; sets `alerted_at`.
- **Skips** `low`/`medium`; skips when `status != "open"`; skips when `alerted_at` already set (de-dup); skips entirely when `reprocess_mode=True`.
- **Recipients:** only `role == "admin"` users receive a row — `user`/`viewer` do not.
- **Preference:** an admin with `anomaly_alert=False` gets no row; others still do.

**`AnomalyDigestService` (in-container):**
- Selects only open high/critical with `created_at > last_run_at`; excludes resolved (`status != "open"`) and low/medium.
- Sends one email per opted-in admin; advances the watermark so a second immediate run returns `not_due` / emails nothing new.
- `feature_disabled` → skipped; empty window → `empty` + watermark advanced.

**Preference gating (`should_send_notification`):** `anomaly_alert` honored for both `"email"` and `"in_app"`; defaults on for a fresh settings row.

**Frontend (vitest):**
- `InAppNotifications` routes an `anomaly_alert` notification (subject `"…#42"`) to `/anomalies?selected=42` and marks it read.
- `NotificationsTab` renders the Anomaly-alerts toggle and round-trips its value on save.

## Risks & mitigations

- **Bulk-reprocess flood** — immediate in-app is hard-suppressed when `reprocess_mode=True`; those anomalies surface only in the next daily digest (one email). Mitigated by design.
- **Kafka at-least-once redelivery** — `alerted_at` guards immediate alerts; the digest is windowed by a watermark — neither re-alerts on replay.
- **Schema change across tenant DBs** — both additions are additive nullable/boolean columns via the existing idempotent per-tenant ensure paths (`anomalies` via `db_init`, `email_notification_settings` via the digest-preference ensure path); no alembic, no backfill needed.
- **Stale `last_run_at` on a brand-new tenant** — first run has no watermark; bound the initial window to the last 24h so a fresh tenant doesn't email its entire anomaly history.
- **Untrusted text in the digest email** — Jinja2 autoescape on; deep-links built from integer ids only.

## What Slice 3 adds

- **Per-tenant rule config:** enable/disable the 7 rules + tune thresholds, and make the alert **severity threshold** (fixed at high+critical here) and the digest **cadence** (fixed daily here) configurable.
