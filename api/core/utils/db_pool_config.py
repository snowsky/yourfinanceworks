"""Env-tunable SQLAlchemy engine pool settings.

The per-tenant pool is created once per worker PROCESS, so the total connections
a tenant can consume is:  workers x (pool_size + max_overflow) x active_tenants.
That product must stay under Postgres `max_connections`. Making these knobs
env-configurable lets ops right-size the connection budget when scaling workers
(or front the DB with pgbouncer) without code changes.

Defaults preserve the previous hardcoded behavior (pool_size=5, max_overflow=10,
pool_timeout=10, pool_recycle=300, pool_pre_ping=True), so this changes nothing
unless the env vars are set.
"""

import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def pool_engine_kwargs() -> dict:
    """Return create_engine pool kwargs from env (DB_POOL_*), with safe defaults."""
    return {
        "pool_pre_ping": True,
        "pool_recycle": _int_env("DB_POOL_RECYCLE", 300),
        "pool_size": _int_env("DB_POOL_SIZE", 5),
        "max_overflow": _int_env("DB_POOL_MAX_OVERFLOW", 10),
        "pool_timeout": _int_env("DB_POOL_TIMEOUT", 10),
    }
