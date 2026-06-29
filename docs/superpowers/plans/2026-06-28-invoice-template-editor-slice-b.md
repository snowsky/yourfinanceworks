# Invoice Template Editor — Slice B (Section Reordering) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let tenants drag-reorder the 5 body sections of their invoice template (Bill To, Details, Line items, Totals, Notes); the order persists in the existing `invoice_branding` config and is honored by the renderer on every surface.

**Architecture:** Add a clamped `section_order: list[str]` to `InvoiceTemplateConfig` (validate-on-write + clamp-on-read, mirroring Slice A). The Jinja template renders body sections through a macro-dispatch loop driven by `section_order` (header pinned top, footer pinned bottom). The editor gets a `@dnd-kit/sortable` list with inline show toggles for the two hideable sections.

**Tech Stack:** FastAPI / Jinja2 / WeasyPrint (backend); React + TypeScript + Vite + `@dnd-kit` (frontend); pytest + vitest.

## Global Constraints

- Section ids are validated against the fixed allowed-set `("billto", "custom", "items", "totals", "notes")` — an id outside this set must never reach the template (injection-safe; ids map to macros via explicit `if`/`elif`, never interpolated as HTML).
- `build_config()` stays pure (no DB) and clamps every value — a bad/stale `section_order` (non-list, unknown id, dupes, missing section) can never break a render.
- No DB migration: `section_order` persists as a JSON list inside the existing flat `invoice_branding` Settings row; a missing key → default order.
- Default order = `["billto", "custom", "items", "totals", "notes"]` (the current top-to-bottom layout).
- `@dnd-kit/core@^6.3.1`, `@dnd-kit/sortable@^10.0.0`, `@dnd-kit/utilities@^3.2.2` are already dependencies — do NOT add a new dnd library.
- i18n: new UI strings go into `ui/src/i18n/locales/en.json` (project uses `fallbackLng: 'en'`, so en-only is sufficient).
- Backend tests run in-container: `docker compose exec api python -m pytest <path> -v` (pure-unit files can use `--noconftest`). Never run bare `pytest` (→ `ModuleNotFoundError: core`).

---

### Task 1: Backend config — `section_order` field + clamp

**Files:**
- Modify: `api/core/services/invoice_render/config.py`
- Test: `api/tests/test_invoice_template_config.py`

**Interfaces:**
- Produces: `ALLOWED_SECTIONS: tuple[str, ...]`, `DEFAULT_SECTION_ORDER: list[str]`, and `InvoiceTemplateConfig.section_order: list[str]`. `build_config(branding: dict) -> InvoiceTemplateConfig` now also returns a normalized `section_order`.

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/test_invoice_template_config.py`:

```python
from core.services.invoice_render.config import (
    build_config, InvoiceTemplateConfig,
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES,
    ALLOWED_SECTIONS, DEFAULT_SECTION_ORDER,
)


def test_section_order_allowed_set_and_default():
    assert ALLOWED_SECTIONS == ("billto", "custom", "items", "totals", "notes")
    assert DEFAULT_SECTION_ORDER == ["billto", "custom", "items", "totals", "notes"]


def test_build_config_default_section_order_when_absent():
    assert build_config({}).section_order == DEFAULT_SECTION_ORDER


def test_build_config_reads_valid_section_order():
    order = ["notes", "totals", "items", "custom", "billto"]
    assert build_config({"section_order": order}).section_order == order


def test_build_config_drops_unknown_section_ids():
    c = build_config({"section_order": ["notes", "bogus", "items"]})
    # unknown dropped, then missing appended in canonical order
    assert c.section_order == ["notes", "items", "billto", "custom", "totals"]


def test_build_config_dedupes_section_order():
    c = build_config({"section_order": ["items", "items", "billto"]})
    assert c.section_order == ["items", "billto", "custom", "totals", "notes"]


def test_build_config_appends_missing_sections():
    c = build_config({"section_order": ["totals"]})
    assert c.section_order == ["totals", "billto", "custom", "items", "notes"]


