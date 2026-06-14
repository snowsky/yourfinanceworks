"""Regression tests for invoice-item serialization in the send-invoice email path.

Bug: the handler called ``item.model_dump()`` on SQLAlchemy ``InvoiceItem`` ORM
rows, which are not Pydantic models, raising
``'InvoiceItem' object has no attribute 'model_dump'`` and returning HTTP 500.
"""
from types import SimpleNamespace

from core.routers.email import _serialize_invoice_items


def _orm_item(**kwargs):
    """An ORM-like row: a plain object WITHOUT a ``model_dump`` method."""
    item = SimpleNamespace(**kwargs)
    assert not hasattr(item, "model_dump")
    return item


def test_serializes_orm_items_to_dicts():
    invoice = SimpleNamespace(items=[
        _orm_item(description="Design work", quantity=2, price=50.0,
                  amount=100.0, unit_of_measure="hr"),
    ])

    result = _serialize_invoice_items(invoice)

    assert result == [{
        "description": "Design work",
        "quantity": 2,
        "price": 50.0,
        "amount": 100.0,
        "unit_of_measure": "hr",
    }]


def test_returns_empty_list_when_no_items():
    assert _serialize_invoice_items(SimpleNamespace(items=[])) == []
    assert _serialize_invoice_items(SimpleNamespace(items=None)) == []
    assert _serialize_invoice_items(SimpleNamespace()) == []
