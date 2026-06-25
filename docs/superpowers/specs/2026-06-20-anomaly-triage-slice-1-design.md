# Anomaly / Fraud Detection — Triage Workflow (Slice 1) Design Spec

**Date:** 2026-06-20
**Status:** Approved design → ready for implementation planning
**Scope:** Slice 1 of competitor feature #4 (AI anomaly / fraud detection). The detection **engine + pipeline are already built** (`api/commercial/anomaly_detection/`, Kafka audit worker, auto-triggers, `Anomaly` model, a list/dismiss router, a `/anomalies` page, a dashboard card). This slice adds a **richer triage workflow**: an anomaly **detail view** and a real **resolution model** (open → confirmed / dismissed) so the flat list becomes a review queue. **Proactive alerting (Slice 2)** and **per-tenant rule config (Slice 3)** are out of scope — see `docs/todos/anomaly-fraud-detection-slices.md`.

---

## Problem

The fraud engine writes rich `Anomaly` rows (risk score/level, reason, `rule_id`, and a `details` JSON of evidence + AI reasoning), but the tenant-facing surface throws most of it away:

- The `/anomalies` page (`ui/src/pages/Anomalies.tsx`) is a flat table — risk badge, reason, `rule_id`, entity link, date — with a single **"dismiss"** button that calls the API **without a note**. The `details` JSON (the actual evidence) is **never shown**.
- The only resolution is a binary **dismiss** (`Anomaly.is_dismissed`). There is **no way to mark an anomaly "confirmed real"** vs. "false positive" — so a reviewer cannot record a real finding, only make flags disappear.

A fraud reviewer needs to (1) see *why* something was flagged, and (2) record an outcome that distinguishes a true problem from a false alarm. That outcome is also what Slice 2's alerting will treat as "handled."

## Goal

Turn the anomaly list into a **review queue**: open the evidence, then resolve each item as **confirmed** (true positive) or **dismissed** (false positive) with an optional note — auditable (who/when), and backward-compatible with the existing engine and super-admin views.

**Non-goals (Slice 1):** notifications/alerting on new anomalies (Slice 2); per-tenant rule enable/disable + thresholds (Slice 3); auto-actions on confirm (void invoice, flag vendor); assignee / comment threads; bulk resolve; bespoke per-rule evidence layouts.

---

## Architecture

### 1. Data model — `Anomaly` (`api/core/models/models_per_tenant.py`)

Add a `status` column as the source of truth, generalizing the existing `is_dismissed` boolean:

- `status` `String(20)`, `nullable=False`, `default="open"`, indexed — one of `open` / `confirmed` / `dismissed`.
- `resolution_note` `Text`, nullable — the reason captured when resolving (either outcome).
- The existing `dismissed_at` / `dismissed_by_id` columns are **reused as the resolution audit fields** (who/when resolved, either outcome). Keep the column names (no rename, to avoid a destructive migration); the API/UI treat them as `resolved_at` / `resolved_by_id`. The existing `dismiss_notes` is superseded by `resolution_note` (kept for back-compat; new writes use `resolution_note`).
- `is_dismissed` is **kept** and maintained as a derived mirror: on every resolve, `is_dismissed = (status != "open")`. This keeps the legacy cross-tenant super-admin aggregator (`routers/super_admin/system.py`) and any other `is_dismissed` reader working unchanged.

**Backfill (per-tenant migration):** existing rows get `status = "dismissed"` where `is_dismissed == True`, else `status = "open"`. Applied through the project's existing per-tenant schema/migration path (`db_init.py`). No data loss; `confirmed` is only ever set by the new resolve action going forward.

### 2. API — `api/core/routers/anomalies.py`

