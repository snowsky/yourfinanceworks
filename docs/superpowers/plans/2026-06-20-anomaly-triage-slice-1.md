# Anomaly Triage Workflow (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the anomaly list into a review queue — a detail drawer that surfaces the evidence, and a real resolution model (open → confirmed / dismissed) replacing the dismiss-only flow.

**Architecture:** Add a `status` source-of-truth column to the existing `Anomaly` model (kept in sync with the legacy `is_dismissed` mirror); a `resolve` + `get-by-id` API on the existing `anomalies` router with a `status` list filter; a URL-addressable Sheet drawer + filter tabs on the existing `/anomalies` page.

**Tech Stack:** FastAPI · SQLAlchemy (per-tenant DBs) · React/TypeScript · TanStack Query · ShadCN (Sheet/Tabs/Textarea) · pytest · vitest.

## Global Constraints

- **Status values (verbatim):** `Anomaly.status ∈ {"open", "confirmed", "dismissed"}`, default `"open"`. `confirmed` = true positive, `dismissed` = false positive.
- **`is_dismissed` mirror invariant:** on every resolution, `is_dismissed = (status != "open")`. Never break this — the legacy super-admin aggregator reads `is_dismissed`.
- **Resolution audit fields:** the existing `dismissed_at` / `dismissed_by_id` columns double as resolved-at / resolved-by (either outcome); `resolution_note` holds the reason (also mirrored into the legacy `dismiss_notes`).
- **Schema change is `db_init` only — NO alembic migration.** The `anomalies` table is created by `create_all` from the model and patched for pre-existing tenant DBs by `db_init.ensure_tenant_required_columns` (alembic never manages this table and is not auto-run at startup).
- **Confirm is record-only this slice:** no notifications, no auto-actions. (Slice 2 / 3 — see `docs/todos/anomaly-fraud-detection-slices.md`.)
- **Generic evidence render:** the `details` JSON is rendered as a key/value list with a JSON fallback — never assume a per-rule shape.
- **Licensing gate:** every endpoint keeps the existing `FeatureConfigService.is_enabled("anomaly_detection", db=db)` → 403 check.
- **Test environment:** backend tests run in-container (stack already up): `docker compose exec api python -m pytest <path> -v` (use `python -m pytest`; the conftest `db_session` needs postgres-master). Frontend: `docker compose exec ui npx vitest run <path>` and `docker compose exec ui npx tsc --noEmit` (the ui workdir is `/app`, so in-container paths drop the `ui/` prefix; pre-existing tsc errors elsewhere are out of scope).

---

## File Structure

- `api/core/models/models_per_tenant.py` — **modify**: add `status` + `resolution_note` to `Anomaly`.
- `api/db_init.py` — **modify**: idempotent `anomalies` column patch in `ensure_tenant_required_columns`.
- `api/core/routers/anomalies.py` — **modify**: `_serialize_anomaly` + `_apply_resolution` helpers, `ResolveAnomalyRequest`, `resolve_anomaly`, `get_anomaly`, `status` filter on `list_anomalies`; `dismiss` becomes a thin alias.
- `api/tests/test_anomaly_status_model.py` — **create**: model default/accept tests.
- `api/tests/test_anomalies_router.py` — **modify**: resolve/get/status-filter tests; update `_make_anomaly` to set `status`.
- `ui/src/lib/api/anomalies.ts` — **modify**: extend `Anomaly` type, `list` status param, add `get` + `resolve`.
- `ui/src/lib/anomaly-ui.ts` — **modify**: add `STATUS_BADGE` + `renderDetailEntries` helper.
- `ui/src/components/anomalies/AnomalyDetailDrawer.tsx` — **create**: evidence + resolution drawer.
- `ui/src/pages/Anomalies.tsx` — **modify**: filter tabs + URL-addressable drawer.
- `ui/src/components/anomalies/__tests__/Anomalies.test.tsx` — **create**: tabs/drawer/resolve test.
- `ui/src/i18n/locales/en.json` — **modify**: new `anomalies.*` keys.

---

### Task 1: `Anomaly` status column + db_init patch

**Files:**
- Modify: `api/core/models/models_per_tenant.py` (the `Anomaly` class, ~line 1525)
- Modify: `api/db_init.py` (`ensure_tenant_required_columns`, ~line 185)
- Test: `api/tests/test_anomaly_status_model.py` (create)

