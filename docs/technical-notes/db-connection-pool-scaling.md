# DB Connection Pool & Worker Scaling

Context for tuning the API's DB connection usage, especially for AI-chat-heavy
load. Background: PRs #409 (stop-the-bleeding), #412 (in-process MCP client,
Layer 2a) and #411 (release connection during LLM calls, Layer 2b) fixed the
per-tenant pool *exhaustion* and the self-HTTP *amplification*. The remaining
lever under high concurrency is **how many worker processes** the API runs.

## The architecture that matters

- The app uses **database-per-tenant**. Each tenant gets its own cached
  SQLAlchemy engine + pool, created **once per worker process**
  (`core/services/tenant_database_manager.py`).
- `ai_chat` and most routers are `async def` but do **synchronous** DB I/O
  inline. A sync DB call in an async coroutine **blocks that worker's single
  event loop** for its duration — including a connection-checkout wait under
  pool contention. So one worker can be starved by a burst of concurrent AI
  chats even when the pool itself isn't fully exhausted.
- **Production currently runs a single uvicorn worker** (`docker-compose-quay.yml`
  api command = `uvicorn main:app … --reload`) → **one event loop**. That is the
  dominant bottleneck observed in load testing (20 concurrent `/ai/chat` starves
  `/invoices/`).

## The connection-budget formula (read before adding workers)

The per-tenant pool is **per worker process**, so total connections a single
tenant can consume is:

```
workers x (DB_POOL_SIZE + DB_POOL_MAX_OVERFLOW) x active_tenants  ≤  Postgres max_connections
```

Adding workers multiplies connections. With the defaults (pool 5 + overflow 10 =
15/tenant/worker) and Postgres default `max_connections=100`, even a few workers
× a few active tenants blows the limit. **Do not bump workers without
right-sizing the pool and/or raising `max_connections` (or fronting the DB with
pgbouncer).**

## The knobs (new, env-tunable; defaults unchanged)

`core/utils/db_pool_config.py` reads these (defaults preserve prior behavior):

| Env var | Default | Meaning |
| --- | --- | --- |
| `DB_POOL_SIZE` | 5 | persistent connections per engine (per tenant, per worker) |
| `DB_POOL_MAX_OVERFLOW` | 10 | burst connections beyond pool_size |
| `DB_POOL_TIMEOUT` | 10 | seconds to wait for a connection before failing fast |
| `DB_POOL_RECYCLE` | 300 | recycle connections after N seconds |

## Recommended production deployment

1. **Drop `--reload`** from the prod (`docker-compose-quay.yml`) api command — it's
   a dev-only flag (file-watching, single worker).
2. **Run multiple workers** with gunicorn + uvicorn workers (add `gunicorn` to
   `api/requirements.txt`):
   ```
   gunicorn main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-4} \
     --bind 0.0.0.0:8000 --timeout 120
   ```
   (or `uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-4}`).
3. **Right-size the pool to stay under `max_connections`.** Example: to go from 1
   worker to 4 while keeping the per-tenant budget ~constant, set
   `DB_POOL_SIZE=2` and `DB_POOL_MAX_OVERFLOW=2` (4 workers × 4 ≈ the prior 15/tenant).
   For real scale, prefer **pgbouncer** (transaction pooling) in front of Postgres
   and/or raise `max_connections`.
4. Re-run `api/scripts/pool_loadtest.py` (`list my clients` body, 20 concurrent)
   and confirm the `/invoices/` probe stays fast and `grep QueuePool` in the logs
   stays empty.

## When to do the deeper refactor (only if the above isn't enough)

If, after multiple workers + right-sized pools, concurrent AI chats still starve
the loop, the next step is to stop doing **synchronous DB I/O on the event loop** —
offload it via `asyncio.to_thread`/`run_in_executor`, or move to an async DB
driver (asyncpg + SQLAlchemy async). That's a substantial refactor; the
worker/pool tuning above is the cheaper first move and is usually sufficient.
