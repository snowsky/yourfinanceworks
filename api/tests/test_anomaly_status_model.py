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


def test_new_anomaly_alerted_at_defaults_to_none(db_session):
    a = Anomaly(entity_type="invoice", entity_id=99, risk_score=80.0,
                risk_level="high", reason="x")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    assert a.alerted_at is None
    db_session.delete(a)
    db_session.commit()
