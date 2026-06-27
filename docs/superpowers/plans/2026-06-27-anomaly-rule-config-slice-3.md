# Anomaly Rule Config (Slice 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each tenant enable/disable the 7 anomaly rules and tune the meaningful numeric thresholds, controlling detection sensitivity without changing the engine's structure.

**Architecture:** A single tenant-DB `Settings` row (key `anomaly_rule_config`) holds the config, fronted by a service that mirrors `invoice_branding.py` (defaults-merge + clamp-on-read, validate-on-write with bounded ranges). The detection engine loads the config once per audit and injects it into the existing per-call `context` dict — skipping disabled rules and dropping sub-floor results. The 3 tunable rules read their thresholds from `context`, falling back to today's hardcoded constants. A new admin-gated `PUT /anomalies/config` + open `GET /anomalies/config` expose it; the Fraud Checks page gets a settings panel.

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant DB), Pydantic, pytest; React + TypeScript, TanStack Query v5.

## Global Constraints

- **Future-only:** config changes affect only new audits. Never read, mutate, hide, or delete existing `Anomaly` rows.
- **Commercial gate:** every config endpoint checks `FeatureConfigService.is_enabled("anomaly_detection", db=db)` → 403 with `"Anomaly detection is not available in your current license"`.
- **Writes are admin-only:** `require_admin_or_superuser(current_user, ...)` (from `core.utils.rbac`).
- **Absent/empty row = today's behavior exactly.** Defaults encode the current hardcoded constants.
- **Rule ids (7, canonical):** `duplicate_billing`, `rounding_anomaly`, `phantom_vendor`, `threshold_splitting`, `temporal_anomaly`, `description_mismatch`, `attachment_audit`.
- Python: PEP 8, type annotations on all signatures. Tests use `python -m pytest` in-container (per project test-deps note).
- Settings-row service pattern is `api/core/services/invoice_branding.py` — follow it.

---

## File Structure

- **Create** `api/core/services/anomaly_rule_config.py` — defaults, `RULE_IDS`, `get_anomaly_rule_config`, `validate_anomaly_rule_config`. (Tasks 1–2)
- **Create** `api/tests/test_anomaly_rule_config.py` — service unit tests. (Tasks 1–2)
- **Modify** `api/commercial/anomaly_detection/service.py` — load config, inject into `context`, skip disabled, apply `min_risk_score` floor. (Task 3)
- **Modify** `api/commercial/anomaly_detection/rules/rounding_anomaly.py`, `threshold_splitting.py`, `temporal_anomaly.py` — read thresholds from `context["rule_config"]`. (Task 4)
- **Modify** `api/tests/test_anomaly_detection_integration.py` — engine config behavior tests. (Tasks 3–4)
- **Modify** `api/core/routers/anomalies.py` — `GET`/`PUT /config`. (Task 5)
- **Modify** `api/tests/test_anomalies_router.py` — config endpoint tests. (Task 5)
- **Modify** `ui/src/lib/api/anomalies.ts` — config types + `getConfig`/`updateConfig`. (Task 6)
- **Modify** `ui/src/pages/Anomalies.tsx` — detection-settings panel. (Task 6)

---

## Task 1: Config service — defaults + validate

**Files:**
- Create: `api/core/services/anomaly_rule_config.py`
- Test: `api/tests/test_anomaly_rule_config.py`

**Interfaces:**
- Produces:
  - `DEFAULT_ANOMALY_RULE_CONFIG: dict` — full default config (shape below).
  - `RULE_IDS: tuple[str, ...]` — the 7 canonical ids.
  - `validate_anomaly_rule_config(value: dict) -> dict` — returns a cleaned dict containing only provided valid keys; raises `ValueError` on bad type / out-of-range.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_anomaly_rule_config.py
import pytest

from core.services.anomaly_rule_config import (
    DEFAULT_ANOMALY_RULE_CONFIG,
    RULE_IDS,
    validate_anomaly_rule_config,
)


def test_defaults_cover_all_seven_rules():
    assert set(DEFAULT_ANOMALY_RULE_CONFIG["rules"].keys()) == set(RULE_IDS)
    assert len(RULE_IDS) == 7
    assert DEFAULT_ANOMALY_RULE_CONFIG["min_risk_score"] == 0
    # Defaults encode today's hardcoded constants.
    rules = DEFAULT_ANOMALY_RULE_CONFIG["rules"]
    assert rules["rounding_anomaly"]["min_amount"] == 250
    assert rules["threshold_splitting"]["min_count"] == 3
    assert rules["threshold_splitting"]["proximity_pct"] == 0.8
    assert rules["temporal_anomaly"]["start_hour"] == 7
    assert rules["temporal_anomaly"]["end_hour"] == 20
    assert rules["temporal_anomaly"]["flag_weekend"] is True
    assert all(r["enabled"] is True for r in rules.values())


