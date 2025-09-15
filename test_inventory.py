#!/usr/bin/env python3

import requests
import json

API_BASE_URL = "http://localhost:8000/api/v1"

def login():
    """Login and get authentication token"""
    login_data = {
        "email": "a@a.com",
        "password": "123456"
    }

    response = requests.post(f"{API_BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print(f"Login successful, token: {token[:20]}...")
        return token
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_inventory_endpoints(token):
    """Test inventory endpoints"""
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "1",
        "Content-Type": "application/json"
    }

    print("\n=== Testing Inventory Categories ===")

    # Test getting categories
    response = requests.get(f"{API_BASE_URL}/inventory/categories", headers=headers)
    print(f"GET categories: {response.status_code}")
    if response.status_code == 200:
        categories = response.json()
        print(f"Found {len(categories)} categories")
    else:
        print(f"Error: {response.text}")

    # Check existing categories
    print(f"Existing categories: {len(categories)}")
    for cat in categories:
        print(f"  - {cat['name']} (ID: {cat['id']})")

    # Test creating a category with unique name
    category_data = {
        "name": f"Test Category {len(categories) + 1}",
        "description": "Test category for inventory",
        "color": "#FF5733",
        "is_active": True
    }

    response = requests.post(f"{API_BASE_URL}/inventory/categories", json=category_data, headers=headers)
    print(f"POST category: {response.status_code}")
    if response.status_code == 200:
        category = response.json()
        print(f"Created category: {category['name']} (ID: {category['id']})")
        category_id = category['id']
    else:
        print(f"Error: {response.text}")
        return

    print("\n=== Testing Inventory Items ===")

    # Test creating an item with unique name and SKU
    item_data = {
        "name": f"Test Item {category_id}",
        "description": "Test inventory item",
        "sku": f"TEST{category_id:03d}",
        "category_id": category_id,
        "unit_price": 10.99,
        "cost_price": 8.50,
        "currency": "USD",
        "track_stock": True,
        "current_stock": 100,
        "minimum_stock": 10,
        "unit_of_measure": "pieces",
        "item_type": "product",
        "is_active": True
    }

    response = requests.post(f"{API_BASE_URL}/inventory/items", json=item_data, headers=headers)
    print(f"POST item: {response.status_code}")
    if response.status_code == 200:
        item = response.json()
        print(f"Created item: {item['name']} (ID: {item['id']})")
        item_id = item['id']
    else:
        print(f"Error: {response.text}")
        return

    print("\n=== Testing Invoice Integration ===")

    # Test populating invoice item from inventory (using query parameters)
    params = {
        "inventory_item_id": item_id,
        "quantity": 5
    }

    response = requests.post(f"{API_BASE_URL}/inventory/invoice-items/populate", params=params, headers=headers)
    print(f"POST populate invoice item: {response.status_code}")
    if response.status_code == 200:
        populated_data = response.json()
        print(f"Populated data: {populated_data}")
    else:
        print(f"Error: {response.text}")

    # Test validating stock
    validate_data = [{
        "inventory_item_id": item_id,
        "quantity": 5
    }]

    response = requests.post(f"{API_BASE_URL}/inventory/invoice-items/validate-stock", json=validate_data, headers=headers)
    print(f"POST validate stock: {response.status_code}")
    if response.status_code == 200:
        validation_result = response.json()
        print(f"Validation result: {validation_result}")
    else:
        print(f"Error: {response.text}")

    print("\n=== Testing Invoice Creation with Inventory ===")

    # Get clients first
    response = requests.get(f"{API_BASE_URL}/clients/", headers=headers)
    print(f"GET clients: {response.status_code}")
    clients = []
    if response.status_code == 200:
        clients = response.json()
        print(f"Found {len(clients)} clients")
        if len(clients) == 0:
            print("No clients found, cannot test invoice creation")
            return
    else:
        print(f"Error getting clients: {response.text}")
        return

    # Calculate total amount from items
    total_amount = populated_data["quantity"] * populated_data["price"]

    # Create an invoice with the inventory item
    invoice_data = {
        "client_id": clients[0]["id"],
        "number": f"INV-{item_id:04d}",
        "amount": total_amount,  # Required field
        "currency": "USD",
        "date": "2025-09-15",
        "due_date": "2025-10-15",
        "status": "pending",
        "paid_amount": 0,
        "items": [{
            "id": None,
            "description": populated_data["description"],
            "quantity": populated_data["quantity"],
            "price": populated_data["price"],
            "inventory_item_id": item_id,
            "unit_of_measure": populated_data["unit_of_measure"]
        }],
        "notes": "Test invoice created from inventory",
        "is_recurring": False,
        "recurring_frequency": "",
        "discount_type": "percentage",
        "discount_value": 0,
        "custom_fields": {},
        "show_discount_in_pdf": False
    }

    print(f"Creating invoice with data: {invoice_data}")

    response = requests.post(f"{API_BASE_URL}/invoices/", json=invoice_data, headers=headers)
    print(f"POST create invoice: {response.status_code}")
    if response.status_code in [200, 201]:
        created_invoice = response.json()
        invoice_id = created_invoice['id']
        print(f"✅ Invoice created successfully! ID: {invoice_id}, Number: {created_invoice['number']}")
        print(f"Invoice amount: {created_invoice['amount']}, Status: {created_invoice['status']}")

        # Now update the invoice status to 'paid' to trigger stock movements
        print("\n--- Updating invoice status to 'paid' to trigger stock movements ---")
        update_data = {
            "status": "paid"
        }

        response = requests.put(f"{API_BASE_URL}/invoices/{invoice_id}", json=update_data, headers=headers)
        print(f"PUT update invoice status: {response.status_code}")
        if response.status_code == 200:
            updated_invoice = response.json()
            print(f"✅ Invoice status updated to: {updated_invoice['status']}")

            # Now check if stock was reduced
            response = requests.get(f"{API_BASE_URL}/inventory/items/{item_id}", headers=headers)
            if response.status_code == 200:
                updated_item = response.json()
                print(f"Updated stock level: {updated_item['current_stock']} (was 100)")
                stock_reduced = 100.0 - updated_item['current_stock']
                print(f"Stock reduced by: {stock_reduced} units")

                # Check stock movements
                response = requests.get(f"{API_BASE_URL}/inventory/items/{item_id}/stock/movements", headers=headers)
                if response.status_code == 200:
                    movements = response.json()
                    print(f"Stock movements recorded: {len(movements)}")
                    if len(movements) > 0:
                        print(f"Latest movement: {movements[0]['movement_type']} {abs(movements[0]['quantity'])} units")
                        print(f"Movement reference: {movements[0].get('reference_type', 'N/A')} - {movements[0].get('reference_id', 'N/A')}")
        else:
            print(f"❌ Error updating invoice status: {response.text}")

    else:
        print(f"❌ Error creating invoice: {response.text}")
        print(f"Response status: {response.status_code}")
        try:
            error_data = response.json()
            print(f"Error details: {error_data}")
        except:
            print(f"Raw response: {response.text}")

if __name__ == "__main__":
    print("Testing Inventory API...")
    token = login()
    if token:
        test_inventory_endpoints(token)
    else:
        print("Cannot proceed without authentication token")
