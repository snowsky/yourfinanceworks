"""
Tax Service Integration Router
Provides endpoints for managing integration with Tax Service API
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime, timezone

from core.models.database import get_db
from core.models.models import MasterUser
from core.models.models_per_tenant import Settings
from core.routers.auth import get_current_user
from core.utils.feature_gate import require_feature
from commercial.integrations.tax.service import (
    get_tax_integration_service,
    IntegrationResult,
    IntegrationType
)
from config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tax-integration", tags=["tax-integration"])


class IntegrationSettings(BaseModel):
    """Tax service integration settings"""
    enabled: bool
    base_url: str
    api_key: str
    timeout: int = 30
    retry_attempts: int = 3


class IntegrationStatus(BaseModel):
    """Integration status response"""
    enabled: bool
    configured: bool
    connection_tested: bool
    last_test_result: Optional[str] = None


class SendToTaxServiceRequest(BaseModel):
    """Request to send expense/invoice to tax service"""
    item_id: int
    item_type: IntegrationType  # "expense" or "invoice"


class BulkSendToTaxServiceRequest(BaseModel):
    """Request to send multiple items to tax service"""
    item_ids: List[int]
    item_type: IntegrationType  # "expense" or "invoice"


class IntegrationResponse(BaseModel):
    """Response for integration operations"""
    success: bool
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


class BulkIntegrationResponse(BaseModel):
    """Response for bulk integration operations"""
    total_items: int
    successful: int
    failed: int
    results: List[IntegrationResponse]


@router.get("/status", response_model=IntegrationStatus)
@require_feature("tax_integration")
async def get_integration_status(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current tax service integration status"""
    try:
        # Check database settings first, fallback to env vars
        tax_settings_record = db.query(Settings).filter(Settings.key == "tax_integration_settings").first()

        if tax_settings_record and tax_settings_record.value:
            tax_settings = tax_settings_record.value
            enabled = tax_settings.get("enabled", config.TAX_SERVICE_ENABLED)
            api_key = tax_settings.get("api_key", config.TAX_SERVICE_API_KEY)
        else:
            # No DB settings, use env vars
            enabled = config.TAX_SERVICE_ENABLED
            api_key = config.TAX_SERVICE_API_KEY

        service = get_tax_integration_service()

        if not service or not enabled:
            return IntegrationStatus(
                enabled=enabled,
                configured=bool(api_key),
                connection_tested=False
            )

        # Test connection
        connection_ok = await service.test_connection()

        return IntegrationStatus(
            enabled=enabled,
            configured=bool(api_key),
            connection_tested=connection_ok,
            last_test_result="Connection successful" if connection_ok else "Connection failed"
        )

    except Exception as e:
        logger.error(f"Error getting integration status: {str(e)}")
        return IntegrationStatus(
            enabled=config.TAX_SERVICE_ENABLED,
            configured=bool(config.TAX_SERVICE_API_KEY),
            connection_tested=False,
            last_test_result=f"Error: {str(e)}"
        )


