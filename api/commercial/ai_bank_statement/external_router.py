"""
External API router for third-party integrations using API keys.
Provides endpoints for PDF statement processing and transaction extraction.
"""

import csv
import io
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.models.database import get_db, get_master_db, set_tenant_context
from core.models.models import TenantPluginSettings, User
from core.models.api_models import APIClient, ExternalTransaction
from core.services.external_api_auth_service import ExternalAPIAuthService, AuthContext, Permission
from core.decorators.sandbox_validation import require_production_auth_context
from core.services.statement_service import process_bank_pdf_with_llm, BankLLMUnavailableError, is_bank_llm_reachable
from core.utils.audit import log_audit_event
from core.utils.file_validation import validate_file_magic_bytes

router = APIRouter(prefix="/external", tags=["external-api"])
logger = logging.getLogger(__name__)

auth_service = ExternalAPIAuthService()


async def get_api_auth_context(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_master_db)
) -> AuthContext:
    # 0. Check if already authenticated via middleware (trusted sidecar)
    auth_context = getattr(request.state, "auth", None)
    if auth_context and auth_context.is_authenticated:
        # Also ensure tenant context is set
        if auth_context.tenant_id:
            set_tenant_context(auth_context.tenant_id)
        return auth_context

    api_key = None
    
    # Try Authorization header first (Bearer token format)
    if authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]  # Remove "Bearer " prefix
        else:
            api_key = authorization
    
    # Fallback to X-API-Key header
    if not api_key and x_api_key:
        api_key = x_api_key
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via Authorization header (Bearer <key>) or X-API-Key header."
        )
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Authenticate API key
    auth_context = await auth_service.authenticate_api_key(db, api_key, client_ip)
    
    if not auth_context:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key or access denied"
        )
    
    # Set tenant context for database operations
    if auth_context.tenant_id:
        set_tenant_context(auth_context.tenant_id)
    
    return auth_context


