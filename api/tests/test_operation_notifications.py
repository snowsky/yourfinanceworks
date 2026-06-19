import core.services.operation_notifications as on


class _FakeSettings:
    def __init__(self, value):
        self.value = value


class _Q:
    def __init__(self, row):
        self._row = row
    def filter(self, *a, **k):
        return self
    def first(self):
        return self._row


class _DB:
    def __init__(self, email_config_row=None):
        self._row = email_config_row
    def query(self, *a, **k):
        return _Q(self._row)


def test_noop_when_email_config_absent():
    # No Settings row -> returns None, sends nothing, never raises.
    on.maybe_send_operation_notification(
        _DB(None), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={},
    )


def test_noop_when_email_disabled():
    row = _FakeSettings({"enabled": False, "provider": "ses"})
    on.maybe_send_operation_notification(
        _DB(row), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={},
    )


def test_sends_when_enabled(monkeypatch):
    sent = {}

    class _NS:
        def __init__(self, db, email_service):
            sent["constructed"] = True
        def send_operation_notification(self, **kwargs):
            sent["call"] = kwargs
            return True

    monkeypatch.setattr(on, "NotificationService", _NS)
    monkeypatch.setattr(on, "EmailService", lambda config: object())
    monkeypatch.setattr(on, "EmailProviderConfig", lambda **k: object())
    monkeypatch.setattr(on, "EmailProvider", lambda v: v)
    monkeypatch.setattr(on, "_tenant_company_name", lambda tenant_id: "Acme Inc")

    row = _FakeSettings({"enabled": True, "provider": "ses", "from_email": "a@b.com"})
    on.maybe_send_operation_notification(
        _DB(row), event_type="client_created", user_id=1, tenant_id=1,
        resource_type="client", resource_id="5", resource_name="Acme", details={"email": "x@y.com"},
    )
    assert sent["call"]["event_type"] == "client_created"
    assert sent["call"]["company_name"] == "Acme Inc"
