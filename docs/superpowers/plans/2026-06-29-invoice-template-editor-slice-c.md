# Invoice Template Editor — Slice C (Line-item Columns + Custom-field Layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let tenants choose which line-item columns appear (Quantity, Unit price, with unit-of-measure merged into the Qty cell) and whether the Details/custom-fields section renders as an inline list or an aligned grid; settings persist in the existing `invoice_branding` config and are honored by the renderer on every surface.

**Architecture:** Add a clamped `columns: Dict[str, bool]` (parallel to the existing `show` dict) and a `custom_fields_layout: str` enum to `InvoiceTemplateConfig` (validate-on-write + clamp-on-read, mirroring Slices A/B). The Jinja `section_items` macro renders optional `<th>`/`<td>` conditionally on `cfg.columns`; `section_custom` switches a wrapper CSS class off the layout enum. The editor gets a "Line items" toggle group and a "Details layout" select. Defaults reproduce today's output exactly.

**Tech Stack:** FastAPI / Jinja2 / WeasyPrint (backend); React + TypeScript + Vite (frontend); pytest + vitest.

## Global Constraints

- Config persists as flat keys in the single `invoice_branding` Settings row — **no DB migration**. New keys: `show_col_quantity`, `show_col_unit_price`, `show_col_unit_of_measure` (bools), `custom_fields_layout` (string). A missing key → its default.
- **Defaults preserve today's output exactly:** `show_col_quantity`=true, `show_col_unit_price`=true, `show_col_unit_of_measure`=false, `custom_fields_layout`="list".
- Allowed layout set: `("list", "grid")`. An out-of-set value must never reach the template as raw text — `custom_fields_layout` is emitted only as a CSS class `custom-{value}`, and only after clamping, so only `custom-list`/`custom-grid` can appear.
- The Qty+UoM merge only renders when **both** `cfg.columns.unit_of_measure` is true **and** `cfg.columns.quantity` is true (UoM has no cell otherwise) **and** the item's `unit_of_measure` is non-empty.
- `build_config()` stays pure (no DB) and clamps every value — a bad/stale value can never break a render.
- Any new branding field MUST be added to `TemplatePreviewRequest` (`api/core/routers/invoices/pdf_email.py`) or it is silently dropped from the editor's live preview (`build_config(body.model_dump(exclude_none=True))`).
- i18n: new UI strings go into `ui/src/i18n/locales/en.json` (project uses `fallbackLng: 'en'`, so en-only is sufficient).
- The `api` service is image-based: after backend changes run `docker compose build api && docker compose up -d api` before backend tests take effect.
- Backend tests run in-container: `docker compose exec api python -m pytest <path> -v` (pure-unit files can add `--noconftest`). Never run bare `pytest` (→ `ModuleNotFoundError: core`). Frontend: `docker compose exec ui npx vitest run <file>`.

---

### Task 1: Backend config — `columns` map + `custom_fields_layout` clamp

**Files:**
- Modify: `api/core/services/invoice_render/config.py`
- Test: `api/tests/test_invoice_template_config.py`

**Interfaces:**
- Produces: `ALLOWED_CUSTOM_FIELDS_LAYOUTS: tuple[str, ...]`, `_DEFAULT_COLUMNS: dict`, and `InvoiceTemplateConfig.columns: Dict[str, bool]` + `InvoiceTemplateConfig.custom_fields_layout: str`. `build_config(branding: dict)` now also returns a normalized `columns` and `custom_fields_layout`.

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/test_invoice_template_config.py`:

```python
from core.services.invoice_render.config import (
    build_config, InvoiceTemplateConfig, ALLOWED_CUSTOM_FIELDS_LAYOUTS,
)


def test_default_columns_and_layout_when_absent():
    c = build_config({})
    assert c.columns == {"quantity": True, "unit_price": True, "unit_of_measure": False}
    assert c.custom_fields_layout == "list"


def test_build_config_reads_column_flags():
    c = build_config({
        "show_col_quantity": False,
        "show_col_unit_price": True,
        "show_col_unit_of_measure": True,
    })
    assert c.columns == {"quantity": False, "unit_price": True, "unit_of_measure": True}


def test_build_config_coerces_column_flags_to_bool():
    c = build_config({"show_col_quantity": 0, "show_col_unit_of_measure": 1})
    assert c.columns["quantity"] is False
    assert c.columns["unit_of_measure"] is True
    assert c.columns["unit_price"] is True  # untouched default


