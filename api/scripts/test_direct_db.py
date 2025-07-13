from models.database import SessionLocal
from models.models import User, Payment, Invoice, Client

def test_direct_db():
    db = SessionLocal()
    try:
        # Get a user (assuming there's at least one user)
        user = db.query(User).first()
        if not user:
            print("No user found in database")
            return
        
        print(f"Testing with user: {user.email}")
        print(f"Current user's tenant_id: {user.tenant_id}")
        
        # List all payments and their tenant IDs
        print("\nAll payments in the database:")
        payments = db.query(Payment).order_by(Payment.id).all()
        for payment in payments:
            print(f"  Payment #{payment.id} - tenant_id: {payment.tenant_id} - invoice_id: {payment.invoice_id} - amount: {payment.amount}")
        
        # List payments for the current user's tenant
        print(f"\nPayments for tenant_id {user.tenant_id}:")
        payments = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).filter(
            Payment.tenant_id == user.tenant_id
        ).order_by(Payment.id).all()

        print(f"Direct database query returned {len(payments)} payments:")
        for payment, invoice_number, client_name in payments:
            print(f"  Payment #{payment.id} - Invoice #{invoice_number} - Amount: ${payment.amount} - Method: {payment.payment_method} - Date: {payment.payment_date}")
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_direct_db() 