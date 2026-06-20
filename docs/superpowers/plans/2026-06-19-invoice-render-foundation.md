# Invoice Render Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify invoice rendering onto one config-driven Jinja2 + WeasyPrint template that drives the PDF, the authenticated web preview, and the public portal/share view — retiring the divergent react-pdf and ReportLab invoice paths.

**Architecture:** A new `api/core/services/invoice_render/` package: a pure `view_model` layer that normalizes an invoice into a render-ready `InvoiceViewModel` (centralizing the money/currency/logo logic currently duplicated across 4 renderers), a `config` layer that reads the existing `invoice_branding` settings, and a `renderer` that turns `(view_model, config)` into HTML (Jinja2) and PDF (WeasyPrint, run in a threadpool). Endpoints and the frontend are re-pointed at this one path.

**Tech Stack:** FastAPI, SQLAlchemy (per-tenant), Jinja2, WeasyPrint, React/TypeScript (Vite), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-19-invoice-render-foundation-design.md` — this plan implements **Phase 1 only** (the editor UI is Phase 2, out of scope).
- Backend tests run **in-container only**: `docker compose exec -T api python -m pytest …` (the host has an arm64/x86_64 `pydantic_core` mismatch that breaks the conftest path). Pure unit tests can run locally with `--noconftest`. Reinstall pytest into the container if the image was rebuilt: `pip install pytest==8.4.1 pytest-asyncio==1.1.0 pytest-mock==3.14.1 pytest-cov==6.2.1`.
- **Parity:** the view-model must reproduce today's computed values — discount proration as in `api/core/utils/pdf_generator.py` (`_build_totals`), `paid_amount = SUM(payments.amount)`, tax keys (`tax_amount`, `tax_rate`) split out of `custom_fields`.
- **Discount visibility stays per-invoice** via the existing `Invoice.show_discount_in_pdf` column — NOT a tenant config toggle.
- **No per-tenant opt-in flag** — the new template ships for all tenants.
- WeasyPrint PDF rendering is sync CPU work; the async endpoints MUST offload it via `run_in_executor` so it never blocks the event loop.
- Money values are floats today (`Numeric(asdecimal=False)`); mirror that (no Decimal migration here).
- Commit messages: plain conventional-commits, no attribution footer.

## File Structure

| File | Responsibility |
|---|---|
| `api/core/services/invoice_render/__init__.py` | Package exports (`build_view_model`, `load_template_config`, `render_invoice_html`, `render_invoice_pdf`) |
| `api/core/services/invoice_render/config.py` | `InvoiceTemplateConfig` + `load_template_config(db)` (reads extended `invoice_branding`) |
| `api/core/services/invoice_render/view_model.py` | `InvoiceViewModel` dataclasses + pure `assemble_view_model(data, config)` + DB-fed `build_view_model(db, invoice, tenant, config)` |
| `api/core/services/invoice_render/money.py` | `format_money(amount, currency)` — single currency formatter |
| `api/core/services/invoice_render/renderer.py` | `render_invoice_html(vm, config)` (Jinja2), `render_invoice_pdf(vm, config)` (WeasyPrint) |
| `api/core/services/invoice_render/templates/invoice/default.html` | The single Jinja invoice template |
| `api/core/services/invoice_render/templates/invoice/default.css` | Template stylesheet |
| `api/tests/test_invoice_view_model.py` | Parity unit tests (pure, `--noconftest`) |
| `api/tests/test_invoice_renderer.py` | HTML section-toggle tests + PDF `%PDF` smoke test |
| `api/Dockerfile` | + WeasyPrint system libs + bundled font |
| `api/requirements.txt` | + `weasyprint` |
| `api/core/routers/invoices/pdf_email.py` (or the PDF download route) | Re-point PDF download + add `GET /invoices/{id}/preview` |
| `api/core/services/email_service.py` | Attach the new unified PDF |
| `api/core/routers/share_tokens.py`, `api/core/routers/client_portal.py` | Serve `render_invoice_html` |
| `ui/src/pages/ViewInvoice.tsx` | Render `/preview` HTML in a sandboxed iframe; "Download PDF" → server |
| `ui/src/pages/SharedRecord.tsx` | Render server HTML in an iframe |
| `ui/src/components/invoices/InvoicePDF.tsx` | Retired (dormant one release) |

---

### Task 1: View-model + config (the parity-critical data layer)

**Files:**
- Create: `api/core/services/invoice_render/__init__.py`, `config.py`, `money.py`, `view_model.py`
- Test: `api/tests/test_invoice_view_model.py`
- Reference (do NOT change): `api/core/utils/pdf_generator.py` `_build_totals` (discount logic), `api/core/services/invoice_branding.py` (`get_invoice_branding`, `DEFAULT_INVOICE_BRANDING`)

**Interfaces:**
- Produces:
  - `InvoiceTemplateConfig` dataclass: `brand_color: str`, `accent_color: str`, `footer_text: str`, `show: dict[str, bool]` (keys `logo`, `notes`, `custom_fields`, `footer`).
  - `load_template_config(db) -> InvoiceTemplateConfig`
  - `assemble_view_model(data: dict, config: InvoiceTemplateConfig) -> InvoiceViewModel` (pure)
  - `build_view_model(db, invoice, tenant, config) -> InvoiceViewModel` (DB-fed)
  - `format_money(amount: float, currency: str) -> str`

- [ ] **Step 1: Write the failing test** — `api/tests/test_invoice_view_model.py`

```python
from core.services.invoice_render.config import InvoiceTemplateConfig
from core.services.invoice_render.view_model import assemble_view_model

