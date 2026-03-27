"""
File and batch validation for batch processing.
"""

import logging
from ._shared import MAX_FILES_PER_BATCH, MAX_FILE_SIZE_BYTES, ALLOWED_FILE_TYPES

logger = logging.getLogger(__name__)


class BatchValidationMixin:
    """Mixin providing file and batch size validation."""

    MAX_FILES_PER_BATCH = MAX_FILES_PER_BATCH
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_BYTES
    ALLOWED_FILE_TYPES = ALLOWED_FILE_TYPES

    def generate_job_id(self) -> str:
        import uuid
        job_id = str(uuid.uuid4())
        logger.debug(f"Generated job ID: {job_id}")
        return job_id

    def get_file_extension(self, filename: str) -> str:
        import os
        _, ext = os.path.splitext(filename)
        return ext.lower()

    def validate_file_type(self, filename: str) -> bool:
        ext = self.get_file_extension(filename)
        is_valid = ext in self.ALLOWED_FILE_TYPES
        if not is_valid:
            logger.warning(f"Invalid file type '{ext}' for file: {filename}")
        return is_valid

    def validate_file_size(self, file_size: int) -> bool:
        is_valid = file_size <= self.MAX_FILE_SIZE_BYTES
        if not is_valid:
            logger.warning(
                f"File size {file_size} bytes exceeds maximum "
                f"{self.MAX_FILE_SIZE_BYTES} bytes"
            )
        return is_valid

    def validate_batch_size(self, file_count: int) -> bool:
        is_valid = 0 < file_count <= self.MAX_FILES_PER_BATCH
        if not is_valid:
            logger.warning(
                f"Batch size {file_count} exceeds maximum "
                f"{self.MAX_FILES_PER_BATCH} files"
            )
        return is_valid
