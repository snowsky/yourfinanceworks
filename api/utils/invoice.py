from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.models import Invoice

def generate_invoice_number(db: Session, tenant_id: int) -> str:
    """
    Generate a unique invoice number for a tenant.
    Format: INV-{YYYYMMDD}-{XXXX} where XXXX is a sequential number
    """
    # Get the current date in YYYYMMDD format
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    
    # Find the latest invoice number for today
    latest_invoice = db.query(Invoice).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.number.like(f"INV-{date_prefix}-%")
    ).order_by(Invoice.number.desc()).first()
    
    if latest_invoice:
        # Extract the sequence number and increment it
        try:
            sequence = int(latest_invoice.number.split("-")[-1])
            new_sequence = sequence + 1
        except (ValueError, IndexError):
            new_sequence = 1
    else:
        new_sequence = 1
    
    # Format the new invoice number
    return f"INV-{date_prefix}-{new_sequence:04d}" 