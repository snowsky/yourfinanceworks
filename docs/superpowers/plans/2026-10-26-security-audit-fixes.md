# Security Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Independent file sets may be delegated using dispatching-parallel-agents.

**Goal:** Fix the identified authentication, authorization, storage, session and deployment boundaries before opening and merging a PR.

**Architecture:** Reuse existing shared security controls at the final decision points. Preserve optional commercial imports and tenant isolation. Test handlers without importing the application startup or destructive shared-database fixtures.

**Tech Stack:** FastAPI/Python, React/TypeScript, Python CLI, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-26-security-audit-fixes-design.md`

## Global Constraints

- No deployed-server mutations, customer data, real identity/provider calls, or secrets in commits.
- Preserve unrelated local files; work on `fix/security-audit-boundaries` in an isolated worktree.
- Isolated Python tests live in `tests/security/`, outside `api/tests/conftest.py`.
- Complete focused regressions, review, PR, merge, and local-main synchronization as authorized.

## Review Focus

- Non-staff/legacy token distinctions and every staff credential consumer.
- Existing-account signup and mobile authentication cannot omit MFA or grant a supplied role.
- Secondary-tenant keys cannot select the primary tenant or inherit its higher role.
- Failed cookie logout stays retryable; cached CLI tokens never cross server/profile/account identity.
- Path fallback, symlinks, disabled tenants, and explicit non-default deployment settings preserve containment.

### Task 1: Staff identity, admission, MFA and device approval

**Files:** auth utilities, staff middleware, `auth/_shared.py`, `auth/login_register.py`, `auth/device.py`, mobile authentication, and `tests/security/test_staff_auth_boundaries.py`.

**Interfaces:** Shared staff-claim validation; existing token issuance and MFA helpers; existing invitation and organization creation flows.

- [x] Add failing tests for plugin/client rejection, valid legacy/staff acceptance, unauthorized existing-tenant admission, MFA-protected alternate issuance and side-effect-free device GET.
- [x] Enforce these invariants without permitting caller-selected existing-tenant authority. Bind device approval to explicit CSRF-protected action and pending session.
- [x] Run isolated authentication regressions; record red/green evidence and compatibility decisions.

### Task 2: API key and financial mutation authority

**Files:** external API auth service, Tools API dependencies/routes, ordinary customer/invoice/payment mutation handlers, and `tests/security/test_api_permission_boundaries.py`.

**Interfaces:** `AuthContext`, `APIClient.tenant_id`, shared `require_component_permission` and role policy.

- [x] Add failing tests for persisted key tenant, removed/disabled membership, viewer and per-component restrictions, and individual financial mutations.
- [x] Resolve the owner's current selected-tenant authority; require component permissions at each affected tool and ordinary mutation.
- [x] Run isolated permission regressions with two dummy tenants and positive authorized controls.

### Task 3: Tenant file containment and portal lifecycle

**Files:** `core/routers/files.py`, `core/utils/file_validation.py`, `core/services/client_portal_auth.py`, and `tests/security/test_resource_boundaries.py`.

**Interfaces:** Resolved tenant root, current tenant context, existing client session dependency.

- [x] Add failing tests for traversal, foreign tenant, missing context, symlink escape, metadata parity, valid fallback and archived/disabled portal tenants.
- [x] Resolve and validate all file candidates within the authenticated tenant root; check master tenant state before opening portal data.
- [x] Run isolated resource regressions with temporary marker files and dummy tenant records.

### Task 4: Browser and CLI credential lifecycle

**Files:** UI auth utility/hook/sidebar and tests; CLI API client and auth/cache tests.

**Interfaces:** One asynchronous server logout primitive; origin/profile/account binding in cached-token payloads.

- [x] Add failing regressions for server-cookie logout, retryable failure, valid cached login and mismatched/legacy cache rejection.
- [x] Route visible logout through the shared primitive and scope persistent CLI credentials to the selected identity.
- [x] Run focused Vitest and CLI tests.

### Task 5: Deployment defaults and portal credential secrecy

**Files:** portal router, both maintained Compose files, example environment, rollout documentation, isolated tests.

- [x] Add failing handler tests ensuring request-link responses never include a credential under DEBUG, for matching/nonmatching clients and mail failure.
- [x] Remove credential-bearing debug responses, default deployments to production/debug-off, and bind management UI ports to loopback.
- [x] Validate both Compose configurations using dummy environment files; document trusted origins, authenticated management access and replica recreation.

### Task 6: Integration, independent review, PR and merge

- [x] Run the combined isolated security and CLI suites, focused UI tests and applicable lint/build checks; distinguish baseline failures.
- [x] Request a fresh whole-branch review and resolve material findings.
- [ ] Commit only agreed changes, push, create PR, verify checks, merge, and synchronize local main.
- [ ] Report merged PR, exact validation and deployment remaining.
