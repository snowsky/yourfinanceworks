# AI Anomaly / Fraud Detection — Remaining Slices (TODO)

**Feature:** Competitor #4 — AI anomaly / fraud detection (duplicate invoices, miscodes, unusual txns).
**Status:** Engine + pipeline ~90% built. Slicing the gaps; **Slice 1 (richer triage) being built first**.

**What's already in place (build on this, don't re-derive):**
- Engine: `api/commercial/anomaly_detection/` — `AnomalyDetectionService` + 7 rules (duplicate_billing, rounding_anomaly, phantom_vendor, threshold_splitting, temporal_anomaly, description_mismatch, attachment_audit) + AI multimodal audit via LiteLLM (`base.py::_run_ai_audit`).
- Pipeline: Kafka — `core/utils/anomaly_trigger.py::trigger_anomaly_audit` → `publish_fraud_audit_task` → `workers/audit_consumer.py` runs `analyze_entity`. Auto-triggered on invoice create/update (`routers/invoices/crud.py`), expense create/update (`routers/expenses/crud.py`), and OCR ingestion.
- Super admin: bulk audit + reprocess + cross-tenant aggregator (`routers/super_admin/system.py`, `ui/.../SuperAdmin/AnomaliesTab.tsx`).
- Model: `Anomaly` in `models_per_tenant.py` (risk_score, risk_level, reason, rule_id, details JSON, is_dismissed, dismissed_at, dismissed_by_id, dismiss_notes).
- Tenant API: `core/routers/anomalies.py` — `GET /anomalies` (summary + filters + bank-txn deep-link) + `PATCH /anomalies/{id}/dismiss`.
- Frontend: `ui/src/pages/Anomalies.tsx` ("Fraud Checks"), `components/dashboard/AnomalyInsightsCard.tsx`, `lib/anomaly-ui.ts`, `lib/api/anomalies.ts`.
- Feature flag: `anomaly_detection` (commercial-gated).
- Tests: `test_anomalies_router.py`, `test_anomaly_detection_integration.py`.

---

## Slice 2 — Proactive alerting (build AFTER triage)

Surface fraud without anyone hunting for it. Notify on **new high/critical** anomalies:
- In-app notification + email (likely a digest, not per-event, to avoid noise) when the audit worker writes a high/critical `Anomaly`.
- Deep-link the alert into the **Slice-1 review view** (anomaly detail / review queue).
- Respect resolution state from Slice 1 — never alert on already confirmed/dismissed items; de-dupe so the same entity re-scored doesn't re-alert.
- Reuse the existing notification infra (notifications service / email_service); commercial-gated under `anomaly_detection`.
- **Decisions for its brainstorm:** per-event vs digest cadence; who gets notified (admins only?); threshold (high+critical only, or configurable); in-app only vs in-app+email.

## Slice 3 — Per-tenant rule config (build LAST)

Settings UI to control detection sensitivity / noise:
- Enable/disable individual rules (the 7 above).
- Tune thresholds: threshold-splitting amount, rounding tolerance, temporal window, risk-score cut-offs.
- Persist per-tenant (likely a Settings row, mirroring `invoice_branding`); the engine's `_initialize_rules` + each rule reads its config.
- **Decisions for its brainstorm:** which thresholds are worth exposing; whether disabling a rule suppresses existing anomalies or only future ones; defaults.

---

## Follow-up from Slice 1 final review (capture for Slice 2/3)
- Re-resolution overwrites the audit fields (`resolved_at`/`resolved_by_id`/`resolution_note`) with no history, and the detail drawer shows Confirm/Dismiss even on already-resolved items (Slice 1 deliberately allows re-resolving). Consider: disable/hide the resolution buttons when `anomaly.status !== 'open'`, or keep a small resolution-history trail. Low priority; acceptable for a record-only single-reviewer slice.
