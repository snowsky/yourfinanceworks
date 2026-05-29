# Plugin Git Installer — Trust Model Design Doc

**Status**: Draft for review
**Author**: Generated as a design artifact for CRITICAL #6 from the plugin-system code review (this session)
**Decision needed**: Whether to keep the live HTTP install endpoint at all, and if so under what hardening

## Why this doc exists

CRITICAL #6 from the plugin-system review:

> **Git installer runs `pip install` and copies arbitrary code from untrusted repositories with no sandboxing** — `api/commercial/plugin_management/services/git_installer.py:259-269`
> `run_install` is super-admin-only, but once invoked it clones an arbitrary git URL and runs `pip install -r requirements.txt` and `shutil.copytree` to write files into the live API plugin directory. There is no checksum/signature verification of the plugin manifest, no allowlist of permitted packages, and no container isolation. A compromised or malicious repository can execute arbitrary Python at install time (via `setup.py`/`pyproject.toml` hooks) and inject code that runs on next server restart.

Of the 7 CRITICALs the review surfaced, #6 is the only one that **can't be honestly fixed by adding code paths in the existing shape**. Every other CRITICAL was a missing check (auth, origin, locking) inside an otherwise-correct design. #6 is the design itself: a live HTTP endpoint that takes "URL of code to clone and execute" as an input. Even with all the hardening we could plausibly bolt on, the endpoint remains equivalent in privilege to shell access on the API container. This doc forces us to make that explicit and pick a posture.

## Current state

`POST /api/v1/plugins/install` (super-admin gated). Payload: `{git_url, ref, github_token?}`. Triggers a `BackgroundTasks` invocation of `run_install(job_id)` in `services/git_installer.py`. The job:

1. `git clone --depth 1 --branch <ref> <git_url> <tmp>` — subprocess.run, 120s timeout. `<ref>` is a branch, tag, or commit; the implementation does not require a pinned SHA.
2. Validates `plugin.json` has `name`, `version`, `description`. No signature, no checksum, no allowlist.
3. If `requirements.txt` exists: `pip install -r requirements.txt` — subprocess.run, 300s timeout, **runs in the live API process's Python environment**. Arbitrary `setup.py` / `pyproject.toml` hooks execute here.
4. `shutil.copytree(repo, /app/plugins_dynamic/<folder>)` — writes into the live plugin directory which `PluginLoader` auto-discovers on next restart.
5. `_validate_and_sanitize_ui_plugin` — only fixes a TypeScript comment-syntax quirk. Despite the name, provides no security guarantee.
6. Resets `PluginLoader` cache. Requires a uvicorn restart to actually load the plugin into the running process.

### The trust model today

The only gating check is `_is_superuser(current_user)`. The implicit assumption is:

- Super-admin credentials are well-protected.
- Super-admins only install plugins they've manually reviewed.
- The repo at `git_url@ref` is exactly what the super-admin reviewed at the moment of install (no branch-pointer drift between review and install).
- A compromised plugin author can't push a malicious update to a repo a super-admin has already approved.