**Interfaces:**
- Produces: `Anomaly.status` (str, default `"open"`), `Anomaly.resolution_note` (str|None). Pre-existing tenant DBs get both columns via `db_init` with `status` backfilled from `is_dismissed`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_anomaly_status_model.py`:

```python
"""Model-level tests for the Anomaly resolution columns (Slice 1)."""
from core.models.models_per_tenant import Anomaly


def test_new_anomaly_defaults_to_open(db_session):
    a = Anomaly(entity_type="invoice", entity_id=1, risk_score=50.0,
                risk_level="high", reason="x")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    assert a.status == "open"
    assert a.resolution_note is None
    db_session.delete(a)
    db_session.commit()


def test_anomaly_accepts_confirmed_status_and_note(db_session):
    a = Anomaly(entity_type="invoice", entity_id=2, risk_score=50.0,
                risk_level="high", reason="x", status="confirmed",
                resolution_note="verified real")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    assert a.status == "confirmed"
    assert a.resolution_note == "verified real"
    db_session.delete(a)
    db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_anomaly_status_model.py -v`
Expected: FAIL — `TypeError: 'status' is an invalid keyword argument for Anomaly` (column doesn't exist yet).

- [ ] **Step 3: Add the model columns**

In `api/core/models/models_per_tenant.py`, in the `Anomaly` class, immediately after the `dismiss_notes = Column(Text, nullable=True)` line (in the `# Status` block), add:

```python
    # Resolution workflow (Slice 1). `status` is the source of truth; the
    # existing is_dismissed boolean is kept as a derived mirror
    # (is_dismissed == (status != "open")) for the legacy super-admin
    # aggregator. dismissed_at / dismissed_by_id double as the resolution
    # audit fields (who/when, either outcome).
    status = Column(String(20), nullable=False, default="open", index=True)  # open, confirmed, dismissed
    resolution_note = Column(Text, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_anomaly_status_model.py -v`
Expected: PASS (2 passed). (The conftest rebuilds the test schema via `create_all`, so the new columns are present.)

- [ ] **Step 5: Add the idempotent db_init patch for pre-existing tenant DBs**

In `api/db_init.py`, inside `ensure_tenant_required_columns`, after the `invoices` block (the one adding `reminder_last_offset` / `reminder_last_sent_at`, ~line 238) and before the function's closing/return, add:

```python
            # anomalies: resolution-workflow columns (Slice 1). status is the
            # source of truth; backfill pre-existing rows from is_dismissed so
            # the NOT NULL default is correct for historical data.
            if "anomalies" in inspector.get_table_names():
                existing = {c["name"] for c in inspector.get_columns("anomalies")}
                if "status" not in existing:
                    logger.info(f"[tenant {tenant_id}] Adding anomalies.status")
                    conn.execute(
                        text(
                            "ALTER TABLE anomalies "
                            "ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE anomalies SET status = 'dismissed' "
                            "WHERE is_dismissed = true"
                        )
                    )
                    conn.commit()
                if "resolution_note" not in existing:
                    logger.info(f"[tenant {tenant_id}] Adding anomalies.resolution_note")
                    conn.execute(
                        text("ALTER TABLE anomalies ADD COLUMN resolution_note TEXT")
                    )
                    conn.commit()
```

(Verify `text` and `inspect` are already imported at the top of `db_init.py` — they are used by the surrounding blocks. No new imports needed.)

- [ ] **Step 6: Sanity-check db_init imports cleanly**

Run: `docker compose exec api python -c "import db_init; print('db_init import OK')"`
Expected: prints `db_init import OK` (no syntax/import error from the new block).

- [ ] **Step 7: Commit**

```bash
git add api/core/models/models_per_tenant.py api/db_init.py api/tests/test_anomaly_status_model.py
git commit -m "feat(anomaly): status + resolution_note columns with db_init backfill"
```

---

### Task 2: Resolve / get-by-id / status filter API

**Files:**
- Modify: `api/core/routers/anomalies.py`
- Test: `api/tests/test_anomalies_router.py`

**Interfaces:**
- Consumes: `Anomaly.status`, `Anomaly.resolution_note` (Task 1).
- Produces:
  - `_serialize_anomaly(a, statement_by_txn=None) -> dict` (adds `status`, `resolution_note`, `resolved_at`, `resolved_by_id`).
  - `_apply_resolution(anomaly, status, note, user)` — sets `status`, `is_dismissed=(status!="open")`, `dismissed_at`, `dismissed_by_id`, `resolution_note`, `dismiss_notes`.
  - `ResolveAnomalyRequest { status: str, note: Optional[str] }`.
  - `PATCH /anomalies/{id}/resolve`, `GET /anomalies/{id}`, `GET /anomalies?status=` filter.

