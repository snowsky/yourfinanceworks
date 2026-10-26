# Security boundary update rollout

Merging this change does not change a running deployment. Apply it during a planned
rollout after confirming HTTPS, trusted origins, administrative access and backups.
Never validate security with customer identities or the shared test database.

## Application settings

The maintained Compose API services explicitly set `DEBUG=false` and
`ENVIRONMENT=production`, overriding old development values in `api/.env`.
Production auth cookies are Secure and require an HTTPS browser origin. Set
`ALLOWED_ORIGINS` to the exact browser origins used by the deployment, for example
`https://finance.example.com`. Wildcard origins are rejected. Debugging never
disables the cookie-authenticated CSRF origin checks or exposes portal login links.

### Configure the demo browser origin

On the demo server, set the following in `api/.env`:

```dotenv
ALLOWED_ORIGINS=https://demo.yourfinanceworks.com
```

If the same API intentionally serves other browser origins, include each one in
the comma-separated list. Origins include the scheme, hostname, and any
non-default port, with no URL path. Only include localhost when that deployment
intentionally supports it; the localhost-only value in `.env.example.full` does
not authorize the hosted demo.

From the deployment's repository root, recreate the API to load the new value:

```sh
docker compose up -d --no-deps --force-recreate api
docker compose logs --tail=100 api
```

Use the same Compose files, project name, and replica count as the running
deployment when recreating the service. Confirm the startup `Allowed origins`
log includes `https://demo.yourfinanceworks.com` on every API replica, then retry
the failed operation with a dummy invoice. Verify an untrusted origin still
receives HTTP 403 for a request carrying a session cookie.

### Troubleshoot `CSRF check failed: untrusted origin`

This HTTP 403 comes from the API's browser-origin check before the invoice update
handler runs. Compare the browser request's `Origin` header with the API startup
`Allowed origins` log and the `CSRF check failed: untrusted Origin` warning.
Configure the exact intended origin and recreate every API replica; restarting
an existing container does not reload its environment. No `InvoiceForm.tsx`
change is required for an origin configuration mismatch.

CSRF protection was introduced on March 16, 2026, in PR #118 (`c508d1af`).
PR #455 (`549aabf5`), merged October 26, 2026, removed the debug-mode bypass.
Deployments that previously relied on that bypass now need explicit trusted
origins. Keep the origin check enabled and avoid wildcard trust.

### Local development and remaining rollout steps

For intentional localhost HTTP development, use a separate Compose override with
`ENVIRONMENT=development`; keep `DEBUG=false` unless diagnostic output is needed.
Use explicit localhost origins. Avoid editing the maintained production defaults.

Recreate **every API replica** after updating source and configuration. An ordinary
restart does not update container environment values. Confirm all replicas report
debug off and production mode, and verify valid HTTPS sign-in, logout, tenant
switching, invited signup, browser CLI approval, and configured MFA using dummy
accounts. Cookie logout now remains visibly retryable if the server cannot clear
the cookie.

Existing untyped staff JWTs remain accepted until expiry. Plugin/client credentials
cannot authenticate as staff. Public registration cannot select an existing tenant
or role; use invitations or approved membership workflows. MFA-enabled existing
accounts must sign in normally before creating another organization. CLI token
caches created before this change need one fresh login because they lack an API,
profile and account binding. Update the backend before using the updated CLI's
device login: the exchange must identify the browser-approved account, and a
configured profile email must match it before any credential is cached.
Existing API keys remain tied to their stored tenant
and current owner permissions.

## Management listeners

Kafdrop and OpenSearch Dashboards are optional under the `admin` Compose profile.
Their published ports are bound to `127.0.0.1`, rather than all host interfaces.
Do not assume a normal `compose up` removes already-running optional containers:
stop/recreate old management containers explicitly during rollout and verify the
old public IPv4/IPv6 listeners are gone. Do not delete their data volumes.

When administrative access is required, enable only the intended tools:

```sh
docker compose --profile admin up -d kafdrop opensearch-dashboards
ssh -L 5601:127.0.0.1:5601 -L 9000:127.0.0.1:9000 user@server
```

The bundled search transport still trusts the private application Docker network;
this patch does not introduce OpenSearch users, TLS certificates or index roles.
Keep untrusted workloads off that network. If search or its administrative tools
must be shared beyond the trusted host, provision authenticated OpenSearch and
Dashboards with TLS and tenant/index authorization before exposing them. A login
on the main application does not protect a separate management listener.

## Validation limits

The security regression suite in `tests/security/` loads real handler bodies with
dummy dependencies and temporary files. Run it separately from `api/tests/`, whose
legacy conftest drops and recreates a database during import. Focused UI and CLI
tests cover cookie logout and cached credential binding. These checks do not prove
provider delivery, real database provisioning, outer ingress, or deployment state.
The audit's deferred coverage items remain separate follow-up work.
