"""Tests for the tenant-facing anomaly endpoints (core/routers/anomalies.py).

The endpoint functions are invoked directly with the in-memory `db_session`
and a fake current user, so we exercise the real query/scoping/gating logic
without standing up the full HTTP + tenant-resolution stack.

Cross-tenant isolation is structural: each tenant has its own database, and the
endpoint only ever queries the injected session. These tests assert the
endpoint reads exclusively from that session (never a global/all-tenant scope).
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core.models.models_per_tenant import Anomaly
from core.routers import anomalies as anomalies_router
from core.routers.anomalies import (
    DismissAnomalyRequest,
    ResolveAnomalyRequest,
    dismiss_anomaly,
    get_anomaly,
    list_anomalies,
    resolve_anomaly,
)
from core.services.feature_config_service import FeatureConfigService


@pytest.fixture
def user():
    return SimpleNamespace(id=7, tenant_id=1)


@pytest.fixture
def feature_on(monkeypatch):
    monkeypatch.setattr(
        FeatureConfigService, "is_enabled", staticmethod(lambda *a, **k: True)
    )


@pytest.fixture
def feature_off(monkeypatch):
    monkeypatch.setattr(
        FeatureConfigService, "is_enabled", staticmethod(lambda *a, **k: False)
    )


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


@pytest.mark.asyncio
async def test_list_returns_open_items_sorted_with_summary(db_session, user, feature_on):
    _make_anomaly(db_session, risk_level="low", risk_score=20.0, entity_id=1)
    _make_anomaly(db_session, risk_level="critical", risk_score=95.0, entity_id=2)
    _make_anomaly(db_session, risk_level="high", risk_score=70.0, entity_id=3)
    # A dismissed one must be excluded from the default (open) view + summary.
    _make_anomaly(db_session, risk_level="high", risk_score=99.0, entity_id=4,
                  is_dismissed=True)

    result = await list_anomalies(
        skip=0, limit=50, risk_level=None, status=None, is_dismissed=False,
        db=db_session, current_user=user,
    )

    assert result["total"] == 3
    # Highest risk_score first.
    assert [i["risk_score"] for i in result["items"]] == [95.0, 70.0, 20.0]
    # Summary counts open anomalies by level; the dismissed high one is excluded.
    assert result["summary"] == {"critical": 1, "high": 1, "medium": 0, "low": 1}


@pytest.mark.asyncio
async def test_list_risk_level_filter(db_session, user, feature_on):
    _make_anomaly(db_session, risk_level="low", entity_id=1)
    _make_anomaly(db_session, risk_level="critical", entity_id=2)

    result = await list_anomalies(
        skip=0, limit=50, risk_level="critical", status=None, is_dismissed=False,
        db=db_session, current_user=user,
    )

    assert result["total"] == 1
    assert result["items"][0]["entity_id"] == 2


@pytest.mark.asyncio
async def test_list_pagination(db_session, user, feature_on):
    for i in range(5):
        _make_anomaly(db_session, risk_score=float(i), entity_id=i + 1)

    page = await list_anomalies(
        skip=2, limit=2, risk_level=None, status=None, is_dismissed=False,
        db=db_session, current_user=user,
    )

    assert page["total"] == 5
    assert len(page["items"]) == 2


@pytest.mark.asyncio
async def test_list_feature_disabled_raises_403(db_session, user, feature_off):
    with pytest.raises(HTTPException) as exc:
        await list_anomalies(
            skip=0, limit=50, risk_level=None, status=None, is_dismissed=False,
            db=db_session, current_user=user,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_dismiss_sets_fields(db_session, create_test_user, feature_on):
    # dismissed_by_id is a real FK to users.id, so persist a user first.
    actor = create_test_user(email="dismisser@example.com")
    a = _make_anomaly(db_session, entity_id=11)

    result = await dismiss_anomaly(
        anomaly_id=a.id,
        payload=DismissAnomalyRequest(notes="confirmed duplicate"),
        db=db_session,
        current_user=actor,
    )

    assert result == {"id": a.id, "is_dismissed": True}
    refreshed = db_session.query(Anomaly).filter(Anomaly.id == a.id).first()
    assert refreshed.is_dismissed is True
    assert refreshed.dismissed_by_id == actor.id
    assert refreshed.dismissed_at is not None
    assert refreshed.dismiss_notes == "confirmed duplicate"

    # Drop the anomaly -> users FK link before the shared fixture teardown,
    # which deletes the users table and would otherwise hit a FK violation
    # (and leak rows into later tests).
    db_session.delete(refreshed)
    db_session.commit()


@pytest.mark.asyncio
async def test_dismiss_unknown_id_raises_404(db_session, user, feature_on):
    with pytest.raises(HTTPException) as exc:
        await dismiss_anomaly(
            anomaly_id=999999,
            payload=DismissAnomalyRequest(),
            db=db_session,
            current_user=user,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_dismiss_feature_disabled_raises_403(db_session, user, feature_off):
    a = _make_anomaly(db_session, entity_id=12)
    with pytest.raises(HTTPException) as exc:
        await dismiss_anomaly(
            anomaly_id=a.id,
            payload=DismissAnomalyRequest(),
            db=db_session,
            current_user=user,
        )
    assert exc.value.status_code == 403
    # Must not have been mutated.
    refreshed = db_session.query(Anomaly).filter(Anomaly.id == a.id).first()
    assert refreshed.is_dismissed is False


@pytest.mark.asyncio
async def test_list_only_reads_injected_session(db_session, user, feature_on, monkeypatch):
    """Guards the isolation contract: the endpoint queries the injected tenant
    session only, never a cross-tenant/global path."""
    _make_anomaly(db_session, entity_id=1)

    # If the endpoint tried to reach the cross-tenant manager, fail loudly.
    import core.routers.anomalies as mod
    if hasattr(mod, "tenant_db_manager"):
        monkeypatch.setattr(
            mod.tenant_db_manager, "get_tenant_session",
            lambda *a, **k: pytest.fail("endpoint must not use cross-tenant sessions"),
            raising=False,
        )

    result = await list_anomalies(
        skip=0, limit=50, risk_level=None, status=None, is_dismissed=False,
        db=db_session, current_user=user,
    )
    assert result["total"] == 1


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
        db=db_session, current_user=(user_fixture_id := actor),
    )
    assert result["total"] == 1
    assert result["items"][0]["entity_id"] == 32
    assert result["items"][0]["status"] == "confirmed"
    # cleanup the confirmed row (FK to users)
    db_session.delete(db_session.query(Anomaly).filter(Anomaly.id == confirmed.id).first())
    db_session.commit()