- [ ] **Step 1: Write the failing tests**

In `api/tests/test_anomalies_router.py`, first update the import block (lines 19-23) to pull in the new symbols:

```python
from core.routers.anomalies import (
    DismissAnomalyRequest,
    ResolveAnomalyRequest,
    dismiss_anomaly,
    get_anomaly,
    list_anomalies,
    resolve_anomaly,
)
```

Update `_make_anomaly` (lines 46-60) to set `status` consistently with the mirror invariant (add the `status` kwarg + default):

```python
def _make_anomaly(db, *, risk_level="high", risk_score=80.0, is_dismissed=False,
                  entity_type="invoice", entity_id=1, reason="suspicious", status=None):
    a = Anomaly(
        entity_type=entity_type,
        entity_id=entity_id,
        risk_score=risk_score,
        risk_level=risk_level,
        reason=reason,
        rule_id="duplicate_billing",
        is_dismissed=is_dismissed,
        status=status or ("dismissed" if is_dismissed else "open"),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a
```

Then append these tests:

```python
@pytest.mark.asyncio
async def test_resolve_confirmed_sets_status_and_mirror(db_session, create_test_user, feature_on):
    actor = create_test_user(email="resolver@example.com")
    a = _make_anomaly(db_session, entity_id=21)

    result = await resolve_anomaly(
        anomaly_id=a.id,
        payload=ResolveAnomalyRequest(status="confirmed", note="real fraud"),
        db=db_session, current_user=actor,
    )

    assert result == {"id": a.id, "status": "confirmed"}
    refreshed = db_session.query(Anomaly).filter(Anomaly.id == a.id).first()
    assert refreshed.status == "confirmed"
    assert refreshed.is_dismissed is True            # mirror: status != "open"
    assert refreshed.resolution_note == "real fraud"
    assert refreshed.dismissed_by_id == actor.id
    assert refreshed.dismissed_at is not None
    db_session.delete(refreshed)
    db_session.commit()


@pytest.mark.asyncio
async def test_resolve_dismissed_mirrors_is_dismissed(db_session, create_test_user, feature_on):
    actor = create_test_user(email="resolver2@example.com")
    a = _make_anomaly(db_session, entity_id=22)

    await resolve_anomaly(
        anomaly_id=a.id,
        payload=ResolveAnomalyRequest(status="dismissed"),
        db=db_session, current_user=actor,
    )

    refreshed = db_session.query(Anomaly).filter(Anomaly.id == a.id).first()
    assert refreshed.status == "dismissed"
    assert refreshed.is_dismissed is True
    db_session.delete(refreshed)
    db_session.commit()


@pytest.mark.asyncio
async def test_resolve_invalid_status_raises_422(db_session, user, feature_on):
    a = _make_anomaly(db_session, entity_id=23)
    with pytest.raises(HTTPException) as exc:
        await resolve_anomaly(
            anomaly_id=a.id,
            payload=ResolveAnomalyRequest(status="bogus"),
            db=db_session, current_user=user,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_get_by_id_returns_item(db_session, user, feature_on):
    a = _make_anomaly(db_session, entity_id=24, reason="dup")
    result = await get_anomaly(anomaly_id=a.id, db=db_session, current_user=user)
    assert result["id"] == a.id
    assert result["status"] == "open"
    assert result["reason"] == "dup"


@pytest.mark.asyncio
async def test_get_by_id_unknown_raises_404(db_session, user, feature_on):
    with pytest.raises(HTTPException) as exc:
        await get_anomaly(anomaly_id=999999, db=db_session, current_user=user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_status_filter_returns_only_that_status(db_session, create_test_user, feature_on):
    actor = create_test_user(email="filter@example.com")
    _make_anomaly(db_session, entity_id=31)  # open
    confirmed = _make_anomaly(db_session, entity_id=32)
    await resolve_anomaly(
        anomaly_id=confirmed.id,
        payload=ResolveAnomalyRequest(status="confirmed"),
        db=db_session, current_user=actor,
    )

    result = await list_anomalies(
        skip=0, limit=50, risk_level=None, status="confirmed", is_dismissed=False,
        db=db_session, current_user=user_fixture_id := actor,
    )
    assert result["total"] == 1
    assert result["items"][0]["entity_id"] == 32
    assert result["items"][0]["status"] == "confirmed"
    # cleanup the confirmed row (FK to users)
    db_session.delete(db_session.query(Anomaly).filter(Anomaly.id == confirmed.id).first())
    db_session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_anomalies_router.py -k "resolve or get_by_id or status_filter" -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_anomaly'`.

