from core.models.database import SessionLocal
from core.models.models import Payment, Invoice, Client

def test_payments_query():
    db = SessionLocal()
    try:
        # Query payments with explicit joins
        result = db.query(
            Payment,
            Invoice.number.label('invoice_number'),
            Client.name.label('client_name')
        ).select_from(Payment).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).join(
            Client, Invoice.client_id == Client.id
        ).all()
        
        print(f'Number of joined results: {len(result)}')
        
        if result:
            payment = result[0][0]
            invoice_number = result[0][1]
            client_name = result[0][2]
            
            print(f'First result: Payment ID={payment.id}, Invoice Number={invoice_number}, Client Name={client_name}')
            
            # Test constructing the dictionary directly
            payment_dict = {
                "id": payment.id,
                "invoice_id": payment.invoice_id,
                "amount": payment.amount,
                "date": payment.date,
                "method": payment.method,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at,
                "invoice_number": invoice_number,
                "client_name": client_name
            }
            
            print(f'Payment dict: {payment_dict}')
        else:
            print('No results found')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_payments_query() 