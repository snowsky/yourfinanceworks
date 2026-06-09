# Invoice Branding + Branded Client Portal (Competitor #5) — Plan

**Status:** ✅ Shipped — slices 1–6 merged (#362 setting+payload, #363 editor+share page, #364 download-PDF colours, #365 emailed-PDF colours, #366 download-PDF logo, #367 emailed-PDF logo). Branding is complete across web view, share page, downloaded PDF, and emailed PDF. The client-login portal is planned separately in `client-portal-plan.md`. Deferred follow-ups below remain optional.
**Scope decided (2026-06):** MVP slice = **branded public invoice page** at `/shared/:token` driven by an **invoice-branding settings panel**. Tokenized link, **no client login**. Branding applies to the **web/share view only** (PDF + email deferred).

## Why this shape
The share-token system already does the hard part:
- `ShareToken` model + public `GET /api/v1/shared/{token}` (no JWT, password/expiry/access-count) — `api/core/routers/share_tokens.py`.
- Frontend `/shared/:token` route → `ui/src/pages/SharedRecord.tsx` already renders a generic, **unbranded** invoice (`InvoiceView`, lines 31-67).
- `record_type=invoice` is already supported.

So the MVP is: (1) make tenants able to set brand colors, (2) include branding in the public payload, (3) render a polished branded invoice on the share page. No new auth, no new token plumbing.

## Gaps this closes
- Public invoice payload (`share_tokens.py:350-366`) carries **no tenant branding** (no company name/logo/colors).
- No per-tenant invoice brand color/accent/footer settings.
- Share page invoice view is generic and unbranded.

---

## Slice 1 — Backend (PR A)

1. **Branding storage** — new per-tenant `Settings` key `invoice_branding`:
   ```json
   { "brand_color": "#1e3a8a", "accent_color": "#3b82f6", "show_logo": true, "footer_text": "Thank you for your business." }
   ```
   Tenant already has `company_logo_url`, name/email/phone/address (master DB, `models.py:121-149`).

2. **Authenticated settings API** (`api/core/routers/settings.py`) — read/write `invoice_branding` (GET returns a `branding` block with sane defaults; PUT validates hex colors `^#[0-9a-fA-F]{6}$`, clamps `footer_text` length).

3. **Public payload branding** — add an optional `branding` object to the invoice public view returned by `_fetch_public_record` (`share_tokens.py:327-366`). Source: Tenant (master, via `token.tenant_id`) for company name/logo/contact + tenant `Settings.invoice_branding` for colors/footer. Fields: `company_name, company_logo_url, company_email, company_phone, company_address, brand_color, accent_color, show_logo, footer_text`. Branding is **invoice-only** (other record types unchanged).

4. **Tests** (`api/tests/`): public invoice payload includes `branding`; settings round-trip + hex validation rejects bad input. Run in Docker (Postgres) — watch NOT-NULL/FK gotchas per prior sessions.

## Slice 2 — Frontend (PR B)

1. **Branding editor** — a "Branding" card (in `InvoiceSettingsTab.tsx` or new `InvoiceBrandingTab`): brand color + accent color pickers, show-logo toggle, footer text, with a **live invoice preview**. Saves via `settingsApi`. Reuse logo upload already in `CompanyInfoTab`.

2. **Branded share view** — replace `SharedRecord.tsx`'s `InvoiceView` with a polished branded layout: logo header band in `brand_color`, company contact block, line-item table with accent borders, totals, `footer_text`. Apply colors via scoped inline CSS vars (no global theme pollution). Graceful fallback when `branding` is absent (older links).

3. **"View online" affordance** — confirm/extend the invoice share UI so the generated `/shared/:token` link is easy to copy/send (share-token creation already exists; verify there's a share button on invoice detail, add if missing).

4. **i18n** — add keys **directly to `en.json`** (no inline fallbacks — matches the convention from the i18n sweep, PRs #359-361).

## Decisions / open items
- **Feature gating:** share tokens are core, so default the branded page to **core (ungated)**. Revisit if branding should be a commercial upsell.
- **PDF/email branding:** deferred to a later slice (two generators: backend ReportLab + frontend react-pdf).
- **Per-client portal (list of all their invoices) + client login:** explicitly out of scope for this MVP.

## Verification
- `npx tsc --noEmit -p tsconfig.app.json` clean vs `main` baseline (use a node_modules-symlinked worktree, NOT `git stash` — repo has 36 foreign stashes).
- Backend tests pass in Docker (Postgres).
- Manual: set brand colors → open a share link in an incognito window → branded invoice renders; old links without branding still render.