def test_build_config_section_order_non_list_falls_back_to_default():
    assert build_config({"section_order": "items,billto"}).section_order == DEFAULT_SECTION_ORDER
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_template_config.py -v --noconftest`
Expected: FAIL — `ImportError: cannot import name 'ALLOWED_SECTIONS'`.

- [ ] **Step 3: Implement the config changes**

In `api/core/services/invoice_render/config.py`, add the allowed-set + default near the other `ALLOWED_*` tuples:

```python
ALLOWED_SECTIONS = ("billto", "custom", "items", "totals", "notes")
DEFAULT_SECTION_ORDER = list(ALLOWED_SECTIONS)
```

Add the field to the dataclass (after `logo_size`):

```python
    section_order: list = field(default_factory=lambda: list(DEFAULT_SECTION_ORDER))
```

Add a pure normalizer above `build_config`:

```python
def _clamp_section_order(value) -> list:
    """Drop unknown ids, de-dupe (first wins), append any missing sections in
    canonical order. A non-list value falls back to the default order."""
    if not isinstance(value, list):
        return list(DEFAULT_SECTION_ORDER)
    seen = []
    for sid in value:
        if sid in ALLOWED_SECTIONS and sid not in seen:
            seen.append(sid)
    for sid in DEFAULT_SECTION_ORDER:
        if sid not in seen:
            seen.append(sid)
    return seen
```

In `build_config`, add `section_order=_clamp_section_order(b.get("section_order"))` to the `InvoiceTemplateConfig(...)` constructor call.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_template_config.py -v --noconftest`
Expected: PASS (all, including the pre-existing cases).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_render/config.py api/tests/test_invoice_template_config.py
git commit -m "feat(invoice-template): clamp section_order in build_config"
```

---

### Task 2: Backend write-validation for `section_order`

**Files:**
- Modify: `api/core/services/invoice_branding.py:61-103` (`validate_invoice_branding`)
- Test: `api/tests/test_invoice_branding.py`

**Interfaces:**
- Consumes: `ALLOWED_SECTIONS` from Task 1.
- Produces: `validate_invoice_branding(value)` keeps a valid `section_order` (list of allowed-id strings) in its cleaned output and raises `ValueError` for a non-list or a list containing a non-string / unknown id.

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/test_invoice_branding.py`:

```python
import pytest
from core.services.invoice_branding import validate_invoice_branding


def test_validate_keeps_valid_section_order():
    out = validate_invoice_branding({"section_order": ["notes", "items", "billto", "custom", "totals"]})
    assert out["section_order"] == ["notes", "items", "billto", "custom", "totals"]


def test_validate_section_order_absent_is_omitted():
    assert "section_order" not in validate_invoice_branding({"font_family": "serif"})


def test_validate_rejects_non_list_section_order():
    with pytest.raises(ValueError):
        validate_invoice_branding({"section_order": "items,billto"})


def test_validate_rejects_unknown_section_id():
    with pytest.raises(ValueError):
        validate_invoice_branding({"section_order": ["items", "bogus"]})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_branding.py -k section_order -v`
Expected: FAIL — `section_order` not in cleaned output / no `ValueError` raised.

- [ ] **Step 3: Implement validation**

In `api/core/services/invoice_branding.py`, import the allowed-set at the top alongside the existing import:

```python
from core.services.invoice_render.config import (
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES, ALLOWED_SECTIONS)
```

In `validate_invoice_branding`, before `return cleaned`, add:

```python
    if value.get("section_order") is not None:
        order = value["section_order"]
        if not isinstance(order, list) or any(
            not isinstance(sid, str) or sid not in ALLOWED_SECTIONS for sid in order
        ):
            raise ValueError(
                f"section_order must be a list of: {', '.join(ALLOWED_SECTIONS)}"
            )
        cleaned["section_order"] = list(order)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_branding.py -v`
Expected: PASS (new cases plus the existing file).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_branding.py api/tests/test_invoice_branding.py
git commit -m "feat(invoice-template): validate section_order on write"
```

---

### Task 3: Template macro-dispatch rendering

**Files:**
- Modify: `api/core/services/invoice_render/templates/invoice/default.html`
- Test: `api/tests/test_invoice_renderer.py`

**Interfaces:**
- Consumes: `cfg.section_order` (Task 1). Each section's existing `cfg.show.*` guard moves inside its macro, so visibility and order compose independently.
- Produces: rendered HTML whose body sections appear in `cfg.section_order` order; header (`class="head"`) stays first, `<footer class="foot">` stays last.

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/test_invoice_renderer.py`:

