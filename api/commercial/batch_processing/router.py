"""
Batch Processing Router

API endpoints for batch file upload and processing.
Supports uploading multiple files for OCR processing and exporting results.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File, Form, Request
from sqlalchemy.orm import Session

from core.models.database import get_db, get_master_db
from core.models.models import MasterUser
from core.models.api_models import APIClient
from core.services.external_api_auth_service import AuthContext
from core.models.models_per_tenant import BatchProcessingJob
from core.routers.auth import get_current_user
from core.utils.feature_gate import require_feature
from commercial.batch_processing.service import BatchProcessingService
from core.services.rate_limiter_service import get_rate_limiter
from core.utils.audit import log_audit_event
from core.decorators.sandbox_validation import require_production_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external-transactions/batch-processing", tags=["batch-processing"])


async def get_api_key_auth(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
    db: Session = Depends(get_master_db)
) -> tuple[int, int, str, Union[APIClient, AuthContext]]:
    """
    Authenticate using API key or Internal Secret and return context.
    
    Returns:
        Tuple of (tenant_id, user_id, auth_id, auth_context_or_client)
    """
    # 1. Check for Internal Secret (Sidecar Trust)
    if x_internal_secret:
        from core.services.external_api_auth_service import ExternalAPIAuthService
        auth_service = ExternalAPIAuthService()
        
        # Extract headers with robust fallback chain
        tenant_id_str = (
            request.headers.get("X-Plugin-Tenant-Id") or 
            request.headers.get("X-Public-Tenant-Id") or
            request.headers.get("X-Tenant-Id")
        )
        user_email = request.headers.get("X-Plugin-User-Email") or request.headers.get("X-User-Email")
        plugin_id = request.headers.get("X-Plugin-Id")
        
        try:
            tenant_id = int(tenant_id_str) if tenant_id_str else None
        except (ValueError, TypeError):
            tenant_id = None
            
        auth_context = await auth_service.authenticate_internal_secret(db, x_internal_secret, tenant_id, user_email, plugin_id)
        
        if auth_context and auth_context.is_authenticated:
            # Set tenant context globally for this request
            if auth_context.tenant_id:
                from core.models.database import set_tenant_context
                set_tenant_context(auth_context.tenant_id)
            
            # Return context mimicking the APIClient structure where possible
            return (
                auth_context.tenant_id, 
                int(auth_context.user_id) if (auth_context.user_id and auth_context.user_id.isdigit()) else 0, 
                "internal_trust", 
                auth_context
            )

    # 2. Fallback to standard API Key
    import hashlib

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide X-API-Key or X-Internal-Secret header."
        )

    # Hash the provided API key
    api_key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    # Query API client by hashed key
    api_client = db.query(APIClient).filter(
            APIClient.api_key_hash == api_key_hash,
            APIClient.is_active == True,
        APIClient.status == "active"
    ).first()

    if not api_client:
        logger.warning(f"Invalid API key attempt: {x_api_key[:7]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    # Check rate limits (with custom quotas if configured)
    rate_limiter = get_rate_limiter()
    allowed, error_message, retry_after = rate_limiter.check_rate_limit(
        api_client_id=api_client.client_id,
        rate_limit_per_minute=api_client.rate_limit_per_minute,
        rate_limit_per_hour=api_client.rate_limit_per_hour,
        rate_limit_per_day=api_client.rate_limit_per_day,
        custom_quotas=api_client.custom_quotas
    )

    if not allowed:
        logger.warning(
            f"Rate limit exceeded for API client {api_client.client_id}: {error_message}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_message,
            headers={"Retry-After": str(retry_after)} if retry_after else {}
        )

    # Update last used timestamp
    api_client.last_used_at = datetime.now(timezone.utc)
    api_client.total_requests += 1
    db.commit()

    # Set tenant context for this request
    from core.models.database import set_tenant_context
    set_tenant_context(api_client.tenant_id)

    logger.info(
        f"API key authenticated: client={api_client.client_id}, "
        f"tenant={api_client.tenant_id}, tenant context set"
    )

    return (api_client.tenant_id, api_client.user_id, api_client.client_id, api_client)


def get_batch_db(auth_context: tuple = Depends(get_api_key_auth)):
    """
    Get tenant database session after API key authentication.
    This ensures tenant context is set before accessing the database.

    Args:
        auth_context: Authenticated API client context (tenant_id, user_id, client_id, api_client)

    Returns:
        Tenant database session generator
    """
    tenant_id, user_id, client_id, api_client = auth_context

    # Set tenant context explicitly before getting DB session
    from core.models.database import set_tenant_context
    set_tenant_context(tenant_id)

    logger.info(f"get_batch_db: Set tenant context to {tenant_id}")

    # Now get the tenant database session
    db_gen = get_db()
    db = next(db_gen)

    try:
        yield db
    finally:
        try:
            next(db_gen, None)
        except StopIteration:
            pass


def get_batch_processing_service(
    db: Session = Depends(get_batch_db)
) -> BatchProcessingService:
    """
    Dependency to get BatchProcessingService with database session.

    Args:
        db: Tenant database session

    Returns:
        BatchProcessingService instance
    """
    return BatchProcessingService(db)


# ============================================================================
# Batch Processing Endpoints
# ============================================================================

# Note: These endpoints are designed for API key authentication
# For now, they can be tested with JWT authentication by replacing
# the get_api_key_auth dependency with get_current_user


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload batch of files for processing",
    description="Upload up to 50 files for batch OCR processing and export. Requires API key authentication via X-API-Key header."
)
@require_production_api_key("Sandbox API keys cannot create real batch processing jobs. Use a production API key for live batch processing.")
async def upload_batch(
    files: List[UploadFile] = File(..., description="Files to process (max 50)"),
    export_destination_id: Optional[int] = Form(None, description="Export destination configuration ID (uses default if not provided)"),
    document_types: Optional[str] = Form(
        None, 
        description="Comma-separated document types (invoice,expense,statement). "
                    "If one type provided, applies to all files. "
                    "If multiple types provided, must match number of files (maps by index). "
                    "If not provided, auto-detects from filenames."
    ),
    client_id: Optional[int] = Form(None, description="Client ID for invoice documents"),
    custom_fields: Optional[str] = Form(None, description="Comma-separated custom fields to include in export"),
    webhook_url: Optional[str] = Form(None, description="Optional webhook URL for completion notification"),
    card_type: str = Form("auto", description="Statement card type for bank statements: auto|debit|credit"),
    auth_context: tuple = Depends(get_api_key_auth),
    service: BatchProcessingService = Depends(get_batch_processing_service)
):
    """
    Upload a batch of files for processing.

    Accepts multipart/form-data with up to 50 files.
    Files are validated, stored, and enqueued for OCR processing.
    Results are exported to the specified destination when complete.

    **Authentication**: Requires API key via X-API-Key header.

    Args:
        files: List of files to process (max 50, max 20MB each)
        export_destination_id: ID of export destination configuration
        document_types: Optional comma-separated document types.
                        If one type provided, applies to all files.
                        If multiple types, must match number of files (maps by index).
                        If not provided, auto-detects from filenames.
        custom_fields: Optional comma-separated fields for export
        webhook_url: Optional webhook URL for completion notification
        auth_context: Authenticated API client context (tenant_id, user_id, api_client_id, api_client)
        db: Database session
        service: Batch processing service

    Returns:
        Job details including job_id, status, and status_url

    Raises:
        HTTPException: If validation fails or processing cannot be started
    """
    try:
        # Extract authentication context from API key
        tenant_id, user_id, api_client_id, api_client = auth_context
        
        # Check if batch_processing feature is enabled
        from core.utils.feature_gate import check_feature
        check_feature("batch_processing", service.db)

        # Validate document types early to catch permission errors before other checks
        doc_types_list = None
        if document_types:
            doc_types_list = [
                dt.strip().lower() for dt in document_types.split(",") if dt.strip()
            ]
            # Validate document types
            valid_types = {"invoice", "expense", "statement"}
            invalid_types = set(doc_types_list) - valid_types
            if invalid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document types: {', '.join(invalid_types)}. Valid types: {', '.join(valid_types)}",
                )

            # Validate document types against allowed types
            # Note: For internal trusted plugins, we skip the strict api_client check
            if api_client_id == "internal_trust":
                normalized_allowed = ["invoice", "expense", "statement"] # Trusted internal plugins allowed all
            else:
                # Standard API Key validation
                normalized_allowed = [
                    dt.lower().strip() if isinstance(dt, str) else dt
                    for dt in api_client.allowed_document_types
                ]

            # Check each document type against allowed document types
            for doc_type in doc_types_list:
                if doc_type not in normalized_allowed:
                    detail = f"Document type '{doc_type}' is not allowed."
                    if api_client_id != "internal_trust":
                         detail += f" Allowed types: {', '.join(api_client.allowed_document_types)}"
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=detail,
                    )

        # If no export destination specified, use default or create one
        if export_destination_id is None:
            from core.models.models_per_tenant import ExportDestinationConfig
            from sqlalchemy import and_
            from datetime import datetime, timezone

            default_dest = (
                service.db.query(ExportDestinationConfig)
                .filter(
                    and_(
                        ExportDestinationConfig.tenant_id == tenant_id,
                        ExportDestinationConfig.is_active == True,
                        ExportDestinationConfig.is_default == True,
                    )
                )
                .first()
            )

            if not default_dest:
                # Try to create a default local export destination
                logger.info(
                    f"No default export destination found, creating one for tenant {tenant_id}"
                )

                try:
                    default_dest = ExportDestinationConfig(
                        tenant_id=tenant_id,
                        name="Default Local Export",
                        destination_type="local",
                        is_active=True,
                        is_default=True,
                        config={"path": "/exports", "format": "csv"},
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )

                    service.db.add(default_dest)
                    service.db.commit()
                    service.db.refresh(default_dest)

                    logger.info(
                        f"Created default local export destination: {default_dest.name} (ID: {default_dest.id})"
                    )

                except Exception as e:
                    logger.error(f"Failed to create default export destination: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create default export destination. Please configure an export destination manually."
                    )

            export_destination_id = default_dest.id
            logger.info(
                f"Using default export destination: {default_dest.name} (ID: {export_destination_id})"
            )

        logger.info(
            f"Batch upload request from user {user_id} (tenant {tenant_id}): "
            f"{len(files)} files, destination {export_destination_id}"
        )

        # Check concurrent job limits (default: 5 concurrent jobs, or from custom quotas)
        rate_limiter = get_rate_limiter()
        allowed, error_message, active_count = rate_limiter.check_concurrent_jobs(
            api_client_id=api_client_id,
            db=service.db,  # Get db from service
            max_concurrent_jobs=5,  # Configurable default
            custom_quotas=api_client.custom_quotas
        )

        if not allowed:
            logger.warning(
                f"Concurrent job limit exceeded for {api_client_id}: {error_message}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_message,
                headers={"X-Active-Jobs": str(active_count)}
            )

        # Validate file count
        if len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one file is required"
            )

        if len(files) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum 50 files allowed per batch. Received {len(files)} files."
            )

        # Document type parsing and validation moved to earlier in the process
        # This is now handled after file count validation to catch permission errors early

        # Parse custom fields if provided
        custom_fields_list = None
        if custom_fields:
            custom_fields_list = [
                cf.strip() for cf in custom_fields.split(",") if cf.strip()
            ]

        # Read file contents and prepare file info
        file_infos = []
        for idx, file in enumerate(files):
            try:
                # Read file content
                content = await file.read()

                # Validate file size
                file_size = len(content)
                if file_size == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File '{file.filename}' is empty"
                    )

                if file_size > 20 * 1024 * 1024:  # 20MB
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File '{file.filename}' exceeds maximum size of 20MB",
                    )

                file_infos.append(
                    {
                        "content": content,
                        "filename": file.filename or f"file_{idx}",
                        "size": file_size,
                        "content_type": file.content_type,
                    }
                )

                logger.debug(
                    f"Read file {idx+1}/{len(files)}: {file.filename} "
                    f"({file_size} bytes)"
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to read file {file.filename}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read file '{file.filename}': {str(e)}"
                )

        # Create batch job
        try:
            batch_job = await service.create_batch_job(
                files=file_infos,
                tenant_id=tenant_id,
                user_id=user_id,
                api_client_id=api_client_id,
                export_destination_id=export_destination_id,
                document_types=doc_types_list,
                client_id=client_id,
                custom_fields=custom_fields_list,
                webhook_url=webhook_url,
                api_client=api_client,
                card_type=card_type
            )

            logger.info(
                f"Created batch job {batch_job.job_id} with {batch_job.total_files} files"
            )

        except ValueError as e:
            logger.error(f"Validation error creating batch job: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to create batch job: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create batch job: {str(e)}"
            )

        # Enqueue files to Kafka for processing
        try:
            enqueue_result = await service.enqueue_files_to_kafka(batch_job.job_id)

            logger.info(
                f"Enqueued {enqueue_result['enqueued']} files for job {batch_job.job_id}, "
                f"{enqueue_result['failed']} failed"
            )

        except Exception as e:
            logger.error(f"Failed to enqueue files for job {batch_job.job_id}: {e}")
            # Job is created but enqueueing failed - mark as failed
            batch_job.status = "failed"
            service.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue files for processing: {str(e)}"
            )

        # Log audit event
        # For API key auth, include both the API key prefix and the associated user's email
        user_email_display = (
            f"{api_client.api_key_prefix}*** ({api_client.user.email})"
            if api_client.user
            else f"{api_client.api_key_prefix}*** (user_{user_id})"
        )

        log_audit_event(
            db=service.db,
            user_id=user_id,
            user_email=user_email_display,
            action="CREATE",
            resource_type="batch_processing_job",
            resource_id=batch_job.job_id,
            resource_name=f"Batch Job {batch_job.job_id}",
            details={
                "total_files": batch_job.total_files,
                "document_types": batch_job.document_types,
                "export_destination_id": export_destination_id,
                "export_destination_type": batch_job.export_destination_type,
                "enqueued_files": enqueue_result['enqueued'],
                "failed_files": enqueue_result['failed'],
                "api_client_id": api_client.client_id
            },
            status="success"
        )

        # Calculate estimated completion time (rough estimate: 30 seconds per file)
        estimated_completion_minutes = max(1, (batch_job.total_files * 30) // 60)

        # Build response
        return {
            "job_id": batch_job.job_id,
            "status": batch_job.status,
            "total_files": batch_job.total_files,
            "estimated_completion_minutes": estimated_completion_minutes,
            "status_url": f"/api/v1/batch-processing/jobs/{batch_job.job_id}",
            "message": f"Batch job created successfully. {enqueue_result['enqueued']} files enqueued for processing."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in batch upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error processing batch upload: {str(e)}"
        )


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get batch job status",
    description="Get detailed status and progress of a batch processing job. Requires API key authentication via X-API-Key header."
)
async def get_job_status(
    job_id: str,
    auth_context: tuple = Depends(get_api_key_auth),
    db: Session = Depends(get_batch_db),
    service: BatchProcessingService = Depends(get_batch_processing_service)
):
    """
    Get detailed status of a batch processing job.

    Returns job status, progress, file details, and export URL when complete.
    Includes estimated completion time based on average processing time.

    **Authentication**: Requires API key via X-API-Key header.

    Args:
        job_id: Batch job ID (UUID)
        auth_context: Authenticated API client context (tenant_id, user_id, api_client_id, api_client)
        db: Database session
        service: Batch processing service

    Returns:
        Job status details including progress and file information

    Raises:
        HTTPException: If job not found or access denied
    """
    try:
        # Extract authentication context from API key
        tenant_id, user_id, api_client_id, api_client = auth_context

        # Check if batch_processing feature is enabled
        from core.utils.feature_gate import check_feature
        check_feature("batch_processing", db)

        logger.info(
            f"Job status request for {job_id} from API client {api_client_id} "
            f"(tenant {tenant_id})"
        )

        # Get job status with tenant isolation validation
        job_status = service.get_job_status(job_id, tenant_id)

        if not job_status:
            # Job not found or tenant doesn't have access (tenant isolation enforced)
            logger.warning(
                f"Job {job_id} not found or access denied for tenant {tenant_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch job {job_id} not found or access denied"
            )

        # Calculate estimated completion time if job is still processing
        estimated_completion_at = None
        if job_status["status"] in ["pending", "processing"]:
            # Estimate based on remaining files (30 seconds per file)
            remaining_files = (
                job_status['progress']['total_files'] - 
                job_status['progress']['processed_files']
            )
            if remaining_files > 0:
                from datetime import datetime, timezone, timedelta
                estimated_seconds = remaining_files * 30
                estimated_completion_at = (
                    datetime.now(timezone.utc) + timedelta(seconds=estimated_seconds)
                ).isoformat()

        # Add estimated completion time to response
        response = {
            **job_status,
            "estimated_completion_at": estimated_completion_at
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get(
    "/jobs",
    status_code=status.HTTP_200_OK,
    summary="List batch jobs",
    description="List all batch processing jobs for the authenticated API client. Requires API key authentication via X-API-Key header."
)
async def list_jobs(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    auth_context: tuple = Depends(get_api_key_auth),
    db: Session = Depends(get_batch_db)
):
    """
    List all batch processing jobs for the authenticated API client.

    Supports filtering by status and pagination.
    Returns job summaries without detailed file information.

    **Authentication**: Requires API key via X-API-Key header.

    Args:
        status_filter: Optional status filter (pending, processing, completed, failed, partial_failure)
        limit: Maximum number of jobs to return (default: 20, max: 100)
        offset: Number of jobs to skip (default: 0)
        auth_context: Authenticated API client context (tenant_id, user_id, api_client_id, api_client)
        db: Database session

    Returns:
        List of job summaries with pagination info

    Raises:
        HTTPException: If query fails
    """
    try:
        # Extract authentication context from API key
        tenant_id, user_id, api_client_id, api_client = auth_context

        # Check if batch_processing feature is enabled
        from core.utils.feature_gate import check_feature
        check_feature("batch_processing", db)

        logger.info(
            f"List jobs request from API client {api_client_id} (tenant {tenant_id}): "
            f"status={status_filter}, limit={limit}, offset={offset}"
        )

        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100"
            )

        # Validate offset
        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Offset must be non-negative"
            )

        # Validate status filter if provided
        if status_filter:
            valid_statuses = {
                "pending",
                "processing",
                "completed",
                "failed",
                "partial_failure",
            }
            if status_filter not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter. Valid values: {', '.join(valid_statuses)}"
                )

        # Build query with tenant isolation
        from sqlalchemy import and_
        query = db.query(BatchProcessingJob).filter(
            and_(
                BatchProcessingJob.tenant_id == tenant_id,  # Tenant isolation
                BatchProcessingJob.api_client_id == api_client_id
            )
        )

        # Apply status filter if provided
        if status_filter:
            query = query.filter(BatchProcessingJob.status == status_filter)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        jobs = query.order_by(
            BatchProcessingJob.created_at.desc()
        ).limit(limit).offset(offset).all()

        # Build job summaries (without file details)
        job_summaries = []
        for job in jobs:
            summary = {
                "job_id": job.job_id,
                "status": job.status,
                "total_files": job.total_files,
                "processed_files": job.processed_files,
                "successful_files": job.successful_files,
                "failed_files": job.failed_files,
                "progress_percentage": job.progress_percentage,
                "document_types": job.document_types,
                "export_destination_type": job.export_destination_type,
                "export_file_url": job.export_file_url,
                "export_completed_at": job.export_completed_at.isoformat() if job.export_completed_at else None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            job_summaries.append(summary)

        logger.info(
            f"Returning {len(job_summaries)} jobs (total: {total}) "
            f"for API client {api_client_id} (user {user_id})"
        )

        return {
            "jobs": job_summaries,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(job_summaries)) < total
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel batch job",
    description="Cancel a batch processing job and free up concurrent processing slots. Requires API key authentication via X-API-Key header."
)
@require_production_api_key("Sandbox API keys cannot cancel real batch processing jobs. Use a production API key for live batch processing.")
async def cancel_job(
    job_id: str,
    auth_context: tuple = Depends(get_api_key_auth),
    db: Session = Depends(get_batch_db),
    service: BatchProcessingService = Depends(get_batch_processing_service)
):
    """
    Cancel a batch processing job.
    
    Args:
        job_id: Batch job ID (UUID)
        auth_context: Authenticated API client context (tenant_id, user_id, api_client_id, api_client)
        db: Database session
        service: Batch processing service
        
    Returns:
        Confirmation message
        
    Raises:
        HTTPException: If job not found, access denied, or already complete
    """
    try:
        # Extract authentication context from API key
        tenant_id, user_id, api_client_id, api_client = auth_context
        
        # Check if batch_processing feature is enabled
        from core.utils.feature_gate import check_feature
        check_feature("batch_processing", db)

        logger.info(
            f"Cancel job request for {job_id} from API client {api_client_id} "
            f"(tenant {tenant_id})"
        )

        # Cancel job with tenant isolation validation
        success, message = service.cancel_job(job_id, tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}"
        )


@router.delete(
    "/jobs",
    status_code=status.HTTP_200_OK,
    summary="Cancel all batch jobs",
    description="Cancel all active batch processing jobs for the authenticated API client. Requires API key authentication via X-API-Key header."
)
@require_production_api_key("Sandbox API keys cannot cancel real batch processing jobs. Use a production API key for live batch processing.")
async def cancel_all_jobs(
    auth_context: tuple = Depends(get_api_key_auth),
    db: Session = Depends(get_batch_db),
    service: BatchProcessingService = Depends(get_batch_processing_service)
):
    """
    Cancel all active batch processing jobs for the client.
    
    Returns confirmation of how many jobs were cancelled.
    
    **Authentication**: Requires API key via X-API-Key header.
    """
    try:
        # Extract authentication context from API key
        tenant_id, user_id, api_client_id, api_client = auth_context
        
        # Check if batch_processing feature is enabled
        from core.utils.feature_gate import check_feature
        check_feature("batch_processing", db)

        logger.info(f"Cancel all jobs request from API client {api_client_id} (tenant {tenant_id})")

        # Cancel all jobs
        success, message = service.cancel_all_jobs(tenant_id, api_client_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

        return {
            "status": "success",
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel all jobs for {api_client_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel all jobs: {str(e)}"
        )
