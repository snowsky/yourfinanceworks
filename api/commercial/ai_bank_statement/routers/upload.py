"""Upload endpoints for bank statements."""

import os
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from core.models.database import get_db
from core.routers.auth import get_current_user
from core.models.models import MasterUser
from core.utils.rbac import require_non_viewer
from core.utils.feature_gate import require_feature
from core.utils.file_validation import validate_file_magic_bytes
from core.models.models_per_tenant import BankStatement
from core.utils.audit import log_audit_event
from commercial.ai.services.ocr_service import publish_bank_statement_task
from ._shared import get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=Dict[str, Any])
@require_feature("ai_bank_statement")
async def upload_statements(
    files: List[UploadFile] = File(..., description="Up to 12 PDF or CSV statements"),
    card_type: str = Form("auto", description="debit|credit|auto"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user),
):
    """Accept up to 12 PDF/CSV files, create one Statement per file, enqueue processing, and return created statements."""
    require_non_viewer(current_user, "upload statements")

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(files) > 12:
        raise HTTPException(status_code=400, detail="Maximum of 12 files are allowed")

    allowed_types = {"application/pdf", "text/csv", "application/vnd.ms-excel"}

    tenant_id = get_tenant_id()

    tenant_folder = f"tenant_{tenant_id}"
    base_dir = Path("attachments") / tenant_folder / "bank_statements"
    base_dir.mkdir(parents=True, exist_ok=True)

    created: List[Dict[str, Any]] = []

    try:
        for f in files:
            if f.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400, detail="Only PDF or CSV files are supported"
                )
            contents = await f.read()
            if len(contents) > 20 * 1024 * 1024:
                raise HTTPException(
                    status_code=400, detail="Each file must be <= 20 MB"
                )
            validate_file_magic_bytes(contents, f.content_type)
            await f.seek(0)

            name = (f.filename or "statement.pdf").strip()
            name = os.path.basename(name)
            name = "".join(ch for ch in name if ch.isalnum() or ch in (".", "_", "-"))
            stem, _ext = os.path.splitext(name)
            unique = uuid.uuid4().hex
            ext = _ext.lower() if _ext else ".pdf"
            if ext not in (".pdf", ".csv"):
                # Normalize unknown extensions to .pdf for storage but keep original filename for display
                ext = ".pdf"
            stored_filename = f"bs_{stem[:100]}_{unique}{ext}"
            out_path = base_dir / stored_filename
            with open(out_path, "wb") as out:
                shutil.copyfileobj(f.file, out)

            # Upload to cloud storage
            cloud_file_url = None
            try:
                try:
                    from commercial.cloud_storage.service import CloudStorageService
                    from commercial.cloud_storage.config import get_cloud_storage_config

                    cloud_config = get_cloud_storage_config()
                    cloud_storage_service = CloudStorageService(db, cloud_config)

                    # Upload file to cloud storage
                    cloud_file_key = f"tenant_{tenant_id}/bank_statements/{stored_filename}"

                    # Upload file to cloud storage
                    storage_result = await cloud_storage_service.store_file(
                        file_content=contents,
                        tenant_id=str(tenant_id),
                        item_id=0,  # Will be updated after statement is created
                        attachment_type="bank_statements",
                        original_filename=name,
                        user_id=current_user.id,
                        metadata={
                            "original_filename": name,
                            "stored_filename": stored_filename,
                            "uploaded_at": datetime.utcnow().isoformat(),
                            "file_size": len(contents),
                            "document_type": "bank_statement",
                            "upload_method": "internal_api",
                        },
                        file_key=cloud_file_key
                    )

                    if storage_result.success:
                        cloud_file_url = storage_result.file_url
                        logger.info(
                            f"Bank statement uploaded to cloud storage: {cloud_file_url}"
                        )
                    else:
                        logger.warning(
                            f"Cloud storage upload failed, using local file: {storage_result.error_message}"
                        )
                except ImportError:
                    logger.info(
                        "Commercial CloudStorageService not found, using local file only"
                    )
            except Exception as e:
                logger.error(f"Cloud storage upload failed: {e}")

            # Create statement in processing state and enqueue OCR task
            statement = BankStatement(
                tenant_id=tenant_id,
                original_filename=name,
                stored_filename=stored_filename,
                file_path=str(out_path),
                cloud_file_url=cloud_file_url,
                status="processing",
                extracted_count=0,
                card_type=card_type,
                created_by_user_id=current_user.id,  # User attribution
            )
            db.add(statement)
            db.flush()
            # Force async-only: always enqueue, no sync fallback
            try:
                topic_name = os.getenv("KAFKA_BANK_TOPIC", "bank_statements_ocr")
                logger.info(
                    f"Enqueue bank statement id={statement.id} topic={topic_name}"
                )
                ok = publish_bank_statement_task(
                    {
                        "tenant_id": tenant_id,
                        "statement_id": statement.id,
                        "file_path": str(out_path),
                        "ts": datetime.utcnow().isoformat(),
                    }
                )
                if not ok:
                    logger.warning(
                        f"Bank enqueue failed servers={os.getenv('KAFKA_BOOTSTRAP_SERVERS')} topic={topic_name}"
                    )
                    raise RuntimeError("Failed to enqueue bank statement task")
                else:
                    logger.info(
                        f"Bank enqueue success id={statement.id} topic={topic_name}"
                    )
            except Exception as e:
                statement.status = "failed"
                statement.analysis_error = "Failed to queue for processing"
                logger.error(f"Failed to enqueue bank statement {statement.id}: {e}")
            finally:
                # Persist statement state so it appears immediately
                db.commit()
                db.refresh(statement)

            # Audit log for bank statement upload
            try:
                log_audit_event(
                    db=db,
                    user_id=current_user.id,
                    user_email=current_user.email,
                    action="statement_upload",
                    resource_type="bank_statement",
                    resource_id=str(statement.id),
                    resource_name=statement.original_filename,
                    details={"file_size": len(contents), "file_type": ext},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to log audit event for bank statement {statement.id}: {e}"
                )

            created.append(
                {
                    "id": statement.id,
                    "original_filename": statement.original_filename,
                    "stored_filename": statement.stored_filename,
                    "file_path": statement.file_path,
                    "status": statement.status,
                    "extracted_count": statement.extracted_count,
                    "created_at": (
                        statement.created_at.isoformat()
                        if statement.created_at
                        else None
                    ),
                }
            )

        return {"success": True, "statements": created}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to process bank statements: {e}"
        )
    finally:
        # No cleanup: keep uploads under attachments for audit/debug
        pass