```python
def test_default_order_renders_all_sections_in_order():
    html = render_invoice_html(assemble_view_model(_data(notes="HELLO"), CFG), CFG)
    # billto before items before totals
    assert html.index('class="billto"') < html.index('class="items"') < html.index('class="totals"')


def test_section_order_reorders_body():
    cfg = InvoiceTemplateConfig(section_order=["notes", "totals", "items", "custom", "billto"])
    html = render_invoice_html(assemble_view_model(_data(notes="HELLO"), cfg), cfg)
    assert html.index('class="notes"') < html.index('class="totals"') < html.index('class="billto"')


def test_section_order_independent_of_visibility():
    cfg = InvoiceTemplateConfig(
        section_order=["notes", "billto", "items", "totals", "custom"],
        show={"logo": True, "notes": False, "custom_fields": True, "footer": True},
    )
    html = render_invoice_html(assemble_view_model(_data(notes="SECRET"), cfg), cfg)
    assert "SECRET" not in html  # notes still hidden despite being first in order
    assert html.index('class="billto"') < html.index('class="items"')
```

Add the import at the top of the file if not present: `from core.services.invoice_render.config import InvoiceTemplateConfig` (already imported).

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest tests/test_invoice_renderer.py -v --noconftest`
Expected: `test_section_order_reorders_body` FAILS (current template ignores `section_order`).

- [ ] **Step 3: Rewrite the template**

Replace the entire contents of `api/core/services/invoice_render/templates/invoice/default.html` with:

```jinja
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{{ css }}</style></head>
<body>
{% macro section_billto(vm, cfg) %}<section class="billto"><h3>Bill To</h3><div>{{ vm.client.name }}</div>
    <div>{{ vm.client.email }}</div><div>{{ vm.client.address }}</div></section>{% endmacro %}
{% macro section_custom(vm, cfg) %}{% if cfg.show.custom_fields and vm.custom_fields %}<section class="custom"><h3>Details</h3>
    {% for cf in vm.custom_fields %}<div>{{ cf.label }}: {{ cf.value }}</div>{% endfor %}</section>{% endif %}{% endmacro %}
{% macro section_items(vm, cfg) %}<table class="items"><thead><tr><th>Description</th><th>Qty</th><th>Price</th><th>Amount</th></tr></thead>
    <tbody>{% for it in vm.items %}<tr><td>{{ it.description }}</td><td>{{ it.quantity }}</td>
      <td>{{ it.unit_price }}</td><td>{{ it.amount }}</td></tr>{% endfor %}</tbody></table>{% endmacro %}
{% macro section_totals(vm, cfg) %}<section class="totals">
    <div><span>Subtotal</span><span>{{ vm.totals.subtotal }}</span></div>
    {% if vm.meta.show_discount and vm.totals.discount_amount_raw %}
      <div><span>Discount</span><span>-{{ vm.totals.discount_amount }}</span></div>{% endif %}
    <div class="grand"><span>Total</span><span>{{ vm.totals.total }}</span></div>
    <div><span>Paid</span><span>{{ vm.totals.paid }}</span></div>
    <div class="balance"><span>Balance Due</span><span>{{ vm.totals.balance }}</span></div>
  </section>{% endmacro %}
{% macro section_notes(vm, cfg) %}{% if cfg.show.notes and vm.notes %}<section class="notes"><h3>Notes</h3><div>{{ vm.notes }}</div></section>{% endif %}{% endmacro %}
{% macro render_section(sid, vm, cfg) %}{% if sid == 'billto' %}{{ section_billto(vm, cfg) }}{% elif sid == 'custom' %}{{ section_custom(vm, cfg) }}{% elif sid == 'items' %}{{ section_items(vm, cfg) }}{% elif sid == 'totals' %}{{ section_totals(vm, cfg) }}{% elif sid == 'notes' %}{{ section_notes(vm, cfg) }}{% endif %}{% endmacro %}
<div class="invoice font-{{ cfg.font_family }}" style="--brand: {{ cfg.brand_color }}; --accent: {{ cfg.accent_color }};">
  <header class="head">
    {% if cfg.show.logo and vm.company.logo_url %}<img class="logo logo-{{ cfg.logo_placement }} logo-{{ cfg.logo_size }}" src="{{ vm.company.logo_url }}">{% endif %}
    <div class="company">
      <h1>{{ vm.company.name }}</h1>
      <div>{{ vm.company.address }}</div><div>{{ vm.company.email }} {{ vm.company.phone }}</div>
      {% if vm.company.tax_id %}<div>Tax ID: {{ vm.company.tax_id }}</div>{% endif %}
    </div>
    <div class="meta">
      <h2>INVOICE</h2>
      <div>#{{ vm.meta.number }}</div><div>Date: {{ vm.meta.issue_date }}</div>
      <div>Due: {{ vm.meta.due_date }}</div><div class="status">{{ vm.meta.status }}</div>
    </div>
  </header>

  {% for sid in cfg.section_order %}{{ render_section(sid, vm, cfg) }}{% endfor %}

  {% if cfg.show.footer and vm.footer_text %}<footer class="foot">{{ vm.footer_text }}</footer>{% endif %}
