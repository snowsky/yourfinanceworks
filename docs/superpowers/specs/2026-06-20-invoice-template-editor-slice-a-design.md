# Invoice Template Editor — Slice A Design Spec

**Date:** 2026-06-20
**Status:** Approved design → ready for implementation planning
**Scope:** Phase 2, **Slice A** of the "drag-and-drop invoice template editor" (competitor differentiator — Feature Matrix "Drag-and-drop template editor + custom fields"). Slice A delivers **style & visibility controls + a live preview**. It builds directly on the Phase 1 unified renderer (`api/core/services/invoice_render/`, shipped in PR #421). The drag-and-drop section reordering, column/display modes, and named/multiple templates are **later slices, out of scope here**.

---

## Problem

Phase 1 established a single config-driven renderer (Jinja2 + WeasyPrint) and the `InvoiceTemplateConfig` schema, but the **only** way a tenant changes invoice appearance is the small branding form in `InvoiceSettingsTab.tsx` (brand/accent colors, a few toggles, footer text, a mini preview). There is no way to choose a font, place/size the logo, or see changes rendered the way the client actually receives them — against the real template, live, before saving.

Slice A turns the existing branding form into a **template editor**: a two-pane surface where the tenant edits style + section visibility on the left and sees a **live, server-rendered sample invoice** on the right, then saves. Because the config flows through Phase 1's `load_template_config`, every client-facing surface (web view, PDF, share/portal, email attachment) picks up the result automatically.

## Goal

Let a tenant **edit and preview** their invoice template's style and section visibility, with the preview rendered by the **same** renderer that produces client-facing output — no second rendering path, no divergence.

**Non-goals (Slice A):** drag-and-drop section reordering; column choice / custom-field display modes; named or multiple templates; additional fonts beyond the bundled DejaVu families; email-body templating; per-invoice overrides (visibility stays tenant-wide except the existing per-invoice `show_discount_in_pdf`).

---

## Config schema extension

Extend `InvoiceTemplateConfig` (`api/core/services/invoice_render/config.py`) with three **enum** fields. The existing `show` dict already covers `logo` / `notes` / `custom_fields` / `footer`; colors and footer text already exist.

```python
font_family: str = "sans"        # one of {"sans", "serif", "mono"}
logo_placement: str = "left"     # one of {"left", "center", "right"}
logo_size: str = "medium"        # one of {"small", "medium", "large"}
```

- `font_family` maps to the bundled DejaVu families: `sans` → DejaVu Sans, `serif` → DejaVu Serif, `mono` → DejaVu Sans Mono. **No new fonts are bundled** in Slice A — these three families ship in the Phase 1 api image already.

## Persistence + validation

- **Storage:** the existing `invoice_branding` Settings row (the Phase 1 config store), extended with keys `font_family`, `logo_placement`, `logo_size`. The `show_*` keys already persist there. **Backward-compatible:** any missing key falls back to the dataclass default.
- **Defense in depth (two layers):**
  1. The branding **write path** (`api/core/services/invoice_branding.py`) validates the three new enums (alongside the existing 6-digit-hex color validation). An invalid value is rejected/normalized on write.
  2. `load_template_config` **clamps** any out-of-range value to its default on **read**. A bad value in the stored row can therefore never reach the renderer.
- Allowed sets are the single source of truth, defined once in `config.py` and reused by both layers and the renderer.

## Rendering (shared template + CSS)

The three new fields are enum-validated, so the template emits them as **CSS class names** — never raw user text interpolated into CSS (preserving the Phase 1 injection-safety posture; colors keep their existing hex-validated `--brand`/`--accent` inline-var mechanism).

- `default.html`: the root element gets `font-{{cfg.font_family}}` (e.g. `font-serif`); the logo wrapper gets `logo-{{cfg.logo_placement}} logo-{{cfg.logo_size}}`.
- `default.css` defines:
  - a font stack per `.font-sans` / `.font-serif` / `.font-mono` (DejaVu families);
  - `text-align` / flex alignment per `.logo-left` / `.logo-center` / `.logo-right`;
  - a logo `width` tier per `.logo-small` (≈80px) / `.logo-medium` (≈120px) / `.logo-large` (≈160px).
- Section visibility continues to use the existing `cfg.show.*` conditionals already in the template.

## Live preview — `POST /invoices/template-preview`

A new **authenticated** route (in `api/core/routers/invoices/pdf_email.py`, alongside the existing preview endpoints).

- **Request body:** the **draft config** only — `brand_color`, `accent_color`, `footer_text`, `show{}`, `font_family`, `logo_placement`, `logo_size`. **No invoice id** — this previews the *template*, not a specific invoice.
- **Sample view model:** a new `sample_view_model(db, tenant, config)` helper in `view_model.py` builds a representative `InvoiceViewModel`:
  - **real company identity** — tenant name + resolved logo (so the tenant sees *their own* logo placed and sized live);
  - **canned** client, three line items, subtotal/discount/total, sample notes, and two custom fields.
- **Response:** `render_invoice_html(sample_vm, draft_config)` returned as `text/html`. (No PDF in the preview path — HTML only, matching the existing `/preview` endpoints.)
- The draft config is validated/clamped on the way in via the same allowed-set logic, so the preview reflects exactly what a save-then-render would produce.

## Frontend — `InvoiceSettingsTab.tsx` → two-pane editor

Grow the existing tab into a two-pane layout (widen the tab if the settings page is cramped). All invoice appearance stays in this one place; the existing branding-save mutation is extended with the three new fields.

- **Left pane — controls:**
  - Brand + accent **colors** (existing hex-validated color inputs).
  - **Font** — select / segmented control: Sans / Serif / Mono.
  - **Logo** — placement (Left / Center / Right) + size (S / M / L) segmented controls, plus the existing show-logo toggle.
  - **Section visibility** — toggles for logo, custom fields, notes, footer. *(Bill-to, line-items table, and totals are always shown — not toggleable.)*
  - **Footer text** (existing).
- **Right pane — live preview:**
  - A **sandboxed** `<iframe srcDoc={previewHtml}>` showing the sample invoice.
  - Re-fetches `POST /invoices/template-preview` **debounced (~300ms)** whenever any control changes, sending the current draft config.
- **Save:** reuses the existing branding-save mutation, extended to send `font_family`, `logo_placement`, `logo_size`.
- New/extended API service: the branding service gains the three fields; add `fetchTemplatePreview(draftConfig)` returning HTML.

## Surfaces affected

None beyond the shared template/CSS. The saved config flows through Phase 1's `load_template_config`, so the **web view, PDF, share/portal, and email attachment** all pick up font + logo placement/size + visibility automatically. No per-surface code changes.

---

## Testing

- **View-model unit:** `sample_view_model(db, tenant, config)` returns a well-formed VM — canned items/client/totals are internally consistent (subtotal/discount/total/balance), company identity comes from the tenant. Pure, no stack.
- **Config unit:** `load_template_config` clamps invalid `font_family` / `logo_placement` / `logo_size` to defaults; reads valid values through; missing keys → defaults (backward-compat).
- **Renderer unit:** the correct `font-*` and `logo-*` classes appear in the rendered HTML per config; an invalid enum never reaches output (clamped); `show.notes = false` → no notes block; `show.custom_fields = false` → no custom-fields block.
- **Endpoint integration:** `POST /invoices/template-preview` returns `200 text/html`, honors the draft config (e.g. `show.notes=false` → no notes block in the HTML), and requires auth (401/403 unauthenticated).
- **Frontend (vitest):** the tab renders the new controls; changing a control triggers a debounced preview fetch; Save sends the three new fields.

## Risks & mitigations

- **CSS injection via new fields** — mitigated by emitting enum-validated values as class names only, never interpolating raw text into CSS (colors keep their existing hex validation).
- **Bad stored value breaks rendering** — mitigated by the two-layer validate-on-write + clamp-on-read.
- **Preview/output divergence** — eliminated by routing the preview through the same `render_invoice_html` + `load_template_config` path as client-facing output; only the *view model* differs (sample vs. real invoice), not the renderer or config handling.
- **Event-loop blocking** — the preview path renders **HTML only** (no WeasyPrint), so it does not incur the PDF CPU cost; the existing `render_invoice_pdf_async` threadpool offload remains for PDF surfaces.

## What later slices add

Drag-and-drop section reordering; column choice and custom-field display modes; named/multiple templates; additional bundled fonts; email-body templating. The `InvoiceTemplateConfig` schema is designed to grow into these without a rewrite.
