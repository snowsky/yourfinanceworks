# Invoice Render Foundation — Design Spec (Phase 1)

**Date:** 2026-06-19
**Status:** Approved design → ready for implementation planning
**Scope:** Phase 1 of the "drag-and-drop invoice template editor" (competitor differentiator, spreadsheet opportunity #5 / Feature Matrix "Drag-and-drop template editor + custom fields"). This spec covers **only the foundation** — a unified, config-driven invoice renderer. The editor UI is **Phase 2** (a separate spec) and is out of scope here.

---

## Problem

Invoice appearance is re-implemented in **4+ places with no shared template and no layout config**:

- **In-app PDF download** → `@react-pdf/renderer` (browser) — `ui/src/components/invoices/InvoicePDF.tsx`
- **Emailed / portal PDF** → **ReportLab** (Python, server) — `api/core/utils/pdf_generator.py` — *a different engine, so the two PDFs visually diverge*
- **Email body** → Jinja2 HTML that **ignores branding entirely** — `api/core/services/email_service.py`
- **Authenticated web view** → bespoke JSX that **ignores brand colors** — `ui/src/pages/ViewInvoice.tsx`
- **Public share / client-portal view** → another JSX block (this one applies branding) — `ui/src/pages/SharedRecord.tsx`, `api/core/routers/share_tokens.py`

"Branding" today is **4 fields** (`brand_color`, `accent_color`, `show_logo`, `footer_text` — `api/core/services/invoice_branding.py`). Discount proration, currency formatting, and logo resolution are **duplicated and divergent** across surfaces; custom fields render in **only** the react-pdf surface. The one `get_layout()` hook in `api/templates/invoice_templates.py` is **dead code**. A template editor therefore has **no config object to target**.

## Goal

**One source of truth** for invoice appearance: a server-side **Jinja2 HTML/CSS template + a layout config**, rendered to HTML and to PDF via **WeasyPrint**, consumed by all client-facing surfaces. This retires the divergent engines and the duplicated logic, and establishes the **config schema the Phase-2 editor will extend**.

**Non-goals (Phase 1):** the drag-and-drop editor UI; rich config (fonts, section ordering, column choice, logo placement, named/multiple templates); email-body templating; PDF caching; a per-tenant opt-in flag.

---

## Architecture

New module **`api/core/services/invoice_render/`**:

- **`view_model.py`** — `build_view_model(invoice, tenant, config) -> InvoiceViewModel`. The **single** place that computes subtotal / discount proration / paid / balance, formats currency, resolves the logo, and splits reserved tax keys out of custom fields.
- **`config.py`** — `InvoiceTemplateConfig` schema (Phase-1 knobs; editor-extensible).
- **`renderer.py`** — `render_invoice_html(vm, config) -> str` (Jinja2) and `render_invoice_pdf(vm, config) -> bytes` (WeasyPrint over that HTML).
- **`templates/invoice/default.html`** + **`default.css`** — the single template.

### Data contract — `InvoiceViewModel`

The template is "dumb"; all computation happens upstream, once.

- `company` — name, resolved `logo_url`, address, phone, email, tax_id *(from the master `Tenant` record — `api/core/models/models.py`)*
- `meta` — number, issue_date, due_date, status, currency
- `client` — bill-to name, email, phone, address
- `items[]` — description, quantity, unit_of_measure, unit_price, amount *(each with raw value + currency-formatted string)*
- `totals` — subtotal, discount `{type, value, amount}`, total, paid, balance *(formatted)*
- `custom_fields[]` — `{label, value}` with reserved tax keys (`tax_amount`, `tax_rate`) split out
- `notes`, `footer_text`

Centralizing this kills three current divergences: **logo resolution** (3 strategies today), **discount proration** (duplicated in `pdf_generator.py` and `InvoicePDF.tsx`), **currency formatting** (3 different implementations).

### Config — `InvoiceTemplateConfig` (Phase-1)

- `colors` — `brand_color`, `accent_color` (existing branding)
- `show` — `{ logo, notes, custom_fields, footer }` booleans — **tenant-wide** section visibility (folds in today's `show_logo`)
- `footer_text`

> **Discount visibility stays per-invoice.** Today's `show_discount_in_pdf` is a per-invoice column; it is **not** folded into the tenant config. The view-model honors it per invoice so no per-invoice control is lost — the discount block renders when `invoice.show_discount_in_pdf` is true.

**Storage:** the config **is the existing `invoice_branding` Settings row, extended** — the 4 current fields are preserved (backward-compatible); we add the `show` toggles. `build_view_model()` reads from **both** stores: master `Tenant` (company identity) + tenant `invoice_branding` Settings (config). **One config per tenant.** *(Phase-2 editor grows this schema: fonts, section order, columns, logo placement, named templates — without breaking it.)*

### Data flow

```
Invoice (+items +payments) + Tenant + config
  → build_view_model()  → InvoiceViewModel
  → render_invoice_html()  → HTML
  → render_invoice_pdf()  → PDF (WeasyPrint)
```

---

## Surfaces (Phase-1 scope)

- **PDF** (in-app download, email attachment, portal download) → `render_invoice_pdf`. **Retires** the ReportLab and react-pdf invoice paths.
- **Authenticated web view** → `GET /api/v1/invoices/{id}/preview` returns the HTML; `ViewInvoice.tsx` shows it in a **sandboxed `<iframe srcdoc>`**; "Download PDF" hits the server endpoint. *(The internal view stops being bespoke React — preview == what the client receives.)*
- **Public share / client-portal view** → `render_invoice_html` using the **public-safe** view-model + the tenant's config; the React share/portal pages display it via the **same sandboxed `<iframe>`** approach as the authenticated web view.
- **Email** → keeps its current short body in Phase 1 but **attaches the new unified PDF**. Email-body templating deferred.

---

## Visual baseline & migration

- **One new polished default template** — branding colors as accents, solid typography, clear line-items table and totals block. The exact HTML/CSS look is **built and visually reviewed during implementation**, not pinned in this spec; it is what the Phase-2 editor then makes editable.
- **No data migration.** Config = the extended `invoice_branding` row; new `show` toggles default sensibly (`logo` ← existing `show_logo`, `notes`/`custom_fields` ← on). Per-invoice discount visibility stays driven by the existing `show_discount_in_pdf` column. Existing invoices render immediately from existing data + branding.
- **New look ships for all tenants** on release — **no per-tenant opt-in flag** (it is strictly a nicer default).
- **Retired code:** `InvoicePDF.tsx` (react-pdf) and the invoice paths in `pdf_generator.py` (ReportLab) are replaced. Kept **dormant for one release** as a rollback hatch, then removed. The `modern`/`classic` template param collapses into two branding-color **presets**.

---

## Rendering pipeline

- **Docker:** add WeasyPrint's system libs to the api Dockerfile (`libpango-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`, `libgdk-pixbuf-2.0-0`, `libffi`) + a **bundled font** (e.g. DejaVu/Inter) so PDFs render identically regardless of host; `pip install weasyprint`. Modest image growth; **no Chromium**.
- **Performance — and a direct lesson from the DB-pool work this session:** WeasyPrint is sync CPU work (~100–500 ms/PDF). Run it in a **threadpool (`run_in_executor`)** so it never blocks the async event loop (the exact starvation pattern fixed in #414/#420). On-demand generation; **PDF caching deferred**.

---

## Testing

- **View-model unit tests** (parity-critical, pure — same approach as `dashboard_service`): invoice + items + payments + config → assert totals, discount proration, currency formatting, tax/custom-field split, logo resolution. No stack required.
- **Renderer tests:** config toggles produce/omit the right sections (e.g. `show.discount=False` → no discount block; custom fields render when present).
- **PDF smoke test:** `render_invoice_pdf` returns valid bytes (`%PDF…`, non-empty) for a sample invoice — proves WeasyPrint runs in-container.
- **Endpoint integration:** correct status + content-type (`application/pdf`, `text/html`).
- **Manual visual review** during implementation (render sample invoices, eyeball PDF + HTML).

---

## Risks & mitigations

- **WeasyPrint CSS limits** (vs a real browser) — acceptable for document layout; bundle fonts for consistency; avoid CSS features it doesn't support.
- **Visible invoice change for all tenants** — mitigated by a strictly-nicer default + the one-release rollback hatch.
- **Public/unauthenticated share rendering** must use the **public-safe** view-model (no internal fields leaked) — reuse the existing public-safe invoice subset (`api/core/schemas/share_token.py`).
- **Event-loop blocking** from sync PDF rendering — mitigated by the threadpool offload above.

---

## What Phase 2 (the editor) adds later

A UI to edit the `InvoiceTemplateConfig` (drag/reorder sections, toggles, fonts, colors, logo placement, custom-field display) with a **live preview** that reuses `render_invoice_html`. The config schema defined here is designed to grow into that without a rewrite.