@router.post("/statements/process")
@require_production_auth_context("Sandbox API keys cannot process real statements. Use a production API key for live statement processing.")
async def process_statement_pdf(
    file: UploadFile = File(..., description="PDF or CSV bank statement file"),
    format: str = "csv",  # Response format: csv, json
    card_type: str = "auto", # debit|credit|auto
    auth_context: AuthContext = Depends(get_api_auth_context),
    db: Session = Depends(get_db),
    master_db: Session = Depends(get_master_db)
) -> StreamingResponse:
    """
    Process a bank statement PDF/CSV file and return extracted transactions.

    **Authentication**: Requires valid API key via Authorization header or X-API-Key header.

    **Parameters**:
    - `file`: PDF or CSV bank statement file (max 20MB)
    - `format`: Response format - "csv" (default) or "json"

    **Returns**:
    - CSV format: Streaming CSV file with transactions
    - JSON format: JSON array of transaction objects

    **Rate Limits**: Subject to API client rate limits
    """
    # Validate permissions
    if Permission.DOCUMENT_PROCESSING not in auth_context.permissions:
        raise HTTPException(
            status_code=403,
            detail="Document processing permission required"
        )

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Check file size (20MB limit)
    file_content = await file.read()
    if len(file_content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be <= 20MB")

    # Check file type
    allowed_types = {"application/pdf", "text/csv", "application/vnd.ms-excel"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and CSV files are supported"
        )
    validate_file_magic_bytes(file_content, file.content_type)

    # Get API client for rate limiting and permissions
    api_client = None
    if auth_context.authentication_method == "internal_secret":
        # 1. Fetch plugin settings to find the attributed user for this sidecar request
        # sidecar requests (from public portal) MUST be attributed to a configured admin user
        plugin_settings = master_db.query(TenantPluginSettings).filter(
            TenantPluginSettings.tenant_id == auth_context.tenant_id
        ).first()
        
        plugin_config = (plugin_settings.plugin_config or {}).get("statement-tools", {}) if plugin_settings else {}
        default_user_email = plugin_config.get("default_background_user_email")
        
        if not default_user_email:
            raise HTTPException(
                status_code=403, 
                detail="Plugin 'statement-tools' is not configured with a default background user. Please set 'default_background_user_email' in plugin settings."
            )
        
        # 2. Lookup the user in the tenant database
        tenant_user = db.query(User).filter(
            User.email == default_user_email,
            User.is_active == True
        ).first()
        
        if not tenant_user:
            raise HTTPException(
                status_code=403, 
                detail=f"Configured background user '{default_user_email}' does not exist or is inactive in this tenant."
            )

        # Create a mock client object to satisfy downstream logic without requiring a real API client
        class MockClient:
            def __init__(self, auth, user_id):
                self.client_id = auth.api_key_id or auth.username
                self.client_name = auth.username
                self.tenant_id = auth.tenant_id
                self.user_id = user_id  # Mandatory for batch job attribution
                self.total_requests = 0
                self.total_transactions_submitted = 0

        api_client = MockClient(auth_context, tenant_user.id)
    else:
        api_client = master_db.query(APIClient).filter(
            APIClient.client_id == auth_context.api_key_id,
            APIClient.is_active == True
        ).first()

        if not api_client:
            raise HTTPException(status_code=401, detail="API client not found")

        # Check rate limits
        rate_limit_ok, rate_limit_msg, retry_after = await auth_service.check_rate_limits(
            master_db, api_client
        )
        if not rate_limit_ok:
            raise HTTPException(
                status_code=429,
                detail=rate_limit_msg or "Rate limit exceeded",
                headers={"Retry-After": str(retry_after)} if retry_after else None
            )

    # Save file temporarily for processing
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(file.filename)
    file_extension = Path(safe_filename).suffix.lower()
    if file_extension not in ['.pdf', '.csv']:
        file_extension = '.pdf'  # Default to PDF

    try:
        # Store file in cloud storage for processing and audit trail
        stored_file_path = None
        cloud_file_key = None

        try:
            from commercial.cloud_storage.service import CloudStorageService
            from commercial.cloud_storage.config import get_cloud_storage_config

            cloud_config = get_cloud_storage_config()
            cloud_storage_service = CloudStorageService(db, cloud_config)

            # Generate unique file key for cloud storage
            file_key = f"bank_statements/api/{api_client.client_id}/{uuid.uuid4().hex}_{safe_filename}"

            # Store file in cloud storage
            storage_result = await cloud_storage_service.store_file(
                file_content=file_content,
                tenant_id=str(api_client.tenant_id),
                item_id=0,  # Use 0 for external API uploads
                attachment_type="bank_statements",
                original_filename=safe_filename,
                user_id=1,  # Use admin user for external API uploads
                metadata={
                    "original_filename": safe_filename,
                    "api_client_id": str(api_client.client_id),
                    "api_client_name": api_client.client_name,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                    "file_size": len(file_content),
                    "document_type": "bank_statement",
                    "file_key": file_key  # Store the original file key in metadata
                }
            )

            if storage_result.success:
                cloud_file_key = file_key
                logger.info(f"Bank statement stored in cloud storage: {file_key}")

                # For processing, we still need a local temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix=file_extension,
                    prefix=f"api_statement_{uuid.uuid4().hex[:8]}_"
                ) as temp_file:
                    temp_file.write(file_content)
                    stored_file_path = temp_file.name
            else:
                logger.warning(f"Cloud storage failed, using temporary file: {storage_result.error}")
                # Fallback to temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix=file_extension,
                    prefix=f"api_statement_{uuid.uuid4().hex[:8]}_"
                ) as temp_file:
                    temp_file.write(file_content)
                    stored_file_path = temp_file.name

        except ImportError:
            logger.info("Cloud storage not available, using temporary file")
            # Fallback to temporary file
            with tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=file_extension,
                prefix=f"api_statement_{uuid.uuid4().hex[:8]}_"
            ) as temp_file:
                temp_file.write(file_content)
                stored_file_path = temp_file.name

        # Validate file path
        from core.utils.file_validation import validate_file_path
        temp_file_path = validate_file_path(stored_file_path)

        logger.info(f"Processing statement file for API client {api_client.client_name}: {file.filename}")

        # Check if AI service is reachable before processing
        if not is_bank_llm_reachable():
            raise HTTPException(
                status_code=503,
                detail="AI processing service is not available. Please ensure the AI provider is configured in Settings > AI Configuration and the service is running."
            )

        # Process the file using the unified OCR service
        try:
            from commercial.ai.services.unified_ocr_service import UnifiedOCRService, DocumentType, OCRConfig

            # Configure OCR service with AI config from database
            ai_config = None
            try:
                from core.models.models_per_tenant import AIConfig as AIConfigModel
                ai_row = db.query(AIConfigModel).filter(
                    AIConfigModel.is_active == True,
                    AIConfigModel.tested == True
                ).order_by(AIConfigModel.is_default.desc()).first()

                if ai_row:
                    ai_config = {
                        "provider_name": ai_row.provider_name,
                        "model_name": ai_row.model_name,
                        "api_key": ai_row.api_key,
                        "provider_url": ai_row.provider_url,
                    }
                    logger.info(f"Using AI config: {ai_row.provider_name} ({ai_row.model_name})")
            except Exception as e:
                logger.warning(f"Failed to load AI config from database: {e}")

            # Create OCR service
            ocr_config = OCRConfig(
                ai_config=ai_config,
                enable_unstructured=True,
                enable_tesseract_fallback=True,
                timeout_seconds=300
            )
            ocr_service = UnifiedOCRService(ocr_config)

            # Extract text from bank statement
            text_result = ocr_service.extract_text(temp_file_path, DocumentType.BANK_STATEMENT)

            if not text_result.success:
                raise Exception(f"Text extraction failed: {text_result.error_message}")
            
            # For now, use the existing transaction extraction logic
            # TODO: Integrate transaction parsing into unified service
            transactions = process_bank_pdf_with_llm(temp_file_path, ai_config, db, card_type=card_type)
        except BankLLMUnavailableError:
            raise HTTPException(
                status_code=503,
                detail="AI processing service temporarily unavailable. Please check Settings > AI Configuration and ensure the AI service is running and accessible."
            )
        except Exception as e:
            # Handle OCR-specific exceptions with detailed user feedback
            try:
                from commercial.ai.exceptions.bank_ocr_exceptions import (
                    OCRUnavailableError,
                    OCRTimeoutError,
                    OCRProcessingError,
                    OCRInvalidFileError,
                    get_retry_delay
                )

                if isinstance(e, OCRTimeoutError):
                    retry_delay = get_retry_delay(e)
                    detail = f"Document processing is taking longer than expected due to OCR requirements. This typically happens with scanned documents. Please try again in {retry_delay or 60} seconds."
                    raise HTTPException(status_code=503, detail=detail)

                elif isinstance(e, OCRUnavailableError):
                    detail = "OCR processing is required for this document but is not available. Please contact your administrator to enable OCR functionality."
                    raise HTTPException(status_code=503, detail=detail)

                elif isinstance(e, OCRProcessingError):
                    if e.is_transient:
                        retry_delay = get_retry_delay(e)
                        detail = f"Document processing temporarily failed. Please try again in {retry_delay or 30} seconds."
                        raise HTTPException(status_code=503, detail=detail)
                    else:
                        detail = "Failed to process document. The file may be corrupted or in an unsupported format."
                        raise HTTPException(status_code=422, detail=detail)

                elif isinstance(e, OCRInvalidFileError):
                    detail = "Invalid file for processing. Please ensure the file is a valid PDF bank statement."
                    raise HTTPException(status_code=422, detail=detail)

            except ImportError:
                pass

            # Generic error handling
            logger.error(f"Error processing statement: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to process statement file. Please check that the file is a valid bank statement and try again."
            )

        if not transactions:
            raise HTTPException(
                status_code=422,
                detail="No transactions found in the provided file. This could mean: 1) The file doesn't contain transaction data, 2) The file format is not supported, or 3) The AI service needs to be configured in Settings > AI Configuration."
            )

        # Update API client usage statistics
        api_client.total_transactions_submitted += len(transactions)
        db.commit()

        # Log audit event with cloud storage information
        audit_details = {
            "api_client_id": api_client.client_id,
            "filename": file.filename,
            "transactions_count": len(transactions),
            "file_size": len(file_content)
        }
        
        if cloud_file_key:
            audit_details["cloud_storage_key"] = cloud_file_key
            audit_details["storage_method"] = "cloud_storage"
        else:
            audit_details["storage_method"] = "temporary_file"
        
        log_audit_event(
            db=db,
            user_id=int(auth_context.user_id),
            action="api_statement_processed",
            resource_type="statement",
            resource_id=None,
            details=audit_details
        )

        # Return response based on requested format
        detected_card_type = transactions[0].get("card_type", "debit") if transactions else "debit"
        if format.lower() == "json":
            return {"transactions": transactions, "statement_type": detected_card_type}
        else:
            # Default to CSV format
            response = _create_csv_response(transactions, file.filename)
            response.headers["X-Statement-Type"] = detected_card_type
            return response

    finally:
        # Clean up temporary file
        try:
            if 'temp_file_path' in locals():
                from core.utils.file_validation import validate_file_path
                validated_temp_path = validate_file_path(temp_file_path)
                os.unlink(validated_temp_path)
                logger.debug(f"Cleaned up temporary file: {validated_temp_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file: {e}")
        
        # Note: Cloud storage files are kept for audit trail and potential reprocessing
        # They can be cleaned up later by a scheduled cleanup job if needed