</div>
</body></html>
```

Note: macro expansion may introduce harmless extra whitespace versus the old fixed layout — that is why the tests assert section **order and presence** (substring index), not byte-equality.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest tests/test_invoice_renderer.py tests/test_invoice_render_endpoints.py -v`
Expected: PASS — including the pre-existing notes/discount/font/logo tests (regression guard) and the new ordering tests.

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_render/templates/invoice/default.html api/tests/test_invoice_renderer.py
git commit -m "feat(invoice-template): render body sections via section_order loop"
```

---

### Task 4: Frontend types, defaults, and order normalizer

**Files:**
- Modify: `ui/src/lib/api/settings.ts:31-42` (`InvoiceBranding`)
- Modify: `ui/src/lib/invoice-branding.ts`
- Test: `ui/src/lib/invoice-branding.test.ts` (create)

**Interfaces:**
- Produces: `SECTION_IDS`, `SectionId`, `DEFAULT_SECTION_ORDER`, `normalizeSectionOrder(order: unknown): SectionId[]` (mirrors the backend clamp), and `InvoiceBranding.section_order?: SectionId[]`.

- [ ] **Step 1: Write the failing test**

Create `ui/src/lib/invoice-branding.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { normalizeSectionOrder, DEFAULT_SECTION_ORDER } from './invoice-branding';