def test_build_config_reads_valid_layout():
    assert build_config({"custom_fields_layout": "grid"}).custom_fields_layout == "grid"


def test_build_config_clamps_unknown_layout_to_list():
    assert build_config({"custom_fields_layout": "fancy"}).custom_fields_layout == "list"


def test_allowed_layouts_constant():
    assert ALLOWED_CUSTOM_FIELDS_LAYOUTS == ("list", "grid")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_template_config.py -v --noconftest`
Expected: FAIL — `ImportError: cannot import name 'ALLOWED_CUSTOM_FIELDS_LAYOUTS'`.

- [ ] **Step 3: Implement the config changes**

In `api/core/services/invoice_render/config.py`, add near the other `ALLOWED_*` tuples (after `DEFAULT_SECTION_ORDER`):

```python
ALLOWED_CUSTOM_FIELDS_LAYOUTS = ("list", "grid")
_DEFAULT_COLUMNS = {"quantity": True, "unit_price": True, "unit_of_measure": False}
```

Add the fields to the dataclass (after `section_order`):

```python
    columns: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_COLUMNS))
    custom_fields_layout: str = "list"
```

In `build_config`, before the `return InvoiceTemplateConfig(...)`, build the columns map (mirroring how `show` is built):

```python
    columns = dict(_DEFAULT_COLUMNS)
    for key in ("quantity", "unit_price", "unit_of_measure"):
        if f"show_col_{key}" in b:
            columns[key] = bool(b[f"show_col_{key}"])
