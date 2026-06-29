# Invoice Template Editor — Slice C: Line-item Columns + Custom-field Display Mode (Design)

**Feature:** Competitor #5 — invoice template editor.
**Slice:** C. Builds directly on the Foundation (PR #421), Slice A (PR #422), and Slice B (PR #426).
**Status:** Design approved 2026-06-29.

## Goal

Let a tenant control the **content density** of their invoice:

1. **Line-item columns** — choose which optional columns appear in the line-items table (Quantity, Unit price), and whether unit-of-measure is shown (merged into the Qty cell).
2. **Custom-field display mode** — render the Details/custom-fields section as the current inline **list** or as an aligned two-column **grid**.

The chosen settings persist in the existing flat `invoice_branding` Settings row and are honored by the unified renderer across **every** surface (web view, share link, PDF, email) automatically — every surface resolves config through `load_template_config(db)` → `build_config` → `default.html`.

C2 (named / multiple templates with per-invoice selection) is explicitly **out of scope** for this slice and captured separately as a future epic (see `docs/todos/invoice-template-c2-named-templates-epic.md`).

## Decisions (settled in brainstorm)

1. **Always-on columns:** Description and Amount always render (a line item is meaningless without a description or a line total). Only **Quantity** and **Unit price** are toggleable columns.
2. **Unit of measure:** rendered **merged into the Qty cell** (e.g. `10 hrs`) when its toggle is on and the item has a non-empty UoM — not a separate column. No empty "Unit" cells for items without a UoM. Controlled by a single flag `show_col_unit_of_measure`. The merge only shows when the Quantity column itself is visible (UoM has no cell to live in otherwise).
3. **Defaults preserve today's output exactly:** Quantity **on**, Unit price **on**, UoM **off**, custom-fields layout **`list`**. An existing tenant who never touches these controls renders identically to pre-Slice-C.
4. **Custom-field layout:** an enum `custom_fields_layout ∈ {"list", "grid"}`, default `list`. Emitted as a CSS class on the section wrapper (`custom-list` / `custom-grid`) — never as raw HTML. `grid` styling lives in `default.css`.
5. **Config shape:** line-item column visibility lives in a new `columns: Dict[str, bool]` on `InvoiceTemplateConfig` (parallel to the existing `show` dict), populated from flat `show_col_*` keys in the branding row. `custom_fields_layout` is a top-level string field.
6. **Qty+UoM merge is template-side:** the view model stays render-agnostic (it already carries `quantity` and `unit_of_measure` separately on `ItemVM`); the template composes the merged label conditionally from `cfg.columns`. No view-model change.

## Architecture

### 1. Config & validation — `api/core/services/invoice_render/config.py`

Add an allowed-set, a default columns map, and two fields:

```python
ALLOWED_CUSTOM_FIELDS_LAYOUTS = ("list", "grid")
_DEFAULT_COLUMNS = {"quantity": True, "unit_price": True, "unit_of_measure": False}

# in InvoiceTemplateConfig:
columns: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_COLUMNS))
custom_fields_layout: str = "list"
```

`build_config()` (pure, clamp-on-read) reads the flat keys, mirroring how `show` is built today:

```python
columns = dict(_DEFAULT_COLUMNS)
for key in ("quantity", "unit_price", "unit_of_measure"):
    if f"show_col_{key}" in b:
        columns[key] = bool(b[f"show_col_{key}"])
# ...
columns=columns,
custom_fields_layout=_clamp(b.get("custom_fields_layout"), ALLOWED_CUSTOM_FIELDS_LAYOUTS, "list"),
```

`build_config` stays pure (no DB); any bad/missing value falls back to a default, so a stale or hostile value can never reach the renderer.

`validate_invoice_branding()` (write path):
- coerces each `show_col_*` key with `bool(...)` into the cleaned output — consistent with the sibling `show_notes`/`show_custom_fields`/`show_footer` handling already in this function (booleans are coerced, not rejected);
- rejects (→ 400) a `custom_fields_layout` present but not in `ALLOWED_CUSTOM_FIELDS_LAYOUTS`, consistent with the existing `font_family`/`logo_*` enum handling (`.strip().lower()` then membership check).

The clamp in `build_config` remains the real safety net (defense in depth, matching Slices A/B).

**Storage:** all keys persist in the single flat `invoice_branding` Settings row. No migration; a missing key → its default.

### 2. View model — `api/core/services/invoice_render/view_model.py`

**No change.** `ItemVM` already carries `quantity` and `unit_of_measure` (and `unit_price`, `amount`). The Qty/UoM merge and column visibility are presentation concerns handled in the template.

### 3. Template — `api/core/services/invoice_render/templates/invoice/default.html`

Rework the `section_items` macro so the optional columns are conditional on `cfg.columns`, with Description and Amount unconditional. The header `<th>` set and each body `<td>` set are gated identically so columns stay aligned:

```jinja
{% macro section_items(vm, cfg) %}<table class="items"><thead><tr>
    <th>Description</th>
    {% if cfg.columns.quantity %}<th>Qty</th>{% endif %}
    {% if cfg.columns.unit_price %}<th>Price</th>{% endif %}
    <th>Amount</th></tr></thead>
  <tbody>{% for it in vm.items %}<tr>
    <td>{{ it.description }}</td>
    {% if cfg.columns.quantity %}<td>{{ it.quantity }}{% if cfg.columns.unit_of_measure and it.unit_of_measure %} {{ it.unit_of_measure }}{% endif %}</td>{% endif %}
    {% if cfg.columns.unit_price %}<td>{{ it.unit_price }}</td>{% endif %}
    <td>{{ it.amount }}</td></tr>{% endfor %}</tbody></table>{% endmacro %}
```

The existing `table.items th:nth-child(n+2)` right-align rule is positional and continues to right-align every column after Description regardless of which optional columns are present.

Rework `section_custom` to switch its wrapper class off the layout enum:

```jinja
{% macro section_custom(vm, cfg) %}{% if cfg.show.custom_fields and vm.custom_fields %}<section class="custom custom-{{ cfg.custom_fields_layout }}"><h3>Details</h3>
    {% for cf in vm.custom_fields %}<div class="cf"><span class="cf-label">{{ cf.label }}</span><span class="cf-value">{{ cf.value }}</span></div>{% endfor %}</section>{% endif %}{% endmacro %}
```

`cfg.custom_fields_layout` is clamped to `list`/`grid`, so only `custom-list` or `custom-grid` can ever be emitted as a class name (injection-safe).

### 4. CSS — `api/core/services/invoice_render/templates/invoice/default.css`

- `.custom-list .cf` keeps the current inline look (label and value on one line, e.g. `PO Number: PO-2026-0042`). Because the markup now uses two spans, `.custom-list .cf-label::after { content: ": "; }` reproduces the existing `label: value` rendering.
- `.custom-grid .cf` lays label/value out as an aligned two-column grid (e.g. `display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px;` per row, or a CSS grid on the section).

Default (`list`) output is visually equivalent to today.

### 5. Live preview — `api/core/routers/invoices/pdf_email.py`

Add the four new flat keys to `TemplatePreviewRequest` (else they are silently dropped from the editor's live preview, since the endpoint does `build_config(body.model_dump(exclude_none=True))`):

```python
show_col_quantity: Optional[bool] = None
show_col_unit_price: Optional[bool] = None
show_col_unit_of_measure: Optional[bool] = None
custom_fields_layout: Optional[str] = None
```

### 6. Frontend — `ui/src/components/settings/InvoiceSettingsTab.tsx`

- **Types** (`ui/src/lib/api/settings.ts`): add the four optional keys to `InvoiceBranding` and export `type CustomFieldsLayout = 'list' | 'grid'`.
- **Defaults / normalizer** (`ui/src/lib/invoice-branding.ts`): add the column/layout defaults to `DEFAULT_BRANDING` (`show_col_quantity: true`, `show_col_unit_price: true`, `show_col_unit_of_measure: false`, `custom_fields_layout: 'list'`) and a small `normalizeCustomFieldsLayout(v): CustomFieldsLayout` (non-`grid` → `'list'`), mirroring the backend clamp.
- **Editor block:** a new "Line items" group with three `Switch` rows (Quantity, Unit price, Show unit of measure) writing the flat `show_col_*` draft keys, and a "Details layout" segmented control / select (List / Grid) writing `custom_fields_layout`. The UoM switch may be visually disabled/greyed when Quantity is off (it has no effect then) — a nicety, not required for correctness since the template already guards on `cfg.columns.quantity`.
- The debounced (~300 ms) `POST /api/v1/invoices/template-preview` already depends on `branding`, so every toggle re-renders the live `<iframe srcDoc>` preview for free.
- i18n keys go into `ui/src/i18n/locales/en.json` (`fallbackLng: 'en'`).

### 7. Surfaces

No surface-specific work. `columns` and `custom_fields_layout` flow everywhere because all surfaces resolve config via `load_template_config(db)` → `build_config` → `default.html`. Web view, share link, PDF (`render_invoice_pdf` / `_async`), and email all inherit them.

## Testing

- **`build_config` clamp cases:** absent keys → defaults (`quantity`/`unit_price` true, `unit_of_measure` false, layout `list`); each `show_col_*` truthy/falsey coerced via `bool`; unknown `custom_fields_layout` → `list`.
- **`validate_invoice_branding`:** non-bool `show_col_*` raises; unknown `custom_fields_layout` raises; valid values pass through into cleaned output; absent keys omitted.
- **Render tests:**
  - default config → header still `Description / Qty / Price / Amount`, body matches pre-Slice-C (regression guard).
  - `columns.unit_price=False` → no `Price` `<th>` and no unit-price cell; Amount still present.
  - `columns.quantity=False` → no Qty column; UoM never appears even if `unit_of_measure=True`.
  - `unit_of_measure=True` with Qty on → an item with `unit_of_measure="hrs"` renders `10 hrs` in the qty cell; an item with empty UoM renders just the quantity.
  - `custom_fields_layout="grid"` → section has class `custom-grid`; default → `custom-list`; the enum value is never emitted outside those two class names.
- **Frontend:** `normalizeCustomFieldsLayout` cases; a vitest asserting the new control writes the correct draft keys (`show_col_*`, `custom_fields_layout`).

## C2 stub (future epic — not built in this slice)

Write `docs/todos/invoice-template-c2-named-templates-epic.md` capturing the named/multiple-templates direction so it is not lost:

- **Storage change:** move from the single flat `invoice_branding` row to N named templates — a new per-tenant `invoice_templates` table (or keyed settings collection) each holding a full branding/layout config blob, with one marked default. (Note: per repo convention, several per-tenant tables are created via `db_init.py`, not Alembic — decide schema-management approach in C2's own spec.)
- **Per-invoice selection:** add `template_id` to the invoice model; selector in the invoice create/edit UI; renderer resolves the invoice's template (fallback to tenant default).
- **CRUD UI:** template list / create / rename / duplicate / delete / set-default, reusing the existing two-pane editor for per-template editing.
- **Surfaces:** every render path resolves the invoice's `template_id` instead of the single tenant config.
- Needs its own brainstorm → spec → plan cycle; larger and higher-risk than A/B/C.

## Out of scope (this slice)

- Named / multiple templates and per-invoice selection (C2 — stub only).
- Reordering or restyling columns (only show/hide + UoM-merge).
- Adding new line-item data (tax-per-line, SKU, etc.).
- Visual polish of the default template typography/spacing.