describe('normalizeSectionOrder', () => {
  it('returns the default order for a non-array', () => {
    expect(normalizeSectionOrder(undefined)).toEqual(DEFAULT_SECTION_ORDER);
    expect(normalizeSectionOrder('items,billto')).toEqual(DEFAULT_SECTION_ORDER);
  });

  it('keeps a valid full order as-is', () => {
    const order = ['notes', 'totals', 'items', 'custom', 'billto'];
    expect(normalizeSectionOrder(order)).toEqual(order);
  });

  it('drops unknown ids then appends missing in canonical order', () => {
    expect(normalizeSectionOrder(['notes', 'bogus', 'items'])).toEqual([
      'notes', 'items', 'billto', 'custom', 'totals',
    ]);
  });

  it('de-dupes keeping first occurrence', () => {
    expect(normalizeSectionOrder(['items', 'items', 'billto'])).toEqual([
      'items', 'billto', 'custom', 'totals', 'notes',
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: FAIL — `normalizeSectionOrder` is not exported.

- [ ] **Step 3: Implement types + normalizer**

In `ui/src/lib/api/settings.ts`, add to the `InvoiceBranding` interface (after `show_footer`):

```ts
  section_order?: SectionId[];
```

And add the export near the other type exports in that file:

```ts
export type SectionId = 'billto' | 'custom' | 'items' | 'totals' | 'notes';
```

In `ui/src/lib/invoice-branding.ts`, update the import and add the helper + default:

```ts
import type { InvoiceBranding, InvoiceFont, LogoPlacement, LogoSize, SectionId } from '@/lib/api/settings';

export const SECTION_IDS: SectionId[] = ['billto', 'custom', 'items', 'totals', 'notes'];
export const DEFAULT_SECTION_ORDER: SectionId[] = [...SECTION_IDS];

/** Mirror of the backend clamp: drop unknown ids, de-dupe (first wins),
 *  append missing sections in canonical order; non-array → default order. */
export function normalizeSectionOrder(order: unknown): SectionId[] {
  if (!Array.isArray(order)) return [...DEFAULT_SECTION_ORDER];
  const allowed = new Set<string>(SECTION_IDS);
  const seen: SectionId[] = [];
  for (const id of order) {
    if (typeof id === 'string' && allowed.has(id) && !seen.includes(id as SectionId)) {
      seen.push(id as SectionId);
    }
  }
  for (const id of SECTION_IDS) {
    if (!seen.includes(id)) seen.push(id);
  }
  return seen;
}
```

Add `section_order: [...DEFAULT_SECTION_ORDER]` to the `DEFAULT_BRANDING` object (after `show_footer`). Reference `DEFAULT_SECTION_ORDER` before `DEFAULT_BRANDING` so it is defined first (move the `SECTION_IDS`/`DEFAULT_SECTION_ORDER` consts above the `DEFAULT_BRANDING` declaration).

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/lib/api/settings.ts ui/src/lib/invoice-branding.ts ui/src/lib/invoice-branding.test.ts
git commit -m "feat(invoice-template): section_order type + normalizer (frontend)"
```

---

### Task 5: Section-order editor UI + i18n

**Files:**
- Create: `ui/src/components/settings/SectionOrderEditor.tsx`
- Modify: `ui/src/components/settings/InvoiceSettingsTab.tsx:438-455` (replace the section-visibility block)
- Modify: `ui/src/i18n/locales/en.json`

**Interfaces:**
- Consumes: `SectionId`, `normalizeSectionOrder` (Task 4); `branding.section_order` and `setBranding` (existing tab state).
- Produces: `SectionOrderEditor` — a drag-reorder list of all 5 sections with inline eye toggles for `custom` (`show_custom_fields`) and `notes` (`show_notes`).

- [ ] **Step 1: Create the component**

Create `ui/src/components/settings/SectionOrderEditor.tsx`:

```tsx
import React from 'react';
import { GripVertical, Eye, EyeOff } from 'lucide-react';
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  verticalListSortingStrategy, useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import { SectionId, normalizeSectionOrder } from '@/lib/invoice-branding';

type ToggleKey = 'show_custom_fields' | 'show_notes';

interface SectionOrderEditorProps {
  order: SectionId[] | undefined;
  onOrderChange: (order: SectionId[]) => void;
  showCustomFields: boolean;
  showNotes: boolean;
  onToggle: (key: ToggleKey, value: boolean) => void;
}

const SECTION_LABELS: Record<SectionId, string> = {
  billto: 'settings.branding.section_billto',
  custom: 'settings.branding.section_custom_fields',
  items: 'settings.branding.section_items',
  totals: 'settings.branding.section_totals',
  notes: 'settings.branding.section_notes',
};

const TOGGLEABLE: Partial<Record<SectionId, ToggleKey>> = {
  custom: 'show_custom_fields',
  notes: 'show_notes',
};

function SortableRow({ id, label, toggle }: { id: SectionId; label: string; toggle?: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div ref={setNodeRef} style={style}
      className="flex items-center justify-between gap-2 p-2 bg-background rounded-lg border border-input">
      <div className="flex items-center gap-2">
        <button type="button" className="cursor-grab text-muted-foreground touch-none"
          aria-label="drag" {...attributes} {...listeners}>
          <GripVertical className="h-4 w-4" />
        </button>
        <span className="text-sm">{label}</span>
      </div>
      {toggle}
    </div>
  );
}

export function SectionOrderEditor({
  order, onOrderChange, showCustomFields, showNotes, onToggle,
}: SectionOrderEditorProps) {
  const { t } = useTranslation();
  const items = normalizeSectionOrder(order);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = items.indexOf(active.id as SectionId);
      const newIndex = items.indexOf(over.id as SectionId);
      onOrderChange(arrayMove(items, oldIndex, newIndex));
    }
  };

  const toggleFor = (id: SectionId): React.ReactNode => {
    const key = TOGGLEABLE[id];
    if (!key) return null;
    const checked = key === 'show_custom_fields' ? showCustomFields : showNotes;
    return (
      <button type="button" onClick={() => onToggle(key, !checked)}
        aria-label={t(checked ? 'settings.branding.hide_section' : 'settings.branding.show_section')}
        className="text-muted-foreground hover:text-foreground">
        {checked ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
      </button>
    );
  };

  return (
    <div className="p-4 bg-muted/30 rounded-xl space-y-2">
      <Label className="text-sm font-semibold">{t('settings.branding.section_order')}</Label>
      <p className="text-xs text-muted-foreground">{t('settings.branding.section_order_hint')}</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {items.map((id) => (
              <SortableRow key={id} id={id} label={t(SECTION_LABELS[id])} toggle={toggleFor(id)} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
```

- [ ] **Step 2: Wire it into `InvoiceSettingsTab.tsx`**

Add the import alongside the other settings imports (top of file):

```tsx
import { SectionOrderEditor } from "@/components/settings/SectionOrderEditor";
import { SectionId } from "@/lib/invoice-branding";
```

Replace the entire "Section visibility" block (`api/...` no — `ui/src/components/settings/InvoiceSettingsTab.tsx` lines 438-455, the `<div className="p-4 bg-muted/30 rounded-xl space-y-3">` … `</div>` that maps `show_custom_fields`/`show_notes`/`show_footer`) with:

```tsx
                            {/* Section order + per-section visibility */}
                            <SectionOrderEditor
                                order={branding.section_order as SectionId[] | undefined}
                                onOrderChange={(order) => setBranding((prev) => ({ ...prev, section_order: order }))}
                                showCustomFields={!!branding.show_custom_fields}
                                showNotes={!!branding.show_notes}
                                onToggle={(key, value) => setBranding((prev) => ({ ...prev, [key]: value }))}
                            />

                            {/* Footer visibility (footer is pinned at the bottom, not reorderable) */}
                            <div className="p-4 bg-muted/30 rounded-xl flex items-center justify-between">
                                <Label htmlFor="show_footer">{t('settings.branding.section_footer')}</Label>
                                <Switch
                                    id="show_footer"
                                    checked={!!branding.show_footer}
                                    onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_footer: checked }))}
                                />
                            </div>
```

(The debounced preview `useEffect` already depends on `branding`, so reordering re-renders the live preview automatically; no other change needed.)

- [ ] **Step 3: Add i18n keys**

In `ui/src/i18n/locales/en.json`, under the existing `settings.branding` object, add the new keys (keep `section_custom_fields`, `section_notes`, `section_footer` which already exist):

```json
"section_billto": "Bill To",
"section_items": "Line Items",
"section_totals": "Totals",
"section_order": "Section order",
"section_order_hint": "Drag to reorder the invoice sections. Use the eye icon to show or hide a section.",
"show_section": "Show section",
"hide_section": "Hide section"
```

- [ ] **Step 4: Verify build + lint + existing tests**

Run: `docker compose exec ui npx tsc --noEmit`
Expected: no new errors from the changed files.
Run: `docker compose exec ui npx vitest run src/lib/invoice-branding.test.ts`
Expected: PASS.

- [ ] **Step 5: Manual smoke (record outcome)**

Open Settings → Invoice template. Confirm: the section-order list shows all 5 rows with drag handles; dragging reorders them and the live preview updates within ~300 ms; the eye toggles on Details and Notes hide/show those sections in the preview; Save persists; reload restores the saved order. Note the result in the PR description.

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/settings/SectionOrderEditor.tsx ui/src/components/settings/InvoiceSettingsTab.tsx ui/src/i18n/locales/en.json
git commit -m "feat(invoice-template): drag-and-drop section order editor"
```

---

## Self-Review

**Spec coverage:**
- Config `section_order` + clamp (drop unknown / de-dupe / append missing / non-list→default) → Task 1. ✓
- Write validation → 400 → Task 2. ✓
- Macro-dispatch template, header pinned top / footer pinned bottom, visibility inside macros → Task 3. ✓
- All surfaces inherit via `load_template_config` → no surface-specific work (confirmed: every surface resolves config through `build_config` → `default.html`). ✓
- Frontend unified drag list, inline toggles for Details/Notes, `@dnd-kit/sortable`, i18n in `en.json` → Tasks 4–5. ✓
- Default order = current order, byte/visual parity guarded by regression test → Task 3 Step 1. ✓
- Out-of-scope items (columns, named templates, header/footer internals) → untouched. ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete content.

**Type consistency:** `ALLOWED_SECTIONS`/`DEFAULT_SECTION_ORDER` (Task 1) reused verbatim in Task 2; `SectionId`/`normalizeSectionOrder`/`DEFAULT_SECTION_ORDER` (Task 4) reused in Task 5; `section_order` key name consistent backend↔frontend; toggle keys `show_custom_fields`/`show_notes` match existing `InvoiceBranding` fields.
```
