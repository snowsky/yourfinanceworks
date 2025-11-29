from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
import logging
import os
from pathlib import Path

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, Client, BankStatement
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.routers.expenses import Expense

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments", tags=["attachments"])

@router.get("/search")
async def search_attachments(
    query: str = Query(..., min_length=1, description="Search query for attachment filenames"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type: invoice, expense, or statement"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Search for attachments across invoices, expenses, and bank statements"""
    try:
        results = []
        
        # Search invoices
        if not entity_type or entity_type == "invoice":
            invoice_results = db.query(
                Invoice.id,
                Invoice.number,
                Invoice.attachment_filename,
                Invoice.attachment_path,
                Invoice.created_at,
                Client.name.label('client_name')
            ).join(
                Client, Invoice.client_id == Client.id
            ).filter(
                and_(
                    Invoice.is_deleted == False,
                    Invoice.attachment_filename.isnot(None),
                    Invoice.attachment_filename.ilike(f"%{query}%")
                )
            ).all()
            
            for inv in invoice_results:
                file_exists = os.path.exists(inv.attachment_path) if inv.attachment_path else False
                results.append({
                    "id": inv.id,
                    "entity_type": "invoice",
                    "entity_number": inv.number,
                    "entity_name": f"Invoice {inv.number}",
                    "client_name": inv.client_name,
                    "filename": inv.attachment_filename,
                    "file_path": inv.attachment_path,
                    "file_exists": file_exists,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    "preview_url": f"/api/v1/invoices/{inv.id}/preview-attachment",
                    "download_url": f"/api/v1/invoices/{inv.id}/download-attachment"
                })
        
        # Search expenses
        if not entity_type or entity_type == "expense":
            try:
                expense_results = db.query(
                    Expense.id,
                    Expense.receipt_filename,
                    Expense.vendor,
                    Expense.category,
                    Expense.expense_date
                ).filter(
                    and_(
                        Expense.receipt_filename.isnot(None),
                        Expense.receipt_filename.ilike(f"%{query}%")
                    )
                ).all()
                
                for exp in expense_results:
                    # Check if file exists in attachments directory
                    from core.models.database import get_tenant_context
                    tenant_id = get_tenant_context()
                    tenant_folder = f"tenant_{tenant_id}" if tenant_id else "tenant_unknown"
                    file_path = Path("attachments") / tenant_folder / "expenses" / exp.receipt_filename
                    file_exists = file_path.exists()
                    
                    results.append({
                        "id": exp.id,
                        "entity_type": "expense",
                        "entity_number": f"#{exp.id}",
                        "entity_name": f"Expense #{exp.id}",
                        "client_name": exp.vendor or "Unknown Vendor",
                        "filename": exp.receipt_filename,
                        "file_path": str(file_path),
                        "file_exists": file_exists,
                        "created_at": exp.expense_date.isoformat() if exp.expense_date else None,
                        "preview_url": f"/api/v1/expenses/{exp.id}/attachments/preview",
                        "download_url": f"/api/v1/expenses/{exp.id}/attachments/download"
                    })
            except Exception as e:
                logger.warning(f"Error searching expenses: {e}")
        
        # Search bank statements
        if not entity_type or entity_type == "statement":
            try:
                statement_results = db.query(
                    BankStatement.id,
                    BankStatement.original_filename,
                    BankStatement.file_path,
                    BankStatement.created_at
                ).filter(
                    BankStatement.original_filename.ilike(f"%{query}%")
                ).all()
                
                for stmt in statement_results:
                    file_exists = os.path.exists(stmt.file_path) if stmt.file_path else False
                    results.append({
                        "id": stmt.id,
                        "entity_type": "statement",
                        "entity_number": f"#{stmt.id}",
                        "entity_name": f"Statement {stmt.original_filename}",
                        "client_name": "Bank Statement",
                        "filename": stmt.original_filename,
                        "file_path": stmt.file_path,
                        "file_exists": file_exists,
                        "created_at": stmt.created_at.isoformat() if stmt.created_at else None,
                        "preview_url": f"/api/v1/bank-statements/{stmt.id}/preview",
                        "download_url": f"/api/v1/bank-statements/{stmt.id}/download"
                    })
            except Exception as e:
                logger.warning(f"Error searching bank statements: {e}")
        
        # Sort results by creation date (newest first)
        results.sort(key=lambda x: x["created_at"] or "", reverse=True)
        
        return {
            "query": query,
            "entity_type": entity_type,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching attachments: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search attachments: {str(e)}"
        )