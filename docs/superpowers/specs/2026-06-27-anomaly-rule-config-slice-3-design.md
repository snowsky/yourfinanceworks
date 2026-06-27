# Anomaly / Fraud Detection — Slice 3: Per-tenant Rule Config (Design)

**Date:** 2026-06-27
**Feature:** Competitor #4 — AI anomaly / fraud detection.
**Slice:** 3 of 3 (final). Builds on Slice 1 (triage, PR #423) and Slice 2 (proactive alerting, PR #424).
**Goal:** Give each tenant control over detection sensitivity / noise — enable or disable individual rules and tune the meaningful numeric thresholds — without touching the detection engine's structure.

---

## Background (already in place — build on this, don't re-derive)

- **Engine:** `api/commercial/anomaly_detection/service.py` — `AnomalyDetectionService` orchestrates 7 modular rules in `rules/`. Rules subclass `BaseAnomalyRule` (`base.py`), expose `rule_id`/`name`/`description`, and implement `async analyze(db, entity, entity_type, context) -> Optional[AnomalyResult]`.
- **`_rules` is a class-level cached list** built once in `_initialize_rules`. `analyze()` already receives a per-call `context` dict (currently AI config, attachments, timestamps). This is the injection point for config — **no per-tenant rule instances needed**.
- **Hardcoded constants today:**
  - `rounding_anomaly`: flags round amounts `> 250`.
  - `threshold_splitting`: `THRESHOLDS = [100, 250, 500, 1000, 2500, 5000]`, proximity `> t * 0.8`, fires when `recent_count >= 2` (3 total).
  - `temporal_anomaly`: weekend, or hour `< 7` or `> 20`.
  - The other 4 (`duplicate_billing`, `phantom_vendor`, `description_mismatch`, `attachment_audit`) are logic/AI-based with no single meaningful exposable number.
- **Settings-row pattern** (`api/core/services/invoice_branding.py`): a single tenant-DB `Settings` row keyed by a string, with a service that merges over defaults (clamp/re-validate on read) and validates on write. This is the template to mirror.
- **Tenant API:** `core/routers/anomalies.py` (`GET /anomalies`, `PATCH /anomalies/{id}/dismiss`, `POST /anomalies/{id}/resolve`, `GET /anomalies/{id}`), all gated by `get_current_user`.
- **RBAC helper:** `core/utils/rbac.py::require_admin_or_superuser(current_user, action)` — raises 403 otherwise. Used across license/notifications/sync routers.
- **Feature flag:** `anomaly_detection` (commercial-gated) via `FeatureConfigService.is_enabled`.
- **Frontend:** `ui/src/pages/Anomalies.tsx` ("Fraud Checks"), `lib/api/anomalies.ts`.

---

## Decisions (locked during brainstorm)

1. **Scope:** Toggles for all 7 rules + numeric tuning for the 3 rules that have meaningful numbers + a global `min_risk_score` floor. (Full spec scope.)
2. **Effect of disabling / tightening:** **Future-only.** Config changes affect only new audits. Existing `Anomaly` rows are never mutated, hidden, or deleted; reviewers clear the backlog through the normal triage flow. Fully reversible.
3. **Access control:** **Admin/owner only** for writes — `require_admin_or_superuser`. Reads stay `get_current_user` so the engine and any tenant user can see effective config.
4. **Validation:** **Bounded ranges** on write (422 on out-of-range), with **clamp-on-read** as defence-in-depth.

---

## 1. Persistence — `api/core/services/anomaly_rule_config.py`

A single tenant-DB `Settings` row under key `anomaly_rule_config`. **An absent or empty row means exactly today's behavior** (defaults encode the current hardcoded constants).

### Config shape

```json
{
  "min_risk_score": 0,
  "rules": {
    "duplicate_billing":    {"enabled": true},
    "rounding_anomaly":     {"enabled": true, "min_amount": 250},
    "phantom_vendor":       {"enabled": true},
    "threshold_splitting":  {"enabled": true, "min_count": 3, "proximity_pct": 0.8},
    "temporal_anomaly":     {"enabled": true, "start_hour": 7, "end_hour": 20, "flag_weekend": true},
    "description_mismatch": {"enabled": true},
    "attachment_audit":     {"enabled": true}
  }
}
```

Notes on field semantics:
- `min_risk_score` — global floor; a rule result with `risk_score < min_risk_score` is discarded (not recorded).
- `threshold_splitting.min_count` — **total** transactions (incl. the entity) required to fire; engine compares `recent_count + 1 >= min_count`. Default 3 (matches `recent_count >= 2`).
- `threshold_splitting.proximity_pct` — lower bound of the "just below" band, `amount > t * proximity_pct`.
- `temporal_anomaly.start_hour`/`end_hour` — normal business hours; flag when `hour < start_hour or hour >= end_hour`. `flag_weekend` toggles the weekend component independently.

### Functions (mirror `invoice_branding.py`)

- `DEFAULT_ANOMALY_RULE_CONFIG: Dict[str, Any]` — the dict above.
- `RULE_IDS` — the 7 canonical rule ids (single source of truth; also lets the engine/validator stay in sync).
- `get_anomaly_rule_config(db) -> Dict[str, Any]`
  - Read the `Settings` row, deep-merge over defaults (per-rule dicts merged, not replaced).
  - **Clamp-on-read:** coerce every numeric into its valid range; coerce `enabled`/`flag_weekend` to bool; if a stored value is the wrong type or a rule key is unknown, fall back to default. Guarantees the engine never sees a nonsensical value regardless of how the row got there.
- `validate_anomaly_rule_config(value) -> Dict[str, Any]`
  - Must be a dict; unknown top-level and unknown rule keys dropped; unknown per-rule sub-keys dropped.
  - **Bounded ranges (422 via `ValueError` on violation):**
    - `min_risk_score`: number in `[0, 100]`.
    - `rounding_anomaly.min_amount`: number `>= 0`.
    - `threshold_splitting.min_count`: int `>= 2`.
    - `threshold_splitting.proximity_pct`: number in `[0.5, 1.0]`.
    - `temporal_anomaly.start_hour`/`end_hour`: ints in `[0, 23]`, with `start_hour < end_hour`.
    - all `enabled` and `flag_weekend`: coerced to bool.
  - Returns a cleaned dict containing only provided, valid keys (partial updates supported — merged over existing/defaults at write time).

## 2. Engine integration — `service.py` (future-only)

In `AnomalyDetectionService.analyze_entity`, after the feature-enabled / already-audited guards:

1. `rule_config = get_anomaly_rule_config(self.db)` — once per audit.
2. Add to the existing `context`: `context["rule_config"] = rule_config`.
3. In the rule loop, **skip** any rule whose `rule_config["rules"][rule.rule_id]["enabled"]` is `False`.
4. After a rule returns an `AnomalyResult`, **discard** it when `result.risk_score < rule_config["min_risk_score"]` (don't save, don't append).

The 3 tunable rules read their own sub-config from `context["rule_config"]["rules"][<rule_id>]`, each key falling back to its current hardcoded constant when absent (so a rule still works if called without config, e.g. in isolation tests). The class-level `_rules` cache is **untouched** — config flows purely through `context`. No existing `Anomaly` row is read or mutated.

## 3. API — `core/routers/anomalies.py`

- `GET /anomalies/config`
  - `get_current_user` + commercial gate (`anomaly_detection`).
  - Returns `get_anomaly_rule_config(db)`.
- `PUT /anomalies/config`
  - `require_admin_or_superuser(current_user, "update anomaly rule config")` + commercial gate.
  - Body validated via `validate_anomaly_rule_config`; on `ValueError` → 422.
  - Upsert the `Settings` row (merge cleaned payload over existing value), set `category="features"`, write an audit-log entry (mirror the `invoice_branding` write in `settings.py`).
  - Return the merged effective config.

(Place the `/config` routes **before** `/{anomaly_id}` path routes so `config` isn't captured as an id — same care taken in Slice 1 with the `status` param.)

## 4. Frontend

- `ui/src/lib/api/anomalies.ts` — add `getAnomalyConfig()` and `updateAnomalyConfig(payload)` typed against the config shape.
- `ui/src/pages/Anomalies.tsx` — add a collapsible **"Detection settings"** panel (gear) on the existing Fraud Checks page:
  - A row per rule (label from `rule.name`/description) with an enable toggle.
  - Inline numeric inputs for the 3 tunable rules, shown under their row.
  - A global "Minimum risk score to record" input.
  - TanStack Query: `useQuery` for config, `useMutation` for save (invalidate on success), toast on save / validation error.
  - Admin-only: hide or disable the panel's Save for non-admins (match the API gate); reuse whatever admin/role check the page/UI already has access to.

## 5. Testing (TDD)

**Service** (`test_anomaly_rule_config.py`):
- Absent row → returns defaults equal to current behavior.
- Deep-merge: partial stored row merges per-rule without dropping sibling defaults.
- `validate_*`: rejects out-of-range (`min_risk_score` 150, `start_hour >= end_hour`, `proximity_pct` 0.2, `min_count` 1), drops unknown keys, coerces bools.
- `get_*` clamp-on-read: a poisoned stored value (wrong type / out of range) returns the clamped/default value.

**Engine** (extend `test_anomaly_detection_integration.py`):
- Disabled rule → produces no anomaly for an entity that would otherwise trip it.
- Tuned threshold changes outcome (e.g. `rounding_anomaly.min_amount` raised above the entity's amount → no flag; `temporal_anomaly` hours widened → no flag).
- `min_risk_score` floor → a low-score result is dropped while a high-score one survives.
- Absent config row → identical results to pre-Slice-3 behavior (regression guard).

**Router** (extend `test_anomalies_router.py`):
- `GET /anomalies/config` → defaults when unset; reflects a written value.
- `PUT` as admin → 200 + persists; as non-admin → 403; invalid body → 422.
- Commercial gate enforced on both.

---

## Out of scope (YAGNI)

- Hiding/deleting existing anomalies on config change (decision: future-only).
- Per-rule risk-score overrides or custom risk levels.
- Custom approval-threshold *lists* for `threshold_splitting` (kept as the built-in ladder; only `min_count`/`proximity_pct` exposed).
- Tuning the 4 logic/AI rules beyond enable/disable.
- Config UI in Super Admin (this is the per-tenant slice).