def _create_csv_response(transactions: List[Dict[str, Any]], original_filename: str) -> StreamingResponse:
    """Create a CSV streaming response from transactions."""

    def generate_csv():
        output = io.StringIO()

        if not transactions:
            # Return empty CSV with headers
            writer = csv.writer(output)
            writer.writerow(['date', 'description', 'amount', 'transaction_type', 'category', 'balance'])
            output.seek(0)
            yield output.getvalue()
            return

        # Write CSV headers
        fieldnames = ['date', 'description', 'amount', 'transaction_type', 'category', 'balance']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Write transaction data
        for transaction in transactions:
            # Ensure all required fields are present
            row = {
                'date': transaction.get('date', ''),
                'description': transaction.get('description', ''),
                'amount': transaction.get('amount', 0),
                'transaction_type': transaction.get('transaction_type', 'debit'),
                'category': transaction.get('category', ''),
                'balance': transaction.get('balance', '')
            }
            writer.writerow(row)

        output.seek(0)
        yield output.getvalue()

    # Generate filename for download - sanitize to prevent path traversal
    import re
    safe_filename = os.path.basename(original_filename)  # Remove any path components
    safe_filename = re.sub(r'[^A-Za-z0-9._-]', '_', safe_filename)  # Remove unsafe characters
    base_name = Path(safe_filename).stem
    csv_filename = f"{base_name}_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={csv_filename}"
        }
    )


