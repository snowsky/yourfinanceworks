# Invoice Template Editor — Slice B: Drag-and-drop Section Reordering (Design)

**Feature:** Competitor #5 — drag-and-drop invoice template editor.
**Slice:** B (the marquee capability). Builds directly on the Foundation (PR #421) and Slice A (PR #422).
**Status:** Design approved 2026-06-28.

## Goal

Let a tenant reorder the invoice's body sections by drag-and-drop. The chosen order persists in the existing `invoice_branding` config and is honored by the unified renderer across **every** surface (web view, share link, PDF, email) automatically.

## Decisions (settled in brainstorm)

1. **Reorder scope:** all 5 body sections are freely reorderable — `billto`, `custom` (Details / custom fields), `items` (line items), `totals`, `notes`. The header (logo / company / meta) is pinned at the top; the footer is pinned at the bottom. Totals may move freely (no Items→Totals lock).
2. **Default order:** the current top-to-bottom order — `billto, custom, items, totals, notes`. Existing tenants render byte-identically until they reorder.
3. **Visibility toggles:** **unify** the show/hide controls into the reorder list. Each reorderable row has a drag handle; the two hideable sections (Details, Notes) get an inline show toggle that writes the existing `show_custom_fields` / `show_notes` keys, replacing those two standalone checkboxes. Bill To / Line items / Totals are always-on (no toggle). Logo-show and Footer-show controls stay where they are (header / footer are not in the reorderable body).
4. **Rendering mechanism:** Jinja2 macro-dispatch loop (Approach A) — smallest change, injection-safe, live preview reflects it for free.

## Architecture

### 1. Config & validation — `api/core/services/invoice_render/config.py`

Add a fixed allowed-set and a new field to `InvoiceTemplateConfig`:

```python
ALLOWED_SECTIONS = ("billto", "custom", "items", "totals", "notes")
DEFAULT_SECTION_ORDER = list(ALLOWED_SECTIONS)

# in the dataclass:
section_order: list[str] = field(default_factory=lambda: list(DEFAULT_SECTION_ORDER))
```

`build_config()` (pure, clamp-on-read) normalizes `section_order` defensively so a bad or stale value can never reach the renderer:
- Read `b.get("section_order")`; if not a list, fall back to the default.
- Drop any id not in `ALLOWED_SECTIONS` (unknown strings never reach the template → injection-safe).
- De-dupe, keeping first occurrence.
- **Append any missing allowed sections** in canonical order, so an order persisted before a section existed never loses that section.

`validate_invoice_branding()` (write path → 400) rejects a `section_order` that is present but not a list of strings. The clamp in `build_config` remains the real safety net (defense in depth, mirroring Slice A's two-layer validate-on-write + clamp-on-read).

**Storage:** persists as a JSON list inside the existing single flat `invoice_branding` Settings row. No migration; a missing key → default order.

### 2. Template — `api/core/services/invoice_render/templates/invoice/default.html`

Convert the 5 body sections into Jinja2 macros, keeping each section's existing `{% if cfg.show.* %}` guard **inside** its own macro so order and visibility compose independently:

```jinja
{% macro section_billto(vm, cfg) %}…{% endmacro %}
{% macro section_custom(vm, cfg) %}{% if cfg.show.custom_fields and vm.custom_fields %}…{% endif %}{% endmacro %}
{% macro section_items(vm, cfg) %}…{% endmacro %}
{% macro section_totals(vm, cfg) %}…{% endmacro %}
{% macro section_notes(vm, cfg) %}{% if cfg.show.notes and vm.notes %}…{% endif %}{% endmacro %}
```

Replace the fixed body block with a dispatch loop. A small `{% macro render_section(sid, vm, cfg) %}` maps each id to its section macro (explicit `{% if sid == 'billto' %}…`), so only known ids render and the id itself is never emitted as raw HTML. Header and `<footer>` stay hard-coded outside the loop.

Output is byte-identical to today when `section_order` is the default order.

### 3. Frontend — `ui/src/components/settings/InvoiceSettingsTab.tsx`

A new "Section order" control: a `@dnd-kit/sortable` vertical list mirroring the existing pattern in `ui/src/components/reminders/ReminderList.tsx` (`@dnd-kit` is already a dependency — `core@^6.3.1`, `sortable@^10.0.0`, `utilities@^3.2.2`; no new dep).

- 5 rows, each with a drag handle, labeled Bill To / Details / Line items / Totals / Notes.
- Details and Notes rows render an inline eye/show toggle bound to the existing `show_custom_fields` / `show_notes` draft keys. Remove those two standalone checkboxes from the tab.
- Reordering mutates the draft config's `section_order` → the existing debounced (~300 ms) `POST /api/v1/invoices/template-preview` already re-renders the live `<iframe srcDoc>` preview for free.
- i18n keys for the new labels go straight into `en.json` (`fallbackLng: 'en'`).

### 4. Surfaces

No surface-specific work: `section_order` flows everywhere because all surfaces resolve config via `load_template_config(db)` → `build_config` → `default.html`. Web view, share link, PDF (`render_invoice_pdf`), and email all inherit it.

## Testing

- **`build_config` clamp cases:** absent key → default order; unknown id dropped; duplicates removed; missing section appended in canonical position; non-list value → default.
- **Render test:** a reordered `section_order` produces sections in the requested order; default order matches the pre-slice output (regression guard).
- **`validate_invoice_branding`:** a non-list `section_order` raises 400; a valid list passes.
- **Frontend:** the sortable list updates draft `section_order`; the Details/Notes inline toggles write the correct `show_*` keys.

## Out of scope (deferred to Slice C)

- Per-section column choices / custom-field display modes (C1).
- Named / multiple templates with per-invoice selection (C2).
- Reordering within the header or footer; making header/footer themselves movable.
- Visual polish of the default template typography/spacing.
```