CFG = InvoiceTemplateConfig(
    brand_color="#1e3a8a", accent_color="#3b82f6", footer_text="Thanks!",
    show={"logo": True, "notes": True, "custom_fields": True, "footer": True},
)

def _data(**over):
    base = dict(
        company={"name": "Acme", "logo_url": None, "address": "1 St",
                 "phone": "", "email": "a@b.co", "tax_id": ""},
        meta={"number": "INV-1", "issue_date": "2026-06-01", "due_date": "2026-06-15",
              "status": "pending", "currency": "USD", "show_discount": True},
        client={"name": "Bob", "email": "", "phone": "", "address": ""},
        items=[{"description": "Work", "quantity": 2, "unit_of_measure": "",
                "unit_price": 50.0, "amount": 100.0}],
        amount=100.0, paid_amount=30.0,
        discount={"type": "percentage", "value": 10.0},
        custom_fields={"PO": "123", "tax_amount": 5.0, "tax_rate": 5.0},
        notes="hi",
    )
    base.update(over)
    return base

def test_totals_with_percentage_discount_and_payment():
    vm = assemble_view_model(_data(), CFG)
    # subtotal 100, 10% discount = 10, total 90, paid 30, balance 60
    assert vm.totals.subtotal_raw == 100.0
    assert vm.totals.discount_amount_raw == 10.0
    assert vm.totals.total_raw == 90.0
    assert vm.totals.paid_raw == 30.0
    assert vm.totals.balance_raw == 60.0

def test_fixed_discount():
    vm = assemble_view_model(_data(discount={"type": "fixed", "value": 25.0}), CFG)
    assert vm.totals.discount_amount_raw == 25.0
    assert vm.totals.total_raw == 75.0

def test_tax_keys_split_out_of_custom_fields():
    vm = assemble_view_model(_data(), CFG)
    labels = {cf.label for cf in vm.custom_fields}
    assert "PO" in labels
    assert "tax_amount" not in labels and "tax_rate" not in labels

def test_currency_formatting_usd():
    vm = assemble_view_model(_data(), CFG)
    assert vm.totals.total == "$90.00"

def test_logo_hidden_when_config_off():
    cfg = InvoiceTemplateConfig(brand_color="#000", accent_color="#000",
        footer_text="", show={"logo": False, "notes": True, "custom_fields": True, "footer": True})
    vm = assemble_view_model(_data(company={"name": "Acme", "logo_url": "http://x/l.png",
        "address": "", "phone": "", "email": "", "tax_id": ""}), cfg)
    assert vm.company.logo_url is None  # suppressed by config
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_view_model.py -q --noconftest`
Expected: FAIL (`ModuleNotFoundError: core.services.invoice_render`).

- [ ] **Step 3: Implement `money.py`**

```python
# api/core/services/invoice_render/money.py
"""Single currency formatter for invoice rendering."""

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
            "CAD": "$", "AUD": "$", "INR": "₹"}
_ZERO_DECIMAL = {"JPY"}

def format_money(amount: float, currency: str) -> str:
    currency = (currency or "USD").upper()
    symbol = _SYMBOLS.get(currency, "")
    if currency in _ZERO_DECIMAL:
        body = f"{amount:,.0f}"
    else:
        body = f"{amount:,.2f}"
    return f"{symbol}{body}" if symbol else f"{body} {currency}"
