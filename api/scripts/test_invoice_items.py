from core.models.database import SessionLocal
from core.models.models import Invoice, Item, Client
import json

def test_invoice_with_items():
    """Test script to verify invoice items are correctly returned in API response"""
    db = SessionLocal()
    try:
        # Get the first invoice from the database
        invoice = db.query(Invoice).first()
        
        if not invoice:
            print("No invoices found in database")
            return
        
        print(f"Found invoice ID: {invoice.id}, Number: {invoice.number}")
        
        # Get client information
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        client_name = client.name if client else "Unknown client"
        
        # Get items for this invoice
        items = db.query(Item).filter(Item.invoice_id == invoice.id).all()
        print(f"Found {len(items)} items for invoice {invoice.number}")
        
        for i, item in enumerate(items, 1):
            print(f"  Item {i}: {item.description}, Quantity: {item.quantity}, Price: {item.price}")
        
        # Create a response similar to what the API would return
        invoice_dict = invoice.__dict__.copy()
        # Remove SQLAlchemy state
        if "_sa_instance_state" in invoice_dict:
            del invoice_dict["_sa_instance_state"]
            
        invoice_dict["client_name"] = client_name
        invoice_dict["items"] = []
        
        for item in items:
            item_dict = item.__dict__.copy()
            if "_sa_instance_state" in item_dict:
                del item_dict["_sa_instance_state"]
            invoice_dict["items"].append(item_dict)
        
        # Convert datetime objects to strings
        invoice_dict["created_at"] = str(invoice_dict["created_at"])
        invoice_dict["updated_at"] = str(invoice_dict["updated_at"])
        invoice_dict["date"] = str(invoice_dict["date"])
        invoice_dict["due_date"] = str(invoice_dict["due_date"])
        
        for item in invoice_dict["items"]:
            if "created_at" in item:
                item["created_at"] = str(item["created_at"])
            if "updated_at" in item:
                item["updated_at"] = str(item["updated_at"])
        
        # Print what the API response would look like
        print("\nAPI Response would look like:")
        pretty_json = json.dumps(invoice_dict, indent=2)
        print(pretty_json)
        
        # Check if items are present
        if len(invoice_dict["items"]) == 0:
            print("\nWARNING: No items found for this invoice. UI may display empty items.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    test_invoice_with_items() 