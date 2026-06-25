# Invoice Template Editor — Remaining Slices (TODO)

**Feature:** Competitor #5 — drag-and-drop invoice template editor + custom fields.
**Status:** Foundation (PR #421) and **Slice A** (PR #422) shipped. Slices below are deferred.

**What's already in place (build on this, don't re-derive):**
- Unified renderer `api/core/services/invoice_render/` (Jinja2 + WeasyPrint).
- `InvoiceTemplateConfig` (`config.py`) with `brand_color`, `accent_color`, `footer_text`, `show{logo,notes,custom_fields,footer}`, `font_family`, `logo_placement`, `logo_size`.
- Two-layer validation: `validate_invoice_branding` (write, → 400) + pure `build_config()` clamp-on-read. Allowed-set tuples live only in `config.py`.
- Config persists in the single flat `invoice_branding` Settings row (no migration; missing keys → defaults).
- Two-pane editor in `ui/src/components/settings/InvoiceSettingsTab.tsx` with sandboxed `<iframe srcDoc>` live preview, debounced ~300ms against `POST /api/v1/invoices/template-preview` (renders `sample_view_model(tenant, config)` — tenant's real logo/name + canned invoice, HTML-only).
- Enums emitted ONLY as CSS class names (`font-*`, `logo-*`) — injection-safe.
- Spec: `docs/superpowers/specs/2026-06-20-invoice-template-editor-slice-a-design.md`
- Plan: `docs/superpowers/plans/2026-06-20-invoice-template-editor-slice-a.md`

---

## Slice B — Drag-and-drop section reordering (the marquee capability)

Let tenants reorder the invoice's sections (e.g. bill-to, custom fields/details, line items, totals, notes) by drag-and-drop, with the order persisted in the config and honored by the renderer across all surfaces.

- **Config:** add a `section_order: list[str]` to `InvoiceTemplateConfig` (allowed section ids = a fixed set; `build_config` clamps to a canonical default order, drops unknown ids, appends any missing ones so the template never loses a section). Persist in the `invoice_branding` row.
- **Template:** drive section rendering from `section_order` (loop emitting each section block by id) instead of the current fixed top-to-bottom layout. Keep the header (logo/company/meta) fixed; reorder only the body sections.
- **Frontend:** a drag-and-drop list in the editor's left pane (check for an existing dnd lib in `ui/` before adding one). Reordering updates the draft config → debounced live preview already reflects it for free.
- **Decisions to settle in brainstorm:** which sections are reorderable vs. pinned (header/totals?); whether totals can move; default order; how it interacts with the existing visibility toggles.

## Slice C — Column choice / custom-field display modes, or named/multiple templates

Two candidate directions (pick one to brainstorm, or split):

- **C1 — Line-item columns / custom-field display modes:** let tenants choose which line-item columns show (e.g. unit-of-measure, qty, unit price) and how custom fields render (inline list vs. table). Extends the `show`-style config with column flags; template renders columns conditionally.
- **C2 — Named / multiple templates:** move from one config-per-tenant to N named templates, with a selector and a per-invoice template choice. Larger: changes storage from the single `invoice_branding` row to a collection (likely a new table or keyed settings), adds a template CRUD UI, and a per-invoice `template_id`. Needs its own spec.

---

## Also deferred (from the Phase-1 foundation, lower priority)
- Visual polish of the default template (typography/spacing) — `default.html` / `default.css`.
- Remove the now-unused `@react-pdf/renderer` npm dep (foundation retired the react-pdf invoice path).
- Email-send path uses sync `render_invoice_pdf`; consider `render_invoice_pdf_async`.
- `_css()` re-reads `default.css` from disk per render — cache it.
- Optional Slice-A polish: gate the preview effect on `!isLoading` to drop one redundant mount-time POST.
