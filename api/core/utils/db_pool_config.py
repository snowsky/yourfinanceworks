"""Env-tunable SQLAlchemy engine pool settings.

The per-tenant pool is created once per worker PROCESS, so the total connections
a tenant can consume is:  workers x (pool_size + max_overflow) x active_tenants.
That product must stay under Postgres `max_connections`. Making these knobs
env-configurable lets ops right-size the connection budget when scaling workers
(or front the DB with pgbouncer) without code changes.

Defaults preserve the previous hardcoded behavior (pool_size=5, max_overflow=10,
pool_timeout=10, pool_recycle=300, pool_pre_ping=True), so this changes nothing
unless the env vars are set.

The primary master engine is a single shared pool (not one-per-tenant), so it
uses its own ``DB_MASTER_POOL_*`` family with a larger 10/20 baseline.
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


def pool_engine_kwargs(
    prefix: str = "DB_POOL",
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 10,
    pool_recycle: int = 300,
) -> dict:
    """Return create_engine pool kwargs from env (``<prefix>_*``), with safe defaults.

    ``prefix`` selects the env-var family so different engines can be tuned
    independently: per-tenant engines use the default ``DB_POOL`` family, while the
    primary master engine uses ``DB_MASTER_POOL`` (it carries a larger baseline
    because it is a single shared pool, not one-per-tenant). The keyword arguments
    are the fallbacks used when an env var is unset, so each engine keeps its own
    baseline size unless explicitly overridden.
    """
    return {
        "pool_pre_ping": True,
        "pool_recycle": _int_env(f"{prefix}_RECYCLE", pool_recycle),
        "pool_size": _int_env(f"{prefix}_SIZE", pool_size),
        "max_overflow": _int_env(f"{prefix}_MAX_OVERFLOW", max_overflow),
        "pool_timeout": _int_env(f"{prefix}_TIMEOUT", pool_timeout),
    }
