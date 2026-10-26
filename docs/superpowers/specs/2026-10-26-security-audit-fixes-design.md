# Security audit boundary fixes

The user requested fixes before PR creation and merge. This change addresses the twelve retained audit concerns and the deployment debug disclosure. It does not claim to resolve the audit's fifteen deferred coverage units or deploy changes to the running server.

Use the application's existing identity, tenant, component-permission, and session policies at every affected entry point. Reject non-staff credentials in staff consumers while accepting existing untyped staff tokens for compatibility. Public registration cannot grant membership or choose authority in an existing organization; alternate password issuance must enforce configured MFA. Device login requires explicit, request-bound approval rather than a GET side effect.

API keys remain bound to their persisted tenant and the owning user's current authority. Tools and ordinary financial mutations must enforce the corresponding component permissions. Tenant file paths must remain within their resolved tenant directory, including fallback and symlink cases. Portal sessions must reject disabled/archived tenants.

Visible logout must clear the server cookie before completing local logout, with a retryable failure. CLI cached credentials must match the selected origin/profile/account. Portal responses never expose login credentials, including in debug mode. Maintained Compose deployments use explicit production defaults and publish management UIs on loopback; documentation describes authenticated administration and the required rollout separately.

Alternatives considered: deployment-only settings leave credential and authorization defects; rejecting all existing tokens adds avoidable disruption. The selected approach repairs the affected shared checks and preserves valid staff, tenant, portal, and CLI workflows where their authority remains valid.

Validation uses dummy users/tenants, temporary files, mocked providers and isolated handler fixtures. Never collect `api/tests/conftest.py`: it drops a database at import. Focused UI and CLI regressions accompany backend tests. No deployment credentials, financial data, or audit exploitation instructions enter the PR.
