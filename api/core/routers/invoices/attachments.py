"""Invoice attachment endpoints (legacy and new attachment system)."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import logging
import os
from pathlib import Path
import re
import mimetypes

from core.models.database import get_db
from core.models.models_per_tenant import Invoice, InvoiceAttachment
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.utils.rbac import require_non_viewer
from core.utils.file_deletion import delete_file_from_storage
from core.utils.timezone import get_tenant_timezone_aware_datetime
from ._shared import get_attachment_info

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{invoice_id}/upload-attachment")
async def upload_invoice_attachment(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Upload an attachment for an invoice using cloud storage with local fallback"""
    logger.info(f"🔍 UPLOAD ENDPOINT CALLED - invoice_id: {invoice_id}, filename: {file.filename}, content_type: {file.content_type}")
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Validate file type
        allowed_types = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'image/jpeg': '.jpg',
            'image/png': '.png'
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="File type not allowed. Supported types: PDF, DOC, DOCX, JPG, PNG"
            )

        # Enforce max file size (e.g., 10 MB)
        MAX_BYTES = 10 * 1024 * 1024
        contents = await file.read()
        if len(contents) > MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 10 MB"
            )

        # Basic content sniffing for PDFs (starts with %PDF)
        if file.content_type == 'application/pdf':
            header_bytes = contents[:4]
            if header_bytes != b'%PDF':
                raise HTTPException(status_code=400, detail="Invalid PDF file")

        # Get tenant context
        from core.models.database import get_tenant_context
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="Tenant context not available")

        # Sanitize filename
        original_name = file.filename or "attachment"
        base_name = os.path.basename(original_name)
        base_name = re.sub(r"[^A-Za-z0-9._-]", "_", base_name)

        # Get tenant context
        try:
            try:
                from commercial.cloud_storage.service import CloudStorageService
                from commercial.cloud_storage.config import get_cloud_storage_config

                cloud_config = get_cloud_storage_config()
                cloud_storage_service = CloudStorageService(db, cloud_config)

                # Store file using cloud storage with automatic fallback
                storage_result = await cloud_storage_service.store_file(
                    file_content=contents,
                    tenant_id=str(tenant_id),
                    item_id=invoice_id,
                    attachment_type="invoices",
                    original_filename=base_name,
                    user_id=current_user.id,
                    metadata={
                        'content_type': file.content_type,
                        'invoice_id': invoice_id
                    }
                )

                if not storage_result.success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store file: {storage_result.error_message}"
                    )

                # Determine storage location and file path
                if storage_result.file_url:
                    # Cloud storage - use file_key as path
                    file_path = storage_result.file_key
                    stored_filename = storage_result.file_key
                    is_cloud_stored = True
                else:
                    # Local storage fallback - construct traditional path
                    tenant_folder = f"tenant_{tenant_id}"
                    attachments_dir = Path("attachments") / tenant_folder / "invoices"
                    name_without_ext = os.path.splitext(base_name)[0][:100]
                    ext_from_ct = allowed_types[file.content_type]
                    filename = f"invoice_{invoice_id}_{name_without_ext}{ext_from_ct}"
                    file_path = str(attachments_dir / filename)
                    stored_filename = filename
                    is_cloud_stored = False

                logger.info(f"File stored successfully: {file_path} (cloud: {is_cloud_stored})")
            except ImportError:
                logger.info("Commercial CloudStorageService not found, falling back to local storage")
                raise Exception("Commercial module not found")

        except Exception as e:
            if "Commercial module not found" not in str(e):
                logger.error(f"Cloud storage service error: {e}")
            # Fallback to local storage
            tenant_folder = f"tenant_{tenant_id}"
            attachments_dir = Path("attachments") / tenant_folder / "invoices"
            attachments_dir.mkdir(parents=True, exist_ok=True)

            name_without_ext = os.path.splitext(base_name)[0][:100]
            ext_from_ct = allowed_types[file.content_type]
            filename = f"invoice_{invoice_id}_{name_without_ext}{ext_from_ct}"
            file_path = attachments_dir / filename

            # Validate file path before any file operations
            from core.utils.file_validation import validate_file_path
            validated_path = validate_file_path(str(file_path), must_exist=False)

            # Remove old attachment if exists
            if invoice.attachment_path and os.path.exists(invoice.attachment_path):
                try:
                    old_validated_path = validate_file_path(invoice.attachment_path)
                    os.remove(old_validated_path)
                    logger.info(f"Removed old attachment: {invoice.attachment_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove old attachment: {e}")

            # Save file locally
            with open(validated_path, "wb") as buffer:
                buffer.write(contents)

            file_path = str(file_path)
            stored_filename = filename
            is_cloud_stored = False
            logger.info(f"File stored locally as fallback: {file_path}")

        # Update invoice with attachment info (old system for backward compatibility)
        invoice.attachment_path = file_path
        invoice.attachment_filename = file.filename
        invoice.updated_at = get_tenant_timezone_aware_datetime(db)

        # Create new-style attachment record
        import hashlib
        file_hash = hashlib.sha256(contents).hexdigest()

        new_attachment = InvoiceAttachment(
            invoice_id=invoice_id,
            filename=file.filename or "attachment",
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=len(contents),
            content_type=file.content_type,
            file_hash=file_hash,
            attachment_type="document",  # Default type for old endpoint
            uploaded_by=current_user.id,
            is_active=True
        )
        db.add(new_attachment)

        # Create history entry for attachment upload
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        history_entry = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action='attachment_uploaded',
            details=f'Attachment uploaded: {file.filename}',
            current_values={
                'attachment_filename': file.filename,
                'file_size': len(contents),
                'content_type': file.content_type
            }
        )
        db.add(history_entry)

        logger.info(f"🔍 BEFORE COMMIT - invoice {invoice_id}: path={file_path}, filename={file.filename}")
        logger.info(f"🔍 BEFORE COMMIT - invoice object: attachment_path={invoice.attachment_path}, attachment_filename={invoice.attachment_filename}")

        try:
            db.commit()
            logger.info(f"✅ DATABASE COMMIT SUCCESSFUL for invoice {invoice_id}")
        except Exception as commit_error:
            logger.error(f"❌ DATABASE COMMIT FAILED for invoice {invoice_id}: {commit_error}")
            raise

        db.refresh(invoice)

        logger.info(f"✅ AFTER COMMIT - invoice {invoice_id}: attachment_path={invoice.attachment_path}, attachment_filename={invoice.attachment_filename}")

        # Verify the data was saved by querying again
        verification_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        logger.info(f"🔍 VERIFICATION QUERY - invoice {invoice_id}: attachment_path={verification_invoice.attachment_path}, attachment_filename={verification_invoice.attachment_filename}")
        logger.info(f"🔍 VERIFICATION QUERY - has_attachment would be: {bool(verification_invoice.attachment_filename)}")

        # Check new-style attachments for consistent response
        new_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        ).all()

        api_has_attachment, api_attachment_filename = get_attachment_info(invoice, new_attachments)

        logger.info(f"🔍 API RESPONSE CHECK - has_attachment: {api_has_attachment}, attachment_filename: '{api_attachment_filename}'")

        logger.info(f"✅ UPLOAD ENDPOINT SUCCESS - Returning response for invoice {invoice_id}")
        return {
            "message": "Attachment uploaded successfully",
            "filename": file.filename,
            "size": len(contents),
            "attachment_path": str(file_path),
            "attachment_filename": api_attachment_filename,
            "has_attachment": api_has_attachment
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading attachment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload attachment: {str(e)}"
        )


