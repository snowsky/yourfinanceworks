from types import SimpleNamespace

from core.services.onboarding_assistant import OnboardingAssistantService


class _Query:
    def __init__(self, store, model_name):
        self._store = store
        self._model = model_name

    def filter(self, *args):
        return self

    def first(self):
        return self._store.get(self._model)


class _FakeDB:
    """Minimal stand-in: maps a model name to a single stored row."""

    def __init__(self, ai_config_row=None, settings_row=None):
        self.rows = {"AIConfig": ai_config_row, "Settings": settings_row}
        self.added = []
        self.committed = False

    def query(self, entity):
        name = getattr(entity, "__name__", "AIConfig")
        return _Query(self.rows, name)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True


def test_status_reports_not_configured_and_not_dismissed(monkeypatch):
    # Isolate the DB-config resolution from the env fallback.
    monkeypatch.setattr(OnboardingAssistantService, "_env_ai_configured", lambda self: False)
    svc = OnboardingAssistantService(_FakeDB())
    assert svc.status() == {"ai_configured": False, "dismissed": False}


def test_status_reports_configured_when_active_default_config_exists():
    active = SimpleNamespace(is_active=True, is_default=True)
    svc = OnboardingAssistantService(_FakeDB(ai_config_row=active))
    assert svc.status()["ai_configured"] is True


def test_status_reports_dismissed_when_settings_flag_set(monkeypatch):
    monkeypatch.setattr(OnboardingAssistantService, "_env_ai_configured", lambda self: False)
    settings_row = SimpleNamespace(value={"dismissed": True})
    svc = OnboardingAssistantService(_FakeDB(settings_row=settings_row))
    assert svc.status()["dismissed"] is True


def test_dismiss_adds_settings_row_and_commits():
    db = _FakeDB()
    svc = OnboardingAssistantService(db)
    result = svc.dismiss()
    assert result["dismissed"] is True
    assert db.committed is True
    assert len(db.added) == 1
