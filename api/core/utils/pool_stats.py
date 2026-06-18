"""Optional, env-gated DB connection-pool instrumentation.

Diagnostic only. Enable by setting ``YFW_LOG_POOL_STATS=1`` in the api
container's environment and restarting the api service, then watch the logs
while driving load (see ``api/scripts/pool_loadtest.py``). It logs every pool
checkout/checkin with live counts so you can see a tenant's pool climb toward
its 15-connection ceiling and confirm whether it drains back down (concurrency)
or not (leak).

No-op unless the env var is set, so it is safe to leave wired in.
"""

import logging
import os

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("yfw.pool_stats")

POOL_STATS_ENABLED = os.getenv("YFW_LOG_POOL_STATS", "").lower() in ("1", "true", "yes")


def _stats(pool) -> str:
    try:
        return f"size={pool.size()} checkedout={pool.checkedout()} overflow={pool.overflow()}"
    except Exception:
        return "stats-unavailable"


def maybe_log_pool(engine: Engine, label: str) -> None:
    """Attach checkout/checkin loggers to ``engine`` when YFW_LOG_POOL_STATS is set."""
    if not POOL_STATS_ENABLED:
        return

    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, conn_record, conn_proxy):  # noqa: ANN001
        logger.warning("[pool %s] checkout %s", label, _stats(engine.pool))

    @event.listens_for(engine, "checkin")
    def _on_checkin(dbapi_conn, conn_record):  # noqa: ANN001
        logger.warning("[pool %s] checkin  %s", label, _stats(engine.pool))
