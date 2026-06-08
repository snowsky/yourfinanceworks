# Anomaly / Fraud Detection — Tenant-Facing Surfacing Plan

> **Status: ✅ Shipped (2026-06-08).** Delivered across PRs #344–#351.
> The plan below is retained for context; the checklist tracks what landed.
>
> | Step | Status | PR |
> | --- | --- | --- |
> | 1. Tenant read endpoint (`GET /anomalies`) | ✅ | #344 |
> | 2. Dismiss endpoint (`PATCH /anomalies/{id}/dismiss`) | ✅ | #345 |
> | 3. Live trigger on invoice/expense writes | ✅ | #345 |
> | 4. Read-path is precomputed-rows only (fast) | ✅ | #344 |
> | 5. Dashboard card | ✅ | #344 |
> | 6. Detail panel + dismiss UI | ✅ (full `/anomalies` page) | #347 |
> | 7. Tests | ✅ (8 passing) | #350 |
>
> **Beyond the original plan:** sidebar nav entry (#349), per-entity deep-links
> incl. precise bank statement+transaction links (#346, #348, #351).
>
> **Deferred follow-ups:** i18n keys (still inline `t(key, fallback)`); a
> "bulk audit historical records" tenant action; email/notification on new
> critical anomalies. The shared pytest teardown also deletes `users` before
> `anomalies` — fine today (worked around in the anomaly tests) but worth a
> proper child-before-parent fix.

## Goal

Expose the **already-built** anomaly/fraud detection engine to ordinary tenant
users (today it is only readable by super-admins), so each tenant sees a live
"issues flagged on your recent invoices/expenses" panel on their dashboard,
with a triage (dismiss) workflow.

This is the #1 "quick visible win" from the competitor analysis
(`YourFinanceWORKS_competitor_features.xlsx`, Feature Matrix row *AI anomaly /
fraud detection*, Top Opportunities #4): detection is the hard part and it is
**done** — the remaining work is surfacing.

## Why this is small

The engine already persists results in a UI-ready, **per-tenant** shape. See
the existing super-admin/bank-statement trigger flow in
[`docs/technical-notes/fraud_detection_reprocess_flow.md`](../technical-notes/fraud_detection_reprocess_flow.md).

| Concern | Status |
| --- | --- |
| Detection rules (7) | ✅ Built — `api/commercial/anomaly_detection/rules/` |
| Orchestration | ✅ `AnomalyDetectionService.analyze_entity` (`api/commercial/anomaly_detection/service.py`) |
| Persistence (per-tenant) | ✅ `Anomaly` model in `api/core/models/models_per_tenant.py` |
| Triage / dismissal model | ✅ `is_dismissed`, `dismissed_by_id`, `dismissed_at`, `dismiss_notes` already on `Anomaly` |
| Async pipeline (Kafka + LiteLLM audit) | ✅ `publish_fraud_audit_task` → `api/workers/audit_consumer.py` |
| Feature gating | ✅ `FeatureConfigService.is_enabled('anomaly_detection')` (commercial feature) |
| **Tenant read endpoint** | ❌ Only `/super-admin/anomalies` exists (aggregates ALL tenants) |
| **Tenant dismiss endpoint** | ❌ Missing |
| **Live trigger on invoice/expense write** | ❌ Audits only fire from the super-admin bulk job / bank-statement OCR today |
| **Tenant UI** | ❌ Only `ui/src/pages/SuperAdmin/AnomaliesTab.tsx` (super-admin) |

### `Anomaly` fields available to the UI (no new modeling needed)

`entity_type` (`expense` / `invoice` / `bank_transaction`), `entity_id`,
`risk_score` (0–100), `risk_level` (low/medium/high/critical), `reason`
(human text), `rule_id`, `details` (JSON evidence, e.g. the duplicate's
invoice/expense ids), plus the dismissal columns above and timestamps.

## Plan

1. **Tenant-scoped read endpoint.**
   Add `GET /anomalies` to a tenant router (e.g. a new
   `api/core/routers/anomalies.py`, registered in `api/main.py`). Query the
   *current tenant's* `anomalies` table: filter `is_dismissed == False`,
   order by `risk_score` desc, paginate. The existing
   `@router.get("/anomalies")` in `api/core/routers/super_admin/system.py`
   (the cross-tenant aggregator) is the query template — just scope it to the
   resolved tenant session instead of looping all tenants.
   Gate behind `FeatureConfigService.is_enabled('anomaly_detection')`.

2. **Dismiss endpoint.**
   Add `PATCH /anomalies/{id}/dismiss` (accepts optional `dismiss_notes`).
   Set `is_dismissed=True`, `dismissed_at=now`, `dismissed_by_id=current_user`.
   All columns already exist on the model.

3. **Live trigger on tenant activity (the only net-new wiring).**
   In the invoice and expense create/update paths
   (`api/core/routers/invoices/crud.py`, `api/core/routers/expenses/crud.py`),
   add a fire-and-forget `publish_fraud_audit_task(tenant_id, "invoice"|"expense", id)`
   after a successful write. This mirrors how `ocr_consumer.py` already
   publishes per bank transaction. Keep it best-effort (try/except + log),
   never blocking the write. No-op when the worker/feature is off.

4. **Read-path performance note.**
   The dashboard card reads precomputed `Anomaly` rows only — **no AI/Kafka in
   the request path**, so it is always fast. The LiteLLM forensic audit runs
   out-of-band on write; the panel never blocks on it.

5. **Dashboard card (high-visibility surface).**
   Add an anomaly summary card to `ui/src/components/dashboard/ProfessionalDashboard.tsx`
   (e.g. "⚠ 3 issues flagged on recent invoices", colored by top `risk_level`).
   Respect the frontend feature flag (`isFeatureEnabled('anomaly_detection')`
   via `FeatureContext`); render nothing when disabled.

6. **Detail panel + dismiss UI.**
   Adapt `ui/src/pages/SuperAdmin/AnomaliesTab.tsx` (already typed `Anomaly`,
   with pagination + dismiss) into a tenant page/drawer. Each row links to its
   `entity_type`/`entity_id` (e.g. open the flagged invoice). Add a typed
   service module under `ui/src/lib/api/` for the two new endpoints.

7. **i18n + tests.**
   Inline `t(key, fallback)` strings (matching existing convention). Backend:
   pytest for the tenant read scoping (a tenant must NOT see another tenant's
   anomalies) and dismiss. Frontend: render/feature-flag tests for the card.

## Scope / effort

**Small–medium.** ~2 thin backend endpoints + 1 publish line per write path +
1 dashboard card and a panel adapted from the existing super-admin UI. No new
data model, no new detection logic.

## Monetization note

`anomaly_detection` is a **commercial** feature, so the tenant-facing surface
is a sellable premium capability for licensed tenants — not just a freebie.

## Out of scope (follow-ups)

- New detection rules / ML scoring improvements.
- Bulk "audit all historical invoices/expenses" tenant action (super-admin
  reprocess already exists for that).
- Email/notification on new critical anomalies (could reuse the reminder/
  notification service later).

## References

- Existing flow: [`docs/technical-notes/fraud_detection_reprocess_flow.md`](../technical-notes/fraud_detection_reprocess_flow.md)
- Competitor analysis: `YourFinanceWORKS_competitor_features.xlsx` (Top Opportunities #4)
- Related quick-wins shortlist discussed alongside: reminder cadences + late
  fees (#6), AI cash-flow forecast card (#8), invoice approval surfacing (#7).