def test_validate_drops_unknown_keys():
    cleaned = validate_anomaly_rule_config(
        {"bogus": 1, "rules": {"not_a_rule": {"enabled": False},
                               "rounding_anomaly": {"enabled": False, "junk": 9}}}
    )
    assert "bogus" not in cleaned
    assert "not_a_rule" not in cleaned["rules"]
    assert cleaned["rules"]["rounding_anomaly"] == {"enabled": False}


def test_validate_coerces_bools():
    cleaned = validate_anomaly_rule_config(
        {"rules": {"temporal_anomaly": {"enabled": 1, "flag_weekend": 0}}}
    )
    assert cleaned["rules"]["temporal_anomaly"]["enabled"] is True
    assert cleaned["rules"]["temporal_anomaly"]["flag_weekend"] is False


@pytest.mark.parametrize("payload", [
    {"min_risk_score": 150},
    {"min_risk_score": -1},
    {"rules": {"rounding_anomaly": {"min_amount": -5}}},
    {"rules": {"threshold_splitting": {"min_count": 1}}},
    {"rules": {"threshold_splitting": {"proximity_pct": 0.2}}},
    {"rules": {"threshold_splitting": {"proximity_pct": 1.5}}},
    {"rules": {"temporal_anomaly": {"start_hour": -1}}},
    {"rules": {"temporal_anomaly": {"end_hour": 24}}},
    {"rules": {"temporal_anomaly": {"start_hour": 20, "end_hour": 7}}},
])
def test_validate_rejects_out_of_range(payload):
    with pytest.raises(ValueError):
        validate_anomaly_rule_config(payload)


def test_validate_rejects_non_dict():
    with pytest.raises(ValueError):
        validate_anomaly_rule_config([1, 2, 3])