- **`PATCH /anomalies/{id}/resolve`** — body `ResolveAnomalyRequest { status: "confirmed" | "dismissed", note: Optional[str] }`. Rejects any other `status` (422). Sets `status`, `dismissed_at = now`, `dismissed_by_id = current_user.id`, `resolution_note = note`, and `is_dismissed = (status != "open")`. Licensing-gated (same `anomaly_detection` check as the rest of the router). Returns the updated anomaly's `id` + `status`.
- **`GET /anomalies/{id}`** — returns one anomaly (same serialized shape as a list item, including the bank-txn `statement_id` deep-link resolution). Lets the drawer open by id even when the item isn't on the current page (needed for Slice 2 deep-links and for refresh-on-`?selected=`). 404 if not found; licensing-gated.
- **`GET /anomalies`** — add a `status: Optional[str]` query param (defaults to `open`). When provided, filter by `status`; for backward-compatibility the existing `is_dismissed` param still works when `status` is omitted. The `summary` block continues to count **open** items only (today it counts `is_dismissed == False`; with the backfill, open == not-resolved, so the count's meaning is preserved). Items are serialized with the new `status`, `resolution_note`, `resolved_at` (from `dismissed_at`), and `resolved_by_id` (from `dismissed_by_id`) fields added.
- **`PATCH /anomalies/{id}/dismiss`** — kept as a thin alias that calls the same resolution logic with `status="dismissed"` (back-compat for any existing caller). The UI stops using it in favor of `/resolve`.

### 3. Frontend

**`ui/src/lib/api/anomalies.ts`:**
- Extend the `Anomaly` type with `status: 'open' | 'confirmed' | 'dismissed'`, `resolution_note?: string | null`, `resolved_at?: string | null`.
- `list(params)` gains `status?: string`.
- Add `get(id) -> Anomaly` and `resolve(id, status, note?) -> { id; status }`. Keep `dismiss` (now unused by the page) for back-compat.

**`ui/src/pages/Anomalies.tsx`:**
- Add **filter tabs: Open · Confirmed · Dismissed** (default Open); the active tab drives `list({ status })`. The header count reflects the active filter's `total`.
- Clicking a row opens a **`Sheet` drawer**, URL-addressable via `?selected=<id>` (read/write the search param so the drawer is deep-linkable and survives refresh; on mount with `?selected=`, fetch via `get(id)`).
- The dismiss-only action column is replaced by opening the drawer; the table stays a scannable index (risk, reason/rule, item link, date, status badge).

**`ui/src/components/anomalies/AnomalyDetailDrawer.tsx` (new):**
- Shows risk level + score, reason, `rule_id`, detected date, a link to the offending invoice/expense (reusing `entityHref`/`entityLabel` from `lib/anomaly-ui.ts`), and a **generic key/value render of the `details` JSON** (flatten one level; show nested objects/arrays as readable JSON). Robust to whatever shape a rule or the AI audit emits — no per-rule layout.
- Resolution controls: **Confirm (real)** and **Dismiss (false positive)** buttons plus an optional **note** textarea → call `resolve(id, status, note)`. On success, invalidate the `anomalies` queries, toast, and close the drawer. For already-resolved items, show the recorded outcome + note + who/when, and allow re-resolving (status change).

**`ui/src/components/dashboard/AnomalyInsightsCard.tsx` + sidebar badge:** unchanged in behavior — they already key off the open summary/count, which still means "needs review."

### Data flow

```
audit worker → Anomaly(status="open")  (unchanged engine)
list page (tab=Open) → GET /anomalies?status=open → table
row click → drawer (?selected=id) → GET /anomalies/{id} → evidence + actions
Confirm/Dismiss → PATCH /anomalies/{id}/resolve {status, note}
   → status + resolved_at/by + resolution_note + is_dismissed mirror
   → item leaves Open, appears under Confirmed/Dismissed tab
```

---

## Testing

- **Model/backfill:** a `dismissed`-mirrored row backfills to `status="dismissed"`; a fresh row defaults to `status="open"`.
- **Router (integration, in-container):**
  - `resolve` with `status="confirmed"` sets `status`, `resolved_at`/`resolved_by_id`, `resolution_note`, and `is_dismissed=True`; an invalid `status` (anything other than `confirmed`/`dismissed`, e.g. `"open"` or `"bogus"`) → 422.
  - `resolve` with `status="dismissed"` mirrors `is_dismissed=True`.
  - `GET /anomalies/{id}` returns the item (and `statement_id` for a bank-txn anomaly); 404 for a missing id.
  - `GET /anomalies?status=confirmed` returns only confirmed; default (no `status`) returns open; `summary` counts open only.
  - `dismiss` alias still resolves to `status="dismissed"`.
  - Licensing gate returns 403 when the feature is disabled.
- **Frontend (vitest):** tabs switch the `status` filter; clicking a row opens the drawer and sets `?selected=`; Confirm/Dismiss call `resolve` with the chosen status + note; an opened `?selected=<id>` fetches via `get`.

## Risks & mitigations

- **Schema change across tenant DBs** — additive columns + a safe backfill via the existing per-tenant migration path; `is_dismissed` kept as a derived mirror so no existing reader breaks.
- **Heterogeneous `details` JSON** — rendered generically (key/value + JSON fallback), never assuming a per-rule shape.
- **Back-compat of the list filter** — `status` defaults to `open` and the legacy `is_dismissed` param is preserved; the `summary` semantics are unchanged by the backfill.

## What later slices add

- **Slice 2 — proactive alerting:** notify (in-app + email/digest) on new high/critical anomalies, deep-linking into this slice's drawer (`?selected=`), respecting resolution state so handled items don't re-alert.
- **Slice 3 — per-tenant rule config:** enable/disable rules + tune thresholds.
