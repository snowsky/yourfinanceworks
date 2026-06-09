# Client-Login Portal (Competitor #5, final piece) — Plan

**Status:** Planned (not started)
**Decisions (2026-06):** Passwordless **magic-link** auth · capabilities = invoice list + branded view/download **+ payment status/balance + contact-info editing** · **commercial feature-gated** (`client_portal`).

Builds on the shipped branding work (#362–#367) — the portal itself reuses `invoice_branding` so it's company-branded.

---

## Goal
A tenant's **clients** (not staff) log in passwordlessly to a branded portal to see *all* their invoices, payment status/balance, download branded PDFs, and update their contact details.

## Reuse (from research)
- **Magic-link** = mirror `PasswordResetToken` (`models.py:84-98`): `secrets.token_urlsafe(32)`, 1h expiry, one-time-use.
- **JWT** machinery (`auth.py`), **email** (`build_tenant_email_service`), **rate limiter** (`core/utils/rate_limiter.py record_and_check`), **public-endpoint + tenant-bypass** pattern (mobile-expense app in `tenant_context_middleware.py` is the precedent for a 2nd user type).
- **PDF** generator (slices 3–6) for branded downloads.
- **Feature gating**: `feature_enabled(...)` backend + `FeatureGate`/`useFeatures()` frontend.

## The hard problem — encrypted email lookup
`Client.email` is an `EncryptedColumn` (AES-256 per tenant) → cannot query by email. **Solution:** add an unencrypted, indexed `email_hash` column to `Client` = `HMAC-SHA256(normalize(email), pepper)` (pepper from a dedicated env/`SECRET_KEY`-derived key). Lets us look up a client by email without decrypting or storing plaintext. Backfill existing rows in tenant context (decrypt → hash) via the `ensure_tenant_required_columns` mechanism in `db_init.py`.

---

## Phase 1 — Auth foundation (backend, PR A)
1. **`Client.email_hash`** column + index; backfill in `db_init.ensure_tenant_required_columns`. Maintain it on client create/update (hook in the client service/schema).
2. **`ClientLoginToken`** model (master DB): `token`, `tenant_id`, `client_id`, `expires_at` (1h), `is_used`, `created_at`. (Master DB so the verify endpoint needs no tenant context to find the token.)
3. **`client_portal` feature flag** registered in `FeatureConfigService`.
4. **Client auth router** `/api/v1/client-portal/*` (added to middleware `skip_tenant_paths`; uses its own tenant resolution):
   - `POST /{tenant_slug}/request-link` `{email}` → resolve tenant from slug → look up client by `email_hash` → create token → email magic link `{UI}/portal/verify/{token}`. **Always returns 200** (no email enumeration). Rate-limited `client_login:{tenant_id}:{email_hash}` (5/60s) + per-IP.
   - `POST /verify/{token}` → validate (exists, not used, not expired) → mark used → issue **client JWT** with claims `{sub: email_hash, type: "client", client_id, tenant_id}` → return token + minimal client profile.
5. **`get_current_client` dependency** — decode client JWT, require `type=="client"`, set tenant context from claim, load the `Client`. **Staff middleware must reject client tokens** (sub is an email-hash, not a `MasterUser` email → already fails staff lookup; add an explicit `type` guard so a client token can never satisfy a staff dependency, and vice-versa).
6. **Tenant slug**: use `Tenant.subdomain` if set, else a generated `portal_public_id` (non-sequential). Decide in PR A.
7. Tests: token lifecycle, email-enumeration safety (unknown email still 200, no token created), rate limiting, client-JWT cannot reach a staff endpoint, staff-JWT cannot reach portal endpoints.

## Phase 2 — Portal data API (backend, PR B)
All under `/api/v1/client-portal/`, `get_current_client` dependency, feature-gated, **always scoped to `client_id` from the token** (never from a request param):
- `GET /me`, `PATCH /me` (update name/phone/address → encrypted write + `email_hash` unchanged + audit log + validation).
- `GET /invoices` (list: number, status, dates, amount, paid/outstanding).
- `GET /invoices/{id}` (404 if not this client's).
- `GET /invoices/{id}/pdf` (branded PDF; reuse generator + `get_invoice_branding`).
- `GET /branding` (so the public portal can render branded before login — company name/logo/colours, like the share payload).
- Tests: cross-client access returns 404; payment math; PATCH validation/audit.

## Phase 3 — Portal frontend (PR C)
- Public routes (no app auth), branded via `/branding`:
  - `/portal/:tenantSlug` — enter email → request link (neutral "check your email" response).
  - `/portal/verify/:token` — consume token → store client JWT (separate storage key from staff) → redirect.
  - `/portal/dashboard` — invoice list + status + balance; download PDF; profile edit.
- Dedicated **client API client** (raw fetch with the client JWT; mirrors `share-tokens.ts` bypassing tenant header).
- `FeatureGate` on the staff-side entry that surfaces/links the portal.
- i18n keys straight into `en.json`.

## Phase 4 — Integration & polish (PR D)
- "View all my invoices" link in the invoice email (carries tenant slug).
- Settings surface for the portal URL + enable toggle (gated).
- Audit events for login/access.

---

## Security checklist (carry through every PR)
- No email enumeration (uniform 200 + timing-insensitive).
- Token: 1h expiry, one-time-use, `secrets.token_urlsafe(32)`.
- Client JWT `type` claim strictly segregated from staff; client endpoints never trust a client_id/tenant_id from the request body/params — only from the verified token.
- Rate limit request-link (per tenant+email and per IP).
- Audit log login + data access (tenant `AuditLog`).
- Feature-gated end to end (hidden + 403 when disabled).

## Out of scope
Online payment (no charging exists), password auth, multi-tenant client accounts (one email across tenants), staff impersonation of portal.

## Verification
- Backend tests in Docker (Postgres) each PR; watch FK/NOT-NULL + encrypted-column backfill.
- Frontend `tsc` vs `main` baseline (node_modules-symlinked worktree; never `git stash`).
- Manual: enable feature → request link → email arrives → verify → dashboard lists only that client's invoices → download branded PDF → edit contact info persists. Disabled feature → portal 403/hidden.
