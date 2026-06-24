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
    name: str
    logo_url: Optional[str]
    address: str
    phone: str
    email: str
    tax_id: str


@dataclass
class MetaVM:
    number: str
    issue_date: str
    due_date: str
    status: str
    currency: str
    show_discount: bool


@dataclass
class ClientVM:
    name: str
    email: str
    phone: str
    address: str


@dataclass
class ItemVM:
    description: str
    quantity: float
    unit_of_measure: str
    unit_price_raw: float
    unit_price: str
    amount_raw: float
    amount: str


@dataclass
class TotalsVM:
    subtotal_raw: float
    subtotal: str
    discount_type: str
    discount_value: float
    discount_amount_raw: float
    discount_amount: str
    total_raw: float
    total: str
    paid_raw: float
    paid: str
    balance_raw: float
    balance: str


@dataclass
class CustomFieldVM:
    label: str
    value: Any


@dataclass
class InvoiceViewModel:
    company: CompanyVM
    meta: MetaVM
    client: ClientVM
    items: List[ItemVM]
    totals: TotalsVM
    custom_fields: List[CustomFieldVM]
    notes: str
    footer_text: str


def _discount_amount(subtotal: float, dtype: str, dvalue: float) -> float:
    if not dvalue:
        return 0.0
    if dtype == "percentage":
        return subtotal * (dvalue / 100.0)
    return min(dvalue, subtotal)  # fixed, never exceeds subtotal


def assemble_view_model(data: Dict[str, Any], config: InvoiceTemplateConfig, public: bool = False) -> InvoiceViewModel:
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

    if public:
        custom_fields: List[CustomFieldVM] = []
    else:
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
    if public:
        client = ClientVM(name=cl.get("name", ""), email="", phone="", address="")
    else:
        client = ClientVM(name=cl.get("name", ""), email=cl.get("email", ""),
                          phone=cl.get("phone", ""), address=cl.get("address", ""))

    notes = "" if public else (data.get("notes", "") or "")

    return InvoiceViewModel(company=company, meta=meta, client=client, items=items,
        totals=totals, custom_fields=custom_fields, notes=notes,
        footer_text=config.footer_text)


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


def build_view_model(db, invoice, tenant, config: InvoiceTemplateConfig, public: bool = False) -> InvoiceViewModel:
    """Adapt ORM objects into the `assemble_view_model` data dict.
    paid_amount = SUM(payments.amount) for this invoice.

    ORM field mapping (verified against models_per_tenant.py / models.py):
    - Invoice: .number, .created_at, .due_date, .status, .currency, .amount,
               .discount_type, .discount_value, .show_discount_in_pdf,
               .custom_fields, .notes, .client, .items
    - InvoiceItem: .description, .quantity, .price (unit price), .amount, .unit_of_measure
    - Payment: .amount, .invoice_id
    - Client: .name, .email, .phone, .address
    - Tenant: .name, .company_logo_url, .address, .phone, .email, .tax_id
    """
    from sqlalchemy import func
    from core.models.models_per_tenant import Payment
    paid = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.invoice_id == invoice.id).scalar() or 0.0
    client = invoice.client
    data = {
        "company": {
            "name": tenant.name if tenant else "",
            "logo_url": getattr(tenant, "company_logo_url", None),
            "address": getattr(tenant, "address", "") or "",
            "phone": getattr(tenant, "phone", "") or "",
            "email": getattr(tenant, "email", "") or "",
            "tax_id": getattr(tenant, "tax_id", "") or "",
        },
        "meta": {
            "number": invoice.number,
            "issue_date": str(invoice.created_at.date()) if invoice.created_at else "",
            "due_date": str(invoice.due_date.date()) if invoice.due_date else "",
            "status": invoice.status,
            "currency": invoice.currency,
            "show_discount": bool(getattr(invoice, "show_discount_in_pdf", True)),
        },
        "client": {
            "name": getattr(client, "name", "") if client else "",
            "email": getattr(client, "email", "") if client else "",
            "phone": getattr(client, "phone", "") if client else "",
            "address": getattr(client, "address", "") if client else "",
        },
        "items": [
            {
                "description": it.description,
                "quantity": it.quantity,
                "unit_of_measure": getattr(it, "unit_of_measure", "") or "",
                "unit_price": float(it.price),  # ORM field is 'price', not 'unit_price'
                "amount": float(it.amount),
            }
            for it in invoice.items
        ],
        "amount": float(invoice.subtotal),  # pre-discount; assemble_view_model applies discount
        "paid_amount": float(paid),
        "discount": {
            "type": invoice.discount_type,
            "value": float(invoice.discount_value or 0.0),
        },
        "custom_fields": invoice.custom_fields or {},
        "notes": invoice.notes or "",
    }
    return assemble_view_model(data, config, public=public)
