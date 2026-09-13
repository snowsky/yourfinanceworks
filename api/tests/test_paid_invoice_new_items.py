"""New items on paid invoices must return a validation error, not a server error."""

import pytest

from tests.test_invoices import auth_headers, test_client_id


@pytest.mark.parametrize("new_item_first", [False, True])
def test_paid_invoice_rejects_mixed_existing_and_new_items(
    client, auth_headers, test_client_id, new_item_first
):
    response = client.post(
        "/api/v1/invoices/",
        headers=auth_headers,
        json={
            "client_id": test_client_id,
            "amount": 100,
            "paid_amount": 100,
            "status": "paid",
            "items": [{"description": "Consulting", "quantity": 1, "price": 100}],
        },
    )
    assert response.status_code == 201, response.text
    invoice = response.json()
    existing = invoice["items"][0]
    items = [
        {key: existing[key] for key in ("id", "description", "quantity", "price")},
        {"description": "New line", "quantity": 1, "price": 10},
    ]
    if new_item_first:
        items.reverse()

    response = client.put(
        f"/api/v1/invoices/{invoice['id']}",
        headers=auth_headers,
        json={"status": "paid", "items": items},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Line items on a paid invoice cannot be modified"
    response = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["amount"] == 100
    assert [item["id"] for item in saved["items"]] == [existing["id"]]
