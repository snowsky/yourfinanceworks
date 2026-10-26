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
profile and account binding. Existing API keys remain tied to their stored tenant
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
