"""Invoice history endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, User
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.schemas.invoice import InvoiceHistory, InvoiceHistoryCreate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{invoice_id}/history")
async def get_invoice_history(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get update history for a specific invoice, including user name"""
    # Set tenant context for proper decryption of user names
    from core.models.database import set_tenant_context
    set_tenant_context(current_user.tenant_id)

    try:
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

        # Verify invoice exists (allow access to history for deleted invoices)
        # No tenant_id filtering needed since we're in the tenant's database
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Get history entries first
        history_entries = (
            db.query(InvoiceHistoryModel)
            .filter(InvoiceHistoryModel.invoice_id == invoice_id)
            .order_by(InvoiceHistoryModel.created_at.desc())
            .all()
        )

        # Get unique user IDs from history
        user_ids = list(set(h.user_id for h in history_entries))

        # Fetch users separately to ensure proper decryption
        users = {}
        if user_ids:
            user_records = db.query(User).filter(User.id.in_(user_ids)).all()
            for user in user_records:
                # Access the encrypted fields to trigger decryption
                first_name = user.first_name or ''
                last_name = user.last_name or ''
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    # Fallback to email if no name
                    full_name = user.email or f"User {user.id}"
                users[user.id] = full_name

        # Return as list of dicts with user_name
        result = []
        for h in history_entries:
            entry = h.__dict__.copy()
            entry["user_name"] = users.get(h.user_id, f"User {h.user_id}")
            result.append(entry)

        # Return only the actual history entries from the database
        # The invoice's updated_at is already reflected in the latest history entry
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching invoice history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch invoice history")


@router.post("/{invoice_id}/history", response_model=InvoiceHistory)
async def create_invoice_history_entry(
    invoice_id: int,
    history_entry: InvoiceHistoryCreate,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Create a new history entry for an invoice"""
    try:
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel

        # Verify invoice exists (no tenant_id filtering needed since we're in the tenant's database)
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id
        ).first()

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        # Create history entry
        db_history = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action=history_entry.action,
            details=history_entry.details,
            previous_values=history_entry.previous_values,
            current_values=history_entry.current_values
        )

        db.add(db_history)
        db.commit()
        db.refresh(db_history)

        return db_history

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invoice history entry: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create invoice history entry"
        )