```

- [ ] **Step 4: Implement `config.py`**

```python
# api/core/services/invoice_render/config.py
"""Invoice template layout config, read from the extended invoice_branding settings row."""
from dataclasses import dataclass, field
from typing import Dict

_DEFAULT_SHOW = {"logo": True, "notes": True, "custom_fields": True, "footer": True}

@dataclass
class InvoiceTemplateConfig:
    brand_color: str = "#1e3a8a"
    accent_color: str = "#3b82f6"
    footer_text: str = ""
    show: Dict[str, bool] = field(default_factory=lambda: dict(_DEFAULT_SHOW))

def load_template_config(db) -> "InvoiceTemplateConfig":
    """Build the config from the tenant's invoice_branding settings row."""
    from core.services.invoice_branding import get_invoice_branding
    b = get_invoice_branding(db)  # dict: brand_color, accent_color, show_logo, footer_text
    show = dict(_DEFAULT_SHOW)
    show["logo"] = bool(b.get("show_logo", True))
    # New per-tenant section toggles (added to the branding row; default on if absent)
    for key in ("notes", "custom_fields", "footer"):
        if f"show_{key}" in b:
            show[key] = bool(b[f"show_{key}"])
    return InvoiceTemplateConfig(
        brand_color=b.get("brand_color", "#1e3a8a"),
        accent_color=b.get("accent_color", "#3b82f6"),
        footer_text=b.get("footer_text", "") or "",
        show=show,
    )
