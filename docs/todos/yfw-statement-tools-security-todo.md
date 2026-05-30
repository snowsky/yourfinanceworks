# TODO: yfw-statement-tools security review (separate client)

> **Status:** Parked. `yfw-statement-tools` is a separate client/service with its own
> trust model and public unauthenticated tier. These findings are **RELAYED from an
> automated review and NOT independently verified** — confirm each against source
> before acting. (In the parent review, 2 of 5 verified API claims turned out to be
> false positives, so treat severity labels as provisional.)
>
> Date parked: 2026-05-30. Source: bank-statement consolidated review.

## To verify first
Open these files and confirm before scheduling fixes:
- `yfw-statement-tools/backend/auth.py`
- `yfw-statement-tools/backend/routers/statements.py`
- `yfw-statement-tools/backend/services/internal_client.py`
- `yfw-statement-tools/.env` (is it gitignored? rotate if a real secret leaked)

## Findings (provisional severity)

### CRITICAL (claimed)
- **Committed `.env` JWT secret** — `.env:9` `YFW_SECRET_KEY=...placeholder`. Confirm
  `.env` is gitignored; ship only `.env.example`; rotate any deployment that used it.
- **Public visitor identity is client-controlled** — `auth.py` trusts
  `X-Public-Visitor-Id` / `X-Public-Tenant-Id` headers with no signing → quota bypass
  + tenant impersonation. Needs server-issued signed/short-lived visitor tokens.
- **`user_id=1` hardcoded** — `internal_client.py:158` attributes all internal-mode
  batch jobs to user 1. Thread the real `per_tenant_user_id` through.
- **Batch IDOR** — `GET /batch/jobs/{job_id}`, `/csv`, `POST /batch/merge-csv` have no
  local ownership check; ownership fully delegated upstream. Confirm upstream enforces
  it, else add a `{job_id -> user/tenant}` guard.
- **Tenant context from user headers in internal mode** — `_tenant_id_arg` falls back to
  client-supplied tenant id; pass tenant/user from the validated JWT instead.

### HIGH (claimed)
- **No rate limiting on any endpoint**, including public upload.
- **CSV formula injection** in generated CSVs (`_build_csv`, merge writer) — sanitize
  cells starting with `= + - @ \t \r`.
- **File-size check after full `await file.read()`** (`statements.py:130`) — public 1 MB
  tier unenforceable pre-buffer; memory-exhaustion DoS.
- **No per-request file-count limit** — multiplies the DoS surface.
- **Path-traversal guard relies only on `uuid.UUID(token)`** — add explicit containment
  check that resolved path stays under temp dir.

### MEDIUM (claimed)
- Extension-only file validation (no magic bytes).
- `postMessage(..., '*')` for usage tracking (frontend) — pin parent origin.
- Visitor-id fallback uses `Math.random()` — use `crypto.randomUUID()` only.
- `job_id` not format-validated before upstream URL construction (SSRF amplification).
- Internal exception messages leaked in HTTP responses.
- CORS `allow_origins: ["*"]` default.

### LOW (claimed)
- Swagger/ReDoc enabled unconditionally.
- Deprecated `@app.on_event("startup")`.
- Temp-cleanup races with download endpoint (possible 500 → return 410).

## Architecture note
Duplicates the main app's JWT auth and statement-parsing path (HTTP vs internal mode).
Keeping the two trust/parse paths in sync is a standing maintenance risk.