- [ ] **Step 3: Implement the helpers + endpoints**

In `api/core/routers/anomalies.py`:

Add a serialization helper + resolution helper near the top (after `RISK_LEVELS`, ~line 29):

```python
RESOLVABLE_STATUSES = ("confirmed", "dismissed")


def _serialize_anomaly(a, statement_by_txn=None):
    statement_by_txn = statement_by_txn or {}
    return {
        "id": a.id,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "risk_score": a.risk_score,
        "risk_level": a.risk_level,
        "reason": a.reason,
        "rule_id": a.rule_id,
        "details": a.details,
        "created_at": a.created_at,
        "status": a.status,
        "resolution_note": a.resolution_note,
        "resolved_at": a.dismissed_at,
        "resolved_by_id": a.dismissed_by_id,
        "statement_id": statement_by_txn.get(a.entity_id),
    }


def _apply_resolution(anomaly, status: str, note, user) -> None:
    """Set the resolution fields + keep the is_dismissed mirror in sync."""
    anomaly.status = status
    anomaly.is_dismissed = status != "open"
    anomaly.dismissed_at = datetime.now(timezone.utc)
    anomaly.dismissed_by_id = user.id
    anomaly.resolution_note = note
    anomaly.dismiss_notes = note  # keep the legacy column in sync
```

Replace the inline item-serialization in `list_anomalies` (the `"items": [ {...} for a in items ]` block, lines 102-116) with `_serialize_anomaly`, and add the `status` filter. The `return` becomes:

```python
    return {
        "total": total,
        "summary": summary,
        "skip": skip,
        "limit": limit,
        "items": [_serialize_anomaly(a, statement_by_txn) for a in items],
    }
```

And change the `list_anomalies` signature + the base query. Add a `status` Query param after `risk_level` (line 36):

```python
    status: Optional[str] = Query(None, description="Filter by resolution status (open/confirmed/dismissed)"),
```

and replace the base-query line (line 53) `query = db.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)` with:

```python
    if status is not None:
        query = db.query(Anomaly).filter(Anomaly.status == status)
    else:
        query = db.query(Anomaly).filter(Anomaly.is_dismissed == is_dismissed)
```

(The `summary` block stays as-is — it counts `is_dismissed == False`, which is the open set under the mirror invariant.)

Add the new request model + endpoints after `dismiss_anomaly` (end of file):

```python
class ResolveAnomalyRequest(BaseModel):
    status: str
    note: Optional[str] = None


@router.patch("/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: int,
    payload: ResolveAnomalyRequest,
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Resolve an anomaly as confirmed (true positive) or dismissed (false positive)."""
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )
    if payload.status not in RESOLVABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be 'confirmed' or 'dismissed'",
        )
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    _apply_resolution(anomaly, payload.status, payload.note, current_user)
    db.commit()
    return {"id": anomaly.id, "status": anomaly.status}


@router.get("/{anomaly_id}")
async def get_anomaly(
    anomaly_id: int,
    db: Session = Depends(get_db),
    current_user: TenantUser = Depends(get_current_user),
):
    """Fetch a single anomaly (for the detail drawer / deep-links)."""
    if not FeatureConfigService.is_enabled("anomaly_detection", db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anomaly detection is not available in your current license",
        )
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    statement_by_txn = {}
    if anomaly.entity_type == "bank_statement_transaction":
        from core.models.models_per_tenant import BankStatementTransaction
        row = (
            db.query(BankStatementTransaction.statement_id)
            .filter(BankStatementTransaction.id == anomaly.entity_id)
            .first()
        )
        if row:
            statement_by_txn[anomaly.entity_id] = row[0]
    return _serialize_anomaly(anomaly, statement_by_txn)
```

Finally, make `dismiss_anomaly` reuse `_apply_resolution` (replace its mutation block, lines 142-145, so the body sets via the helper):

