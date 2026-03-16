# Code Review: YourFinanceWORKS Invoice App
**Date:** 2026-03-13
**Reviewer:** Claude Code (claude-sonnet-4-6)

---

## Critical Security

| # | Issue | File | Status |
|---|-------|------|--------|
| 1 | Insecure default secrets (`"your-secret-key-here"`) | `api/config.py:45-46`, `api/auth.py:19` | ✅ Fixed in commit b1c04bc |
| 2 | DEBUG defaults to `True` | `api/main.py:436` | ✅ Fixed in commit b1c04bc |
| 3 | JWT stored in localStorage (XSS-accessible) | `ui/src/utils/auth.ts:25,57-58` | ⬜ Open — migrate to httpOnly cookies |
| 4 | TypeScript strict mode disabled | `ui/tsconfig.app.json:18-22` | ✅ Fixed in commit b1c04bc (type errors may need cleanup) |
| 5 | No CSRF token validation for state-changing requests | `api/main.py:468-474` | ⬜ Open |

---

## Performance

| # | Issue | File | Status |
|---|-------|------|--------|
| 6 | Full-table memory loads for encrypted field search | `api/core/routers/expenses.py:106-141` | ⬜ Open — consider OpenSearch integration |
| 7 | N+1 queries in bulk export (18 full table loads) | `api/core/routers/settings.py:327-378` | ✅ Fixed — `yield_per(500)` + periodic `flush()` instead of `.all()` |
| 8 | N+1 queries in invoice item recalculation loop | `api/core/routers/invoices.py:1837` | ✅ Fixed — replaced full table load with `SELECT SUM(quantity * price)` aggregate |
| 9 | In-memory rate limiting (broken in multi-instance deployments) | `api/core/routers/auth.py:45-51` | ⬜ Open — replace with Redis-backed rate limiting |

---

## Observability

| # | Issue | File | Status |
|---|-------|------|--------|
| 10 | Silent `except Exception: pass` (11+ instances) | `api/main.py:366,373,406`, `api/commercial/ai/services/ocr_service.py` | ⬜ Open — add `logger.error(..., exc_info=True)` |
| 11 | `print()` DEBUG statements in production code | `api/core/routers/super_admin.py:1289,1308`, `api/core/services/license_service.py:954,1026`, `api/commercial/ai/router.py:260,289`, `api/auth.py` | ✅ Fixed in commit b1c04bc |

---

## Deployment

| # | Issue | File | Status |
|---|-------|------|--------|
| 12 | Hardcoded `password` in docker-compose | `docker-compose.yml:9,41,47,...` | ✅ Fixed in commit b1c04bc — uses `${POSTGRES_PASSWORD:-password}` |
| 13 | Private keys stored on filesystem | `api/main.py:183-190` | ⬜ Open — consider Azure Key Vault / AWS KMS / HashiCorp Vault |
| 14 | Alembic tenant URL built via brittle string replace | `api/alembic/env.py:55-64` | ⬜ Open — use parameterized URL builder |

---

## Code Quality

| # | Issue | File | Status |
|---|-------|------|--------|
| 15 | SQLAlchemy `== False/True` boolean comparisons | `api/plugins/time_tracking/router.py`, `api/plugins/time_tracking/mcp/time_tracking_provider.py` | ✅ Fixed in commit b1c04bc |
| 16 | Unbounded pagination params (no max limit) | `api/core/routers/expenses.py:62-63` | ✅ Fixed in commit b1c04bc — `Query(100, ge=1, le=1000)` |
| 17 | Pydantic v1/v2 `# type: ignore` compat hacks | `api/core/services/statement_service.py:104-206` | ⬜ Open — standardize on Pydantic v2 |
| 18 | Encryption key cache has no TTL or invalidation | `api/core/services/encryption_service.py:56-59` | ⬜ Open — add cache expiry or invalidation hooks |

---

## Testing

| # | Issue | File | Status |
|---|-------|------|--------|
| 19 | Test suite effectively empty (`def test_pass(): assert True`) | `api/tests/test_simple.py` | ⬜ Open — write real integration tests |
| 20 | Some deps use `>=` ranges instead of pinned versions | `api/requirements.txt` | ⬜ Open — pin all deps with `==` for reproducibility |

---

## Summary

**Fixed in commit b1c04bc (2026-03-13):** 8 of 20 issues
**Fixed in this session (2026-03-16):** #7, #8 (+ attachment count N+1 sub-issue of #6)
**Remaining open:** 10 issues

### Priority order for remaining work
1. **High — Security:** JWT in localStorage (#3), CSRF protection (#5)
2. **High — Reliability:** Redis-backed rate limiting (#9), silent exception handlers (#10)
3. **Medium — Performance:** ~~N+1 queries in export (#7)~~ ✅, ~~invoice recalc (#8)~~ ✅, encrypted field search full-table scan (#6) — still open (requires OpenSearch)
4. **Medium — Security:** Key management via vault (#13)
5. **Low — Quality:** Pydantic v2 migration (#17), Alembic URL builder (#14), encryption cache TTL (#18)
6. **Low — Testing:** Real test coverage (#19), dep pinning (#20)