```

- [ ] **Step 5: Implement `view_model.py`**

```python
# api/core/services/invoice_render/view_model.py
"""Normalized, render-ready invoice view model. `assemble_view_model` is pure
(unit-tested without a DB); `build_view_model` adapts ORM objects to it."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.services.invoice_render.money import format_money
from core.services.invoice_render.config import InvoiceTemplateConfig

_RESERVED_CUSTOM_KEYS = {"tax_amount", "tax_rate"}

@dataclass
class CompanyVM:
    name: str; logo_url: Optional[str]; address: str; phone: str; email: str; tax_id: str
@dataclass
class MetaVM:
    number: str; issue_date: str; due_date: str; status: str; currency: str; show_discount: bool
@dataclass
class ClientVM:
    name: str; email: str; phone: str; address: str
@dataclass
class ItemVM:
    description: str; quantity: float; unit_of_measure: str
    unit_price_raw: float; unit_price: str; amount_raw: float; amount: str
@dataclass
class TotalsVM:
    subtotal_raw: float; subtotal: str
    discount_type: str; discount_value: float; discount_amount_raw: float; discount_amount: str
    total_raw: float; total: str; paid_raw: float; paid: str; balance_raw: float; balance: str
@dataclass
class CustomFieldVM:
    label: str; value: Any
@dataclass
class InvoiceViewModel:
    company: CompanyVM; meta: MetaVM; client: ClientVM
    items: List[ItemVM]; totals: TotalsVM; custom_fields: List[CustomFieldVM]
    notes: str; footer_text: str

def _discount_amount(subtotal: float, dtype: str, dvalue: float) -> float:
    if not dvalue:
        return 0.0
    if dtype == "percentage":
        return subtotal * (dvalue / 100.0)
    return min(dvalue, subtotal)  # fixed, never exceeds subtotal

def assemble_view_model(data: Dict[str, Any], config: InvoiceTemplateConfig) -> InvoiceViewModel:
    cur = data["meta"]["currency"] or "USD"
    fm = lambda v: format_money(v, cur)

    items = [ItemVM(
        description=i.get("description", ""), quantity=i.get("quantity", 0),
        unit_of_measure=i.get("unit_of_measure", "") or "",
        unit_price_raw=i.get("unit_price", 0.0), unit_price=fm(i.get("unit_price", 0.0)),
        amount_raw=i.get("amount", 0.0), amount=fm(i.get("amount", 0.0)),
    ) for i in data.get("items", [])]

    subtotal = float(data.get("amount", 0.0))
    d = data.get("discount") or {"type": "percentage", "value": 0.0}
    damt = _discount_amount(subtotal, d.get("type", "percentage"), float(d.get("value", 0.0)))
    total = subtotal - damt
    paid = float(data.get("paid_amount", 0.0))
    balance = total - paid

    totals = TotalsVM(
        subtotal_raw=subtotal, subtotal=fm(subtotal),
        discount_type=d.get("type", "percentage"), discount_value=float(d.get("value", 0.0)),
        discount_amount_raw=damt, discount_amount=fm(damt),
        total_raw=total, total=fm(total), paid_raw=paid, paid=fm(paid),
        balance_raw=balance, balance=fm(balance),
    )

    raw_cf = data.get("custom_fields") or {}
    custom_fields = [CustomFieldVM(label=k, value=v) for k, v in raw_cf.items()
                     if k not in _RESERVED_CUSTOM_KEYS]

    c = data["company"]
    logo = c.get("logo_url") if config.show.get("logo", True) else None
    company = CompanyVM(name=c.get("name", ""), logo_url=logo, address=c.get("address", ""),
                        phone=c.get("phone", ""), email=c.get("email", ""), tax_id=c.get("tax_id", ""))
    m = data["meta"]
    meta = MetaVM(number=m.get("number", ""), issue_date=m.get("issue_date", ""),
                  due_date=m.get("due_date", ""), status=m.get("status", ""),
                  currency=cur, show_discount=bool(m.get("show_discount", True)))
    cl = data["client"]
    client = ClientVM(name=cl.get("name", ""), email=cl.get("email", ""),
                      phone=cl.get("phone", ""), address=cl.get("address", ""))

    return InvoiceViewModel(company=company, meta=meta, client=client, items=items,
        totals=totals, custom_fields=custom_fields, notes=data.get("notes", "") or "",
        footer_text=config.footer_text)

def build_view_model(db, invoice, tenant, config: InvoiceTemplateConfig) -> InvoiceViewModel:
    """Adapt ORM objects into the `assemble_view_model` data dict.
    paid_amount = SUM(payments.amount) for this invoice."""
    from sqlalchemy import func
    from core.models.models_per_tenant import Payment
    paid = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.invoice_id == invoice.id).scalar() or 0.0
    client = invoice.client
    data = {
        "company": {"name": tenant.name, "logo_url": getattr(tenant, "company_logo_url", None),
            "address": getattr(tenant, "address", "") or "", "phone": getattr(tenant, "phone", "") or "",
            "email": getattr(tenant, "email", "") or "", "tax_id": getattr(tenant, "tax_id", "") or ""},
        "meta": {"number": invoice.number, "issue_date": str(invoice.created_at.date()) if invoice.created_at else "",
            "due_date": str(invoice.due_date.date()) if invoice.due_date else "",
            "status": invoice.status, "currency": invoice.currency,
            "show_discount": bool(getattr(invoice, "show_discount_in_pdf", True))},
        "client": {"name": getattr(client, "name", "") if client else "",
            "email": getattr(client, "email", "") if client else "",
            "phone": getattr(client, "phone", "") if client else "",
            "address": getattr(client, "address", "") if client else ""},
        "items": [{"description": it.description, "quantity": it.quantity,
            "unit_of_measure": getattr(it, "unit_of_measure", "") or "",
            "unit_price": float(it.price), "amount": float(it.amount)} for it in invoice.items],
        "amount": float(invoice.amount),
        "paid_amount": float(paid),
        "discount": {"type": invoice.discount_type, "value": float(invoice.discount_value or 0.0)},
        "custom_fields": invoice.custom_fields or {},
        "notes": invoice.notes or "",
    }
    return assemble_view_model(data, config)
```

Also create `api/core/services/invoice_render/__init__.py`:

```python
from core.services.invoice_render.config import InvoiceTemplateConfig, load_template_config
from core.services.invoice_render.view_model import (
    InvoiceViewModel, assemble_view_model, build_view_model)
__all__ = ["InvoiceTemplateConfig", "load_template_config",
           "InvoiceViewModel", "assemble_view_model", "build_view_model"]
```

- [ ] **Step 6: Run to verify pass**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_view_model.py -q --noconftest`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add api/core/services/invoice_render/ api/tests/test_invoice_view_model.py
git commit -m "feat(invoice-render): view-model + config (parity-critical data layer)"
```

---

### Task 2: Jinja HTML template + `render_invoice_html`

**Files:**
- Create: `api/core/services/invoice_render/renderer.py`, `templates/invoice/default.html`, `templates/invoice/default.css`
- Test: `api/tests/test_invoice_renderer.py`

**Interfaces:**
- Consumes: `InvoiceViewModel`, `InvoiceTemplateConfig` (Task 1).
- Produces: `render_invoice_html(vm, config) -> str`.

- [ ] **Step 1: Write the failing test** — `api/tests/test_invoice_renderer.py`

```python
from core.services.invoice_render.config import InvoiceTemplateConfig
from core.services.invoice_render.view_model import assemble_view_model
from core.services.invoice_render.renderer import render_invoice_html
from tests.test_invoice_view_model import _data, CFG  # reuse fixtures

def test_html_contains_core_fields():
    html = render_invoice_html(assemble_view_model(_data(), CFG), CFG)
    assert "INV-1" in html and "Acme" in html and "Bob" in html
    assert "$90.00" in html  # total

def test_html_hides_notes_when_toggled_off():
    cfg = InvoiceTemplateConfig(brand_color="#000", accent_color="#000", footer_text="",
        show={"logo": True, "notes": False, "custom_fields": True, "footer": True})
    html = render_invoice_html(assemble_view_model(_data(notes="SECRET"), cfg), cfg)
    assert "SECRET" not in html

def test_html_hides_discount_when_invoice_flag_off():
    html = render_invoice_html(assemble_view_model(_data(meta={**_data()["meta"], "show_discount": False}), CFG), CFG)
    assert "Discount" not in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_renderer.py -q --noconftest`
Expected: FAIL (no `renderer`).

- [ ] **Step 3: Implement `renderer.py` (HTML half) + the template**

```python
# api/core/services/invoice_render/renderer.py
"""Render an InvoiceViewModel + config to HTML (Jinja2) and PDF (WeasyPrint)."""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR),
                   autoescape=select_autoescape(["html", "xml"]))

def _css() -> str:
    with open(os.path.join(_TEMPLATE_DIR, "invoice", "default.css"), encoding="utf-8") as f:
        return f.read()

def render_invoice_html(vm, config) -> str:
    return _env.get_template("invoice/default.html").render(vm=vm, cfg=config, css=_css())
```

`templates/invoice/default.html` (real, minimal — polished visually later; uses `cfg.show` + `vm.meta.show_discount`):

```html
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{{ css }}</style></head>
<body>
<div class="invoice" style="--brand: {{ cfg.brand_color }}; --accent: {{ cfg.accent_color }};">
  <header class="head">
    {% if cfg.show.logo and vm.company.logo_url %}<img class="logo" src="{{ vm.company.logo_url }}">{% endif %}
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

  <section class="billto"><h3>Bill To</h3><div>{{ vm.client.name }}</div>
    <div>{{ vm.client.email }}</div><div>{{ vm.client.address }}</div></section>

  {% if cfg.show.custom_fields and vm.custom_fields %}
  <section class="custom"><h3>Details</h3>
    {% for cf in vm.custom_fields %}<div>{{ cf.label }}: {{ cf.value }}</div>{% endfor %}</section>
  {% endif %}

  <table class="items"><thead><tr><th>Description</th><th>Qty</th><th>Price</th><th>Amount</th></tr></thead>
    <tbody>{% for it in vm.items %}<tr><td>{{ it.description }}</td><td>{{ it.quantity }}</td>
      <td>{{ it.unit_price }}</td><td>{{ it.amount }}</td></tr>{% endfor %}</tbody></table>

  <section class="totals">
    <div><span>Subtotal</span><span>{{ vm.totals.subtotal }}</span></div>
    {% if vm.meta.show_discount and vm.totals.discount_amount_raw %}
      <div><span>Discount</span><span>-{{ vm.totals.discount_amount }}</span></div>{% endif %}
    <div class="grand"><span>Total</span><span>{{ vm.totals.total }}</span></div>
    <div><span>Paid</span><span>{{ vm.totals.paid }}</span></div>
    <div class="balance"><span>Balance Due</span><span>{{ vm.totals.balance }}</span></div>
  </section>

  {% if cfg.show.notes and vm.notes %}<section class="notes"><h3>Notes</h3><div>{{ vm.notes }}</div></section>{% endif %}
  {% if cfg.show.footer and vm.footer_text %}<footer class="foot">{{ vm.footer_text }}</footer>{% endif %}
</div>
</body></html>
```

`templates/invoice/default.css` (starter — visual polish is a later review step, but this is real working CSS):

```css
* { box-sizing: border-box; } body { font-family: "DejaVu Sans", Arial, sans-serif; color: #1f2937; margin: 0; }
.invoice { max-width: 800px; margin: 0 auto; padding: 32px; }
.head { display: flex; justify-content: space-between; border-bottom: 3px solid var(--brand); padding-bottom: 16px; }
.logo { max-height: 64px; } .company h1 { color: var(--brand); margin: 0 0 6px; font-size: 20px; }
.meta { text-align: right; } .meta h2 { color: var(--brand); margin: 0; letter-spacing: 2px; }
.meta .status { display: inline-block; margin-top: 6px; padding: 2px 10px; background: var(--accent); color: #fff; border-radius: 4px; text-transform: uppercase; font-size: 11px; }
.billto, .custom, .notes { margin-top: 20px; } h3 { color: var(--brand); font-size: 13px; text-transform: uppercase; }
table.items { width: 100%; border-collapse: collapse; margin-top: 20px; }
table.items th { background: var(--brand); color: #fff; text-align: left; padding: 8px; }
table.items td { border-bottom: 1px solid #e5e7eb; padding: 8px; }
table.items th:nth-child(n+2), table.items td:nth-child(n+2) { text-align: right; }
.totals { margin-top: 20px; width: 280px; margin-left: auto; }
.totals > div { display: flex; justify-content: space-between; padding: 4px 0; }
.totals .grand { border-top: 2px solid var(--brand); font-weight: 700; }
.totals .balance { border-top: 1px solid #e5e7eb; color: var(--accent); font-weight: 700; }
.foot { margin-top: 32px; text-align: center; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 12px; }
```

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_renderer.py::test_html_contains_core_fields tests/test_invoice_renderer.py::test_html_hides_notes_when_toggled_off tests/test_invoice_renderer.py::test_html_hides_discount_when_invoice_flag_off -q --noconftest`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api/core/services/invoice_render/renderer.py api/core/services/invoice_render/templates api/tests/test_invoice_renderer.py
git commit -m "feat(invoice-render): Jinja HTML template + render_invoice_html"
```

---

### Task 3: WeasyPrint PDF + Docker deps + threadpool

**Files:**
- Modify: `api/core/services/invoice_render/renderer.py` (add PDF fns), `api/requirements.txt` (+`weasyprint`), `api/Dockerfile` (system libs + font)
- Test: `api/tests/test_invoice_renderer.py` (add a `%PDF` smoke test — runs in-container, NOT `--noconftest`-only since it needs WeasyPrint installed)

**Interfaces:**
- Produces: `render_invoice_pdf(vm, config) -> bytes`; `render_invoice_pdf_async(vm, config) -> bytes` (awaitable, threadpool).

- [ ] **Step 1: Add deps**

`api/requirements.txt`: append `weasyprint==62.3`.
`api/Dockerfile`: in the system-package layer add:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev \
    fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Implement the PDF functions** (append to `renderer.py`)

```python
import asyncio
from weasyprint import HTML

def render_invoice_pdf(vm, config) -> bytes:
    html = render_invoice_html(vm, config)
    return HTML(string=html).write_pdf()

async def render_invoice_pdf_async(vm, config) -> bytes:
    # WeasyPrint is sync CPU work — offload so it never blocks the event loop.
    return await asyncio.get_event_loop().run_in_executor(None, render_invoice_pdf, vm, config)
```

- [ ] **Step 3: Write the smoke test** (append to `api/tests/test_invoice_renderer.py`)

```python
def test_render_pdf_returns_valid_pdf_bytes():
    from core.services.invoice_render.renderer import render_invoice_pdf
    pdf = render_invoice_pdf(assemble_view_model(_data(), CFG), CFG)
    assert isinstance(pdf, bytes) and pdf[:5] == b"%PDF-" and len(pdf) > 1000
```

- [ ] **Step 4: Rebuild the image + install + run**

```bash
docker compose build api
docker compose up -d --no-deps api
docker compose exec -T api pip install pytest==8.4.1 pytest-asyncio==1.1.0 pytest-mock==3.14.1 pytest-cov==6.2.1
docker compose exec -T api python -m pytest tests/test_invoice_renderer.py::test_render_pdf_returns_valid_pdf_bytes -q --noconftest
```
Expected: PASS — proves WeasyPrint + its system libs work in-container.

- [ ] **Step 5: Commit**

```bash
git add api/requirements.txt api/Dockerfile api/core/services/invoice_render/renderer.py api/tests/test_invoice_renderer.py
git commit -m "feat(invoice-render): WeasyPrint PDF (threadpool) + Docker deps"
```

---

### Task 4: PDF download + `/preview` endpoints

**Files:**
- Modify: the authenticated invoice PDF download route (find via `grep -rn "def .*pdf" api/core/routers/invoices/`) and add a preview route in the same router.
- Test: `api/tests/test_invoice_render_endpoints.py`

**Interfaces:**
- Consumes: `build_view_model`, `load_template_config`, `render_invoice_pdf_async`, `render_invoice_html`.
- Produces: `GET /api/v1/invoices/{id}/pdf` → `application/pdf`; `GET /api/v1/invoices/{id}/preview` → `text/html`.

- [ ] **Step 1: Write the failing endpoint test** — `api/tests/test_invoice_render_endpoints.py`

```python
# Integration test — runs in-container with conftest (real tenant fixtures).
import pytest

@pytest.mark.asyncio
async def test_preview_returns_html(async_client, seeded_invoice, auth_headers):
    r = await async_client.get(f"/api/v1/invoices/{seeded_invoice.id}/preview", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert seeded_invoice.number in r.text

@pytest.mark.asyncio
async def test_pdf_returns_pdf(async_client, seeded_invoice, auth_headers):
    r = await async_client.get(f"/api/v1/invoices/{seeded_invoice.id}/pdf", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
```

> The implementer reuses the existing invoice-test fixtures (`grep -rn "seeded_invoice\|auth_headers\|async_client" api/tests/conftest.py api/tests/`); if none match, build the invoice via the existing create-invoice test helper.

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_render_endpoints.py -q`
Expected: FAIL (routes 404).

- [ ] **Step 3: Implement the routes** (in the invoices router)

```python
from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from core.services.invoice_render import build_view_model, load_template_config
from core.services.invoice_render.renderer import render_invoice_html, render_invoice_pdf_async

def _load_invoice_tenant(db, master_db, invoice_id, current_user):
    from core.models.models_per_tenant import Invoice
    from core.models.models import Tenant
    inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.is_deleted == False).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    tenant = master_db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    return inv, tenant

@router.get("/{invoice_id}/preview")
async def preview_invoice(invoice_id: int, db=Depends(get_db), master_db=Depends(get_master_db),
                          current_user=Depends(get_current_user)):
    inv, tenant = _load_invoice_tenant(db, master_db, invoice_id, current_user)
    cfg = load_template_config(db)
    html = render_invoice_html(build_view_model(db, inv, tenant, cfg), cfg)
    return HTMLResponse(content=html)

@router.get("/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: int, db=Depends(get_db), master_db=Depends(get_master_db),
                      current_user=Depends(get_current_user)):
    inv, tenant = _load_invoice_tenant(db, master_db, invoice_id, current_user)
    cfg = load_template_config(db)
    pdf = await render_invoice_pdf_async(build_view_model(db, inv, tenant, cfg), cfg)
    return Response(content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="invoice-{inv.number}.pdf"'})
```

> If a `…/pdf` route already exists (ReportLab), replace its body with the above; keep the old `pdf_generator` import only if other non-invoice callers use it (`grep -rn "pdf_generator" api/`).

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec -T api python -m pytest tests/test_invoice_render_endpoints.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api/core/routers/invoices/ api/tests/test_invoice_render_endpoints.py
git commit -m "feat(invoice-render): PDF download + HTML preview endpoints"
```

---

### Task 5: Email attachment + portal/share wiring

**Files:**
- Modify: `api/core/services/email_service.py` (invoice send → attach `render_invoice_pdf`), `api/core/routers/share_tokens.py` + `api/core/routers/client_portal.py` (serve `render_invoice_html`).
- Test: extend `api/tests/test_invoice_render_endpoints.py` (public share returns HTML).

**Interfaces:** Consumes Task 1–3 functions. The public share path must use the **public-safe** view-model (reuse `api/core/schemas/share_token.py`'s public invoice subset — do not expose internal fields).

- [ ] **Step 1: Failing test** — public share renders the template HTML

```python
@pytest.mark.asyncio
async def test_public_share_invoice_renders_template(async_client, shared_invoice_token):
    r = await async_client.get(f"/api/v1/share/{shared_invoice_token}")
    assert r.status_code == 200 and "INVOICE" in r.text.upper()
```

- [ ] **Step 2: Run → fails.** `docker compose exec -T api python -m pytest tests/test_invoice_render_endpoints.py::test_public_share_invoice_renders_template -q`

- [ ] **Step 3: Implement.**
  - In the share-token invoice view handler, build a config + a public-safe view-model from the public invoice subset and return `HTMLResponse(render_invoice_html(vm, cfg))`.
  - In `email_service.py` invoice-send, replace the ReportLab attachment with: `cfg = load_template_config(db); pdf = render_invoice_pdf(build_view_model(db, invoice, tenant, cfg), cfg)`; attach as `invoice-{number}.pdf`. (Email body unchanged. The send path is a worker/sync context, so the sync `render_invoice_pdf` is fine here — only the async HTTP endpoints need the `_async` variant.)

- [ ] **Step 4: Run → passes.** Same command. Plus manually verify a send: `grep -rn "ReportLab\|pdf_generator\|build_invoice_pdf" api/core/services/email_service.py` returns nothing for the invoice path.

- [ ] **Step 5: Commit** `git commit -am "feat(invoice-render): unified PDF in email + portal/share HTML"`

---

### Task 6: Frontend — preview iframe + server PDF; retire react-pdf

**Files:**
- Modify: `ui/src/pages/ViewInvoice.tsx`, `ui/src/pages/SharedRecord.tsx`
- Reference to retire: `ui/src/components/invoices/InvoicePDF.tsx`

**Interfaces:** Consumes `GET /invoices/{id}/preview` (HTML) + `GET /invoices/{id}/pdf`.

- [ ] **Step 1:** In `ViewInvoice.tsx`, fetch the preview HTML and render it sandboxed:

```tsx
const [previewHtml, setPreviewHtml] = useState<string>("");
useEffect(() => {
  apiRequest<string>(`/invoices/${id}/preview`, { raw: true }).then(setPreviewHtml).catch(() => {});
}, [id]);
// …in render:
<iframe title="Invoice preview" sandbox="" srcDoc={previewHtml} className="w-full min-h-[1000px] border rounded" />
```
(If `apiRequest` can't return raw text, add a small `fetchText` helper using the same auth headers.)

- [ ] **Step 2:** Change "Download PDF" to open the server endpoint instead of react-pdf:

```tsx
const downloadPdf = () => window.open(`${API_BASE_URL}/invoices/${id}/pdf`, "_blank");
```
Remove the `InvoicePDF`/`@react-pdf/renderer` import and its usage from `ViewInvoice.tsx`.

- [ ] **Step 3:** In `SharedRecord.tsx`, render the server-provided invoice HTML in the same sandboxed iframe (the public share endpoint now returns HTML).

- [ ] **Step 4: Verify** the Vite dev build is clean (`docker compose logs ui --since 30s | grep -i error` → none) and load `:8080` → the invoice view shows the templated preview and Download PDF returns the WeasyPrint PDF.

- [ ] **Step 5: Commit** `git commit -am "feat(invoice-render): web view + share render the unified template; retire react-pdf"`

---

### Task 7: Retire the ReportLab invoice path + final review

**Files:**
- Modify: `api/core/utils/pdf_generator.py` (mark the invoice-PDF entrypoints dormant — keep one release) — only if no non-invoice caller remains (`grep -rn "pdf_generator" api/`).
- Modify: `ui/src/components/invoices/InvoicePDF.tsx` — leave the file but remove all imports of it (already done in Task 6); add a top-of-file comment marking it deprecated/dormant.

- [ ] **Step 1:** `grep -rn "pdf_generator\|InvoicePDF" api/ ui/src/` — confirm no live invoice caller remains (only the dormant files themselves).
- [ ] **Step 2:** Add deprecation header comments to both dormant files referencing this plan + the removal-next-release note.
- [ ] **Step 3:** Run the full new suite in-container: `docker compose exec -T api python -m pytest tests/test_invoice_view_model.py tests/test_invoice_renderer.py tests/test_invoice_render_endpoints.py -q` → all pass.
- [ ] **Step 4: Commit** `git commit -am "chore(invoice-render): retire ReportLab/react-pdf invoice paths (dormant one release)"`

---

## Self-Review notes (for the executor)

- **Parity:** confirm `_discount_amount` matches `pdf_generator.py` `_build_totals` (percentage = subtotal×value/100; fixed capped at subtotal) before trusting Task 1.
- **Currency:** `money.format_money` is a small static map — if a tenant uses a currency not in `_SYMBOLS`, it renders `"<amount> <CODE>"`. Acceptable; extend the map if QA finds a gap.
- **Public-safe rendering (Task 5):** never pass the full ORM invoice to the public share renderer — only the public subset, or internal fields (e.g. internal notes) could leak.
- **Threadpool (Task 3/4):** the `…/pdf` endpoint MUST use `render_invoice_pdf_async`, not the sync version, or it blocks the event loop under load.