```

Then add these two arguments to the `InvoiceTemplateConfig(...)` constructor call:

```python
        columns=columns,
        custom_fields_layout=_clamp(b.get("custom_fields_layout"), ALLOWED_CUSTOM_FIELDS_LAYOUTS, "list"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_template_config.py -v --noconftest`
Expected: PASS (all, including the pre-existing Slice A/B cases).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_render/config.py api/tests/test_invoice_template_config.py
git commit -m "feat(invoice-template): clamp line-item columns + custom_fields_layout in build_config"
```

---

### Task 2: Backend write-validation for the new keys

**Files:**
- Modify: `api/core/services/invoice_branding.py` (`validate_invoice_branding`, ~lines 61-103)
- Test: `api/tests/test_invoice_branding.py`

**Interfaces:**
- Consumes: `ALLOWED_CUSTOM_FIELDS_LAYOUTS` from Task 1.
- Produces: `validate_invoice_branding(value)` keeps `show_col_*` (coerced to bool, mirroring the sibling `show_notes`/`show_custom_fields`/`show_footer` handling) and a valid `custom_fields_layout` (allowed string) in its cleaned output; raises `ValueError` for an unknown `custom_fields_layout` (mirroring the `font_family`/`logo_*` enum handling).

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/test_invoice_branding.py`:

```python
import pytest
from core.services.invoice_branding import validate_invoice_branding


def test_validate_keeps_valid_column_flags():
    out = validate_invoice_branding({
        "show_col_quantity": True, "show_col_unit_price": False,
        "show_col_unit_of_measure": True,
    })
    assert out["show_col_quantity"] is True
    assert out["show_col_unit_price"] is False
    assert out["show_col_unit_of_measure"] is True


def test_validate_coerces_truthy_column_flag():
    # mirrors the existing show_notes/show_footer bool() coercion
    out = validate_invoice_branding({"show_col_quantity": 1, "show_col_unit_price": 0})
    assert out["show_col_quantity"] is True
    assert out["show_col_unit_price"] is False


def test_validate_keeps_valid_layout():
    assert validate_invoice_branding({"custom_fields_layout": "grid"})["custom_fields_layout"] == "grid"


def test_validate_column_keys_absent_are_omitted():
    out = validate_invoice_branding({"font_family": "serif"})
    assert "show_col_quantity" not in out
    assert "custom_fields_layout" not in out


def test_validate_rejects_unknown_layout():
    with pytest.raises(ValueError):
        validate_invoice_branding({"custom_fields_layout": "fancy"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_branding.py -k "column or layout" -v`
Expected: FAIL — keys not in cleaned output / no `ValueError` raised.

- [ ] **Step 3: Implement validation**

In `api/core/services/invoice_branding.py`, extend the existing import from the config module to include the layouts constant:

```python
from core.services.invoice_render.config import (
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES, ALLOWED_SECTIONS,
    ALLOWED_CUSTOM_FIELDS_LAYOUTS)
```

In `validate_invoice_branding`, before `return cleaned`, add (the `show_col_*` loop mirrors the existing `show_notes`/`show_custom_fields`/`show_footer` `bool()`-coercion loop; the layout check mirrors the existing `font_family`/`logo_*` enum loop, including `.strip().lower()`):

```python
    for col_key in ("show_col_quantity", "show_col_unit_price", "show_col_unit_of_measure"):
        if value.get(col_key) is not None:
            cleaned[col_key] = bool(value[col_key])

    if value.get("custom_fields_layout") is not None:
        layout = str(value["custom_fields_layout"]).strip().lower()
        if layout not in ALLOWED_CUSTOM_FIELDS_LAYOUTS:
            raise ValueError(
                f"custom_fields_layout must be one of: {', '.join(ALLOWED_CUSTOM_FIELDS_LAYOUTS)}"
            )
        cleaned["custom_fields_layout"] = layout
```

Rationale: booleans are coerced (not rejected) to stay consistent with the sibling `show_*` keys in this same function; only the `custom_fields_layout` enum is rejected on an unknown value, consistent with `font_family`/`logo_*`. The `build_config` clamp remains the defense-in-depth net.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_branding.py -v`
Expected: PASS (new cases plus the existing file).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_branding.py api/tests/test_invoice_branding.py
git commit -m "feat(invoice-template): validate column flags + custom_fields_layout on write"
```

---

### Task 3: Template — conditional columns + custom-field layout class

**Files:**
- Modify: `api/core/services/invoice_render/templates/invoice/default.html`
- Modify: `api/core/services/invoice_render/templates/invoice/default.css`
- Test: `api/tests/test_invoice_renderer.py`

**Interfaces:**
- Consumes: `cfg.columns` (`quantity`/`unit_price`/`unit_of_measure` bools) and `cfg.custom_fields_layout` (Task 1). `ItemVM.unit_of_measure` already exists on the view model.
- Produces: rendered HTML whose line-items table omits the Qty/Price `<th>`+`<td>` when the corresponding flag is false; merges `unit_of_measure` into the qty cell when enabled; and whose Details section carries class `custom-list` or `custom-grid`.

- [ ] **Step 1: Write the failing tests**

The file already imports `InvoiceTemplateConfig`, `render_invoice_html`, `assemble_view_model`, and (from `tests.test_invoice_view_model`) the `_data`/`CFG` helpers. `_data(**over)` merges keyword args over top-level data keys, so override line items via `items=[...]` and custom fields via `custom_fields={...}` — **no helper change is needed**. A `_data()` item is `{"description": "Work", "quantity": N, "unit_of_measure": "...", "unit_price": 50.0, "amount": 100.0}`.

Add to `api/tests/test_invoice_renderer.py`:

```python
_ITEM_HRS = [{"description": "Work", "quantity": 10, "unit_of_measure": "hrs",
              "unit_price": 50.0, "amount": 500.0}]


def test_default_columns_render_qty_and_price():
    cfg = InvoiceTemplateConfig()
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<th>Qty</th>" in html
    assert "<th>Price</th>" in html


def test_hiding_unit_price_column_drops_price_header_and_cells():
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": False, "unit_of_measure": False})
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<th>Price</th>" not in html
    assert "<th>Qty</th>" in html
    assert "<th>Amount</th>" in html  # always-on


def test_hiding_quantity_column_drops_qty_and_suppresses_uom():
    cfg = InvoiceTemplateConfig(columns={"quantity": False, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(items=_ITEM_HRS), cfg), cfg)
    assert "<th>Qty</th>" not in html
    assert "hrs" not in html  # UoM has no cell when Qty is hidden


def test_uom_merges_into_qty_cell_when_enabled():
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(items=_ITEM_HRS), cfg), cfg)
    assert "10 hrs" in html


def test_uom_absent_renders_bare_quantity():
    # default _data() item has unit_of_measure="" and quantity=2
    cfg = InvoiceTemplateConfig(columns={"quantity": True, "unit_price": True, "unit_of_measure": True})
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "<td>2</td>" in html  # bare quantity, no trailing UoM


def test_custom_fields_layout_emits_class():
    list_cfg = InvoiceTemplateConfig(custom_fields_layout="list")
    grid_cfg = InvoiceTemplateConfig(custom_fields_layout="grid")
    list_html = render_invoice_html(assemble_view_model(_data(custom_fields={"PO": "123"}), list_cfg), list_cfg)
    grid_html = render_invoice_html(assemble_view_model(_data(custom_fields={"PO": "123"}), grid_cfg), grid_cfg)
    assert 'class="custom custom-list"' in list_html
    assert 'class="custom custom-grid"' in grid_html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_renderer.py -v --noconftest`
Expected: FAIL — current template always emits Qty/Price and has no `custom-list`/`custom-grid` class.

- [ ] **Step 3: Rewrite the two macros**

In `api/core/services/invoice_render/templates/invoice/default.html`, replace the `section_custom` macro (line 6-7) with:

```jinja
{% macro section_custom(vm, cfg) %}{% if cfg.show.custom_fields and vm.custom_fields %}<section class="custom custom-{{ cfg.custom_fields_layout }}"><h3>Details</h3>
    {% for cf in vm.custom_fields %}<div class="cf"><span class="cf-label">{{ cf.label }}</span><span class="cf-value">{{ cf.value }}</span></div>{% endfor %}</section>{% endif %}{% endmacro %}
```

Replace the `section_items` macro (line 8-10) with:

```jinja
{% macro section_items(vm, cfg) %}<table class="items"><thead><tr><th>Description</th>{% if cfg.columns.quantity %}<th>Qty</th>{% endif %}{% if cfg.columns.unit_price %}<th>Price</th>{% endif %}<th>Amount</th></tr></thead>
    <tbody>{% for it in vm.items %}<tr><td>{{ it.description }}</td>{% if cfg.columns.quantity %}<td>{{ it.quantity }}{% if cfg.columns.unit_of_measure and it.unit_of_measure %} {{ it.unit_of_measure }}{% endif %}</td>{% endif %}{% if cfg.columns.unit_price %}<td>{{ it.unit_price }}</td>{% endif %}<td>{{ it.amount }}</td></tr>{% endfor %}</tbody></table>{% endmacro %}
```

- [ ] **Step 4: Update the CSS**

In `api/core/services/invoice_render/templates/invoice/default.css`, the existing rule (line 7) is:

```css
.billto, .custom, .notes { margin-top: 20px; } h3 { color: var(--brand); font-size: 13px; text-transform: uppercase; }
```

After that line, add custom-field layout rules. `custom-list` reproduces the old `label: value` inline rendering (the markup now uses two spans, so synthesize the colon); `custom-grid` aligns label/value in two columns:

```css
.custom-list .cf-label::after { content: ": "; }
.custom-grid { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; }
.custom-grid h3 { grid-column: 1 / -1; }
.custom-grid .cf { display: contents; }
.custom-grid .cf-label { font-weight: 600; }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_renderer.py tests/test_invoice_render_endpoints.py -v`
Expected: PASS — including pre-existing notes/discount/font/logo/section-order tests (regression guard) and the new column/layout tests.

- [ ] **Step 6: Commit**

```bash
git add api/core/services/invoice_render/templates/invoice/default.html api/core/services/invoice_render/templates/invoice/default.css api/tests/test_invoice_renderer.py
git commit -m "feat(invoice-template): conditional line-item columns + custom-field layout class"
```

---

### Task 4: Live-preview request model

**Files:**
- Modify: `api/core/routers/invoices/pdf_email.py:44-57` (`TemplatePreviewRequest`)
- Test: `api/tests/test_invoice_render_endpoints.py`

**Interfaces:**
- Consumes: nothing new (flat keys flow into `build_config` via `model_dump(exclude_none=True)`).
- Produces: `TemplatePreviewRequest` accepts `show_col_quantity`, `show_col_unit_price`, `show_col_unit_of_measure` (Optional[bool]) and `custom_fields_layout` (Optional[str]), so the live preview honors them.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/test_invoice_render_endpoints.py` (reuse the existing authenticated client + preview-endpoint pattern already in that file; mirror an existing `template-preview` test for the request shape and route path):

```python
def test_template_preview_honors_column_and_layout_keys(client, auth_headers):
    resp = client.post(
        "/api/v1/invoices/template-preview",
        json={"show_col_unit_price": False, "custom_fields_layout": "grid"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    html = resp.text
    assert "<th>Price</th>" not in html          # unit-price column hidden
    assert 'class="custom custom-grid"' in html  # grid layout applied
```

If the existing preview tests use different fixture names for the client/headers, match those names instead — do not introduce new fixtures.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/test_invoice_render_endpoints.py -k preview -v`
Expected: FAIL — `show_col_unit_price` / `custom_fields_layout` are dropped (not on the model), so `Price` header still present.

- [ ] **Step 3: Add the fields to the model**

In `api/core/routers/invoices/pdf_email.py`, add to `TemplatePreviewRequest` after `section_order` (line 57):

```python
    show_col_quantity: Optional[bool] = None
    show_col_unit_price: Optional[bool] = None
    show_col_unit_of_measure: Optional[bool] = None
    custom_fields_layout: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/test_invoice_render_endpoints.py -k preview -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/invoices/pdf_email.py api/tests/test_invoice_render_endpoints.py
git commit -m "feat(invoice-template): accept column + layout keys in template-preview"
```

---

### Task 5: Frontend types, defaults, and layout normalizer

**Files:**
- Modify: `ui/src/lib/api/settings.ts` (`InvoiceBranding` + a type export)
- Modify: `ui/src/lib/invoice-branding.ts` (`DEFAULT_BRANDING` + normalizer)
- Test: `ui/src/lib/invoice-branding.test.ts` (the file created in Slice B — add a describe block)

**Interfaces:**
- Produces: `CustomFieldsLayout` type, `InvoiceBranding.show_col_quantity?/show_col_unit_price?/show_col_unit_of_measure?: boolean` + `custom_fields_layout?: CustomFieldsLayout`, `DEFAULT_CUSTOM_FIELDS_LAYOUT`, and `normalizeCustomFieldsLayout(v: unknown): CustomFieldsLayout`.

- [ ] **Step 1: Write the failing test**

Add to `ui/src/lib/invoice-branding.test.ts`:

```ts
import { normalizeCustomFieldsLayout, DEFAULT_CUSTOM_FIELDS_LAYOUT } from './invoice-branding';

describe('normalizeCustomFieldsLayout', () => {
  it('keeps a valid layout', () => {
    expect(normalizeCustomFieldsLayout('grid')).toBe('grid');
    expect(normalizeCustomFieldsLayout('list')).toBe('list');
  });

  it('falls back to list for anything else', () => {
    expect(normalizeCustomFieldsLayout('fancy')).toBe('list');
    expect(normalizeCustomFieldsLayout(undefined)).toBe('list');
    expect(normalizeCustomFieldsLayout(42)).toBe('list');
  });

  it('default constant is list', () => {
    expect(DEFAULT_CUSTOM_FIELDS_LAYOUT).toBe('list');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: FAIL — `normalizeCustomFieldsLayout` is not exported.

- [ ] **Step 3: Implement types + normalizer + defaults**

In `ui/src/lib/api/settings.ts`, add to the `InvoiceBranding` interface (after `section_order`):

```ts
  show_col_quantity?: boolean;
  show_col_unit_price?: boolean;
  show_col_unit_of_measure?: boolean;
  custom_fields_layout?: CustomFieldsLayout;
```

And add the type export near the other type exports (e.g. next to `SectionId`):

```ts
export type CustomFieldsLayout = 'list' | 'grid';
```

In `ui/src/lib/invoice-branding.ts`, update the import to include the new type and add the helper + default const (place the const above `DEFAULT_BRANDING` so it is defined first):

```ts
import type {
  InvoiceBranding, InvoiceFont, LogoPlacement, LogoSize, SectionId, CustomFieldsLayout,
} from '@/lib/api/settings';

export const CUSTOM_FIELDS_LAYOUTS: CustomFieldsLayout[] = ['list', 'grid'];
export const DEFAULT_CUSTOM_FIELDS_LAYOUT: CustomFieldsLayout = 'list';

/** Mirror of the backend clamp: a value outside the allowed set → 'list'. */
export function normalizeCustomFieldsLayout(value: unknown): CustomFieldsLayout {
  return value === 'grid' ? 'grid' : 'list';
}
```

Add the column/layout defaults to the `DEFAULT_BRANDING` object (after `section_order`):

```ts
  show_col_quantity: true,
  show_col_unit_price: true,
  show_col_unit_of_measure: false,
  custom_fields_layout: 'list',
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: PASS (new block plus the Slice B `normalizeSectionOrder` cases).

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/api/settings.ts ui/src/lib/invoice-branding.ts ui/src/lib/invoice-branding.test.ts
git commit -m "feat(invoice-template): column flags + custom_fields_layout type/normalizer (frontend)"
```

---

### Task 6: Line-items controls UI + i18n

**Files:**
- Modify: `ui/src/components/settings/InvoiceSettingsTab.tsx`
- Modify: `ui/src/i18n/locales/en.json`

**Interfaces:**
- Consumes: `CustomFieldsLayout`, `normalizeCustomFieldsLayout` (Task 5); `branding` + `setBranding` (existing tab state); the existing `Switch`, `Label`, and `Select` (or equivalent) components already imported in this file.
- Produces: a "Line items" control group (3 `Switch`es writing `show_col_*`) and a "Details layout" select writing `custom_fields_layout`, all mutating the draft `branding` so the existing debounced preview re-renders.

- [ ] **Step 1: Add the controls**

In `ui/src/components/settings/InvoiceSettingsTab.tsx`, add the import alongside the other branding imports:

```tsx
import { normalizeCustomFieldsLayout, CUSTOM_FIELDS_LAYOUTS } from "@/lib/invoice-branding";
import type { CustomFieldsLayout } from "@/lib/api/settings";
```

Insert a new control block immediately after the existing `SectionOrderEditor` block (Slice B) and before the footer-visibility block. Use the same wrapper styling as the neighboring blocks (`<div className="p-4 bg-muted/30 rounded-xl space-y-3">`):

```tsx
                            {/* Line-item columns */}
                            <div className="p-4 bg-muted/30 rounded-xl space-y-3">
                                <Label className="text-sm font-semibold">{t('settings.branding.columns')}</Label>
                                <p className="text-xs text-muted-foreground">{t('settings.branding.columns_hint')}</p>
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="show_col_quantity">{t('settings.branding.col_quantity')}</Label>
                                    <Switch id="show_col_quantity" checked={branding.show_col_quantity !== false}
                                        onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_col_quantity: checked }))} />
                                </div>
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="show_col_unit_price">{t('settings.branding.col_unit_price')}</Label>
                                    <Switch id="show_col_unit_price" checked={branding.show_col_unit_price !== false}
                                        onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_col_unit_price: checked }))} />
                                </div>
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="show_col_unit_of_measure">{t('settings.branding.col_unit_of_measure')}</Label>
                                    <Switch id="show_col_unit_of_measure"
                                        checked={!!branding.show_col_unit_of_measure}
                                        disabled={branding.show_col_quantity === false}
                                        onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_col_unit_of_measure: checked }))} />
                                </div>
                            </div>

                            {/* Custom-field (Details) layout */}
                            <div className="p-4 bg-muted/30 rounded-xl space-y-3">
                                <Label className="text-sm font-semibold">{t('settings.branding.custom_fields_layout')}</Label>
                                <div className="flex gap-2">
                                    {CUSTOM_FIELDS_LAYOUTS.map((layout) => (
                                        <button key={layout} type="button"
                                            onClick={() => setBranding((prev) => ({ ...prev, custom_fields_layout: layout as CustomFieldsLayout }))}
                                            className={`flex-1 rounded-lg border px-3 py-2 text-sm ${
                                                normalizeCustomFieldsLayout(branding.custom_fields_layout) === layout
                                                    ? 'border-primary bg-primary/10 text-primary'
                                                    : 'border-input text-muted-foreground'
                                            }`}>
                                            {t(`settings.branding.layout_${layout}`)}
                                        </button>
                                    ))}
                                </div>
                            </div>
```

(If `InvoiceSettingsTab.tsx` already imports a ShadCN `Select`/segmented component used elsewhere in the file, prefer that over the inline buttons for visual consistency; the inline button-group above is the dependency-free fallback. Either way the behavior — writing `custom_fields_layout` to the draft — is identical.)

- [ ] **Step 2: Add i18n keys**

In `ui/src/i18n/locales/en.json`, under the existing `settings.branding` object, add:

```json
"columns": "Line item columns",
"columns_hint": "Choose which optional columns appear in the line-items table.",
"col_quantity": "Quantity",
"col_unit_price": "Unit price",
"col_unit_of_measure": "Show unit of measure (e.g. \"hrs\")",
"custom_fields_layout": "Details layout",
"layout_list": "List",
"layout_grid": "Grid"
```

- [ ] **Step 3: Typecheck the changed files**

Run (real typecheck — plain `npx tsc --noEmit` checks nothing here):
`docker compose exec ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "InvoiceSettingsTab|invoice-branding|settings.ts"`
Expected: no output (no new errors from the changed files; the repo has ~1800 pre-existing errors elsewhere — ignore those).

- [ ] **Step 4: Run the frontend unit tests**

Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: PASS.

- [ ] **Step 5: Manual smoke (record outcome)**

Rebuild/restart if needed (`docker compose build api && docker compose up -d api`), then open Settings → Invoice template. Confirm: the "Line item columns" switches hide/show the Qty and Price columns in the live preview within ~300 ms; toggling "Show unit of measure" makes the first sample item read `10 hrs`; the UoM switch greys out when Quantity is off; the Details layout List/Grid buttons switch the custom-fields rendering; Save persists; reload restores. Note the result in the PR description.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/settings/InvoiceSettingsTab.tsx ui/src/i18n/locales/en.json
git commit -m "feat(invoice-template): line-item column toggles + details layout control"
```

---

### Task 7: C2 stub epic doc

**Files:**
- Create: `docs/todos/invoice-template-c2-named-templates-epic.md`
- Modify: `docs/todos/invoice-template-editor-slices.md` (mark C1 shipped, point C2 at the epic)

**Interfaces:** none (documentation only).

- [ ] **Step 1: Write the C2 epic stub**

Create `docs/todos/invoice-template-c2-named-templates-epic.md` capturing the named/multiple-templates direction (storage move to an `invoice_templates` table or keyed settings collection with one default; per-invoice `template_id`; template CRUD/selector UI reusing the two-pane editor; every render path resolving the invoice's template; note that several per-tenant tables are created via `db_init.py` not Alembic, so the schema-management approach is a C2 spec decision; flag it needs its own brainstorm→spec→plan cycle). Pull the content from the "C2 stub" section of the Slice C design doc (`docs/superpowers/specs/2026-06-29-invoice-template-editor-slice-c-design.md`).

- [ ] **Step 2: Update the slices TODO**

In `docs/todos/invoice-template-editor-slices.md`, update the Slice C section: mark **C1 shipped** (this slice — line-item columns + custom-field layout) and repoint **C2** to the new epic doc as the future direction.

- [ ] **Step 3: Commit**

```bash
git add docs/todos/invoice-template-c2-named-templates-epic.md docs/todos/invoice-template-editor-slices.md
git commit -m "docs(invoice-template): C1 shipped; C2 named-templates epic stub"
```

---

## Self-Review

**Spec coverage:**
- Config `columns` map + `custom_fields_layout` clamp (defaults preserve output, bool coercion, unknown-layout→list) → Task 1. ✓
- Write handling: `show_col_*` coerced via `bool()` (sibling-consistent), `custom_fields_layout` rejected → 400 on unknown value → Task 2. ✓
- Template conditional columns, Qty+UoM merge (guarded on quantity column + non-empty UoM), `custom-{layout}` class; CSS for list/grid → Task 3. ✓
- `TemplatePreviewRequest` gains the 4 keys so live preview honors them → Task 4. ✓
- Frontend types/defaults/normalizer → Task 5; controls UI + i18n → Task 6. ✓
- All surfaces inherit via `load_template_config` → no surface-specific work (every surface resolves config through `build_config` → `default.html`). ✓
- Defaults render identically to today, guarded by `test_default_columns_render_qty_and_price` + existing regression tests → Task 3. ✓
- C2 captured as a stub epic, not built → Task 7. ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete content. Task 3/4 note where to reuse existing test helpers/fixtures rather than inventing names.

**Type consistency:** `_DEFAULT_COLUMNS`/`ALLOWED_CUSTOM_FIELDS_LAYOUTS` (Task 1) reused in Task 2; flat keys `show_col_quantity`/`show_col_unit_price`/`show_col_unit_of_measure` + `custom_fields_layout` consistent across config (Task 1), validation (Task 2), template (Task 3), preview model (Task 4), and frontend (Tasks 5-6); `CustomFieldsLayout`/`normalizeCustomFieldsLayout`/`DEFAULT_CUSTOM_FIELDS_LAYOUT` (Task 5) reused in Task 6; CSS classes `cf`/`cf-label`/`cf-value`/`custom-list`/`custom-grid` consistent between template (Task 3 Step 3) and CSS (Task 3 Step 4).