def test_validate_partial_update_keeps_only_provided():
    cleaned = validate_anomaly_rule_config({"rules": {"phantom_vendor": {"enabled": False}}})
    assert cleaned == {"rules": {"phantom_vendor": {"enabled": False}}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomaly_rule_config.py -v --noconftest`
Expected: FAIL with `ModuleNotFoundError: core.services.anomaly_rule_config` (import error).

- [ ] **Step 3: Write the service module (defaults + validate only)**

```python
# api/core/services/anomaly_rule_config.py
"""Per-tenant anomaly detection rule configuration.

Stored as a single tenant-DB ``Settings`` row under the ``anomaly_rule_config``
key. Mirrors ``invoice_branding.py``: defaults encode today's hardcoded engine
behavior, reads merge over the defaults with clamp-on-read, writes validate with
bounded ranges. An absent/empty row therefore means exactly the current
behavior. Config changes are future-only — the engine consults this at audit
time and never mutates existing ``Anomaly`` rows.
"""

from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

ANOMALY_RULE_CONFIG_KEY = "anomaly_rule_config"

RULE_IDS: Tuple[str, ...] = (
    "duplicate_billing",
    "rounding_anomaly",
    "phantom_vendor",
    "threshold_splitting",
    "temporal_anomaly",
    "description_mismatch",
    "attachment_audit",
)

DEFAULT_ANOMALY_RULE_CONFIG: Dict[str, Any] = {
    "min_risk_score": 0,
    "rules": {
        "duplicate_billing": {"enabled": True},
        "rounding_anomaly": {"enabled": True, "min_amount": 250},
        "phantom_vendor": {"enabled": True},
        "threshold_splitting": {"enabled": True, "min_count": 3, "proximity_pct": 0.8},
        "temporal_anomaly": {
            "enabled": True,
            "start_hour": 7,
            "end_hour": 20,
            "flag_weekend": True,
        },
        "description_mismatch": {"enabled": True},
        "attachment_audit": {"enabled": True},
    },
}


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def validate_anomaly_rule_config(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an incoming (possibly partial) config payload.

    Unknown top-level keys, unknown rule ids, and unknown per-rule sub-keys are
    dropped. Numeric fields are bounded (raise ``ValueError`` out of range).
    Returns a cleaned dict containing only the provided, valid keys so callers
    can merge it over the existing stored value.
    """
    if not isinstance(value, dict):
        raise ValueError("anomaly_rule_config must be an object")

    cleaned: Dict[str, Any] = {}

    if value.get("min_risk_score") is not None:
        score = _as_number(value["min_risk_score"], "min_risk_score")
        if not (0 <= score <= 100):
            raise ValueError("min_risk_score must be between 0 and 100")
        cleaned["min_risk_score"] = score

    rules_in = value.get("rules")
    if rules_in is not None:
        if not isinstance(rules_in, dict):
            raise ValueError("rules must be an object")
        cleaned_rules: Dict[str, Any] = {}
        for rule_id, rule_cfg in rules_in.items():
            if rule_id not in RULE_IDS:
                continue
            if not isinstance(rule_cfg, dict):
                raise ValueError(f"rules.{rule_id} must be an object")
            cleaned_rule = _validate_rule(rule_id, rule_cfg)
            if cleaned_rule:
                cleaned_rules[rule_id] = cleaned_rule
        if cleaned_rules:
            cleaned["rules"] = cleaned_rules

    return cleaned


def _validate_rule(rule_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if cfg.get("enabled") is not None:
        out["enabled"] = bool(cfg["enabled"])

    if rule_id == "rounding_anomaly" and cfg.get("min_amount") is not None:
        amount = _as_number(cfg["min_amount"], "rounding_anomaly.min_amount")
        if amount < 0:
            raise ValueError("rounding_anomaly.min_amount must be >= 0")
        out["min_amount"] = amount

    if rule_id == "threshold_splitting":
        if cfg.get("min_count") is not None:
            count = cfg["min_count"]
            if isinstance(count, bool) or not isinstance(count, int):
                raise ValueError("threshold_splitting.min_count must be an integer")
            if count < 2:
                raise ValueError("threshold_splitting.min_count must be >= 2")
            out["min_count"] = count
        if cfg.get("proximity_pct") is not None:
            pct = _as_number(cfg["proximity_pct"], "threshold_splitting.proximity_pct")
            if not (0.5 <= pct <= 1.0):
                raise ValueError("threshold_splitting.proximity_pct must be between 0.5 and 1.0")
            out["proximity_pct"] = pct

    if rule_id == "temporal_anomaly":
        start = cfg.get("start_hour")
        end = cfg.get("end_hour")
        if start is not None:
            if isinstance(start, bool) or not isinstance(start, int) or not (0 <= start <= 23):
                raise ValueError("temporal_anomaly.start_hour must be an integer 0-23")
            out["start_hour"] = start
        if end is not None:
            if isinstance(end, bool) or not isinstance(end, int) or not (0 <= end <= 23):
                raise ValueError("temporal_anomaly.end_hour must be an integer 0-23")
            out["end_hour"] = end
        # When both are provided in the same payload they must be ordered.
        if start is not None and end is not None and start >= end:
            raise ValueError("temporal_anomaly.start_hour must be < end_hour")
        if cfg.get("flag_weekend") is not None:
            out["flag_weekend"] = bool(cfg["flag_weekend"])

    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_anomaly_rule_config.py -v --noconftest`
Expected: PASS (all tests in this file).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/anomaly_rule_config.py api/tests/test_anomaly_rule_config.py
git commit -m "feat(anomaly): anomaly rule config defaults + validate-on-write"
```

---

## Task 2: Config service — get (merge + clamp-on-read)

**Files:**
- Modify: `api/core/services/anomaly_rule_config.py`
- Test: `api/tests/test_anomaly_rule_config.py`

**Interfaces:**
- Consumes: `DEFAULT_ANOMALY_RULE_CONFIG`, `RULE_IDS`, `ANOMALY_RULE_CONFIG_KEY`.
- Produces: `get_anomaly_rule_config(db: Session) -> dict` — full effective config (defaults deep-merged with the stored row, every value clamped/coerced into range).

- [ ] **Step 1: Write the failing tests** (append to `test_anomaly_rule_config.py`)

```python
from core.models.models_per_tenant import Settings
from core.services.anomaly_rule_config import (
    ANOMALY_RULE_CONFIG_KEY,
    get_anomaly_rule_config,
)


def _set_row(db, value):
    db.add(Settings(key=ANOMALY_RULE_CONFIG_KEY, value=value))
    db.commit()


def test_get_returns_defaults_when_unset(db_session):
    assert get_anomaly_rule_config(db_session) == DEFAULT_ANOMALY_RULE_CONFIG


def test_get_deep_merges_partial_row(db_session):
    _set_row(db_session, {"rules": {"rounding_anomaly": {"enabled": False}}})
    cfg = get_anomaly_rule_config(db_session)
    # Overridden field applied...
    assert cfg["rules"]["rounding_anomaly"]["enabled"] is False
    # ...sibling default within the same rule preserved...
    assert cfg["rules"]["rounding_anomaly"]["min_amount"] == 250
    # ...other rules untouched.
    assert cfg["rules"]["phantom_vendor"]["enabled"] is True


def test_get_clamps_poisoned_values(db_session):
    _set_row(db_session, {
        "min_risk_score": 999,
        "rules": {
            "temporal_anomaly": {"start_hour": "nonsense", "end_hour": 50},
            "threshold_splitting": {"min_count": 0, "proximity_pct": 5.0},
        },
    })
    cfg = get_anomaly_rule_config(db_session)
    assert cfg["min_risk_score"] == 100            # clamped to max
    assert cfg["rules"]["temporal_anomaly"]["start_hour"] == 7   # bad type -> default
    assert cfg["rules"]["temporal_anomaly"]["end_hour"] == 23    # clamped to max
    assert cfg["rules"]["threshold_splitting"]["min_count"] == 2  # clamped to min
    assert cfg["rules"]["threshold_splitting"]["proximity_pct"] == 1.0  # clamped to max
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomaly_rule_config.py -k "get_" -v`
Expected: FAIL with `ImportError: cannot import name 'get_anomaly_rule_config'`.
(Note: dropped `--noconftest` — these need the `db_session` fixture from conftest, so the postgres-master stack must be up.)

- [ ] **Step 3: Implement `get_anomaly_rule_config` + clamp helpers** (append to the service module)

```python
def _clamp_number(value: Any, lo: float, hi: float, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(min(max(value, lo), hi))


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return min(max(value, lo), hi)


def _clamp_rule(rule_id: str, stored: Dict[str, Any]) -> Dict[str, Any]:
    default = DEFAULT_ANOMALY_RULE_CONFIG["rules"][rule_id]
    out: Dict[str, Any] = dict(default)
    if not isinstance(stored, dict):
        return out

    out["enabled"] = bool(stored.get("enabled", default["enabled"]))

    if rule_id == "rounding_anomaly":
        out["min_amount"] = _clamp_number(
            stored.get("min_amount", default["min_amount"]), 0, float("inf"), default["min_amount"]
        )
    elif rule_id == "threshold_splitting":
        out["min_count"] = _clamp_int(
            stored.get("min_count", default["min_count"]), 2, 1000, default["min_count"]
        )
        out["proximity_pct"] = _clamp_number(
            stored.get("proximity_pct", default["proximity_pct"]), 0.5, 1.0, default["proximity_pct"]
        )
    elif rule_id == "temporal_anomaly":
        out["start_hour"] = _clamp_int(
            stored.get("start_hour", default["start_hour"]), 0, 23, default["start_hour"]
        )
        out["end_hour"] = _clamp_int(
            stored.get("end_hour", default["end_hour"]), 0, 23, default["end_hour"]
        )
        out["flag_weekend"] = bool(stored.get("flag_weekend", default["flag_weekend"]))

    return out


def get_anomaly_rule_config(db: Session) -> Dict[str, Any]:
    """Return the tenant's effective rule config: defaults deep-merged with the
    stored row, every value clamped/coerced into its valid range (defence in
    depth on top of :func:`validate_anomaly_rule_config`)."""
    from core.models.models_per_tenant import Settings

    record = (
        db.query(Settings).filter(Settings.key == ANOMALY_RULE_CONFIG_KEY).first()
    )
    stored = record.value if record and isinstance(record.value, dict) else {}

    merged: Dict[str, Any] = {
        "min_risk_score": _clamp_number(
            stored.get("min_risk_score", 0), 0, 100, 0
        ),
        "rules": {
            rule_id: _clamp_rule(rule_id, (stored.get("rules") or {}).get(rule_id, {}))
            for rule_id in RULE_IDS
        },
    }
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_anomaly_rule_config.py -v`
Expected: PASS (full file, including the Task 1 `--noconftest` tests which also pass under conftest).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/anomaly_rule_config.py api/tests/test_anomaly_rule_config.py
git commit -m "feat(anomaly): get_anomaly_rule_config with defaults-merge + clamp-on-read"
```

---

## Task 3: Engine — inject config, skip disabled rules, apply risk floor

**Files:**
- Modify: `api/commercial/anomaly_detection/service.py:108-140`
- Test: `api/tests/test_anomaly_detection_integration.py`

**Interfaces:**
- Consumes: `get_anomaly_rule_config(db)` (Task 2); `context["rule_config"]` is read by rules in Task 4.
- Produces: per-audit behavior — disabled rules don't run; results with `risk_score < min_risk_score` are not saved.

- [ ] **Step 1: Write the failing tests** (append to `test_anomaly_detection_integration.py`)

```python
from core.models.models_per_tenant import Settings
from core.services.anomaly_rule_config import ANOMALY_RULE_CONFIG_KEY


def _set_rule_config(db, value):
    db.add(Settings(key=ANOMALY_RULE_CONFIG_KEY, value=value))
    db.commit()


@pytest.mark.asyncio
async def test_disabled_rule_produces_no_anomaly(db_session):
    _set_rule_config(db_session, {"rules": {"rounding_anomaly": {"enabled": False}}})
    expense = Expense(
        user_id=1, vendor="Acme Co", amount=500.00, currency="USD",
        expense_date=datetime(2023, 10, 3, 14, 0, tzinfo=timezone.utc),  # a Tuesday
        category="Office", description="Office chairs", status="recorded",
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
    assert "rounding_anomaly" not in rule_ids


@pytest.mark.asyncio
async def test_min_risk_score_floor_drops_low_results(db_session):
    # Floor above rounding_anomaly's 40.0 score -> it gets dropped even though it fires.
    _set_rule_config(db_session, {"min_risk_score": 50})
    expense = Expense(
        user_id=1, vendor="Acme Co", amount=500.00, currency="USD",
        expense_date=datetime(2023, 10, 3, 14, 0, tzinfo=timezone.utc),
        category="Office", description="Office chairs", status="recorded",
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)

    service = AnomalyDetectionService(db_session)
    await service.analyze_entity(expense, "expense")

    saved = db_session.query(Anomaly).filter(Anomaly.entity_id == expense.id).all()
    assert all(a.risk_score >= 50 for a in saved)
    assert "rounding_anomaly" not in [a.rule_id for a in saved]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomaly_detection_integration.py -k "disabled_rule or min_risk_score" -v`
Expected: FAIL — `rounding_anomaly` still recorded (config not yet consulted).

- [ ] **Step 3: Wire config into `analyze_entity`**

In `api/commercial/anomaly_detection/service.py`, after the attachment-paths fetch and before building `context` (around line 106), load config:

```python
        # Per-tenant rule config (future-only: consulted here, never mutates existing rows).
        from core.services.anomaly_rule_config import get_anomaly_rule_config
        rule_config = get_anomaly_rule_config(self.db)
        min_risk_score = rule_config["min_risk_score"]
```

Add it to the `context` dict (extend the existing literal):

```python
        context = {
            "ai_config": ai_config,
            "attachment_paths": attachment_paths,
            "audit_timestamp": datetime.now(timezone.utc),
            "forensic_persona": "Senior Forensic Auditor and Fraud Detection Specialist",
            "rule_config": rule_config,
        }
```

Replace the rule loop (currently lines ~118-130) with skip + floor logic:

```python
        # 3. Run all rules
        for rule in self._rules:
            if not rule_config["rules"].get(rule.rule_id, {}).get("enabled", True):
                continue
            try:
                result = await rule.analyze(self.db, entity, entity_type, context)
                if result:
                    if result.risk_score < min_risk_score:
                        continue
                    anomaly = self._save_anomaly(entity, entity_type, result)
                    created_anomalies.append(anomaly)
                    logger.warning(
                        f"🚩 Anomaly detected by {rule.rule_id} for {entity_type} {entity.id}: {result.reason}"
                    )
            except Exception as e:
                logger.error(
                    f"Error running anomaly rule {rule.rule_id}: {e}", exc_info=True
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_anomaly_detection_integration.py -v`
Expected: PASS — new tests pass and the original `test_anomaly_detection_integration` still passes (absent-row regression guard).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/anomaly_detection/service.py api/tests/test_anomaly_detection_integration.py
git commit -m "feat(anomaly): engine consults per-tenant rule config (toggles + risk floor)"
```

---

## Task 4: Tunable rules read thresholds from context

**Files:**
- Modify: `api/commercial/anomaly_detection/rules/rounding_anomaly.py`
- Modify: `api/commercial/anomaly_detection/rules/threshold_splitting.py`
- Modify: `api/commercial/anomaly_detection/rules/temporal_anomaly.py`
- Test: `api/tests/test_anomaly_detection_integration.py`

**Interfaces:**
- Consumes: `context["rule_config"]["rules"][<rule_id>]` (injected in Task 3). Each key falls back to today's hardcoded constant when the sub-config or key is absent (so a rule called in isolation still works).

- [ ] **Step 1: Write the failing tests** (append to `test_anomaly_detection_integration.py`)

```python
from commercial.anomaly_detection.rules.rounding_anomaly import RoundingAnomalyRule
from commercial.anomaly_detection.rules.temporal_anomaly import TemporalAnomalyRule


@pytest.mark.asyncio
async def test_rounding_rule_respects_min_amount(db_session):
    rule = RoundingAnomalyRule()
    expense = Expense(
        user_id=1, vendor="Acme", amount=500.00, currency="USD",
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
        user_id=1, vendor="Acme", amount=10.0, currency="USD",
        expense_date=datetime(2023, 10, 3, 22, 0, tzinfo=timezone.utc),  # 22:00 Tuesday
        category="Office", status="recorded",
    )
    # Default hours (7-20) flag 22:00.
    assert await rule.analyze(db_session, expense, "expense", {}) is not None
    # Widen end_hour to 23 and drop weekend flag -> 22:00 Tuesday no longer odd.
    ctx = {"rule_config": {"rules": {"temporal_anomaly": {"end_hour": 23, "flag_weekend": False}}}}
    assert await rule.analyze(db_session, expense, "expense", ctx) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomaly_detection_integration.py -k "respects" -v`
Expected: FAIL — rules ignore `context`, so the custom-config assertions return the default outcome.

- [ ] **Step 3a: `rounding_anomaly.py` — read `min_amount`**

Replace the body of `analyze` after computing `amount` (the `if is_round and amount > 250:` block) so the threshold comes from config:

```python
        rule_cfg = (context or {}).get("rule_config", {}).get("rules", {}).get("rounding_anomaly", {})
        min_amount = rule_cfg.get("min_amount", 250)

        is_round = False
        if amount >= 100 and amount % 100 == 0:
            is_round = True
        elif amount >= 50 and amount % 50 == 0:
            is_round = True

        if is_round and amount > min_amount:
            return AnomalyResult(
                risk_score=40.0,
                risk_level="medium",
                reason=f"Rounding anomaly: Perfect round amount of {amount} detected. This may indicate a lack of precise documentation or potential falsification.",
                rule_id=self.rule_id,
                details={"amount": amount},
            )
        return None
```

- [ ] **Step 3b: `temporal_anomaly.py` — read hours + weekend toggle**

Replace the `is_weekend`/`is_odd_hours` computation:

```python
        rule_cfg = (context or {}).get("rule_config", {}).get("rules", {}).get("temporal_anomaly", {})
        start_hour = rule_cfg.get("start_hour", 7)
        end_hour = rule_cfg.get("end_hour", 20)
        flag_weekend = rule_cfg.get("flag_weekend", True)

        is_weekend = flag_weekend and dt.weekday() >= 5  # 5=Sat, 6=Sun
        is_odd_hours = dt.hour < start_hour or dt.hour >= end_hour
```

(Leave the `reasons`/`risk_score` block below unchanged.)

- [ ] **Step 3c: `threshold_splitting.py` — read `min_count` + `proximity_pct`**

After resolving `vendor`/`amount` (before the `THRESHOLDS` loop), read config:

```python
        rule_cfg = (context or {}).get("rule_config", {}).get("rules", {}).get("threshold_splitting", {})
        min_count = rule_cfg.get("min_count", 3)
        proximity_pct = rule_cfg.get("proximity_pct", 0.8)
```

Replace the two `* 0.8` proximity comparisons (in the `THRESHOLDS` loop and the DB query) with `* proximity_pct`, and change the firing check:

```python
        if recent_count + 1 >= min_count:  # total transactions just below threshold
            return AnomalyResult(
                risk_score=80.0,
                risk_level="high",
                reason=f"Threshold splitting detected: {recent_count + 1} transactions for '{vendor}' are all just below the ${target_threshold} approval limit.",
                rule_id=self.rule_id,
                details={"threshold": target_threshold, "count": recent_count + 1},
            )

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_anomaly_detection_integration.py -v`
Expected: PASS — including the original integration test (defaults unchanged).

- [ ] **Step 5: Commit**

```bash
git add api/commercial/anomaly_detection/rules/rounding_anomaly.py \
        api/commercial/anomaly_detection/rules/threshold_splitting.py \
        api/commercial/anomaly_detection/rules/temporal_anomaly.py \
        api/tests/test_anomaly_detection_integration.py
git commit -m "feat(anomaly): tunable rules read thresholds from rule config"
```

---

## Task 5: API — GET/PUT /anomalies/config

**Files:**
- Modify: `api/core/routers/anomalies.py`
- Test: `api/tests/test_anomalies_router.py`

**Interfaces:**
- Consumes: `get_anomaly_rule_config`, `validate_anomaly_rule_config`, `ANOMALY_RULE_CONFIG_KEY` (Tasks 1–2); `require_admin_or_superuser` (rbac); `log_audit_event` (`core.utils.audit`).
- Produces:
  - `GET /anomalies/config` → effective config dict.
  - `PUT /anomalies/config` (body `UpdateAnomalyConfigRequest`) → effective config dict; admin-only; 422 on `ValueError`.

- [ ] **Step 1: Write the failing tests** (append to `test_anomalies_router.py`)

```python
from core.routers.anomalies import (
    UpdateAnomalyConfigRequest,
    get_anomaly_config,
    update_anomaly_config,
)


@pytest.fixture
def admin_user():
    return SimpleNamespace(id=7, tenant_id=1, email="a@x.com", role="admin", is_superuser=False)


@pytest.fixture
def viewer_user():
    return SimpleNamespace(id=8, tenant_id=1, email="v@x.com", role="viewer", is_superuser=False)


@pytest.mark.asyncio
async def test_get_config_returns_defaults(db_session, user, feature_on):
    result = await get_anomaly_config(db=db_session, current_user=user)
    assert result["rules"]["rounding_anomaly"]["min_amount"] == 250
    assert result["min_risk_score"] == 0


@pytest.mark.asyncio
async def test_get_config_feature_off(db_session, user, feature_off):
    with pytest.raises(HTTPException) as exc:
        await get_anomaly_config(db=db_session, current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_config_admin_persists(db_session, admin_user, feature_on):
    payload = UpdateAnomalyConfigRequest(
        config={"min_risk_score": 30, "rules": {"phantom_vendor": {"enabled": False}}}
    )
    result = await update_anomaly_config(payload=payload, db=db_session, current_user=admin_user)
    assert result["min_risk_score"] == 30
    assert result["rules"]["phantom_vendor"]["enabled"] is False
    # Persisted + reads back.
    again = await get_anomaly_config(db=db_session, current_user=admin_user)
    assert again["rules"]["phantom_vendor"]["enabled"] is False


@pytest.mark.asyncio
async def test_update_config_non_admin_forbidden(db_session, viewer_user, feature_on):
    payload = UpdateAnomalyConfigRequest(config={"min_risk_score": 10})
    with pytest.raises(HTTPException) as exc:
        await update_anomaly_config(payload=payload, db=db_session, current_user=viewer_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_config_invalid_is_422(db_session, admin_user, feature_on):
    payload = UpdateAnomalyConfigRequest(config={"min_risk_score": 999})
    with pytest.raises(HTTPException) as exc:
        await update_anomaly_config(payload=payload, db=db_session, current_user=admin_user)
    assert exc.value.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomalies_router.py -k "config" -v`
Expected: FAIL with `ImportError` (`get_anomaly_config` not defined).

- [ ] **Step 3: Add the endpoints to `anomalies.py`**

Add imports near the top (with the other imports):

```python
from core.utils.rbac import require_admin_or_superuser
from core.utils.audit import log_audit_event
from core.services.anomaly_rule_config import (
    ANOMALY_RULE_CONFIG_KEY,
    get_anomaly_rule_config,
    validate_anomaly_rule_config,
)
from core.models.models_per_tenant import Settings
```

Add a small feature-gate helper next to the existing handlers (DRY — replaces the repeated inline check; reuse for the two new endpoints, leave existing ones as-is):

```python
def _require_anomaly_feature(db: Session) -> None:
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )
```

Add the endpoints. **Place them BEFORE the `@router.get("/{anomaly_id}")` route** so `config` isn't captured as an id:

```python
@router.get("/config")
async def get_anomaly_config(
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Return the tenant's effective anomaly rule config (defaults merged + clamped)."""
    _require_anomaly_feature(db)
    return get_anomaly_rule_config(db)


class UpdateAnomalyConfigRequest(BaseModel):
    config: dict


@router.put("/config")
async def update_anomaly_config(
    payload: UpdateAnomalyConfigRequest,
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Update the tenant's anomaly rule config (admin-only). Future audits only."""
    _require_anomaly_feature(db)
    require_admin_or_superuser(current_user, "update anomaly rule config")

    try:
        cleaned = validate_anomaly_rule_config(payload.config)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    record = db.query(Settings).filter(Settings.key == ANOMALY_RULE_CONFIG_KEY).first()
    if record:
        current_value = record.value or {}
        merged_rules = {**(current_value.get("rules") or {}), **(cleaned.get("rules") or {})}
        new_value = {**current_value, **{k: v for k, v in cleaned.items() if k != "rules"}}
        if "rules" in cleaned or "rules" in current_value:
            new_value["rules"] = merged_rules
        record.value = new_value
        record.updated_at = datetime.now(timezone.utc)
    else:
        record = Settings(
            key=ANOMALY_RULE_CONFIG_KEY,
            value=cleaned,
            category="features",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(record)
    db.commit()

    log_audit_event(
        db=db,
        user_id=current_user.id,
        user_email=current_user.email,
        action="UPDATE",
        resource_type="anomaly_rule_config",
        resource_id="1",
        resource_name="Anomaly Rule Config",
        details=cleaned,
        status="success",
    )

    return get_anomaly_rule_config(db)
```

(Note the per-rule merge so a partial update to one rule doesn't drop other rules' stored overrides.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_anomalies_router.py -v`
Expected: PASS (config tests + existing router tests).

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/anomalies.py api/tests/test_anomalies_router.py
git commit -m "feat(anomaly): GET/PUT /anomalies/config endpoints (admin-gated write)"
```

---

## Task 6: Frontend — config API client + settings panel

**Files:**
- Modify: `ui/src/lib/api/anomalies.ts`
- Modify: `ui/src/pages/Anomalies.tsx`

**Interfaces:**
- Consumes: `GET/PUT /anomalies/config` (Task 5); `useAuth` (`currentUser.role`, `currentUser.is_superuser`); `apiRequest` (`./_base`).
- Produces: `anomaliesApi.getConfig()`, `anomaliesApi.updateConfig(config)`; `AnomalyRuleConfig` type.

- [ ] **Step 1: Add config types + client methods to `ui/src/lib/api/anomalies.ts`**

```typescript
export interface AnomalyRuleSettings {
  enabled: boolean;
  min_amount?: number;       // rounding_anomaly
  min_count?: number;        // threshold_splitting
  proximity_pct?: number;    // threshold_splitting
  start_hour?: number;       // temporal_anomaly
  end_hour?: number;         // temporal_anomaly
  flag_weekend?: boolean;    // temporal_anomaly
}

export interface AnomalyRuleConfig {
  min_risk_score: number;
  rules: Record<string, AnomalyRuleSettings>;
}
```

Add to the `anomaliesApi` object:

```typescript
  getConfig: () => apiRequest<AnomalyRuleConfig>('/anomalies/config'),

  updateConfig: (config: Partial<AnomalyRuleConfig>) =>
    apiRequest<AnomalyRuleConfig>('/anomalies/config', {
      method: 'PUT',
      body: JSON.stringify({ config }),
    }),
```

- [ ] **Step 2: Add the settings panel to `ui/src/pages/Anomalies.tsx`**

Add imports:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings as SettingsIcon } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/hooks/useAuth';
import type { AnomalyRuleConfig } from '@/lib/api/anomalies';
```

Add a `RULE_LABELS` map (the 7 ids → display names, matching the engine `name` properties):

```typescript
const RULE_LABELS: Record<string, string> = {
  duplicate_billing: 'Duplicate Billing',
  rounding_anomaly: 'Rounding Anomaly',
  phantom_vendor: 'Phantom Vendor',
  threshold_splitting: 'Threshold Splitting',
  temporal_anomaly: 'Temporal Anomaly',
  description_mismatch: 'Description Mismatch',
  attachment_audit: 'Attachment Audit',
};
```

Add a `DetectionSettingsPanel` component in this file. It:
- reads `const { currentUser } = useAuth();` and computes `const isAdmin = currentUser?.role === 'admin' || currentUser?.is_superuser === true;`
- `useQuery({ queryKey: ['anomalies', 'config'], queryFn: anomaliesApi.getConfig })`
- holds a local editable copy in `useState<AnomalyRuleConfig | null>(null)` seeded from the query (via `useEffect` on data)
- renders, per rule id in `Object.keys(RULE_LABELS)`: a `Switch` bound to `rules[id].enabled`; for `rounding_anomaly` a number `Input` for `min_amount`; for `threshold_splitting` number `Input`s for `min_count` and `proximity_pct`; for `temporal_anomaly` number `Input`s for `start_hour`/`end_hour` and a `Switch` for `flag_weekend`
- renders a "Minimum risk score to record" number `Input` bound to `min_risk_score`
- a Save `ProfessionalButton` wired to `useMutation({ mutationFn: () => anomaliesApi.updateConfig(edited), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['anomalies', 'config'] }) })`
- when `!isAdmin`: render the controls `disabled` and hide the Save button (matches the API 403 gate)
- shows a toast on success / on error (reuse whatever toast the page/codebase already uses, e.g. `sonner`'s `toast`)

Mount it inside `AnomaliesList`'s returned layout as a collapsible card (gear/`SettingsIcon` header) above or beside the existing table, wrapped by the existing `FeatureGate`.

- [ ] **Step 3: Typecheck + tests**

Run: `docker compose exec ui npx tsc --noEmit`
Expected: no new errors from the changed files.
Run: `docker compose exec ui npx vitest run src/lib/api/anomalies` (if a test file exists; otherwise skip)
Expected: PASS.

- [ ] **Step 4: Manual smoke (browser)**

Log in as an admin, open **Fraud Checks**, expand **Detection settings**, toggle a rule off, change a threshold, Save → expect a success toast and values persisting on reload. Log in as a viewer → controls disabled, no Save.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/api/anomalies.ts ui/src/pages/Anomalies.tsx
git commit -m "feat(anomaly): detection settings panel for per-tenant rule config"
```

---

## Self-Review Notes

- **Spec coverage:** persistence/service (Tasks 1–2), engine future-only toggles + floor (Task 3), threshold tuning for the 3 rules (Task 4), GET/PUT API with admin gate + bounded validation (Task 5), frontend panel (Task 6), tests at every layer including the absent-row regression guard (Tasks 3–5). All spec sections mapped.
- **Type consistency:** `get_anomaly_rule_config` / `validate_anomaly_rule_config` / `ANOMALY_RULE_CONFIG_KEY` / `RULE_IDS` / `DEFAULT_ANOMALY_RULE_CONFIG` used consistently across tasks; `UpdateAnomalyConfigRequest.config: dict`, `AnomalyRuleConfig` shape matches backend defaults.
- **Route ordering gotcha** (`/config` before `/{anomaly_id}`) called out, consistent with the Slice-1 `status`-param note.
