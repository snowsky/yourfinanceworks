# Invoice Template Editor — Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Invoice Settings branding form into a two-pane template editor — style (colors, font, logo placement/size) + section visibility on the left, a live server-rendered sample-invoice preview on the right.

**Architecture:** Extend `InvoiceTemplateConfig` with three enum fields; add a pure `build_config(branding_dict)` that clamps any out-of-range value (read layer) alongside the existing `validate_invoice_branding` (write layer). The renderer emits the enums as CSS class names. A new authenticated `POST /invoices/template-preview` renders a canned sample invoice (with the tenant's real logo/name) through the *same* `render_invoice_html` used for client output. The frontend debounce-fetches that endpoint as controls change.

**Tech Stack:** FastAPI · SQLAlchemy · Jinja2/WeasyPrint (existing `invoice_render` package) · React/TypeScript · TanStack Query · vitest · pytest.

## Global Constraints

- **Allowed enum values (verbatim, single source of truth in `config.py`):** `font_family ∈ {"sans","serif","mono"}` (default `"sans"`); `logo_placement ∈ {"left","center","right"}` (default `"left"`); `logo_size ∈ {"small","medium","large"}` (default `"medium"`).
- **Storage:** the single tenant-DB `invoice_branding` `Settings` row, flat keys (`font_family`, `logo_placement`, `logo_size`, `show_notes`, `show_custom_fields`, `show_footer` join the existing `brand_color`/`accent_color`/`show_logo`/`footer_text`). **Backward-compatible:** any missing key falls back to its default. **No DB migration.**
- **Two-layer validation:** `validate_invoice_branding` rejects invalid enums on write (raises `ValueError` → HTTP 400); `build_config` clamps invalid/missing values to defaults on read. A bad stored value can never reach the renderer.
- **Injection safety:** the three enums are emitted **only as CSS class names** (`font-*`, `logo-*`), never interpolated as raw text into CSS; colors keep their 6-digit-hex validation.
- **No new fonts bundled** — only the DejaVu families already in the api image. **No Dockerfile change.**
- **Preview path is HTML-only** (no WeasyPrint / PDF).
- **Always shown, not toggleable:** bill-to, line-items table, totals. Only logo / custom fields / notes / footer have visibility switches.
- **Test environment (no image rebuild needed this slice):** Backend tests run in-container — `docker compose up -d`, then if `pytest` is missing reinstall test deps (`docker compose exec api pip install -r requirements-test.txt`; see project memory "API test deps"), then `docker compose exec api python -m pytest <path> -v` (use `python -m pytest`, never bare `pytest`). Pure-logic tests (config, view_model, branding) may alternatively run on the host: `PYTHONPATH=api /usr/local/bin/python -m pytest <file> --noconftest -v`. Frontend: `docker compose exec ui npx vitest run <file>`.

---

## File Structure

- `api/core/services/invoice_render/config.py` — **modify**: add 3 enum fields to `InvoiceTemplateConfig`; add allowed-set constants + pure `build_config(branding)`; refactor `load_template_config` to delegate to it.
- `api/core/services/invoice_render/__init__.py` — **modify**: export `build_config`, `sample_view_model`.
- `api/core/services/invoice_branding.py` — **modify**: extend `DEFAULT_INVOICE_BRANDING` + `validate_invoice_branding` with the new fields.
- `api/core/services/invoice_render/view_model.py` — **modify**: add pure `sample_view_model(tenant, config)`.
- `api/core/services/invoice_render/templates/invoice/default.html` — **modify**: emit `font-*` on root, `logo-*` on the logo img.
- `api/core/services/invoice_render/templates/invoice/default.css` — **modify**: define font/logo-placement/logo-size class rules.
- `api/core/routers/invoices/pdf_email.py` — **modify**: add `TemplatePreviewRequest` + `POST /template-preview`.
- `ui/src/lib/api/settings.ts` — **modify**: extend `InvoiceBranding` type; add `previewInvoiceTemplate`.
- `ui/src/lib/invoice-branding.ts` — **modify**: extend `DEFAULT_BRANDING`; add option constants.
- `ui/src/components/settings/InvoiceSettingsTab.tsx` — **modify**: two-pane editor (new controls + server live preview iframe).
- Tests: `api/tests/test_invoice_template_config.py` (new), `api/tests/test_invoice_branding.py`, `api/tests/test_invoice_view_model.py`, `api/tests/test_invoice_renderer.py`, `api/tests/test_invoice_render_endpoints.py`, `ui/src/components/settings/__tests__/InvoiceSettingsTab.test.tsx` (new).

---

### Task 1: Config schema + `build_config` (clamp-on-read)

**Files:**
- Modify: `api/core/services/invoice_render/config.py`
- Modify: `api/core/services/invoice_render/__init__.py`
- Test: `api/tests/test_invoice_template_config.py` (create)

**Interfaces:**
- Produces: `InvoiceTemplateConfig(brand_color, accent_color, footer_text, show, font_family, logo_placement, logo_size)` dataclass; `build_config(branding: dict) -> InvoiceTemplateConfig` (pure, clamps); constants `ALLOWED_FONTS`, `ALLOWED_LOGO_PLACEMENTS`, `ALLOWED_LOGO_SIZES`. `load_template_config(db)` unchanged signature, now delegates to `build_config`.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_invoice_template_config.py`:

```python
from core.services.invoice_render.config import (
    build_config, InvoiceTemplateConfig,
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES,
)


def test_allowed_sets_are_the_documented_values():
    assert ALLOWED_FONTS == ("sans", "serif", "mono")
    assert ALLOWED_LOGO_PLACEMENTS == ("left", "center", "right")
    assert ALLOWED_LOGO_SIZES == ("small", "medium", "large")


def test_build_config_defaults_when_empty():
    c = build_config({})
    assert isinstance(c, InvoiceTemplateConfig)
    assert c.font_family == "sans"
    assert c.logo_placement == "left"
    assert c.logo_size == "medium"
    assert c.brand_color == "#1e3a8a"
    assert c.accent_color == "#3b82f6"
    assert c.footer_text == ""
    assert c.show == {"logo": True, "notes": True, "custom_fields": True, "footer": True}


def test_build_config_reads_valid_values():
    c = build_config({"font_family": "serif", "logo_placement": "center",
                      "logo_size": "large", "brand_color": "#abcdef",
                      "accent_color": "#123456", "footer_text": "Thanks"})
    assert c.font_family == "serif"
    assert c.logo_placement == "center"
    assert c.logo_size == "large"
    assert c.brand_color == "#abcdef"
    assert c.accent_color == "#123456"
    assert c.footer_text == "Thanks"


def test_build_config_clamps_invalid_enums_to_defaults():
    c = build_config({"font_family": "comic", "logo_placement": "diagonal", "logo_size": "huge"})
    assert c.font_family == "sans"
    assert c.logo_placement == "left"
    assert c.logo_size == "medium"


def test_build_config_clamps_invalid_color():
    c = build_config({"brand_color": "red", "accent_color": "#xyz"})
    assert c.brand_color == "#1e3a8a"
    assert c.accent_color == "#3b82f6"


def test_build_config_reads_show_toggles():
    c = build_config({"show_logo": False, "show_notes": False,
                      "show_custom_fields": False, "show_footer": False})
    assert c.show == {"logo": False, "notes": False, "custom_fields": False, "footer": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_template_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_config'` (and `ALLOWED_*`).

- [ ] **Step 3: Implement the config changes**

Replace the entire contents of `api/core/services/invoice_render/config.py` with:

```python
# api/core/services/invoice_render/config.py
"""Invoice template layout config, read from the extended invoice_branding settings row."""
import re
from dataclasses import dataclass, field
from typing import Dict

_DEFAULT_SHOW = {"logo": True, "notes": True, "custom_fields": True, "footer": True}

ALLOWED_FONTS = ("sans", "serif", "mono")
ALLOWED_LOGO_PLACEMENTS = ("left", "center", "right")
ALLOWED_LOGO_SIZES = ("small", "medium", "large")

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_BRAND = "#1e3a8a"
_DEFAULT_ACCENT = "#3b82f6"


@dataclass
class InvoiceTemplateConfig:
    brand_color: str = _DEFAULT_BRAND
    accent_color: str = _DEFAULT_ACCENT
    footer_text: str = ""
    show: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_SHOW))
    font_family: str = "sans"
    logo_placement: str = "left"
    logo_size: str = "medium"


def _clamp(value, allowed, default):
    return value if value in allowed else default


def _clamp_color(value, default):
    return value if isinstance(value, str) and _HEX_RE.match(value) else default


def build_config(branding: Dict) -> "InvoiceTemplateConfig":
    """Build a config from a flat invoice_branding dict, clamping every value.

    Pure (no DB). Out-of-range or missing values fall back to defaults so a bad
    value — from the stored row or a posted draft — can never reach the renderer.
    """
    b = branding or {}
    show = dict(_DEFAULT_SHOW)
    show["logo"] = bool(b.get("show_logo", True))
    for key in ("notes", "custom_fields", "footer"):
        if f"show_{key}" in b:
            show[key] = bool(b[f"show_{key}"])
    return InvoiceTemplateConfig(
        brand_color=_clamp_color(b.get("brand_color"), _DEFAULT_BRAND),
        accent_color=_clamp_color(b.get("accent_color"), _DEFAULT_ACCENT),
        footer_text=(b.get("footer_text") or ""),
        show=show,
        font_family=_clamp(b.get("font_family"), ALLOWED_FONTS, "sans"),
        logo_placement=_clamp(b.get("logo_placement"), ALLOWED_LOGO_PLACEMENTS, "left"),
        logo_size=_clamp(b.get("logo_size"), ALLOWED_LOGO_SIZES, "medium"),
    )


def load_template_config(db) -> "InvoiceTemplateConfig":
    """Build the config from the tenant's invoice_branding settings row."""
    from core.services.invoice_branding import get_invoice_branding
    return build_config(get_invoice_branding(db))
```

Then edit `api/core/services/invoice_render/__init__.py` — change the config import line and `__all__`:

```python
from core.services.invoice_render.config import (
    InvoiceTemplateConfig, build_config, load_template_config)
from core.services.invoice_render.view_model import (
    InvoiceViewModel, assemble_view_model, build_view_model)

__all__ = ["InvoiceTemplateConfig", "build_config", "load_template_config",
           "InvoiceViewModel", "assemble_view_model", "build_view_model"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_template_config.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the existing render/view-model tests to confirm no regression**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_view_model.py -v`
Expected: PASS (unchanged — `InvoiceTemplateConfig(...)` still accepts the old kwargs; new fields default).

- [ ] **Step 6: Commit**

```bash
git add api/core/services/invoice_render/config.py api/core/services/invoice_render/__init__.py api/tests/test_invoice_template_config.py
git commit -m "feat(invoice-render): font/logo enums + clamp-on-read build_config"
```

---

### Task 2: Write-path validation + defaults (`invoice_branding.py`)

**Files:**
- Modify: `api/core/services/invoice_branding.py`
- Test: `api/tests/test_invoice_branding.py`

**Interfaces:**
- Consumes: `ALLOWED_FONTS`, `ALLOWED_LOGO_PLACEMENTS`, `ALLOWED_LOGO_SIZES` from Task 1's `config.py`.
- Produces: `validate_invoice_branding` accepts/normalizes `font_family`/`logo_placement`/`logo_size` (lowercased, enum-checked) and `show_notes`/`show_custom_fields`/`show_footer` (bool); `DEFAULT_INVOICE_BRANDING` includes the new keys.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_invoice_branding.py`:

```python
def test_validate_accepts_new_style_fields():
    out = validate_invoice_branding({
        "font_family": "Serif", "logo_placement": "CENTER", "logo_size": "large",
        "show_notes": False, "show_custom_fields": True, "show_footer": False,
    })
    assert out["font_family"] == "serif"          # lowercased
    assert out["logo_placement"] == "center"
    assert out["logo_size"] == "large"
    assert out["show_notes"] is False
    assert out["show_custom_fields"] is True
    assert out["show_footer"] is False


@pytest.mark.parametrize("field,bad", [
    ("font_family", "comic"), ("logo_placement", "diagonal"), ("logo_size", "huge")])
def test_validate_rejects_bad_enum(field, bad):
    with pytest.raises(ValueError):
        validate_invoice_branding({field: bad})


def test_defaults_include_new_style_fields():
    assert DEFAULT_INVOICE_BRANDING["font_family"] == "sans"
    assert DEFAULT_INVOICE_BRANDING["logo_placement"] == "left"
    assert DEFAULT_INVOICE_BRANDING["logo_size"] == "medium"
    assert DEFAULT_INVOICE_BRANDING["show_notes"] is True
    assert DEFAULT_INVOICE_BRANDING["show_custom_fields"] is True
    assert DEFAULT_INVOICE_BRANDING["show_footer"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_branding.py -k "new_style or bad_enum or defaults_include" -v`
Expected: FAIL — new keys not in `DEFAULT_INVOICE_BRANDING`; enums not validated (no `ValueError`).

- [ ] **Step 3: Implement the validation + defaults**

In `api/core/services/invoice_branding.py`, add the import near the top (after the existing imports, before `INVOICE_BRANDING_KEY`):

```python
from core.services.invoice_render.config import (
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES)
```

Extend `DEFAULT_INVOICE_BRANDING` to:

```python
DEFAULT_INVOICE_BRANDING: Dict[str, Any] = {
    "brand_color": "#1e3a8a",
    "accent_color": "#3b82f6",
    "show_logo": True,
    "footer_text": "",
    "font_family": "sans",
    "logo_placement": "left",
    "logo_size": "medium",
    "show_notes": True,
    "show_custom_fields": True,
    "show_footer": True,
}
```

In `validate_invoice_branding`, after the existing `footer_text` block and before `return cleaned`, insert:

```python
    for key, allowed in (
        ("font_family", ALLOWED_FONTS),
        ("logo_placement", ALLOWED_LOGO_PLACEMENTS),
        ("logo_size", ALLOWED_LOGO_SIZES),
    ):
        if value.get(key) is not None:
            v = str(value[key]).strip().lower()
            if v not in allowed:
                raise ValueError(f"{key} must be one of: {', '.join(allowed)}")
            cleaned[key] = v

    for key in ("show_notes", "show_custom_fields", "show_footer"):
        if value.get(key) is not None:
            cleaned[key] = bool(value[key])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_branding.py -v`
Expected: PASS (all, including the pre-existing branding tests).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_branding.py api/tests/test_invoice_branding.py
git commit -m "feat(invoice-branding): validate font/logo enums + section toggles on write"
```

---

### Task 3: `sample_view_model` (canned preview data)

**Files:**
- Modify: `api/core/services/invoice_render/view_model.py`
- Modify: `api/core/services/invoice_render/__init__.py`
- Test: `api/tests/test_invoice_view_model.py`

**Interfaces:**
- Consumes: `assemble_view_model`, `InvoiceTemplateConfig`.
- Produces: `sample_view_model(tenant, config) -> InvoiceViewModel` — pure (no DB; the spec's `db` param is unnecessary because `paid` is canned, which keeps the helper unit-testable without a stack per the spec's "Pure, no stack" testing requirement). Company identity from `tenant` (or safe fallback if `tenant is None`); canned client / 3 items / totals / notes / 2 custom fields. Fixed sample numbers: subtotal `2500.0`, 10% discount, paid `500.0`.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_invoice_view_model.py`:

```python
class _FakeTenant:
    name = "Acme Co"
    company_logo_url = "http://x/logo.png"
    address = "1 Main St"
    phone = "555-0100"
    email = "hello@acme.co"
    tax_id = "TAX-1"


def test_sample_view_model_uses_tenant_identity_and_canned_items():
    from core.services.invoice_render.view_model import sample_view_model
    vm = sample_view_model(_FakeTenant(), CFG)
    assert vm.company.name == "Acme Co"
    assert vm.company.logo_url == "http://x/logo.png"
    assert len(vm.items) == 3
    assert vm.totals.subtotal_raw == 2500.0
    assert vm.totals.discount_amount_raw == 250.0   # 10% of 2500
    assert vm.totals.total_raw == 2250.0
    assert vm.totals.paid_raw == 500.0
    assert vm.totals.balance_raw == 1750.0
    assert any(cf.label == "PO Number" for cf in vm.custom_fields)


def test_sample_view_model_handles_none_tenant():
    from core.services.invoice_render.view_model import sample_view_model
    vm = sample_view_model(None, CFG)
    assert vm.company.name        # non-empty fallback
    assert len(vm.items) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_view_model.py -k sample_view_model -v`
Expected: FAIL — `ImportError: cannot import name 'sample_view_model'`.

- [ ] **Step 3: Implement `sample_view_model`**

Append to `api/core/services/invoice_render/view_model.py`:

```python
def sample_view_model(tenant, config: InvoiceTemplateConfig) -> InvoiceViewModel:
    """A representative invoice for the template editor's live preview.

    Real company identity comes from `tenant` (the tenant sees their own logo
    placed/sized); the client, line items, totals, notes and custom fields are
    canned. Pure — no DB access.
    """
    data = {
        "company": {
            "name": (getattr(tenant, "name", "") or "Your Company") if tenant else "Your Company",
            "logo_url": getattr(tenant, "company_logo_url", None) if tenant else None,
            "address": (getattr(tenant, "address", "") or "") if tenant else "",
            "phone": (getattr(tenant, "phone", "") or "") if tenant else "",
            "email": (getattr(tenant, "email", "") or "") if tenant else "",
            "tax_id": (getattr(tenant, "tax_id", "") or "") if tenant else "",
        },
        "meta": {
            "number": "INV-0001", "issue_date": "2026-06-01", "due_date": "2026-06-15",
            "status": "sent", "currency": "USD", "show_discount": True,
        },
        "client": {
            "name": "Sample Client LLC", "email": "billing@sampleclient.com",
            "phone": "(555) 123-4567", "address": "123 Market St, Springfield",
        },
        "items": [
            {"description": "Consulting services", "quantity": 10, "unit_of_measure": "hrs",
             "unit_price": 150.0, "amount": 1500.0},
            {"description": "Design work", "quantity": 1, "unit_of_measure": "",
             "unit_price": 800.0, "amount": 800.0},
            {"description": "Support retainer", "quantity": 1, "unit_of_measure": "mo",
             "unit_price": 200.0, "amount": 200.0},
        ],
        "amount": 2500.0, "paid_amount": 500.0,
        "discount": {"type": "percentage", "value": 10.0},
        "custom_fields": {"PO Number": "PO-2026-0042", "Project": "Website Redesign"},
        "notes": "Thank you for your business! Payment due within 15 days.",
    }
    return assemble_view_model(data, config, public=False)
```

Then add the export in `api/core/services/invoice_render/__init__.py`:

```python
from core.services.invoice_render.view_model import (
    InvoiceViewModel, assemble_view_model, build_view_model, sample_view_model)

__all__ = ["InvoiceTemplateConfig", "build_config", "load_template_config",
           "InvoiceViewModel", "assemble_view_model", "build_view_model", "sample_view_model"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=api /usr/local/bin/python -m pytest api/tests/test_invoice_view_model.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_render/view_model.py api/core/services/invoice_render/__init__.py api/tests/test_invoice_view_model.py
git commit -m "feat(invoice-render): sample_view_model for template-editor preview"
```

---

### Task 4: Template + CSS — font & logo classes

**Files:**
- Modify: `api/core/services/invoice_render/templates/invoice/default.html`
- Modify: `api/core/services/invoice_render/templates/invoice/default.css`
- Test: `api/tests/test_invoice_renderer.py`

**Interfaces:**
- Consumes: `cfg.font_family`, `cfg.logo_placement`, `cfg.logo_size` (Task 1).
- Produces: rendered HTML carries `class="invoice font-<family>"` on the root and `class="logo logo-<placement> logo-<size>"` on the logo `<img>`.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_invoice_renderer.py`:

```python
def test_html_applies_font_class():
    cfg = InvoiceTemplateConfig(font_family="serif")
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert "font-serif" in html


def test_html_applies_logo_placement_and_size_classes():
    cfg = InvoiceTemplateConfig(logo_placement="right", logo_size="large")
    data = _data(company={"name": "Acme", "logo_url": "http://x/l.png", "address": "",
                          "phone": "", "email": "", "tax_id": ""})
    html = render_invoice_html(assemble_view_model(data, cfg), cfg)
    assert "logo-right" in html and "logo-large" in html


def test_css_defines_font_and_logo_classes():
    cfg = InvoiceTemplateConfig()
    html = render_invoice_html(assemble_view_model(_data(), cfg), cfg)
    assert ".font-serif" in html and ".logo-large" in html  # CSS rules inlined in <style>
```

(These import `InvoiceTemplateConfig`, `assemble_view_model`, `render_invoice_html`, `_data` already at the top of the file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest api/tests/test_invoice_renderer.py -k "font_class or logo_placement or css_defines" -v`
Expected: FAIL — classes/rules not present yet. *(Renderer tests need the in-container Jinja2/WeasyPrint environment; bring the stack up first per Global Constraints.)*

- [ ] **Step 3: Edit the template**

In `api/core/services/invoice_render/templates/invoice/default.html`:

Change line 4 (root div) from:

```html
<div class="invoice" style="--brand: {{ cfg.brand_color }}; --accent: {{ cfg.accent_color }};">
```

to:

```html
<div class="invoice font-{{ cfg.font_family }}" style="--brand: {{ cfg.brand_color }}; --accent: {{ cfg.accent_color }};">
```

Change line 6 (logo img) from:

```html
    {% if cfg.show.logo and vm.company.logo_url %}<img class="logo" src="{{ vm.company.logo_url }}">{% endif %}
```

to:

```html
    {% if cfg.show.logo and vm.company.logo_url %}<img class="logo logo-{{ cfg.logo_placement }} logo-{{ cfg.logo_size }}" src="{{ vm.company.logo_url }}">{% endif %}
```

- [ ] **Step 4: Edit the CSS**

In `api/core/services/invoice_render/templates/invoice/default.css`, append these rules (after the existing `.foot` rule on line 16):

```css
.invoice.font-sans { font-family: "DejaVu Sans", Arial, sans-serif; }
.invoice.font-serif { font-family: "DejaVu Serif", Georgia, serif; }
.invoice.font-mono { font-family: "DejaVu Sans Mono", monospace; }
.logo.logo-small { max-width: 80px; max-height: 56px; }
.logo.logo-medium { max-width: 120px; max-height: 72px; }
.logo.logo-large { max-width: 160px; max-height: 96px; }
.logo.logo-left { margin-right: auto; }
.logo.logo-center { display: block; margin-left: auto; margin-right: auto; }
.logo.logo-right { margin-left: auto; }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest api/tests/test_invoice_renderer.py -v`
Expected: PASS (all, including the pre-existing renderer + PDF smoke tests).

- [ ] **Step 6: Commit**

```bash
git add api/core/services/invoice_render/templates/invoice/default.html api/core/services/invoice_render/templates/invoice/default.css api/tests/test_invoice_renderer.py
git commit -m "feat(invoice-render): font + logo placement/size classes in template"
```

---

### Task 5: `POST /invoices/template-preview` endpoint

**Files:**
- Modify: `api/core/routers/invoices/pdf_email.py`
- Test: `api/tests/test_invoice_render_endpoints.py`

**Interfaces:**
- Consumes: `build_config` (Task 1), `sample_view_model` (Task 3), `render_invoice_html`, `get_current_user`, `get_master_db`, `Tenant`.
- Produces: `POST /api/v1/invoices/template-preview` — authenticated; body = flat draft branding (all optional); returns `text/html` of the sample invoice rendered with the clamped draft config.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_invoice_render_endpoints.py` (reuses the module's `render_client` / `render_auth` fixtures):

```python
def test_template_preview_renders_sample_with_draft_config(render_client, render_auth):
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        headers=render_auth,
        json={"font_family": "serif", "show_notes": False},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "font-serif" in body                 # draft font applied
    assert "Sample Client LLC" in body          # canned sample data rendered
    assert "Payment due within 15 days" not in body  # notes hidden by draft toggle


def test_template_preview_clamps_bad_enum(render_client, render_auth):
    resp = render_client.post(
        "/api/v1/invoices/template-preview",
        headers=render_auth,
        json={"font_family": "comic-sans"},
    )
    assert resp.status_code == 200
    assert "font-sans" in resp.text             # clamped to default, never raw value
    assert "comic-sans" not in resp.text


def test_template_preview_requires_auth(render_client):
    resp = render_client.post("/api/v1/invoices/template-preview", json={})
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api python -m pytest api/tests/test_invoice_render_endpoints.py -k template_preview -v`
Expected: FAIL — route returns 404/405 (not yet defined).

- [ ] **Step 3: Implement the endpoint**

In `api/core/routers/invoices/pdf_email.py`, update the import on line 16-17 to add `build_config` and `sample_view_model`:

```python
from core.services.invoice_render import (
    assemble_view_model, build_config, build_view_model, load_template_config, sample_view_model)
from core.services.invoice_render.renderer import render_invoice_html, render_invoice_pdf_async
```

Add this request model after the `InvoicePreviewRequest` class (after line 40):

```python
class TemplatePreviewRequest(BaseModel):
    """Draft template config for the settings editor's live preview.
    Flat keys mirror the invoice_branding row; all optional → defaults apply."""
    brand_color: Optional[str] = None
    accent_color: Optional[str] = None
    footer_text: Optional[str] = None
    show_logo: Optional[bool] = None
    show_notes: Optional[bool] = None
    show_custom_fields: Optional[bool] = None
    show_footer: Optional[bool] = None
    font_family: Optional[str] = None
    logo_placement: Optional[str] = None
    logo_size: Optional[str] = None
```

Add this route (place it after the `POST /preview` route, before `GET /{invoice_id}/pdf` — it must not be shadowed by the `GET /{invoice_id}/preview` path):

```python
@router.post("/template-preview", response_class=HTMLResponse)
async def preview_invoice_template(
    body: TemplatePreviewRequest,
    master_db: Session = Depends(get_master_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Render a canned sample invoice with the posted draft template config.

    Powers the Invoice Settings template editor's live preview. Company identity
    (name + logo) comes from the tenant; the rest of the invoice is sample data.
    The draft config is clamped via build_config, so an out-of-range value is
    rendered as its default class, never as raw text.
    """
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    cfg = build_config(body.model_dump(exclude_none=True))
    vm = sample_view_model(tenant, cfg)
    return HTMLResponse(content=render_invoice_html(vm, cfg))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api python -m pytest api/tests/test_invoice_render_endpoints.py -v`
Expected: PASS (all, including the pre-existing endpoint tests).

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/invoices/pdf_email.py api/tests/test_invoice_render_endpoints.py
git commit -m "feat(invoices): POST /template-preview renders sample with draft config"
```

---

### Task 6: Frontend — two-pane template editor

**Files:**
- Modify: `ui/src/lib/api/settings.ts`
- Modify: `ui/src/lib/invoice-branding.ts`
- Modify: `ui/src/components/settings/InvoiceSettingsTab.tsx`
- Test: `ui/src/components/settings/__tests__/InvoiceSettingsTab.test.tsx` (create)

**Interfaces:**
- Consumes: `POST /api/v1/invoices/template-preview` (Task 5).
- Produces: `InvoiceBranding` type with `font_family`/`logo_placement`/`logo_size`/`show_notes`/`show_custom_fields`/`show_footer`; `settingsApi.previewInvoiceTemplate(branding) -> Promise<string>`; `DEFAULT_BRANDING` + option constants; two-pane Branding card with debounced server preview.

- [ ] **Step 1: Extend the API types + service**

In `ui/src/lib/api/settings.ts`, update the import on line 1 to also pull `getTenantId`:

```ts
import { API_BASE_URL, apiRequest, getTenantId } from './_base';
```

Replace the `InvoiceBranding` interface (lines 27-32) with:

```ts
export type InvoiceFont = 'sans' | 'serif' | 'mono';
export type LogoPlacement = 'left' | 'center' | 'right';
export type LogoSize = 'small' | 'medium' | 'large';

export interface InvoiceBranding {
  brand_color: string;
  accent_color: string;
  show_logo: boolean;
  footer_text: string;
  font_family: InvoiceFont;
  logo_placement: LogoPlacement;
  logo_size: LogoSize;
  show_notes: boolean;
  show_custom_fields: boolean;
  show_footer: boolean;
}
```

In the `settingsApi` object (after the `updateSettings` entry, ~line 239), add:

```ts
  previewInvoiceTemplate: async (branding: Partial<InvoiceBranding>): Promise<string> => {
    const tenantId = getTenantId();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (tenantId) headers['X-Tenant-ID'] = tenantId;
    const res = await fetch(`${API_BASE_URL}/invoices/template-preview`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(branding),
    });
    if (!res.ok) throw new Error(`Template preview failed: ${res.status}`);
    return res.text();
  },
```

- [ ] **Step 2: Extend defaults + option constants**

Replace the `DEFAULT_BRANDING` block in `ui/src/lib/invoice-branding.ts` (lines 3-8) with:

```ts
export const DEFAULT_BRANDING: InvoiceBranding = {
  brand_color: '#1e3a8a',
  accent_color: '#3b82f6',
  show_logo: true,
  footer_text: '',
  font_family: 'sans',
  logo_placement: 'left',
  logo_size: 'medium',
  show_notes: true,
  show_custom_fields: true,
  show_footer: true,
};

export const FONT_OPTIONS: InvoiceFont[] = ['sans', 'serif', 'mono'];
export const LOGO_PLACEMENTS: LogoPlacement[] = ['left', 'center', 'right'];
export const LOGO_SIZES: LogoSize[] = ['small', 'medium', 'large'];
```

Update the import on line 1 to bring in the new types:

```ts
import type { InvoiceBranding, InvoiceFont, LogoPlacement, LogoSize } from '@/lib/api/settings';
```

- [ ] **Step 3: Wire the editor controls + live preview in `InvoiceSettingsTab.tsx`**

Update the imports — change line 18 to:

```tsx
import { DEFAULT_BRANDING, isHexColor, FONT_OPTIONS, LOGO_PLACEMENTS, LOGO_SIZES } from "@/lib/invoice-branding";
```

(`readableTextColor` is dropped — the JSX mini-preview it served is being replaced by the server iframe.)

Add preview state + a debounced fetch effect. Immediately after the `const [branding, setBranding] = useState<InvoiceBranding>(DEFAULT_BRANDING);` line (line 50), add:

```tsx
    const [previewHtml, setPreviewHtml] = useState<string>("");

    useEffect(() => {
        if (!isAdmin) return;
        const handle = setTimeout(() => {
            settingsApi
                .previewInvoiceTemplate(branding)
                .then(setPreviewHtml)
                .catch(() => { /* keep last good preview */ });
        }, 300);
        return () => clearTimeout(handle);
    }, [branding, isAdmin]);
```

Replace the entire Branding Card (the `{/* Branding Card */}` block, lines 301-421) with the two-pane editor below:

```tsx
            {/* Branding / Template Editor Card */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Palette className="w-4 h-4 text-primary" />
                        {t('settings.branding.title')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <p className="text-sm text-muted-foreground mb-4">
                        {t('settings.branding.description')}
                    </p>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Left: controls */}
                        <div className="space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label htmlFor="brand_color">{t('settings.branding.brand_color')}</Label>
                                    <div className="flex items-center gap-3">
                                        <input
                                            type="color"
                                            aria-label={t('settings.branding.brand_color')}
                                            value={isHexColor(branding.brand_color) ? branding.brand_color : '#1e3a8a'}
                                            onChange={(e) => setBrandColor('brand_color', e.target.value)}
                                            className="h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1"
                                        />
                                        <ProfessionalInput
                                            id="brand_color"
                                            value={branding.brand_color}
                                            onChange={(e) => setBrandColor('brand_color', e.target.value)}
                                            className="font-mono"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="accent_color">{t('settings.branding.accent_color')}</Label>
                                    <div className="flex items-center gap-3">
                                        <input
                                            type="color"
                                            aria-label={t('settings.branding.accent_color')}
                                            value={isHexColor(branding.accent_color) ? branding.accent_color : '#3b82f6'}
                                            onChange={(e) => setBrandColor('accent_color', e.target.value)}
                                            className="h-10 w-14 cursor-pointer rounded-md border border-input bg-background p-1"
                                        />
                                        <ProfessionalInput
                                            id="accent_color"
                                            value={branding.accent_color}
                                            onChange={(e) => setBrandColor('accent_color', e.target.value)}
                                            className="font-mono"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Font */}
                            <div className="space-y-2">
                                <Label htmlFor="font_family">{t('settings.branding.font')}</Label>
                                <div className="flex gap-2" role="group" aria-label={t('settings.branding.font')}>
                                    {FONT_OPTIONS.map((font) => (
                                        <button
                                            key={font}
                                            type="button"
                                            onClick={() => setBranding((prev) => ({ ...prev, font_family: font }))}
                                            className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.font_family === font ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                        >
                                            {t(`settings.branding.font_${font}`)}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Logo */}
                            <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                                <div className="space-y-0.5 pr-4">
                                    <Label htmlFor="show_logo" className="text-base font-semibold">
                                        {t('settings.branding.show_logo')}
                                    </Label>
                                    <p className="text-sm text-muted-foreground">
                                        {companyLogo
                                            ? t('settings.branding.show_logo_description')
                                            : t('settings.branding.no_logo_hint')}
                                    </p>
                                </div>
                                <Switch
                                    id="show_logo"
                                    checked={!!branding.show_logo}
                                    onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, show_logo: checked }))}
                                />
                            </div>
                            {branding.show_logo && (
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>{t('settings.branding.logo_placement')}</Label>
                                        <div className="flex gap-2" role="group" aria-label={t('settings.branding.logo_placement')}>
                                            {LOGO_PLACEMENTS.map((p) => (
                                                <button
                                                    key={p}
                                                    type="button"
                                                    onClick={() => setBranding((prev) => ({ ...prev, logo_placement: p }))}
                                                    className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.logo_placement === p ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                                >
                                                    {t(`settings.branding.placement_${p}`)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>{t('settings.branding.logo_size')}</Label>
                                        <div className="flex gap-2" role="group" aria-label={t('settings.branding.logo_size')}>
                                            {LOGO_SIZES.map((s) => (
                                                <button
                                                    key={s}
                                                    type="button"
                                                    onClick={() => setBranding((prev) => ({ ...prev, logo_size: s }))}
                                                    className={`px-3 py-1.5 rounded-lg border text-sm capitalize ${branding.logo_size === s ? 'border-primary bg-primary/10 font-semibold' : 'border-input'}`}
                                                >
                                                    {t(`settings.branding.size_${s}`)}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Section visibility */}
                            <div className="p-4 bg-muted/30 rounded-xl space-y-3">
                                <p className="text-sm font-semibold">{t('settings.branding.sections')}</p>
                                {([
                                    ['show_custom_fields', 'settings.branding.section_custom_fields'],
                                    ['show_notes', 'settings.branding.section_notes'],
                                    ['show_footer', 'settings.branding.section_footer'],
                                ] as const).map(([key, label]) => (
                                    <div key={key} className="flex items-center justify-between">
                                        <Label htmlFor={key}>{t(label)}</Label>
                                        <Switch
                                            id={key}
                                            checked={!!branding[key]}
                                            onCheckedChange={(checked) => setBranding((prev) => ({ ...prev, [key]: checked }))}
                                        />
                                    </div>
                                ))}
                            </div>

                            <ProfessionalTextarea
                                label={t('settings.branding.footer_text')}
                                id="branding_footer"
                                name="branding_footer"
                                rows={2}
                                maxLength={500}
                                value={branding.footer_text || ''}
                                onChange={(e) => setBranding((prev) => ({ ...prev, footer_text: e.target.value }))}
                                placeholder={t('settings.branding.footer_placeholder')}
                            />
                        </div>

                        {/* Right: live preview */}
                        <div className="space-y-2">
                            <p className="text-sm font-medium">{t('settings.branding.preview')}</p>
                            <iframe
                                title="invoice-template-preview"
                                sandbox=""
                                srcDoc={previewHtml}
                                className="w-full h-[640px] rounded-xl border bg-white"
                            />
                        </div>
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>
```

Add the new i18n keys to `ui/src/i18n/locales/en.json` under `settings.branding` (alongside the existing branding keys): `"font": "Font"`, `"font_sans": "Sans"`, `"font_serif": "Serif"`, `"font_mono": "Mono"`, `"logo_placement": "Logo placement"`, `"logo_size": "Logo size"`, `"placement_left": "Left"`, `"placement_center": "Center"`, `"placement_right": "Right"`, `"size_small": "Small"`, `"size_medium": "Medium"`, `"size_large": "Large"`, `"sections": "Sections"`, `"section_custom_fields": "Custom fields"`, `"section_notes": "Notes"`, `"section_footer": "Footer"`. (`fallbackLng: 'en'` means the English file is sufficient.)

- [ ] **Step 4: Write the failing component test**

Create `ui/src/components/settings/__tests__/InvoiceSettingsTab.test.tsx`:

```tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { InvoiceSettingsTab } from '../InvoiceSettingsTab';
import { DEFAULT_BRANDING } from '@/lib/invoice-branding';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const previewMock = vi.fn().mockResolvedValue('<html><body>preview</body></html>');

vi.mock('@/lib/api', () => ({
  settingsApi: {
    getSettings: vi.fn().mockResolvedValue({
      invoice_settings: {}, invoice_branding: { ...DEFAULT_BRANDING }, company_info: { name: 'Acme', logo: '' },
    }),
    getClientPortalLink: vi.fn().mockResolvedValue({ enabled: false, portal_url: null, path: null }),
    updateSettings: vi.fn().mockResolvedValue({}),
    previewInvoiceTemplate: (...args: unknown[]) => previewMock(...args),
  },
}));

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InvoiceSettingsTab isAdmin={true} />
    </QueryClientProvider>,
  );
}

describe('InvoiceSettingsTab template editor', () => {
  beforeEach(() => previewMock.mockClear());

  it('renders the font controls once settings load', async () => {
    renderTab();
    expect(await screen.findByText('settings.branding.font_serif')).toBeInTheDocument();
  });

  it('debounce-fetches the server preview', async () => {
    renderTab();
    await screen.findByText('settings.branding.font_serif');
    await waitFor(() => expect(previewMock).toHaveBeenCalled());
  });

  it('updates the draft and re-previews when a font is chosen', async () => {
    const user = userEvent.setup();
    renderTab();
    const serif = await screen.findByText('settings.branding.font_serif');
    previewMock.mockClear();
    await user.click(serif);
    await waitFor(() =>
      expect(previewMock).toHaveBeenCalledWith(expect.objectContaining({ font_family: 'serif' })),
    );
  });
});
```

- [ ] **Step 5: Run the test to verify it fails, then passes**

Run: `docker compose exec ui npx vitest run src/components/settings/__tests__/InvoiceSettingsTab.test.tsx`
Expected after Steps 1-3: PASS (3 passed). If run before the component edits, it FAILs (controls/preview absent).

- [ ] **Step 6: Type-check the frontend**

Run: `docker compose exec ui npx tsc --noEmit`
Expected: no new errors in `settings.ts`, `invoice-branding.ts`, `InvoiceSettingsTab.tsx`. *(Pre-existing unrelated errors elsewhere are out of scope.)*

- [ ] **Step 7: Commit**

```bash
git add ui/src/lib/api/settings.ts ui/src/lib/invoice-branding.ts ui/src/components/settings/InvoiceSettingsTab.tsx ui/src/components/settings/__tests__/InvoiceSettingsTab.test.tsx ui/src/i18n/locales/en.json
git commit -m "feat(ui): two-pane invoice template editor with live server preview"
```

---

## Self-Review

**1. Spec coverage:**
- Config schema extension (font/placement/size) → Task 1. ✓
- Persistence + two-layer validation (write: `validate_invoice_branding`; read: `build_config` clamp) → Task 2 (write) + Task 1 (read). ✓
- Rendering as CSS classes → Task 4. ✓
- `POST /invoices/template-preview` + `sample_view_model` (tenant identity + canned data) → Tasks 3 + 5. ✓
- Frontend two-pane editor + debounced preview + save with new fields → Task 6 (save path unchanged — `handleSave` already sends `invoice_branding: branding`, which now carries the new fields). ✓
- Testing (view-model / config / renderer / endpoint / frontend) → Tasks 3 / 1 / 4 / 5 / 6. ✓
- Surfaces unchanged (config flows through `load_template_config`) → no task needed; `load_template_config` delegates to `build_config` (Task 1) so all surfaces read the new fields automatically. ✓

**2. Placeholder scan:** none — every code step shows complete code; every run step shows the command + expected result.

**3. Type/name consistency:** `build_config`, `sample_view_model`, `InvoiceTemplateConfig` field names, `ALLOWED_FONTS/ALLOWED_LOGO_PLACEMENTS/ALLOWED_LOGO_SIZES`, the flat branding keys (`font_family`/`logo_placement`/`logo_size`/`show_notes`/`show_custom_fields`/`show_footer`), the `font-*`/`logo-*` CSS class names, and `settingsApi.previewInvoiceTemplate` are used identically across backend, template, endpoint, and frontend tasks.

**Note (spec deviation, intentional):** the spec wrote `sample_view_model(db, tenant, config)`; the plan drops `db` because no DB access is needed (paid amount is canned), which keeps the helper pure and unit-testable without a stack — exactly what the spec's own testing section ("Pure, no stack") requires.