```python
    _apply_resolution(anomaly, "dismissed", payload.notes, current_user)
    db.commit()

    return {"id": anomaly.id, "is_dismissed": True}
```

- [ ] **Step 4: Run the new + existing router tests**

Run: `docker compose exec api python -m pytest tests/test_anomalies_router.py -v`
Expected: PASS (all — the new resolve/get/status-filter tests plus the pre-existing list/dismiss tests; note `test_dismiss_sets_fields` still asserts `dismiss_notes` is set, which `_apply_resolution` preserves).

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/anomalies.py api/tests/test_anomalies_router.py
git commit -m "feat(anomaly): resolve + get-by-id endpoints and status list filter"
```

---

### Task 3: Frontend — detail drawer + queue tabs

**Files:**
- Modify: `ui/src/lib/api/anomalies.ts`
- Modify: `ui/src/lib/anomaly-ui.ts`
- Create: `ui/src/components/anomalies/AnomalyDetailDrawer.tsx`
- Modify: `ui/src/pages/Anomalies.tsx`
- Modify: `ui/src/i18n/locales/en.json`
- Test: `ui/src/components/anomalies/__tests__/Anomalies.test.tsx` (create)

**Interfaces:**
- Consumes: `PATCH /anomalies/{id}/resolve`, `GET /anomalies/{id}`, `GET /anomalies?status=` (Task 2).
- Produces: `anomaliesApi.get(id)`, `anomaliesApi.resolve(id, status, note?)`, `list({ status })`; `AnomalyDetailDrawer`.

- [ ] **Step 1: Extend the API client + types**

In `ui/src/lib/api/anomalies.ts`, add the status type, extend `Anomaly`, and add `get`/`resolve`:

```ts
export type AnomalyStatus = 'open' | 'confirmed' | 'dismissed';
```

Add to the `Anomaly` interface (after `statement_id`):

```ts
  status: AnomalyStatus;
  resolution_note?: string | null;
  resolved_at?: string | null;
