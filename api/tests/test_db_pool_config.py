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