Each assumption is fragile. The first is generally true (it's the same assumption every admin-gated action makes). The next three are not — they're "this is fine because we trust the operator," and the cost of a single mistake is RCE on the API container.

### What the existing `--depth 1 --branch <ref>` clone enables

The clone targets a **mutable ref**, not an immutable commit. Even if the super-admin manually reviewed the repo five minutes earlier, between their review and the install:

- The branch tip can be advanced.
- A tag can be moved (annotated tags can be force-pushed).
- The repo can be replaced entirely (if it's been transferred or renamed).

A patient attacker who has compromised the source repo can wait for an admin to start an install and update the ref mid-flight. The 120s clone timeout is a wide window.

## Constraints we must respect

| # | Constraint | Implication |
|---|-----------|-------------|
| 1 | **The install operation is fundamentally privileged** | Whatever we ship, the endpoint (if it exists at all) writes code to a directory that the API process auto-loads. There's no design that makes this safe to expose to non-trusted callers. |
| 2 | **Some operators rely on the UI flow** | Removing it forces those operators into a CLI/SSH workflow. We need to know which deployments depend on the UI and pick a transition path. |
| 3 | **`pip install` install hooks run arbitrary Python** | `--no-build-isolation`, `--no-binary :all:`, allowlists — none of these stop `setup.py install` from executing arbitrary code at install time. True sandboxing means subprocess isolation (containers, seccomp, dropped capabilities) which is well beyond a bolt-on hardening pass. |
| 4 | **Manifest signing requires infrastructure we don't have** | A trusted-signer allowlist + signature verification only works if there's a key-management system to ground it. Treating signing as a "small addition" is not honest. |
| 5 | **Plugins that are part of the product are different from plugins customers install** | The first-party plugins under `api/plugins/<name>/` (currency_rates, investments, time_tracking) ship via the normal Docker image build, not via this endpoint. The endpoint is only for plugins in `api/plugins_dynamic/`. |

## Three options

### Option A: Remove the HTTP install endpoint. Make installation a deployment-time operation.

`POST /api/v1/plugins/install` is removed. The corresponding UI surface (super-admin Plugins tab → "Install from git" button) is removed. A new operator CLI replaces it:

```
docker compose exec api python -m commercial.plugin_management.cli install \
  --git-url <url> --ref <SHA> [--github-token <token>]
```

The CLI does the same work `run_install` does today. Installation is a ssh-and-run-command operation, equivalent to other ops-tier tasks (database migrations, secret rotations, image rebuilds).

```
Pros
─────
+ Eliminates the live HTTP attack surface entirely. A compromised super-admin
  session can no longer install a plugin without also achieving shell on the
  container.
+ Forces the operator to specify a commit SHA (CLI argument, not a branch ref).
+ The trust model becomes: "you have shell on this container." That's an
  ops-tier privilege most teams already have controls around.
+ Smallest implementation: delete the endpoint, lift the existing `run_install`
  into a CLI entrypoint, document the workflow.

Cons
─────
− Non-engineer super-admins can no longer self-serve plugin installs from the
  UI. They have to file an ops ticket.
− Operators on managed deployments (e.g. tenants using a fully-managed plan)
  may not have shell access — they'd be entirely dependent on the platform
  operator for plugin installs.
− Plugin install audit trail moves from the AuditLog table to the shell
  command history, which is harder to query and may not be retained.
```

### Option B: Keep the endpoint. Add a deployment-level feature flag (default off) plus hardening.

`POST /api/v1/plugins/install` stays. A new config flag `ALLOW_LIVE_PLUGIN_INSTALL` defaults to `False`. When False, the endpoint returns `503 plugin installation is disabled at the deployment level`. When True, the endpoint:

1. Requires a **commit SHA** in the payload, not a branch or tag. Branch refs are rejected with 400.
2. Validates the `git_url` host against a per-tenant `plugin_install_allowed_hosts` Settings row (e.g. `["github.com/your-org/", "internal-git.example.com/"]`).
3. Runs `pip install` in a temporary venv mounted under a tmpdir, then `mv` the resulting site-packages into the plugin's own directory rather than the host process venv. The host process imports plugin packages via `sys.path` injection at startup, so the plugin's `requirements` remain isolated to that plugin.
4. Audit-logs every install, every config-flag flip, and every attempted install with status="error" and the reason.

The flag is documented as "Only enable for trusted single-tenant deployments where the operator and super-admin are the same person."

```
Pros
─────
+ Preserves the UI flow for tenants where it's acceptable.
+ Adds real hardening: pinned SHA + host allowlist closes the
  branch-pointer-drift attack and limits the source surface.
+ Per-plugin venv prevents one plugin's bad dep from breaking the host
  process; closes the "pip install hook clobbers the host venv" path.

Cons
─────
− Defaults drift. Tenants who flip the flag on for one install and forget
  to flip it off retain the live endpoint indefinitely.
− Per-plugin venv handling is non-trivial; getting sys.path injection
  right at startup is a meaningful chunk of work.
− Doesn't solve the pip install hook RCE: even in a tmpdir venv, hooks
  execute Python. They just can't pollute the host venv.
− Manifest signing is NOT in this option (see Constraint #4 — we don't
  have the key infrastructure).
```

### Option C: Hybrid — Option A by default, Option B as a build-time opt-in for trusted product editions.

The HTTP endpoint is gated behind a **build-time** flag, not a runtime config setting. By default (community edition / SaaS deployments), the endpoint is not registered at all; the only install path is the CLI from Option A. An enterprise/single-tenant build of the API image registers the endpoint with the Option B hardening applied.

The flag lives in the build pipeline (Docker build arg or compile-time const), not in a database row or env var. Operators can't accidentally flip it on at runtime.

```
Pros
─────
+ SaaS tenants and the community edition get the strongest model
  (endpoint doesn't exist).
+ Enterprise single-tenant deployments retain the UI flow under hardening.
+ The build-time switch eliminates the runtime-config drift risk that
  Option B alone has.
+ Naturally aligns with how other "enterprise-only" features in this
  codebase are gated.

Cons
─────
− Two build variants of the API image to maintain.
− The Option B hardening still has to be built to support the enterprise
  variant — so the total implementation work is A + B's hardening,
  minus the runtime flag plumbing.
− "Build-time opt-in" is opaque to operators; the contract for when the
  enterprise build is used has to be documented carefully.
```

## Recommendation

**Option A**, ship now. Option C is the right long-term answer if there's enterprise demand for a UI install flow, but A is the honest short-term posture and gives us months to learn whether C is actually needed.

Rationale:

- **A is the smallest implementation**. Lift `run_install` into a CLI module, remove the route handler, remove the UI button, write a short ops runbook. Closes the CRITICAL.
- **A's "downsides" are mostly hypothetical**. The review listed "non-engineer super-admins can't self-serve" as a con, but this codebase ships in tenant deployments where the super-admin and the operator are typically the same role. Filing-an-ops-ticket isn't a regression for that audience.
- **B's hardening is genuinely deep work** (per-plugin venv with `sys.path` injection at startup is a non-trivial change to the `PluginLoader`) for a benefit that's mostly retained by going to A directly.
- **Manifest signing isn't on the table** until there's a key-management system. Conflating "harden the installer" with "build a signing infrastructure" inflates the scope of #6 unjustifiably; the signing work is a separate item that may or may not be worth doing later.
- **The audit-log con of A is real but solvable**: ship an `AUDITLOG` write from the CLI itself, identical in shape to the HTTP endpoint's audit log entry. Same observability, different invocation.

## Migration plan

Option A:

1. **CLI**: new `api/commercial/plugin_management/cli.py` exposing `install` as a `__main__` entrypoint that does the same work `run_install` does today (clone → validate → install deps → copy → cache reset). Replaces the `pip install` step with one that runs in the host venv but takes the same code path as `run_install` to avoid duplicating the install pipeline.
2. **Audit log from CLI**: import `log_audit_event` from `core.utils.audit`, write the same `PLUGIN_INSTALL` shape the HTTP endpoint used. CLI requires `--operator-email` (for the audit_log `user_email` field; defaults to `$YFW_OPERATOR_EMAIL` env var with no fallback — refuse to proceed without an email).
3. **Router**: delete the `POST /api/v1/plugins/install` route handler. The `services/git_installer.py` module survives; the CLI imports `run_install` and calls it directly.
4. **UI**: in `ui/src/components/settings/PluginsTab.tsx`, remove the "Install from git" button and its modal. Replace with a short help text linking to the CLI runbook.
5. **Docs**: new `docs/admin-guide/PLUGIN_INSTALL_RUNBOOK.md` covering the CLI workflow, the requirement to specify a commit SHA (not a branch), pre-install review steps, and how to audit-log the action.
6. **Tracking**: add `docs/todos/PLUGIN_INSTALLER_TRUST.md` (or close out via this PR) so we know to revisit if enterprise demand for B/C surfaces.

Backward compatibility: there is no migration path for in-flight installs because installs aren't durable mid-flight today (they require a server restart anyway). Any deployment with the old endpoint flipped on continues to work until image redeploy.

## Open questions for the decision meeting

1. **Is there a deployment that currently relies on the HTTP install endpoint?** If yes, who, and can they tolerate the CLI workflow? This is the single highest-information question.
2. **Audit log retention.** Today's audit log lives in the per-tenant `AuditLog` table. The CLI-driven install would write to the same table. Is that the right destination, or should ops-tier actions go to a separate operator-audit stream?
3. **Do we want to do anything about the existing dynamic plugins that were installed via the endpoint?** They're already on disk. The CLI workflow only affects future installs.
4. **CLI runtime context.** Is `docker compose exec api python -m ...` the right invocation, or should the CLI be a standalone script outside the API container? Standalone has the advantage of not requiring the API process; container-exec has the advantage of inheriting the API's exact Python environment.
5. **Enterprise demand signal.** Has anyone asked for a UI install flow in the last 6 months? If no, Option A stands. If yes, we should know who and what their constraints are before locking in.

## Out of scope

- CRITICAL #4 (SSO token in localStorage) — covered by separate design doc (PR #312).
- Other HIGH-tier findings from the review (X-Plugin-Caller header validation, sidecar manifest signing, `enable_plugin` normalization, plugin tools routers without auth dependency, etc.). Each warrants its own follow-up.
- Manifest signing as a general capability. Useful, but a much larger surface than #6 alone needs to address.
- Subprocess sandboxing / seccomp / per-plugin container isolation. Real defenses but enormous scope; mention only to acknowledge that "hardening pip install" stops short of them.

## References

- Plugin-system code review findings (this session).
- Current installer service: `api/commercial/plugin_management/services/git_installer.py:200-369` (`run_install`).
- Current HTTP endpoint: `api/commercial/plugin_management/router.py:954-1000` (`install_plugin_from_git`).
- Super-admin gate: `api/commercial/plugin_management/router.py:52-54` (`_is_superuser`).
- Auto-discovery of installed plugins on next restart: `api/plugins/loader.py:97-182` (`PluginLoader.discover`).
- Companion design doc for CRITICAL #4: `docs/technical-notes/PLUGIN_SSO_TOKEN_DELIVERY_DESIGN.md`.