```

Replace the `list` signature to accept `status`, and add `get` + `resolve` to `anomaliesApi`:

```ts
  list: (params: { skip?: number; limit?: number; risk_level?: string; status?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.skip != null) q.set('skip', String(params.skip));
    if (params.limit != null) q.set('limit', String(params.limit));
    if (params.risk_level) q.set('risk_level', params.risk_level);
    if (params.status) q.set('status', params.status);
    const qs = q.toString();
    return apiRequest<AnomalyListResponse>(`/anomalies${qs ? `?${qs}` : ''}`);
  },

  get: (id: number) => apiRequest<Anomaly>(`/anomalies/${id}`),

  resolve: (id: number, status: 'confirmed' | 'dismissed', note?: string) =>
    apiRequest<{ id: number; status: AnomalyStatus }>(`/anomalies/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ status, note: note ?? null }),
    }),
```

(Keep the existing `dismiss` for back-compat.)

- [ ] **Step 2: Add UI helpers**

In `ui/src/lib/anomaly-ui.ts`, append a status badge map + a generic details flattener:

```ts
/** Tailwind classes for an outline Badge, keyed by resolution status. */
export const STATUS_BADGE: Record<string, string> = {
  open: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  confirmed: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
  dismissed: 'bg-muted text-muted-foreground border-border',
};

/** Flatten an anomaly `details` blob into label/value rows for generic display. */
export function renderDetailEntries(details: unknown): Array<{ label: string; value: string }> {
  if (!details || typeof details !== 'object') return [];
  return Object.entries(details as Record<string, unknown>).map(([k, v]) => ({
    label: k.replace(/_/g, ' '),
    value:
      v != null && typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v),
  }));
}
```

- [ ] **Step 3: Create the detail drawer**

Create `ui/src/components/anomalies/AnomalyDetailDrawer.tsx`:

```tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ExternalLink, ShieldCheck, ShieldX } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { anomaliesApi, type Anomaly } from '@/lib/api';
import { RISK_BADGE, STATUS_BADGE, entityHref, entityLabel, renderDetailEntries } from '@/lib/anomaly-ui';

interface Props {
  anomaly: Anomaly | null;
  open: boolean;
  onClose: () => void;
}

export function AnomalyDetailDrawer({ anomaly, open, onClose }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');

  const resolve = useMutation({
    mutationFn: ({ status }: { status: 'confirmed' | 'dismissed' }) =>
      anomaliesApi.resolve(anomaly!.id, status, note || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      toast.success(t('anomalies.resolved'));
      setNote('');
      onClose();
    },
    onError: () => toast.error(t('anomalies.resolve_failed')),
  });

  const href = anomaly ? entityHref(anomaly) : null;
  const entries = anomaly ? renderDetailEntries(anomaly.details) : [];

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {anomaly && (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Badge variant="outline" className={RISK_BADGE[anomaly.risk_level] ?? ''}>
                  {t(`dashboard.anomalies.level.${anomaly.risk_level}`, anomaly.risk_level)}
                </Badge>
                <Badge variant="outline" className={STATUS_BADGE[anomaly.status] ?? ''}>
                  {t(`anomalies.status.${anomaly.status}`, anomaly.status)}
                </Badge>
              </SheetTitle>
            </SheetHeader>

            <div className="mt-4 space-y-4">
              <div>
                <p className="text-sm font-medium">{anomaly.reason}</p>
                {anomaly.rule_id && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{anomaly.rule_id}</p>
                )}
              </div>

              {href && (
                <button
                  type="button"
                  onClick={() => navigate(href)}
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  {entityLabel(anomaly)}
                  <ExternalLink className="h-3 w-3" />
                </button>
              )}

              {entries.length > 0 && (
                <div className="rounded-lg border p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    {t('anomalies.evidence')}
                  </p>
                  <dl className="space-y-1.5">
                    {entries.map((e) => (
                      <div key={e.label} className="grid grid-cols-3 gap-2 text-sm">
                        <dt className="capitalize text-muted-foreground">{e.label}</dt>
                        <dd className="col-span-2 whitespace-pre-wrap break-words font-mono text-xs">
                          {e.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {anomaly.status !== 'open' && anomaly.resolution_note && (
                <p className="text-sm text-muted-foreground">
                  {t('anomalies.prior_note')}: {anomaly.resolution_note}
                </p>
              )}

              <Textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t('anomalies.note_placeholder')}
              />

              <div className="flex gap-2">
                <ProfessionalButton
                  variant="destructive"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ status: 'confirmed' })}
                >
                  <ShieldX className="h-4 w-4" />
                  {t('anomalies.confirm_real')}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ status: 'dismissed' })}
                >
                  <ShieldCheck className="h-4 w-4" />
                  {t('anomalies.dismiss_false')}
                </ProfessionalButton>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 4: Rework the page — tabs + URL-addressable drawer**

Replace `ui/src/pages/Anomalies.tsx` with:

```tsx
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, ShieldCheck, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react';
import {
  ProfessionalCard,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardContent,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { FeatureGate } from '@/components/FeatureGate';
import { anomaliesApi } from '@/lib/api';
import { RISK_BADGE, STATUS_BADGE, entityHref, entityLabel } from '@/lib/anomaly-ui';
import { AnomalyDetailDrawer } from '@/components/anomalies/AnomalyDetailDrawer';

const PAGE_SIZE = 20;
const STATUSES = ['open', 'confirmed', 'dismissed'] as const;

function AnomaliesList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusTab, setStatusTab] = useState<(typeof STATUSES)[number]>('open');
  const [page, setPage] = useState(0);

  const selectedId = searchParams.get('selected');

  const { data, isLoading } = useQuery({
    queryKey: ['anomalies', 'page', statusTab, page],
    queryFn: () => anomaliesApi.list({ skip: page * PAGE_SIZE, limit: PAGE_SIZE, status: statusTab }),
    staleTime: 30_000,
  });

  // The selected anomaly: prefer the row already in the list; else fetch by id.
  const listItem = data?.items.find((a) => String(a.id) === selectedId) ?? null;
  const { data: fetched } = useQuery({
    queryKey: ['anomalies', 'detail', selectedId],
    queryFn: () => anomaliesApi.get(Number(selectedId)),
    enabled: !!selectedId && !listItem,
  });
  const selected = listItem ?? fetched ?? null;

  const openDrawer = (id: number) => {
    searchParams.set('selected', String(id));
    setSearchParams(searchParams, { replace: false });
  };
  const closeDrawer = () => {
    searchParams.delete('selected');
    setSearchParams(searchParams, { replace: false });
  };

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2 text-base font-semibold">
          <ShieldAlert className="h-4 w-4 text-warning" />
          {t('anomalies.title')}
          {total > 0 && <Badge variant="outline" className="ml-1">{total}</Badge>}
        </ProfessionalCardTitle>
        <p className="text-sm text-muted-foreground">
          {t('anomalies.description', 'Items flagged by automated fraud and anomaly detection on your invoices, expenses and bank transactions.')}
        </p>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <Tabs
          value={statusTab}
          onValueChange={(v) => { setStatusTab(v as (typeof STATUSES)[number]); setPage(0); }}
          className="mb-4"
        >
          <TabsList>
            {STATUSES.map((s) => (
              <TabsTrigger key={s} value={s}>{t(`anomalies.tab.${s}`, s)}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-center">
            <ShieldCheck className="h-10 w-10 text-success" />
            <p className="font-medium">{t('anomalies.empty_title')}</p>
            <p className="text-sm text-muted-foreground">
              {t('anomalies.empty_description', 'Nothing needs review right now. New flags appear here automatically.')}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">{t('anomalies.col_risk')}</TableHead>
                    <TableHead>{t('anomalies.col_issue')}</TableHead>
                    <TableHead className="w-44">{t('anomalies.col_item')}</TableHead>
                    <TableHead className="w-40">{t('anomalies.col_detected')}</TableHead>
                    <TableHead className="w-28 text-right">{t('anomalies.col_action')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((a) => {
                    const href = entityHref(a);
                    return (
                      <TableRow
                        key={a.id}
                        className="cursor-pointer"
                        onClick={() => openDrawer(a.id)}
                      >
                        <TableCell>
                          <Badge variant="outline" className={RISK_BADGE[a.risk_level] ?? ''}>
                            {t(`dashboard.anomalies.level.${a.risk_level}`, a.risk_level)}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-md">
                          <p className="text-sm">{a.reason}</p>
                          {a.rule_id && <p className="mt-0.5 text-xs text-muted-foreground">{a.rule_id}</p>}
                        </TableCell>
                        <TableCell>
                          {href ? (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); navigate(href); }}
                              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                            >
                              {entityLabel(a)}
                              <ExternalLink className="h-3 w-3" />
                            </button>
                          ) : (
                            <span className="text-sm text-muted-foreground">{entityLabel(a)}</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge variant="outline" className={STATUS_BADGE[a.status] ?? ''}>
                            {t(`anomalies.status.${a.status}`, a.status)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {t('anomalies.page_of', { page: page + 1, pages: pageCount })}
              </p>
              <div className="flex items-center gap-2">
                <ProfessionalButton variant="outline" size="sm" disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}>
                  <ChevronLeft className="h-4 w-4" />{t('common.previous')}
                </ProfessionalButton>
                <ProfessionalButton variant="outline" size="sm" disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => p + 1)}>
                  {t('common.next')}<ChevronRight className="h-4 w-4" />
                </ProfessionalButton>
              </div>
            </div>
          </>
        )}
      </ProfessionalCardContent>
      <AnomalyDetailDrawer anomaly={selected} open={!!selectedId} onClose={closeDrawer} />
    </ProfessionalCard>
  );
}

export default function Anomalies() {
  return (
    <FeatureGate feature="anomaly_detection" showUpgradePrompt>
      <AnomaliesList />
    </FeatureGate>
  );
}
```

- [ ] **Step 5: Add i18n keys**

In `ui/src/i18n/locales/en.json`, under the `anomalies` object, add: `"resolved": "Anomaly resolved"`, `"resolve_failed": "Could not resolve the anomaly"`, `"evidence": "Evidence"`, `"prior_note": "Note"`, `"note_placeholder": "Optional note (why you're confirming or dismissing)"`, `"confirm_real": "Confirm real"`, `"dismiss_false": "False positive"`, and the objects `"tab": { "open": "Open", "confirmed": "Confirmed", "dismissed": "Dismissed" }` and `"status": { "open": "Open", "confirmed": "Confirmed", "dismissed": "Dismissed" }`. (`fallbackLng: 'en'`, so en-only is sufficient.)

- [ ] **Step 6: Write the failing component test**

Create `ui/src/components/anomalies/__tests__/Anomalies.test.tsx`:

```tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Anomalies from '@/pages/Anomalies';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string, fb?: unknown) => (typeof fb === 'string' ? fb : key) }),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/components/FeatureGate', () => ({
  FeatureGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const listMock = vi.fn();