@router.get("/{invoice_id}/download-attachment")
async def download_invoice_attachment(
    invoice_id: int,
    attachment_id: Optional[int] = Query(None, description="Specific attachment ID to download"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Download an invoice attachment (supports both cloud and local storage)"""
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Try new-style attachments first
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_id:
            new_attachment = query.filter(InvoiceAttachment.id == attachment_id).first()
        else:
            new_attachment = query.order_by(InvoiceAttachment.created_at.desc()).first()

        if new_attachment:
            # Check if this is a cloud storage file (file_path doesn't start with local path)
            if not new_attachment.file_path.startswith('/') and not new_attachment.file_path.startswith('attachments'):
                # This is likely a cloud storage file key - download and serve directly
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)

                            # Download file content from cloud storage
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=new_attachment.file_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,  # Download content instead of URL
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                # Return file content as streaming response with attachment disposition
                                headers = {
                                    "Content-Disposition": f"attachment; filename={new_attachment.filename or 'attachment'}",
                                    # Add CORS headers for browser access
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }

                                return StreamingResponse(
                                    io.BytesIO(storage_result.file_content),
                                    media_type=new_attachment.content_type or 'application/octet-stream',
                                    headers=headers
                                )
                            else:
                                logger.warning(f"Failed to download from cloud storage: {storage_result.error_message}")
                    except ImportError:
                        logger.info("Commercial CloudStorageService not found, cannot download from cloud")
                except Exception as e:
                    logger.warning(f"Cloud storage retrieval failed, falling back to local: {e}")

            # Local file or cloud storage fallback - serve directly
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(new_attachment.file_path)
                return FileResponse(
                    path=validated_path,
                    filename=new_attachment.filename,
                    media_type=new_attachment.content_type or 'application/octet-stream'
                )
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # Fall back to old-style attachment
        if invoice.attachment_path and invoice.attachment_filename:
            # Check if this is a cloud storage file
            if not invoice.attachment_path.startswith('/') and not invoice.attachment_path.startswith('attachments'):
                # This is likely a cloud storage file key - download and serve directly
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)

                            # Download file content from cloud storage
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=invoice.attachment_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,  # Download content instead of URL
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                # Return file content as streaming response with attachment disposition
                                headers = {
                                    "Content-Disposition": f"attachment; filename={invoice.attachment_filename or 'attachment'}",
                                    # Add CORS headers for browser access
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }

                                return StreamingResponse(
                                    io.BytesIO(storage_result.file_content),
                                    media_type='application/octet-stream',
                                    headers=headers
                                )
                            else:
                                logger.warning(f"Failed to download from cloud storage: {storage_result.error_message}")
                    except ImportError:
                        logger.info("Commercial CloudStorageService not found, cannot download from cloud")
                except Exception as e:
                    logger.warning(f"Cloud storage retrieval failed, falling back to local: {e}")

            # Local file - serve directly
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(invoice.attachment_path)
                return FileResponse(
                    path=validated_path,
                    filename=invoice.attachment_filename,
                    media_type='application/octet-stream'
                )
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # No attachment found
        raise HTTPException(status_code=404, detail="No attachment found for this invoice")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading attachment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download attachment: {str(e)}"
        )


@router.get("/{invoice_id}/attachment-info")
async def get_invoice_attachment_info(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Return metadata for the invoice attachment so the UI can decide to preview or download."""
    try:
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        has_attachment = bool(getattr(invoice, "attachment_path", None) and os.path.exists(invoice.attachment_path))
        content_type, _ = (mimetypes.guess_type(invoice.attachment_filename or "") if has_attachment else (None, None))
        size_bytes = os.path.getsize(invoice.attachment_path) if has_attachment else None
        return {
            "has_attachment": has_attachment,
            "filename": invoice.attachment_filename,
            "content_type": content_type or "application/octet-stream",
            "file_size": size_bytes,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attachment info for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attachment info")


@router.get("/{invoice_id}/preview-attachment")
async def preview_invoice_attachment(
    invoice_id: int,
    attachment_id: Optional[int] = Query(None, description="Specific attachment ID to preview"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Serve the invoice attachment with inline Content-Disposition for browser preview (PDF/images)."""
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Try new-style attachments first
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_id:
            new_attachment = query.filter(InvoiceAttachment.id == attachment_id).first()
        else:
            new_attachment = query.order_by(InvoiceAttachment.created_at.desc()).first()

        if new_attachment:
            # Check if this is a cloud storage file
            if not new_attachment.file_path.startswith('/') and not new_attachment.file_path.startswith('attachments'):
                # Cloud storage logic
                try:
                    try:
                        from commercial.cloud_storage.service import CloudStorageService
                        from commercial.cloud_storage.config import get_cloud_storage_config
                        from core.models.database import get_tenant_context
                        import io

                        tenant_id = get_tenant_context()
                        if tenant_id:
                            cloud_config = get_cloud_storage_config()
                            cloud_storage_service = CloudStorageService(db, cloud_config)
                            storage_result = await cloud_storage_service.retrieve_file(
                                file_key=new_attachment.file_path,
                                tenant_id=str(tenant_id),
                                user_id=current_user.id,
                                generate_url=False,
                                expiry_seconds=3600
                            )

                            if storage_result.success and storage_result.file_content:
                                media_type = new_attachment.content_type or mimetypes.guess_type(new_attachment.filename)[0] or "application/octet-stream"
                                headers = {
                                    "Content-Disposition": f"inline; filename={new_attachment.filename}",
                                    "Access-Control-Allow-Origin": "*",
                                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                                    "Access-Control-Allow-Headers": "*"
                                }
                                return StreamingResponse(io.BytesIO(storage_result.file_content), media_type=media_type, headers=headers)
                    except ImportError: pass
                except Exception as e: logger.warning(f"Cloud preview failed: {e}")

            # Local fallback
            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(new_attachment.file_path)
                media_type = new_attachment.content_type or mimetypes.guess_type(new_attachment.filename)[0] or "application/octet-stream"
                return FileResponse(path=validated_path, filename=new_attachment.filename, media_type=media_type, headers={"Content-Disposition": f"inline; filename={new_attachment.filename}"})
            except Exception as e:
                logger.error(f"Failed to serve local file: {e}")
                raise HTTPException(status_code=404, detail="Attachment file not accessible")

        # Fallback to old-style attachment
        if invoice.attachment_path:
            # (Keep existing legacy fallback logic basically, but adapted)
            if not invoice.attachment_path.startswith('/') and not invoice.attachment_path.startswith('attachments'):
                # Cloud storage legacy...
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config
                    from core.models.database import get_tenant_context
                    import io
                    tenant_id = get_tenant_context()
                    if tenant_id:
                        cloud_config = get_cloud_storage_config()
                        cloud_storage_service = CloudStorageService(db, cloud_config)
                        storage_result = await cloud_storage_service.retrieve_file(file_key=invoice.attachment_path, tenant_id=str(tenant_id), user_id=current_user.id, generate_url=False, expiry_seconds=3600)
                        if storage_result.success and storage_result.file_content:
                            media_type, _ = mimetypes.guess_type(invoice.attachment_filename or "")
                            media_type = media_type or "application/octet-stream"
                            return StreamingResponse(io.BytesIO(storage_result.file_content), media_type=media_type, headers={"Content-Disposition": f"inline; filename={invoice.attachment_filename or 'attachment'}", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS"})
                except: pass

            try:
                from core.utils.file_validation import validate_file_path
                validated_path = validate_file_path(invoice.attachment_path)
                media_type, _ = mimetypes.guess_type(invoice.attachment_filename or "")
                media_type = media_type or "application/octet-stream"
                return FileResponse(path=validated_path, filename=invoice.attachment_filename, media_type=media_type, headers={"Content-Disposition": f"inline; filename={invoice.attachment_filename or 'attachment'}"})
            except: pass

        raise HTTPException(status_code=404, detail="No attachment found")

    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error previewing attachment for invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview attachment")


# === Invoice Attachments Endpoints (new system) ===

@router.post("/{invoice_id}/attachments/")
@router.post("/{invoice_id}/attachments")
async def upload_invoice_attachment_new(
    invoice_id: int,
    file: UploadFile = File(...),
    attachment_type: Optional[str] = Query("document", description="Attachment type: 'image' or 'document'"),
    document_type: Optional[str] = Query(None, description="Document type (for documents)"),
    description: Optional[str] = Query(None, description="Optional description"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Upload a new attachment for an invoice (using new attachment system)
    """
    try:
        # Check if user has permission
        require_non_viewer(current_user, "upload attachments")

        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Basic validation
        if attachment_type and attachment_type not in ['image', 'document']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment_type must be 'image' or 'document'"
            )

        # Default to document if not specified
        if not attachment_type:
            attachment_type = "document"

        # Validate file type before reading
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        file_ext = os.path.splitext(file.filename.lower())[1]
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv'}
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}")

        # Read file content for validation
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided"
            )

        # Validate file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is 10MB")

        import uuid
        import hashlib

        # Create attachments directory
        from core.models.database import get_tenant_context
        from core.utils.file_validation import validate_file_path

        tenant_id = get_tenant_context()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context not available")

        tenant_folder = f"tenant_{tenant_id}"
        attachments_dir = Path("attachments") / tenant_folder / "invoices"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with validated extension
        file_extension = Path(file.filename or "attachment").suffix
        if file_extension not in allowed_extensions:
            file_extension = ".txt"  # Safe fallback

        stored_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = attachments_dir / stored_filename

        # Validate file path before saving
        validated_path = validate_file_path(str(file_path))

        # Save file to disk
        with open(validated_path, "wb") as f:
            f.write(file_content)

        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Create attachment record
        attachment = InvoiceAttachment(
            invoice_id=invoice_id,
            filename=file.filename or "attachment",
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_size=len(file_content),
            content_type=file.content_type,
            file_hash=file_hash,
            attachment_type=attachment_type,
            document_type=document_type,
            description=description,
            uploaded_by=current_user.id,
            is_active=True
        )

        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        # Queue invoice for async OCR processing if it's a document that could contain invoice data
        ocr_queued = False
        task_id = None
        if attachment_type == "document" and file_ext in {'.pdf', '.jpg', '.jpeg', '.png'}:
            try:
                from commercial.ai.services.ocr_service import publish_invoice_task

                # Generate task ID for tracking
                task_id = str(uuid.uuid4())

                # Queue the OCR task
                message = {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "file_path": str(file_path),
                    "filename": file.filename,
                    "user_id": current_user.id,
                    "invoice_id": invoice_id,
                    "attachment_id": attachment.id,
                    "attempt": 0
                }

                success = publish_invoice_task(message)

                if success:
                    ocr_queued = True
                    logger.info(f"Invoice attachment queued for OCR: task_id={task_id}, attachment_id={attachment.id}")
                else:
                    logger.warning(f"Failed to queue invoice attachment for OCR: attachment_id={attachment.id}")

            except Exception as e:
                logger.error(f"Failed to queue invoice OCR: {e}")

        response = {
            "id": attachment.id,
            "invoice_id": invoice_id,
            "filename": attachment.filename,
            "file_size": attachment.file_size,
            "attachment_type": attachment.attachment_type,
            "document_type": attachment.document_type,
            "description": attachment.description,
            "created_at": attachment.created_at.isoformat(),
            "status": "success",
            "message": "Attachment uploaded successfully"
        }

        # Include OCR task info if queued
        if ocr_queued and task_id:
            response["ocr_status"] = "queued"
            response["ocr_task_id"] = task_id
            response["message"] = "Attachment uploaded and queued for OCR processing"

        # Release processing lock for invoice if it was used
        try:
            from commercial.ai.services.ocr_service import release_processing_lock
            invoice_id_for_lock = invoice_id
            released = release_processing_lock("invoice", invoice_id_for_lock)
            if released:
                logger.info(f"Released processing lock for invoice {invoice_id_for_lock}")
        except Exception as lock_error:
            logger.warning(f"Failed to release processing lock for invoice {invoice_id}: {lock_error}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process invoice attachment upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process file upload"
        )


@router.delete("/{invoice_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_attachment(
    invoice_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Delete an invoice attachment (soft delete by marking as inactive)
    """
    try:
        # Check if user has permission
        require_non_viewer(current_user, "delete attachments")

        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Find the attachment
        attachment = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.id == attachment_id,
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        ).first()

        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # Allow deletion regardless of whether the file can be previewed
        # This handles cases where files are missing or corrupted

        # Soft delete the attachment (mark as inactive)
        attachment.is_active = False
        attachment.updated_at = get_tenant_timezone_aware_datetime(db)

        # Clear old-style attachment fields on the invoice if no active attachments remain
        remaining_attachments = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True,
            InvoiceAttachment.id != attachment_id  # Exclude the one we're deleting
        ).count()

        if remaining_attachments == 0:
            # No active attachments left, clear old fields
            invoice.attachment_filename = None
            invoice.attachment_path = None

        # Delete the physical file from storage (cloud and/or local)
        if attachment.file_path:
            await delete_file_from_storage(attachment.file_path, current_user.tenant_id, current_user.id, db)

        # Create history entry for attachment deletion
        from core.models.models_per_tenant import InvoiceHistory as InvoiceHistoryModel
        history_entry = InvoiceHistoryModel(
            invoice_id=invoice_id,
            user_id=current_user.id,
            action='attachment_deleted',
            details=f'Attachment deleted: {attachment.filename}',
            current_values={
                'attachment_id': attachment.id,
                'filename': attachment.filename,
                'file_size': attachment.file_size
            }
        )
        db.add(history_entry)
        db.commit()

        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete invoice attachment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment"
        )


@router.get("/{invoice_id}/attachments/")
@router.get("/{invoice_id}/attachments")
async def get_invoice_attachments(
    invoice_id: int,
    attachment_type: Optional[str] = Query(None, description="Filter by attachment type"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """
    Get all attachments for an invoice
    """
    try:
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.is_deleted == False
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Query attachments
        query = db.query(InvoiceAttachment).filter(
            InvoiceAttachment.invoice_id == invoice_id,
            InvoiceAttachment.is_active == True
        )

        if attachment_type:
            query = query.filter(InvoiceAttachment.attachment_type == attachment_type)

        attachments = query.order_by(InvoiceAttachment.created_at.desc()).all()

        # Format response
        attachment_list = []
        for attachment in attachments:
            attachment_list.append({
                "id": attachment.id,
                "filename": attachment.filename,
                "file_size": attachment.file_size,
                "content_type": attachment.content_type,
                "attachment_type": attachment.attachment_type,
                "document_type": attachment.document_type,
                "description": attachment.description,
                "created_at": attachment.created_at.isoformat(),
                "uploaded_by": attachment.uploaded_by
            })

        return {
            "invoice_id": invoice_id,
            "attachments": attachment_list,
            "total_count": len(attachment_list)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get invoice attachments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attachments"
        )
