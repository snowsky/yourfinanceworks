"""feature_gate must open the master DB session with a deterministic lifecycle.

Regression test for master-pool exhaustion: LicenseService self-creates a master
session via next(get_master_db()) (in _get_or_create_global_installation) and only
releases it on GC. Under concurrent load / a dashboard burst those checked-out
master connections pile up and exhaust the master pool, raising QueuePool timeouts.

feature_gate is the hot path (every protected request runs a check), so it must
open the master session itself and close it in a finally — passing it to
LicenseService so nothing is self-created and leaked.
"""

import pytest
from fastapi import HTTPException

import core.utils.feature_gate as fg


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeLicense:
    """Stand-in for LicenseService; records the master_db it was handed."""

    last_master_db = None

    def __init__(self, db, master_db=None):
        _FakeLicense.last_master_db = master_db
        self._allow = True

    def has_feature_for_gating(self, feature_id):
        return self._allow

    def has_feature_read_only(self, feature_id):
        return self._allow

    def get_trial_status(self):
        return {"is_trial": False, "trial_active": False, "in_grace_period": False}

    def get_license_status(self):
        return {"is_licensed": False, "license_status": "invalid"}


def _patch(monkeypatch, allow=True):
    """Patch feature_gate's SessionLocal + LicenseService; return the created sessions."""
    created = []

    def _factory():
        s = _FakeSession()
        created.append(s)
        return s

    monkeypatch.setattr(fg, "SessionLocal", _factory)

    class _L(_FakeLicense):
        def __init__(self, db, master_db=None):
            super().__init__(db, master_db=master_db)
            self._allow = allow

    monkeypatch.setattr(fg, "LicenseService", _L)
    return created


def test_check_feature_allow_closes_master_session(monkeypatch):
    created = _patch(monkeypatch, allow=True)
    fg.check_feature("ai_chat", db="tenant-db")  # allow path: no raise
    assert len(created) == 1
    assert created[0].closed is True
    assert _FakeLicense.last_master_db is created[0]  # handed to LicenseService


def test_check_feature_denied_still_closes_master_session(monkeypatch):
    created = _patch(monkeypatch, allow=False)
    with pytest.raises(HTTPException) as exc:
        fg.check_feature("ai_chat", db="tenant-db")  # denied: raises 402
    assert exc.value.status_code == 402
    assert created[0].closed is True  # finally ran despite the raise


def test_feature_enabled_closes_master_session(monkeypatch):
    created = _patch(monkeypatch, allow=True)
    assert fg.feature_enabled("ai_chat", db="tenant-db") is True
    assert created[0].closed is True
    assert _FakeLicense.last_master_db is created[0]


def test_check_feature_read_only_closes_master_session(monkeypatch):
    created = _patch(monkeypatch, allow=True)
    fg.check_feature_read_only("cloud_storage", db="tenant-db")
    assert created[0].closed is True
    assert _FakeLicense.last_master_db is created[0]