const resolveMock = vi.fn().mockResolvedValue({ id: 1, status: 'confirmed' });
vi.mock('@/lib/api', () => ({
  anomaliesApi: {
    list: (...a: unknown[]) => listMock(...a),
    get: vi.fn(),
    resolve: (...a: unknown[]) => resolveMock(...a),
  },
}));

const row = {
  id: 1, entity_type: 'invoice', entity_id: 9, risk_score: 80, risk_level: 'high',
  reason: 'Duplicate billing', rule_id: 'duplicate_billing', details: { amount: 100 },
  created_at: '2026-06-01T00:00:00Z', status: 'open', statement_id: null,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/anomalies']}>
        <Anomalies />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Anomalies triage page', () => {
  beforeEach(() => {
    listMock.mockReset();
    listMock.mockResolvedValue({ total: 1, summary: {}, skip: 0, limit: 20, items: [row] });
    resolveMock.mockClear();
  });

  it('lists with the default open status filter', async () => {
    renderPage();
    await waitFor(() => expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ status: 'open' })));
    expect(await screen.findByText('Duplicate billing')).toBeInTheDocument();
  });

  it('switches the status filter when a tab is clicked', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Duplicate billing');
    await user.click(screen.getByText('Confirmed'));
    await waitFor(() => expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ status: 'confirmed' })));
  });

  it('opens the drawer and resolves as confirmed', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByText('Duplicate billing'));
    const confirm = await screen.findByText('Confirm real');
    await user.click(confirm);
    await waitFor(() => expect(resolveMock).toHaveBeenCalledWith(1, 'confirmed', undefined));
  });
});
```

- [ ] **Step 7: Run the component test + type-check**

Run: `docker compose exec ui npx vitest run src/components/anomalies/__tests__/Anomalies.test.tsx`
Expected: PASS (3 passed).

Run: `docker compose exec ui npx tsc --noEmit`
Expected: no NEW errors in `anomalies.ts`, `anomaly-ui.ts`, `AnomalyDetailDrawer.tsx`, `Anomalies.tsx`.

- [ ] **Step 8: Commit**

```bash
git add ui/src/lib/api/anomalies.ts ui/src/lib/anomaly-ui.ts ui/src/components/anomalies/AnomalyDetailDrawer.tsx ui/src/pages/Anomalies.tsx ui/src/components/anomalies/__tests__/Anomalies.test.tsx ui/src/i18n/locales/en.json
git commit -m "feat(ui): anomaly triage queue — detail drawer + confirm/dismiss tabs"
```

---

## Self-Review

**1. Spec coverage:**
- Data model `status` + `resolution_note` + `is_dismissed` mirror + backfill → Task 1. ✓
- `PATCH /resolve`, `GET /{id}`, `status` list filter, `dismiss` alias, serialization with new fields → Task 2. ✓
- Frontend: filter tabs, URL-addressable drawer (`?selected=`), generic evidence render, Confirm/Dismiss with note → Task 3. ✓
- Backward compat (legacy `is_dismissed` filter + summary, super-admin aggregator) → Task 2 keeps `is_dismissed` path + mirror; summary unchanged. ✓
- Dashboard card / sidebar unchanged (still key off the open summary) → no task needed. ✓
- Testing (model, router, frontend) → Tasks 1 / 2 / 3. ✓

**2. Placeholder scan:** none — every code step has complete code; every run step has its command + expected result.

**3. Type/name consistency:** `status` values (`open`/`confirmed`/`dismissed`), `_serialize_anomaly`, `_apply_resolution`, `ResolveAnomalyRequest`, `RESOLVABLE_STATUSES`, the mirror `is_dismissed = (status != "open")`, and the frontend `AnomalyStatus`, `anomaliesApi.resolve(id, status, note?)`, `STATUS_BADGE`, `renderDetailEntries` are used identically across tasks. The serialized `resolved_at`/`resolved_by_id` map to the `dismissed_at`/`dismissed_by_id` columns consistently in Task 2.

**Note (deliberate deviation from spec wording):** the spec mentioned "the existing per-tenant migration path (`db_init.py`)" and an Alembic migration in passing; the plan uses **`db_init` only and no Alembic migration**, because the `anomalies` table is not Alembic-managed (it is created by `create_all`) and Alembic is not auto-run at startup — an Alembic migration referencing `anomalies` would break `alembic upgrade head` on a fresh DB. This matches the established pattern for this table.