@router.get("/statements/health")
async def health_check(
    auth_context: AuthContext = Depends(get_api_auth_context),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Health check endpoint for API clients.

    **Authentication**: Requires valid API key.

    **Returns**: API client status and service availability.
    """

    # Check AI service availability
    ai_service_available = is_bank_llm_reachable()
    overall_status = "healthy" if ai_service_available else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_client": auth_context.api_key_id,
        "authentication_method": auth_context.authentication_method,
        "permissions": list(auth_context.permissions),
        "services": {
            "ai_processing": "available" if ai_service_available else "unavailable"
        },
        "message": "All services operational" if ai_service_available else "AI processing service unavailable - please configure in Settings > AI Configuration"
    }


@router.get("/statements/usage")
async def get_usage_stats(
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(get_api_auth_context)
) -> Dict[str, Any]:
    """
    Get usage statistics for the authenticated API client.

    **Authentication**: Requires valid API key.

    **Returns**: Usage statistics including request counts and limits.
    """

    # Get API client
    api_client = db.query(APIClient).filter(
        APIClient.client_id == auth_context.api_key_id,
        APIClient.is_active == True
    ).first()

    if not api_client:
        raise HTTPException(status_code=404, detail="API client not found")

    return {
        "client_id": api_client.client_id,
        "client_name": api_client.client_name,
        "total_requests": api_client.total_requests,
        "total_transactions_submitted": api_client.total_transactions_submitted,
        "last_used_at": api_client.last_used_at.isoformat() if api_client.last_used_at else None,
        "rate_limits": {
            "per_minute": api_client.rate_limit_per_minute,
            "per_hour": api_client.rate_limit_per_hour,
            "per_day": api_client.rate_limit_per_day
        },
        "permissions": {
            "allowed_document_types": api_client.allowed_document_types or [],
            "max_transaction_amount": float(api_client.max_transaction_amount) if api_client.max_transaction_amount else None
        },
        "status": api_client.status,
        "is_sandbox": api_client.is_sandbox
    }