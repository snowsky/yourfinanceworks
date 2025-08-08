### Security and architecture improvements

This document summarizes recent improvements and recommended next steps to harden the Invoice API and its multi-tenant architecture.

### Implemented changes

- CORS hardening (env-driven)
  - `ALLOWED_ORIGINS` (comma-separated), `ALLOW_CORS_CREDENTIALS` respected
  - DEBUG-aware defaults; credentials disabled when wildcard origin in use

- JWT/secret management
  - `SECRET_KEY` enforced in non-DEBUG environments
  - Unified JWT usage in tenant middleware to `python-jose`

- File upload hardening (invoice attachments)
  - Tenant-scoped storage: `attachments/tenant_<id>/invoices/`
  - Filenames sanitized; max size enforced at 10 MB
  - Basic PDF signature check (`%PDF`)

- Rate limiting (basic, in-memory)
  - `/auth/login` and `/auth/request-password-reset` limited per-email
  - Tunables: `MAX_LOGIN_ATTEMPTS`, `MAX_RESET_ATTEMPTS`, `RATE_LIMIT_WINDOW_SECONDS`

- Security headers for API responses
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - Conservative `Content-Security-Policy` for API responses

See `api/README.md` for configuration details.

### Operational guidance

- Always set a strong `SECRET_KEY` in production
- Provide explicit `ALLOWED_ORIGINS`; only enable credentials with specific origins (no wildcard)
- Enforce upload body size limits at the reverse proxy as well (e.g., nginx `client_max_body_size`)
- Scope storage per tenant (done) and restrict file permissions on the server filesystem

### Recommended next steps (prioritized)

1) Redis-backed rate limiting (multi-instance ready)
- Replace in-memory counters with a shared store (Redis) and sliding window or token bucket algorithm
- Add IP-based component to rate keys to further deter abuse

2) Object storage for attachments (S3/GCS/Azure Blob)
- Store under per-tenant prefixes with server-side encryption
- Use presigned URLs for upload/download; restrict content-type/size in policies
- Set lifecycle policies (cold storage/retention)

3) Malware scanning and content validation
- Integrate ClamAV (or provider scanning) on upload path
- Use content-type detection (`python-magic`) in addition to `UploadFile.content_type`
- Consider content disarm (strip active content from office files) for higher assurance

4) Authentication/token lifecycle
- Short-lived access tokens with refresh tokens (rotation + revocation)
- Optional httpOnly secure cookies if same-site deployment is feasible
- Preemptive expiry handling in UI/mobile (decode `exp` and refresh proactively)

5) Logging and observability
- Reduce PII in logs and standardize levels; avoid logging tokens/headers
- Centralize logs; add metrics for 401/403, rate-limit hits, and tenant context errors
- Add audit events for security-sensitive actions (already partly present)

6) Secrets management and configuration
- Use secret managers (e.g., AWS SSM/Secrets Manager) instead of plain env where possible
- Ensure env injection in orchestrator avoids accidental debug defaults

7) Tenant isolation review and tests
- Verify all tenant-specific routes depend on `get_db` + `get_current_user`
- Add end-to-end tests for tenant ID switching and denial on unauthorized tenant access

8) CSP tuning (if serving web content from API)
- For static assets served by API, tighten CSP to exact origins/paths as needed

9) Client app hardening (UI/mobile)
- UI: background token validation/refresh; ensure robust error-code i18n mapping
- Mobile: move `API_BASE_URL` to env/build config, remove hardcoded IPs; handle tenant selection UX explicitly

### Environment variable summary

- `SECRET_KEY` (required in production)
- `DEBUG` (default: `False`)
- `ALLOWED_ORIGINS` (comma-separated)
- `ALLOW_CORS_CREDENTIALS` (default: `False`)
- `MAX_LOGIN_ATTEMPTS` (default: `5`)
- `MAX_RESET_ATTEMPTS` (default: `5`)
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`)


