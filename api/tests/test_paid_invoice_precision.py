"""Paid invoices must retain all four decimal places of line-item precision."""

import pytest

from tests.test_invoices import auth_headers, test_client_id


@pytest.mark.parametrize(
    "quantity,price,new_quantity,new_price",
    [(1, 10000, 1.004, 10000), (10000, 1, 10000, 1.004)],
)
def test_paid_invoice_rejects_subcent_item_changes(
    client, auth_headers, test_client_id, quantity, price, new_quantity, new_price
):
    response = client.post(
        "/api/v1/invoices/",
        headers=auth_headers,
        json={
            "client_id": test_client_id,
            "amount": 10000,
            "paid_amount": 10000,
            "status": "paid",
            "items": [{"description": "Consulting", "quantity": quantity, "price": price}],
        },
    )
    assert response.status_code == 201, response.text
    invoice = response.json()
    item = invoice["items"][0]

    response = client.put(
        f"/api/v1/invoices/{invoice['id']}",
        headers=auth_headers,
        json={
            "status": "paid",
            "items": [{
                "id": item["id"],
                "description": item["description"],
                "quantity": new_quantity,
                "price": new_price,
            }],
        },
    )
    assert response.status_code == 400, response.text
    saved = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers).json()
    assert saved["amount"] == 10000
    assert saved["items"][0]["quantity"] == quantity
    assert saved["items"][0]["price"] == price
