"""
Batch Processing Service for handling batch file uploads and processing.

Orchestrates batch file processing operations including job creation,
file enqueueing to Kafka, progress tracking, and completion handling.

Implementation split across focused modules in services/:
  - validation:    file type/size/batch-size checks
  - classification: document-type detection (heuristics + LangChain/LLM)
  - storage:        local disk write, cloud upload, cleanup
  - job_creation:   create_batch_job orchestration
  - kafka:          enqueue to topics, publish with retry
  - progress:       file completion, export trigger, job status
  - retry:          per-file and bulk retry with exponential backoff
  - cancellation:   cancel individual or all jobs
"""

import logging
from sqlalchemy.orm import Session

from .services import (
    BatchValidationMixin,
    BatchClassificationMixin,
    BatchStorageMixin,
    BatchJobCreationMixin,
    BatchKafkaMixin,
    BatchProgressMixin,
    BatchRetryMixin,
    BatchCancellationMixin,
)

logger = logging.getLogger(__name__)


class BatchProcessingService(
    BatchValidationMixin,
    BatchClassificationMixin,
    BatchStorageMixin,
    BatchJobCreationMixin,
    BatchKafkaMixin,
    BatchProgressMixin,
    BatchRetryMixin,
    BatchCancellationMixin,
):
    """
    Service for orchestrating batch file processing operations.

    Handles job creation, file validation, Kafka enqueueing, progress tracking,
    and completion detection for batch document processing.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        logger.info("BatchProcessingService initialized")
