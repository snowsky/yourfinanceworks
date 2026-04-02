"""
Batch job creation for batch processing.

Orchestrates validation, document-type detection, file storage,
cloud upload, and audit logging when creating a new batch job.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import and_

from core.models.models_per_tenant import (
    BatchProcessingJob,
    BatchFileProcessing,
    ExportDestinationConfig,
)
from core.utils.audit import log_audit_event
from core.utils.plugin_context import bypass_plugin_isolation

logger = logging.getLogger(__name__)


class BatchJobCreationMixin:
    """Mixin providing batch job creation logic."""

    async def create_batch_job(
        self,
        files: List[Dict[str, Any]],
        tenant_id: int,
        user_id: int,
        api_client_id: str,
        export_destination_id: int,
        document_types: Optional[List[str]] = None,
        client_id: Optional[int] = None,
        custom_fields: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        api_client: Optional[Any] = None,
        card_type: str = "auto"
    ) -> BatchProcessingJob:
        try:
            if not self.validate_batch_size(len(files)):
                raise ValueError(
                    f"Batch size must be between 1 and {self.MAX_FILES_PER_BATCH} files. "
                    f"Received {len(files)} files."
                )

            export_destination = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == export_destination_id,
                    ExportDestinationConfig.tenant_id == tenant_id,
                    ExportDestinationConfig.is_active == True
                )
            ).first()

            if not export_destination:
                logger.warning(
                    f"Export destination {export_destination_id} not found for tenant {tenant_id}. "
                    f"Attempting to use default destination."
                )
                export_destination = self.db.query(ExportDestinationConfig).filter(
                    and_(
                        ExportDestinationConfig.tenant_id == tenant_id,
                        ExportDestinationConfig.is_active == True,
                        ExportDestinationConfig.is_default == True
                    )
                ).first()

            if not export_destination:
                raise ValueError(
                    f"Export destination {export_destination_id} not found or inactive "
                    f"for tenant {tenant_id} and no default destination configured"
                )

            for idx, file_info in enumerate(files):
                filename = file_info.get('filename', f'file_{idx}')
                file_size = file_info.get('size', 0)

                if not self.validate_file_type(filename):
                    ext = self.get_file_extension(filename)
                    raise ValueError(
                        f"File '{filename}' has invalid type '{ext}'. "
                        f"Allowed types: {', '.join(self.ALLOWED_FILE_TYPES)}"
                    )

                if not self.validate_file_size(file_size):
                    raise ValueError(
                        f"File '{filename}' size {file_size} bytes exceeds maximum "
                        f"{self.MAX_FILE_SIZE_BYTES} bytes "
                        f"({self.MAX_FILE_SIZE_BYTES // (1024*1024)}MB)"
                    )

            job_id = self.generate_job_id()

            if not document_types:
                document_types = []
                for file_info in files:
                    filename = file_info.get('filename', '')
                    doc_type = await self.determine_document_type(
                        filename, content=file_info.get('content')
                    )
                    if doc_type not in document_types:
                        document_types.append(doc_type)

            file_document_types = []
            if document_types:
                if len(document_types) == 1:
                    file_document_types = [document_types[0]] * len(files)
                elif len(document_types) == len(files):
                    file_document_types = document_types
                else:
                    raise ValueError(
                        f"Number of document types ({len(document_types)}) must match "
                        f"number of files ({len(files)}) or be 1 (applied to all files). "
                        f"Provided types: {', '.join(document_types)}"
                    )
            else:
                file_document_types = []
                for idx, file_info in enumerate(files):
                    doc_type = await self.determine_document_type(
                        file_info.get('filename', f'file_{idx}'),
                        content=file_info.get('content')
                    )
                    file_document_types.append(doc_type)
                document_types = list(set(file_document_types))

            batch_job = BatchProcessingJob(
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                api_client_id=api_client_id,
                document_types=document_types,
                client_id=client_id,
                total_files=len(files),
                export_destination_type=export_destination.destination_type,
                export_destination_config_id=export_destination.id,
                custom_fields=custom_fields,
                webhook_url=webhook_url,
                status="pending",
                processed_files=0,
                successful_files=0,
                failed_files=0,
                progress_percentage=0.0
            )

            self.db.add(batch_job)
            self.db.flush()

            stored_files = []
            for idx, file_info in enumerate(files):
                try:
                    filename = file_info.get('filename', f'file_{idx}')
                    file_content = file_info.get('content')
                    file_size = file_info.get('size', len(file_content) if file_content else 0)
                    doc_type = file_document_types[idx]

                    stored_filename = self._generate_stored_filename(job_id, idx, filename)
                    file_path = self._store_file_to_disk(
                        file_content, tenant_id, job_id, stored_filename
                    )

                    batch_file = BatchFileProcessing(
                        job_id=job_id,
                        original_filename=filename,
                        stored_filename=stored_filename,
                        file_path=file_path,
                        file_size=file_size,
                        document_type=doc_type,
                        status="pending",
                        retry_count=0,
                        extracted_data={"card_type": card_type} if doc_type == "statement" else None
                    )

                    self.db.add(batch_file)
                    self.db.flush()
                    stored_files.append(batch_file)

                    logger.info(f"Stored file {idx+1}/{len(files)}: {filename} -> {file_path}")

                except Exception as e:
                    logger.error(f"Failed to store file {filename}: {e}")
                    self._cleanup_stored_files(stored_files)
                    raise ValueError(f"Failed to store file '{filename}': {str(e)}")

            self.db.commit()
            self.db.refresh(batch_job)

            logger.info(
                f"Created batch job {job_id} with {len(files)} files "
                f"for tenant {tenant_id}"
            )

            if export_destination:
                logger.info(f"Uploading {len(stored_files)} files to cloud storage")
                import asyncio

                # Extract IDs and paths to avoid DetachedInstanceError in background task
                file_info_list = [
                    {
                        "id": f.id,
                        "file_path": f.file_path,
                        "original_filename": f.original_filename
                    }
                    for f in stored_files
                ]
                export_dest_id = export_destination.id

                async def upload_files_to_cloud():
                    from core.services.tenant_database_manager import tenant_db_manager
                    SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
                    
                    with bypass_plugin_isolation():
                        with SessionLocal_tenant() as db:
                            # Re-fetch configuration in the new session
                            if export_dest_id:
                                dest_config = db.query(ExportDestinationConfig).filter(
                                    ExportDestinationConfig.id == export_dest_id
                                ).first()
                            else:
                                # Try to find default destination for tenant if none was provided
                                from sqlalchemy import and_
                                dest_config = db.query(ExportDestinationConfig).filter(
                                    and_(
                                        ExportDestinationConfig.tenant_id == tenant_id,
                                        ExportDestinationConfig.is_default == True
                                    )
                                ).first()
                            
                            if not dest_config:
                                logger.warning(f"No export destination found for tenant {tenant_id} in background task. Skipping cloud upload.")
                                return

                            for file_info in file_info_list:
                                file_id = file_info["id"]
                                try:
                                    cloud_url = await self._upload_file_to_cloud(
                                        file_path=file_info["file_path"],
                                        original_filename=file_info["original_filename"],
                                        destination_config=dest_config,
                                        tenant_id=tenant_id,
                                        job_id=job_id,
                                        db=db
                                    )
                                    if cloud_url:
                                        # Update record in the background task's session
                                        db.query(BatchFileProcessing).filter(
                                            BatchFileProcessing.id == file_id
                                        ).update({"cloud_file_url": cloud_url})
                                        db.commit()
                                        logger.info(f"✅ [Background] Uploaded {file_info['original_filename']} to cloud for job {job_id}")
                                    else:
                                        logger.error(f"❌ [Background] Failed to get cloud URL for {file_info['original_filename']} (job {job_id})")
                                except Exception as e:
                                    logger.error(
                                        f"❌ [Background] Error uploading {file_info['original_filename']} for job {job_id}: {e}"
                                    )
                            
                            logger.info(f"🏁 [Background] Completed cloud upload phase for job {job_id}")

                try:
                    asyncio.create_task(upload_files_to_cloud())
                except RuntimeError:
                    asyncio.run(upload_files_to_cloud())

            try:
                from core.models.database import set_tenant_context
                set_tenant_context(tenant_id)

                if api_client and hasattr(api_client, 'api_key_prefix') and hasattr(api_client, 'user'):
                    user_email_display = (
                        f"{api_client.api_key_prefix}*** ({api_client.user.email})"
                        if api_client.user
                        else f"{api_client.api_key_prefix}*** (user_{user_id})"
                    )
                else:
                    user_email_display = f"user_{user_id}@tenant_{tenant_id}"

                log_audit_event(
                    db=self.db,
                    user_id=user_id,
                    user_email=user_email_display,
                    action="CREATE",
                    resource_type="batch_processing_job",
                    resource_id=job_id,
                    resource_name=f"Batch Job {job_id}",
                    details={
                        "total_files": len(files),
                        "document_types": document_types,
                        "export_destination_id": export_destination_id,
                        "export_destination_type": export_destination.destination_type,
                        "api_client_id": api_client_id,
                        "webhook_url": webhook_url is not None
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log audit event for batch job creation: {e}")

            return batch_job

        except Exception as e:
            logger.error(f"Failed to create batch job: {e}")
            self.db.rollback()
            raise
