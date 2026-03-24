"""
Tools API — Email reference endpoints.
Exposes source email links for invoices, expenses, and bank statements
for agent consumption.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.services.document_email_reference_service import DocumentEmailReferenceService

from .deps import (
    AuthContext,
    ToolResponse,
    _check_domain_access,
    get_api_auth_context,
    get_tenant_db,
)

router = APIRouter(prefix="/api/v1/tools", tags=["tools-email-references"])
logger = logging.getLogger(__name__)


@router.get("/invoices/{invoice_id}/email-references")
async def tools_invoice_email_references(
    invoice_id: int,
    auth: AuthContext = Depends(get_api_auth_context),
    tenant_db: Session = Depends(get_tenant_db),
):
    """List all source emails linked to an invoice."""
    _check_domain_access(auth, "invoice")
    svc = DocumentEmailReferenceService(tenant_db)
    refs = svc.get_email_references("invoice", invoice_id)
    return ToolResponse(success=True, data=refs, count=len(refs))


@router.get("/expenses/{expense_id}/email-references")
async def tools_expense_email_references(
    expense_id: int,
    auth: AuthContext = Depends(get_api_auth_context),
    tenant_db: Session = Depends(get_tenant_db),
):
    """List all source emails linked to an expense."""
    _check_domain_access(auth, "expense")
    svc = DocumentEmailReferenceService(tenant_db)
    refs = svc.get_email_references("expense", expense_id)
    return ToolResponse(success=True, data=refs, count=len(refs))


@router.get("/bank-statements/{statement_id}/email-references")
async def tools_statement_email_references(
    statement_id: int,
    auth: AuthContext = Depends(get_api_auth_context),
    tenant_db: Session = Depends(get_tenant_db),
):
    """List all source emails linked to a bank statement."""
    _check_domain_access(auth, "bank_statement")
    svc = DocumentEmailReferenceService(tenant_db)
    refs = svc.get_email_references("bank_statement", statement_id)
    return ToolResponse(success=True, data=refs, count=len(refs))
