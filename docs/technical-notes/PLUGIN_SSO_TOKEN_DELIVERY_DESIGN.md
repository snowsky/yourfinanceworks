# Plugin SSO Token Delivery — Design Doc

**Status**: Draft for review
**Author**: Generated as a design artifact for CRITICAL #4 from the plugin-system code review (this session)
**Decision needed**: Which delivery mechanism replaces the current URL-param-base64 flow

## Why this doc exists

CRITICAL #4 from the plugin-system review:

> **Unverified SSO Token Stored to localStorage** — `App.tsx:133-134`
> The `token_data` query parameter is base64-decoded and stored directly into `localStorage` as `plugin_token_<pluginId>` with no signature verification, expiry check, or origin binding. Any page that can trick a user into visiting the `/auth-callback` URL (phishing, CSRF, clickjacking) can plant an arbitrary token object. This token is later used by `PublicPluginWrapper` to pass an `access_token` into plugin iframes.

The remaining CRITICALs from the review are being fixed as standalone PRs (✅ #1 #2 #3 #5 #7 are done; #6 is a deployment-policy question). **#4 cannot be fixed without picking a different delivery model** — it's not a code-level patch, it's an architecture call. This doc lays out three options so we can decide and then ship.

## Current flow (the vulnerable one)

```
┌─────────┐                                ┌──────────────┐                              ┌─────────────────┐
│ Browser │  GET /api/v1/plugins/<id>/     │  Plugin auth │   GET <google>/oauth/token   │ Google / Azure  │
│         │ ─ public-auth/google/login ──▶ │  (FastAPI)   │ ──────────────────────────▶ │ OAuth provider  │
└─────────┘                                └──────────────┘                              └─────────────────┘
     ▲                                            │
     │                                            │ access_token issued via create_access_token() — JWT
     │                                            │ {sub, type:"plugin", plugin_id, tenant_id, plugin_user_id}
     │                                            ▼
     │      302 redirect to                ┌──────────────┐
     │   /p/<id>/auth-callback             │ token_url_   │
     │   ?token_data=<base64>              │   encoded =  │
     │ ◀──────────────────────────────────  base64(json.{ │
     │                                        access_     │
     │                                        token, user})│
     │                                      └──────────────┘
     ▼
┌─────────────────────────────────┐
│ App.tsx: PublicPluginCatchAll   │   atob() →
│   if pathname ends auth-callback│   JSON.parse →
│   localStorage[plugin_token_<id>│   localStorage.setItem
│     = json                      │
│   window.location = ?next=...   │
└─────────────────────────────────┘
                  ▼
┌─────────────────────────────────┐
│ PublicPluginWrapper             │   - reads token from localStorage
│   - calls paywall endpoints     │   - sends access_token via JSON body
│   - postMessage(token) → iframe │   - posts token into the plugin iframe
└─────────────────────────────────┘
```

The token in `localStorage` is the actual JWT issued by `create_access_token`. The reference to "no signature verification" in the review is about the **client side** — `App.tsx` does not validate that the URL-supplied `token_data` blob is one the server actually issued. The server signs it; the client just trusts whatever appears in the URL.

### Concrete attacks this enables

1. **Phishing token plant**: Attacker crafts `https://yourtenant.example/p/<plugin>/auth-callback?token_data=<b64 of a JWT they signed with a forged key>&next=/p/<plugin>`. The client `atob → JSON.parse` succeeds, the token lands in localStorage. `App.tsx` doesn't verify the signature. The next request to the plugin sends it as `access_token`. The **server** rejects the forged JWT (we validate it in `_validate_plugin_user_token` post-#310), so the attacker doesn't get authorized API calls — but they get the user into a "logged in as someone else" state that misroutes UI flows and leaks confused-deputy info.

2. **Session fixation**: Attacker who already holds a valid JWT (e.g. expired free-trial account) crafts an auth-callback URL planting their own token. The victim now has the attacker's session and any clicks they make count against the attacker's plugin user (or vice versa, depending on the action).

3. **localStorage as a token store** is the second-order issue: any XSS anywhere on the same origin (host app or plugin iframe with `allow-same-origin`) reads the JWT directly and exfiltrates it. The main app already avoids this for the host SSO flow by using HttpOnly cookies (`api/commercial/sso/router.py:409`); the plugin flow is the outlier.

### Why the main app's SSO flow is fine

`api/commercial/sso/router.py` for the host application:

```python
redirect_url = f"{ui_base}/oauth-callback?user={user_b64}&next={redirect_next}"
redirect_response = RedirectResponse(url=redirect_url)
redirect_response.set_cookie(
    key=AUTH_COOKIE_NAME,
    value=access_token,
    httponly=True,
    samesite="lax",
    secure=_is_production,
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    path="/",
)
```

The URL carries only **user metadata** (the b64-encoded user record), never the token. The actual JWT is in an HttpOnly cookie scoped to `/`. The browser presents it automatically; JS can't read it.

**The fix for plugins is to apply this same pattern to the plugin flow, with three adjustments**: per-plugin scoping, iframe sub-context for sidecar plugins on a different origin, and a backward-compatible migration so existing logged-in sessions don't all break the moment we ship.

## Constraints we must respect

| # | Constraint | Implication |
|---|-----------|-------------|
| 1 | **Multiple plugins per browser** | Each plugin currently has its own `plugin_token_<id>` in localStorage. Whatever replaces it has to scope per-plugin (cookie path, cookie name, or origin segregation). |
| 2 | **Plugin iframe needs the token** | `PublicPluginWrapper` posts the token to the in-page iframe via `postMessage`. If the host can read the token but the iframe can't, the host has to **either** forward iframe API calls **or** issue a per-iframe scoped credential. |
| 3 | **Sidecar plugins are cross-origin** | `plugin_<name>:8000` is a different origin from the host. Host cookies can't span origins. Sidecars need their own token issuance — or, the host proxies their API calls. |
| 4 | **Public plugin portal is unauthenticated initially** | Anonymous users visit `/p/<plugin>` before SSO. The flow has to support pre-login state. |
| 5 | **Existing logged-in users must not all be logged out on rollout** | Migration needs a grace period where both old and new tokens are honored. |
| 6 | **The `access_token` JWT is already validated server-side** (post-#310) | This is partial mitigation — the value of fixing #4 is reducing the **client-side attack surface** (XSS exfiltration, phishing token plant). Server-side checks already block forged tokens from being **accepted** at API boundaries. |

## Three options

### Option A: HttpOnly cookie, per-plugin path scope

Mirror the host SSO flow exactly. The server sets `plugin_auth_<pluginId>` as an HttpOnly cookie with `path=/p/<pluginId>` (or `/api/v1/plugins/<pluginId>/`), so the browser presents it only on requests to that plugin's URL space. The auth-callback URL carries `?user=<b64>&next=...` like the host flow — user metadata, no token.

**The iframe problem**: the plugin iframe is loaded at `/api/v1/plugins/<id>/public/...` (or a sidecar URL). The host's cookie path matches the iframe's URL, so requests from inside the iframe carry the cookie automatically. **No `postMessage(token)` handshake required.** The current `PLUGIN_READY` postMessage flow becomes legacy.

For paywall endpoints (`POST /plugins/<id>/public-paywall/...`), the cookie is presented on the request; the server reads it instead of the `access_token` field in the body. The body's `access_token` field becomes optional and is deprecated.

```
Pros
─────
+ Strongest in-browser protection: JS in the iframe (or any XSS) can't read the JWT.
+ Same pattern as host SSO — engineers already understand it.
+ Eliminates the `postMessage` token handshake entirely.
+ Eliminates the localStorage write — no token in any JS-readable storage.

Cons
─────
− Doesn't work for sidecar plugins on a different origin. They'd need a separate token issuance.
− `SameSite=lax` blocks cross-site iframe contexts (e.g. if a partner embeds the public portal). `SameSite=none` requires `Secure` and reduces some CSRF mitigations.
− Cookie path matching is per-plugin, so the user has N cookies stored. Acceptable but cookie-jar bloat at 100+ plugins.
− Backward compatibility requires a transitional window where the server accepts both cookie and body-token; rollback is harder once UI fully cuts over to cookies.
```

### Option B: Short-lived server-validated exchange code

Auth-callback URL carries a **single-use exchange code**, not the token. The client POSTs the code to `/plugins/<id>/public-auth/exchange`, which validates the code (one-shot, ≤30s TTL, bound to the originating session) and returns the JWT in the response body. The client stores the JWT in `sessionStorage` (not `localStorage`) so it dies with the tab.

```
Pros
─────
+ Even a phishing URL with a planted exchange code is useless: by the time the attacker tricks the victim into visiting, the code has been used or expired.
+ `sessionStorage` halves the lifetime — closes the tab, loses the token. No cross-tab token sharing.
+ Works for sidecar plugins: the exchange endpoint is on the host, and the resulting JWT travels into the sidecar via the existing `postMessage` handshake (now happens after the exchange completes).
+ No cookie scoping issues; rollback is easy because the server controls the exchange endpoint independently.

Cons
─────
− Still puts the JWT in JS-readable storage. XSS in the iframe or host can exfiltrate.
− Adds one extra HTTP round-trip on every fresh login.
− Exchange-code TTL window is short but non-zero; a sophisticated attacker who can read the URL fragment in real time (e.g. compromised referrer logger) could race.
− Migration is the more annoying half: we have to invalidate every existing `plugin_token_*` localStorage entry on the first post-rollout app load.
```

### Option C: HttpOnly cookie for in-process plugins + per-sidecar BFF token endpoint

Hybrid: in-process plugins use Option A (HttpOnly cookie). Sidecars use a small backend-for-frontend endpoint on the host (`/api/v1/plugins/<id>/sidecar-token`) that the sidecar iframe calls via `fetch` with the host cookie. The endpoint mints a short-lived (~5min) JWT scoped to that sidecar's API and returns it in the response body for in-iframe storage.

```
Pros
─────
+ In-process plugins get the strongest model (HttpOnly cookie, no token in JS).
+ Sidecars still work without leaking the host JWT to a cross-origin iframe.
+ The sidecar's local token is short-lived — XSS exfiltration is limited to 5 minutes of damage and the affected scope is just that sidecar.

Cons
─────
− Two delivery models for engineers to keep straight ("which kind of plugin am I writing?").
− Sidecar-token endpoint is new code with its own attack surface (the BFF pattern is well-understood, but it's still one more thing).
− Migration is the most involved because two flows roll out in parallel.
```

## Recommendation

**Option C, phased**:

1. **Phase 1 (now)**: implement Option A for in-process plugins only. This is the most common case in this repo (currency_rates, investments, time_tracking, expenses) and gets the JWT out of `localStorage` for them.
2. **Phase 2 (after Phase 1 is in production)**: add the sidecar BFF endpoint. Sidecars keep working on the old flow during Phase 1 (they have their own `is_sidecar` branch in PluginContext, so we can gate behavior).
3. **Phase 3**: deprecate the URL `token_data` parameter entirely. Remove the `access_token` body field from the paywall request schemas (server reads cookie).

Rationale for picking C over B:
- Option B keeps the JWT in `sessionStorage`. That's better than `localStorage` but still JS-readable, so any in-iframe XSS exfiltrates it. The whole point of fixing #4 is to remove the JS-readable storage.
- Option A's iframe problem is solvable for in-process plugins because they're same-origin — cookie path scoping handles it without `postMessage(token)`. We don't need to invent an exchange code for the common case.
- Sidecars are a real but smaller surface, and they justify their own BFF pattern because they're already a distinct architectural shape.

Rationale for picking C over A alone:
- A doesn't solve sidecars. We can't ship A without breaking time-tracking and any other sidecar plugin. C lets us ship A for the common case immediately.

## Migration plan

Phase 1 (Option A for in-process):

1. **Server**: change the in-process auth-callback path (`api/commercial/plugin_management/auth.py:220` and `:307`) to set an HttpOnly cookie scoped to `path=/api/v1/plugins/<plugin_id>/` and `path=/p/<plugin_id>` (the public portal URL), and redirect to `/p/<plugin_id>/auth-callback?user=<b64>&next=...` (no `token_data`).
2. **Server**: paywall endpoints accept the cookie as the primary auth source. The `access_token` body field is honored for one release as a fallback so already-logged-in sessions don't break, then removed.
3. **Client**: `App.tsx:PublicPluginCatchAll` reads `?user=` (not `?token_data=`) and stores the user metadata in `sessionStorage` (for display only — `email`, `id`). No JWT in JS storage. Existing `localStorage.plugin_token_*` reads remain in `PublicPluginWrapper` as a transitional fallback for the deprecation window, then removed.
4. **Client**: `PublicPluginWrapper`'s `postMessage(AUTH_TOKEN)` becomes a no-op for in-process plugins because the iframe receives the cookie via the browser. For sidecars (Phase 2), it remains.
5. **Backward compat**: the existing `localStorage.plugin_token_*` entries are read and **migrated** on first post-rollout load: client calls `/plugins/<id>/public-auth/migrate` with the localStorage token; server validates it, sets the new cookie, returns success; client clears localStorage. This avoids a mass-logout event.
6. **Telemetry**: add a counter on the migrate endpoint so we can watch the curve and decide when to drop the fallback.

Phase 2 (sidecar BFF — separate PR sequence):

1. New `GET /api/v1/plugins/<id>/sidecar-token` endpoint: requires the in-process cookie, mints a 5-minute JWT scoped to that sidecar, returns in body.
2. Sidecar iframe calls this endpoint via `fetch` on load. Existing `postMessage(AUTH_TOKEN)` from `PublicPluginWrapper` is replaced by the sidecar fetching its own token from the host.
3. Sidecar manifest declares `requires_short_lived_token: true` so we can detect old-flow sidecars during the deprecation window.

Phase 3 (cleanup): remove the migration endpoint, remove the `access_token` body field from the paywall schemas, remove the `localStorage` fallback paths.

## Open questions for the decision meeting

1. **Cookie path or cookie subdomain?** Path scoping (`/api/v1/plugins/<id>/`) is simpler. Subdomain scoping (`plugin-<id>.tenant.example`) requires DNS work but isolates cookies per plugin at the browser level. For 100+ plugins, subdomains might be cleaner. Worth it now or later?
2. **`SameSite` setting on the plugin cookie?** Host SSO uses `lax`. Plugins that get embedded as iframes by external partner sites would need `none`. Do we have any such partners?
3. **Migration window length?** 30 days of dual-accept (cookie + body fallback) is conservative; 7 days is aggressive. Pick based on tenant rollout cadence.
4. **Phase 2 timing.** Can we ship Phase 1 standalone and accept that sidecars stay on the old flow for 1-2 sprints, or does Phase 1 require Phase 2 to be ready first because of compliance?
5. **What about the `PLUGIN_INTERACTION` postMessage path?** Post-#311 it's origin-gated, so even with the old flow it's now safe against external sites posting. Does Phase 2's BFF model affect this? (My read: no, because `PLUGIN_INTERACTION` only carries usage counts, not the token. The token-handshake postMessage is the only one that changes shape.)

## Out of scope

- CRITICAL #6 (git installer RCE) — separate deployment-policy decision.
- The HIGH-tier findings from the review (X-Plugin-Caller header validation, sidecar manifest signing, etc.). Each gets its own follow-up.
- Refactoring the host SSO flow. The host flow is already on the right pattern; this doc is only about catching the plugin flow up.

## References

- Plugin-system code review findings (this session, summarized in PR #310 and PR #311 bodies).
- Host SSO cookie flow: `api/commercial/sso/router.py:402-418`.
- Current plugin auth-callback issuers: `api/commercial/plugin_management/auth.py:208-220` (Google), `:296-307` (Azure).
- Client consumer of the URL-supplied token: `ui/src/App.tsx:138-156` (`PublicPluginCatchAll`).
- All downstream consumers of `localStorage.plugin_token_*`: `ui/src/components/plugins/PublicPluginWrapper.tsx`, `ui/src/pages/PluginAuth.tsx`, `ui/src/pages/PluginPaywall.tsx`.
