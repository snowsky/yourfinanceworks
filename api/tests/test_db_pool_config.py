import core.utils.db_pool_config as dpc


def test_defaults_preserve_previous_hardcoded_behavior(monkeypatch):
    for var in ("DB_POOL_RECYCLE", "DB_POOL_SIZE", "DB_POOL_MAX_OVERFLOW", "DB_POOL_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    assert dpc.pool_engine_kwargs() == {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 10,
    }


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "2")
    monkeypatch.setenv("DB_POOL_MAX_OVERFLOW", "2")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "5")
    kw = dpc.pool_engine_kwargs()
    assert kw["pool_size"] == 2
    assert kw["max_overflow"] == 2
    assert kw["pool_timeout"] == 5
    assert kw["pool_recycle"] == 300  # untouched -> default


def test_blank_or_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "")
    monkeypatch.setenv("DB_POOL_MAX_OVERFLOW", "notanint")
    kw = dpc.pool_engine_kwargs()
    assert kw["pool_size"] == 5
    assert kw["max_overflow"] == 10


def test_master_prefix_is_an_independent_env_family(monkeypatch):
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.setenv("DB_MASTER_POOL_SIZE", "15")
    # master family reads its own var...
    assert dpc.pool_engine_kwargs("DB_MASTER_POOL", pool_size=10, max_overflow=20)["pool_size"] == 15
    # ...and does not bleed into the default per-tenant family
    assert dpc.pool_engine_kwargs()["pool_size"] == 5


def test_custom_defaults_preserve_master_baseline_when_env_unset(monkeypatch):
    for var in (
        "DB_MASTER_POOL_SIZE",
        "DB_MASTER_POOL_MAX_OVERFLOW",
        "DB_MASTER_POOL_TIMEOUT",
        "DB_MASTER_POOL_RECYCLE",
    ):
        monkeypatch.delenv(var, raising=False)
    # This is exactly how database.py builds the primary master engine.
    assert dpc.pool_engine_kwargs("DB_MASTER_POOL", pool_size=10, max_overflow=20) == {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 10,
    }
