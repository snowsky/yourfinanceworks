from models.database import SessionLocal
from models.models import Payment, Invoice, Client

def test_payments():
    db = SessionLocal()
    try:
        # Get all payments with invoice and client info
        payments = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).order_by(Payment.id).all()
        
        print(f'Total payments found: {len(payments)}')
        print('\nAll payments:')
        for payment, invoice_number, client_name in payments:
            print(f'Payment ID: {payment.id}, Invoice: {invoice_number}, Client: {client_name}, Amount: ${payment.amount}, Method: {payment.payment_method}, Date: {payment.payment_date}')
        
        # Check if there are any gaps in payment IDs
        payment_ids = [p.id for p, _, _ in payments]
        if payment_ids:
            print(f'\nPayment IDs: {payment_ids}')
            expected_ids = list(range(1, max(payment_ids) + 1))
            missing_ids = set(expected_ids) - set(payment_ids)
            if missing_ids:
                print(f'Missing payment IDs: {sorted(missing_ids)}')
            else:
                print('No missing payment IDs')
        
    except Exception as e:
        print(f'Error: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_payments() 