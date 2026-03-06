"""
Accounting Export Router

Provides accountant-ready export endpoints detached from legacy tax-service sync.
"""

from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Settings
from core.routers.auth import get_current_user
from core.utils.audit import log_audit_event
from core.utils.feature_gate import require_feature

from commercial.accounting_export.service import AccountingExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounting-export", tags=["accounting-export"])


@router.get("/journal")
@require_feature("advanced_export")
async def export_accounting_journal(
    date_from: Optional[datetime] = Query(default=None, description="Filter from datetime (inclusive)"),
    date_to: Optional[datetime] = Query(default=None, description="Filter to datetime (inclusive)"),
    include_drafts: bool = Query(default=False, description="Include draft invoices"),
    tax_only: bool = Query(default=False, description="Include only tax-relevant records"),
    include_expenses: bool = Query(default=True, description="Include expenses in export"),
    include_invoices: bool = Query(default=True, description="Include invoices in export"),
    include_payments: bool = Query(default=True, description="Include payments in export"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Export accountant-ready double-entry journal CSV."""
    try:
        if not any([include_expenses, include_invoices, include_payments]):
            raise HTTPException(
                status_code=400,
                detail="At least one source must be included (expenses, invoices, or payments)"
            )

        account_mapping = None
        account_settings_record = db.query(Settings).filter(Settings.key == "accounting_export_settings").first()
        if account_settings_record and isinstance(account_settings_record.value, dict):
            account_mapping = account_settings_record.value.get("account_mapping")

        export_service = AccountingExportService(db=db, account_mapping=account_mapping)
        expenses, invoices, payments = export_service.fetch_records(
            date_from=date_from,
            date_to=date_to,
            include_expenses=include_expenses,
            include_invoices=include_invoices,
            include_payments=include_payments,
            include_drafts=include_drafts
        )
        if tax_only:
            expenses, invoices, payments = export_service.filter_tax_relevant_records(
                expenses=expenses,
                invoices=invoices,
                payments=payments,
            )
        csv_content = export_service.generate_journal_csv(
            expenses=expenses,
            invoices=invoices,
            payments=payments
        )

        date_from_label = date_from.strftime("%Y%m%d") if date_from else "all"
        date_to_label = date_to.strftime("%Y%m%d") if date_to else "all"
        filename = f"accounting_journal_{date_from_label}_{date_to_label}.csv"

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="EXPORT",
            resource_type="accounting_journal",
            resource_id="csv",
            resource_name="Accounting Journal CSV",
            details={
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "include_drafts": include_drafts,
                "tax_only": tax_only,
                "include_expenses": include_expenses,
                "include_invoices": include_invoices,
                "include_payments": include_payments,
                "expense_count": len(expenses),
                "invoice_count": len(invoices),
                "payment_count": len(payments)
            },
            status="success"
        )

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting accounting journal: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export accounting journal: {str(e)}"
        )


@router.get("/tax-summary")
@require_feature("advanced_export")
async def export_tax_summary(
    date_from: Optional[datetime] = Query(default=None, description="Filter from datetime (inclusive)"),
    date_to: Optional[datetime] = Query(default=None, description="Filter to datetime (inclusive)"),
    include_drafts: bool = Query(default=False, description="Include draft invoices"),
    include_expenses: bool = Query(default=True, description="Include expenses in summary"),
    include_invoices: bool = Query(default=True, description="Include invoices in summary"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Export tax summary CSV grouped by input/output tax rates."""
    try:
        if not any([include_expenses, include_invoices]):
            raise HTTPException(
                status_code=400,
                detail="At least one source must be included (expenses or invoices)"
            )

        account_mapping = None
        account_settings_record = db.query(Settings).filter(Settings.key == "accounting_export_settings").first()
        if account_settings_record and isinstance(account_settings_record.value, dict):
            account_mapping = account_settings_record.value.get("account_mapping")

        export_service = AccountingExportService(db=db, account_mapping=account_mapping)
        expenses, invoices, _ = export_service.fetch_records(
            date_from=date_from,
            date_to=date_to,
            include_expenses=include_expenses,
            include_invoices=include_invoices,
            include_payments=False,
            include_drafts=include_drafts
        )
        csv_content = export_service.generate_tax_summary_csv(
            expenses=expenses,
            invoices=invoices,
            date_from=date_from,
            date_to=date_to
        )

        date_from_label = date_from.strftime("%Y%m%d") if date_from else "all"
        date_to_label = date_to.strftime("%Y%m%d") if date_to else "all"
        filename = f"tax_summary_{date_from_label}_{date_to_label}.csv"

        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="EXPORT",
            resource_type="tax_summary",
            resource_id="csv",
            resource_name="Tax Summary CSV",
            details={
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "include_drafts": include_drafts,
                "include_expenses": include_expenses,
                "include_invoices": include_invoices,
                "expense_count": len(expenses),
                "invoice_count": len(invoices)
            },
            status="success"
        )

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting tax summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export tax summary: {str(e)}"
        )