@router.post("/test-connection")
@require_feature("tax_integration")
async def test_tax_service_connection(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test connection to tax service using database settings"""
    try:
        # Get settings from database first, fallback to env vars
        tax_settings_record = db.query(Settings).filter(Settings.key == "tax_integration_settings").first()

        if tax_settings_record and tax_settings_record.value:
            tax_settings = tax_settings_record.value
            base_url = tax_settings.get("base_url", config.TAX_SERVICE_BASE_URL)
            api_key = tax_settings.get("api_key", config.TAX_SERVICE_API_KEY)
            timeout = tax_settings.get("timeout", config.TAX_SERVICE_TIMEOUT)
            retry_attempts = tax_settings.get("retry_attempts", config.TAX_SERVICE_RETRY_ATTEMPTS)
        else:
            # No DB settings, use env vars
            base_url = config.TAX_SERVICE_BASE_URL
            api_key = config.TAX_SERVICE_API_KEY
            timeout = config.TAX_SERVICE_TIMEOUT
            retry_attempts = config.TAX_SERVICE_RETRY_ATTEMPTS

        # Create temporary service instance with current settings
        from commercial.integrations.tax.service import TaxServiceConfig, TaxIntegrationService
        temp_config = TaxServiceConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            retry_attempts=retry_attempts,
            enabled=True
        )
        temp_service = TaxIntegrationService(temp_config)

        try:
            connection_ok = await temp_service.test_connection()

            return {
                "success": connection_ok,
                "message": "Connection successful" if connection_ok else "Connection failed"
            }
        finally:
            # Clean up the temporary service
            await temp_service.close()

    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Connection test failed: {str(e)}"
        )


@router.post("/send", response_model=IntegrationResponse)
@require_feature("tax_integration")
async def send_to_tax_service(
    request: SendToTaxServiceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Send an expense or invoice to tax service"""
    try:
        service = get_tax_integration_service()

        if not service:
            raise HTTPException(
                status_code=400,
                detail="Tax service integration is not configured or disabled"
            )

        if request.item_type == IntegrationType.EXPENSE:
            # Get expense data
            from core.models.models_per_tenant import Expense
            item = db.query(Expense).filter(Expense.id == request.item_id).first()
            if not item:
                raise HTTPException(status_code=404, detail="Expense not found")

            # Convert SQLAlchemy object to dict
            expense_data = {
                "id": item.id,
                "amount": float(item.amount),
                "currency": item.currency,
                "expense_date": item.expense_date.isoformat() if item.expense_date else None,
                "category": item.category,
                "vendor": item.vendor,
                "label": item.label,
                "labels": item.labels,
                "tax_rate": float(item.tax_rate) if item.tax_rate else None,
                "tax_amount": float(item.tax_amount) if item.tax_amount else None,
                "total_amount": float(item.total_amount) if item.total_amount else None,
                "payment_method": item.payment_method,
                "reference_number": item.reference_number,
                "status": item.status,
                "notes": item.notes
            }

            result = await service.send_expense_to_tax_service(expense_data)

        elif request.item_type == IntegrationType.INVOICE:
            # Get invoice data with client info
            from core.models.models_per_tenant import Invoice, Client
            invoice_query = db.query(
                Invoice,
                Client.name.label('client_name'),
                Client.email.label('client_email')
            ).join(Client, Invoice.client_id == Client.id).filter(Invoice.id == request.item_id).first()

            if not invoice_query:
                raise HTTPException(status_code=404, detail="Invoice not found")

            invoice, client_name, client_email = invoice_query

            # Convert to dict
            invoice_data = {
                "id": invoice.id,
                "number": invoice.number,
                "amount": float(invoice.amount),
                "currency": invoice.currency,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "status": invoice.status,
                "notes": invoice.notes,
                "client_id": invoice.client_id,
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
                "discount_type": invoice.discount_type,
                "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
                "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount)
            }

            client_data = {
                "id": invoice.client_id,
                "name": client_name,
                "email": client_email
            }

            result = await service.send_invoice_to_tax_service(invoice_data, client_data)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported item type: {request.item_type}"
            )

        return IntegrationResponse(
            success=result.success,
            transaction_id=result.transaction_id,
            error_message=result.error_message,
            response_data=result.response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending to tax service: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send to tax service: {str(e)}"
        )


