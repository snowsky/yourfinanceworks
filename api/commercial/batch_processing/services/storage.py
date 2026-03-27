"""
File storage operations for batch processing.

Handles local disk storage, cloud upload, and cleanup of batch files.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.models.models_per_tenant import BatchFileProcessing, ExportDestinationConfig

logger = logging.getLogger(__name__)


class BatchStorageMixin:
    """Mixin providing file storage, cloud upload, and cleanup operations."""

    def _generate_stored_filename(
        self,
        job_id: str,
        file_index: int,
        original_filename: str
    ) -> str:
        _, ext = os.path.splitext(original_filename)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{job_id}_{file_index:03d}_{timestamp}{ext}"

    def _store_file_to_disk(
        self,
        file_content: bytes,
        tenant_id: int,
        job_id: str,
        stored_filename: str
    ) -> str:
        base_dir = os.getenv("BATCH_FILES_DIR", "api/batch_files")
        tenant_dir = os.path.join(base_dir, f"tenant_{tenant_id}", job_id)
        os.makedirs(tenant_dir, exist_ok=True)
        file_path = os.path.join(tenant_dir, stored_filename)

        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            logger.debug(f"Stored file to: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write file to {file_path}: {e}")
            raise IOError(f"Failed to store file: {str(e)}")

    async def _upload_file_to_cloud(
        self,
        file_path: str,
        original_filename: str,
        destination_config: ExportDestinationConfig,
        tenant_id: int,
        job_id: str
    ) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            cloud_filename = f"{job_id}/{original_filename}"

            from core.services.export_service import ExportService
            export_service = ExportService(self.db)

            destination_type = destination_config.destination_type

            if destination_type == 's3':
                url = await export_service.upload_to_s3(
                    file_content, destination_config, cloud_filename, tenant_id
                )
            elif destination_type == 'azure':
                url = await export_service.upload_to_azure(
                    file_content, destination_config, cloud_filename, tenant_id
                )
            elif destination_type == 'gcs':
                url = await export_service.upload_to_gcs(
                    file_content, destination_config, cloud_filename, tenant_id
                )
            elif destination_type == 'google_drive':
                url = await export_service.upload_to_google_drive(
                    file_content, destination_config, cloud_filename, tenant_id
                )
            elif destination_type == 'local':
                url = await export_service.upload_to_local(
                    file_content, destination_config, cloud_filename, tenant_id
                )
            else:
                logger.warning(f"Unknown destination type: {destination_type}")
                return None

            logger.info(f"Uploaded file: {original_filename} -> {url}")
            return url

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return None

    def _cleanup_stored_files(self, batch_files: List[BatchFileProcessing]) -> None:
        for batch_file in batch_files:
            if batch_file.file_path and os.path.exists(batch_file.file_path):
                try:
                    os.remove(batch_file.file_path)
                    logger.debug(f"Cleaned up file: {batch_file.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up file {batch_file.file_path}: {e}")