@router.post("/send-bulk", response_model=BulkIntegrationResponse)
@require_feature("tax_integration")
async def send_bulk_to_tax_service(
    request: BulkSendToTaxServiceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Send multiple expenses or invoices to tax service"""
    try:
        service = get_tax_integration_service()

        if not service:
            raise HTTPException(
                status_code=400,
                detail="Tax service integration is not configured or disabled"
            )

        results = []

        if request.item_type == IntegrationType.EXPENSE:
            # Get expenses data
            from core.models.models_per_tenant import Expense
            expenses = db.query(Expense).filter(Expense.id.in_(request.item_ids)).all()

            expenses_data = []
            for item in expenses:
                expense_data = {
                    "id": item.id,
                    "amount": float(item.amount),
                    "currency": item.currency,
                    "expense_date": item.expense_date.isoformat() if item.expense_date else None,
                    "category": item.category,
                    "vendor": item.vendor,
                    "label": item.label,
                    "labels": item.labels,
                    "tax_rate": float(item.tax_rate) if item.tax_rate else None,
                    "tax_amount": float(item.tax_amount) if item.tax_amount else None,
                    "total_amount": float(item.total_amount) if item.total_amount else None,
                    "payment_method": item.payment_method,
                    "reference_number": item.reference_number,
                    "status": item.status,
                    "notes": item.notes
                }
                expenses_data.append(expense_data)

            bulk_results = await service.send_bulk_expenses_to_tax_service(expenses_data)

        elif request.item_type == IntegrationType.INVOICE:
            # Get invoices data with client info
            from core.models.models_per_tenant import Invoice, Client
            invoices_query = db.query(
                Invoice,
                Client.name.label('client_name'),
                Client.email.label('client_email')
            ).join(Client, Invoice.client_id == Client.id).filter(Invoice.id.in_(request.item_ids)).all()

            invoices_data = []
            clients_data = {}

            for invoice, client_name, client_email in invoices_query:
                invoice_data = {
                    "id": invoice.id,
                    "number": invoice.number,
                    "amount": float(invoice.amount),
                    "currency": invoice.currency,
                    "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                    "status": invoice.status,
                    "notes": invoice.notes,
                    "client_id": invoice.client_id,
                    "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                    "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
                    "discount_type": invoice.discount_type,
                    "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
                    "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount)
                }
                invoices_data.append(invoice_data)

                clients_data[invoice.client_id] = {
                    "id": invoice.client_id,
                    "name": client_name,
                    "email": client_email
                }

            bulk_results = await service.send_bulk_invoices_to_tax_service(invoices_data, clients_data)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported item type: {request.item_type}"
            )

        # Convert results
        response_results = []
        successful = 0
        failed = 0

        for result in bulk_results:
            response_result = IntegrationResponse(
                success=result.success,
                transaction_id=result.transaction_id,
                error_message=result.error_message,
                response_data=result.response_data
            )
            response_results.append(response_result)

            if result.success:
                successful += 1
            else:
                failed += 1

        return BulkIntegrationResponse(
            total_items=len(request.item_ids),
            successful=successful,
            failed=failed,
            results=response_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending bulk to tax service: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send bulk to tax service: {str(e)}"
        )


@router.get("/settings", response_model=IntegrationSettings)
@require_feature("tax_integration")
async def get_integration_settings(
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current integration settings (masked for security)"""
    # Check database settings first, fallback to env vars
    tax_settings_record = db.query(Settings).filter(Settings.key == "tax_integration_settings").first()

    if tax_settings_record and tax_settings_record.value:
        tax_settings = tax_settings_record.value
        enabled = tax_settings.get("enabled", config.TAX_SERVICE_ENABLED)
        base_url = tax_settings.get("base_url", config.TAX_SERVICE_BASE_URL)
        api_key = tax_settings.get("api_key", config.TAX_SERVICE_API_KEY)
        timeout = tax_settings.get("timeout", config.TAX_SERVICE_TIMEOUT)
        retry_attempts = tax_settings.get("retry_attempts", config.TAX_SERVICE_RETRY_ATTEMPTS)
    else:
        # No DB settings, use env vars
        enabled = config.TAX_SERVICE_ENABLED
        base_url = config.TAX_SERVICE_BASE_URL
        api_key = config.TAX_SERVICE_API_KEY
        timeout = config.TAX_SERVICE_TIMEOUT
        retry_attempts = config.TAX_SERVICE_RETRY_ATTEMPTS

    return IntegrationSettings(
        enabled=enabled,
        base_url=base_url,
        api_key=f"{'*' * 8}...{api_key[-4:]}" if api_key else "",
        timeout=timeout,
        retry_attempts=retry_attempts
    )


@router.put("/settings", response_model=IntegrationSettings)
@require_feature("tax_integration")
async def update_integration_settings(
    settings: IntegrationSettings,
    current_user: MasterUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update tax integration settings"""
    try:
        logger.info(f"Updating tax integration settings for user {current_user.id}")

        # Validate settings
        if settings.timeout < 1 or settings.timeout > 300:
            raise HTTPException(status_code=400, detail="Timeout must be between 1 and 300 seconds")

        if settings.retry_attempts < 0 or settings.retry_attempts > 10:
            raise HTTPException(status_code=400, detail="Retry attempts must be between 0 and 10")

        # Get or create the settings record
        tax_settings_record = db.query(Settings).filter(Settings.key == "tax_integration_settings").first()

        # Prepare settings data
        settings_data = {
            "enabled": settings.enabled,
            "base_url": settings.base_url,
            "api_key": settings.api_key,  # Store the actual API key
            "timeout": settings.timeout,
            "retry_attempts": settings.retry_attempts
        }

        if tax_settings_record:
            # Update existing record
            tax_settings_record.value = settings_data
            tax_settings_record.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            tax_settings_record = Settings(
                key="tax_integration_settings",
                value=settings_data,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(tax_settings_record)

        db.commit()

        # Log audit event
        from core.utils.audit import log_audit_event
        log_audit_event(
            db=db,
            user_id=current_user.id,
            user_email=current_user.email,
            action="UPDATE",
            resource_type="tax_integration_settings",
            resource_id="1",
            resource_name="Tax Integration Settings",
            details={"enabled": settings.enabled},
            status="success"
        )

        return IntegrationSettings(
            enabled=settings.enabled,
            base_url=settings.base_url,
            api_key=f"{'*' * 8}...{settings.api_key[-4:]}" if settings.api_key else "",
            timeout=settings.timeout,
            retry_attempts=settings.retry_attempts
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating integration settings: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update integration settings: {str(e)}"
        )


@router.get("/expenses/{expense_id}/tax-transaction")
@require_feature("tax_integration")
async def get_expense_tax_transaction(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get tax transaction details for an expense (for debugging)"""
    try:
        from core.models.models_per_tenant import Expense
        expense = db.query(Expense).filter(Expense.id == expense_id).first()

        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")

        service = get_tax_integration_service()
        if not service:
            raise HTTPException(
                status_code=400,
                detail="Tax service integration not configured"
            )

        # Map expense to transaction format for preview
        expense_data = {
            "id": expense.id,
            "amount": float(expense.amount),
            "currency": expense.currency,
            "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
            "category": expense.category,
            "vendor": expense.vendor,
            "label": expense.label,
            "labels": expense.labels,
            "tax_rate": float(expense.tax_rate) if expense.tax_rate else None,
            "tax_amount": float(expense.tax_amount) if expense.tax_amount else None,
            "total_amount": float(expense.total_amount) if expense.total_amount else None,
            "payment_method": expense.payment_method,
            "reference_number": expense.reference_number,
            "status": expense.status,
            "notes": expense.notes
        }

        transaction_data = service._map_expense_to_transaction(expense_data)

        return {
            "expense_id": expense_id,
            "mapped_transaction": transaction_data,
            "endpoint": "/api/v1/transactions/expenses"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense tax transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get expense tax transaction: {str(e)}"
        )


@router.get("/invoices/{invoice_id}/tax-transaction")
@require_feature("tax_integration")
async def get_invoice_tax_transaction(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get tax transaction details for an invoice (for debugging)"""
    try:
        from core.models.models_per_tenant import Invoice, Client
        invoice_query = db.query(
            Invoice,
            Client.name.label('client_name'),
            Client.email.label('client_email')
        ).join(Client, Invoice.client_id == Client.id).filter(Invoice.id == invoice_id).first()

        if not invoice_query:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice, client_name, client_email = invoice_query

        service = get_tax_integration_service()
        if not service:
            raise HTTPException(
                status_code=400,
                detail="Tax service integration not configured"
            )

        # Map invoice to transaction format for preview
        invoice_data = {
            "id": invoice.id,
            "number": invoice.number,
            "amount": float(invoice.amount),
            "currency": invoice.currency,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "status": invoice.status,
            "notes": invoice.notes,
            "client_id": invoice.client_id,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
            "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
            "discount_type": invoice.discount_type,
            "discount_value": float(invoice.discount_value) if invoice.discount_value else 0,
            "subtotal": float(invoice.subtotal) if invoice.subtotal else float(invoice.amount)
        }

        client_data = {
            "id": invoice.client_id,
            "name": client_name,
            "email": client_email
        }

        transaction_data = service._map_invoice_to_transaction(invoice_data, client_data)

        return {
            "invoice_id": invoice_id,
            "mapped_transaction": transaction_data,
            "endpoint": "/api/v1/transactions/income"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invoice tax transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get invoice tax transaction: {str(e)}"
        )
