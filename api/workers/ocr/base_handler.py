from typing import Optional, Dict, Any

from ._shared import (
    OCRConfig,
    ProcessingResult,
    logger,
    release_processing_lock,
)


# ============================================================================
# Base Message Handler
# ============================================================================

class BaseMessageHandler:
    """Base class for message handlers"""

    def __init__(self, config: OCRConfig):
        self.config = config
        self.logger = logger

    def can_handle(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Check if handler can process this message type"""
        raise NotImplementedError

    async def process(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Template method for processing messages with automatic lock release"""
        is_batch = self.is_batch_job(payload)
        resource_type = self.get_resource_type()

        try:
            if is_batch:
                return await self.process_batch(consumer, message, payload)
            else:
                return await self.process_single(consumer, message, payload)
        except Exception as e:
            self.logger.error(f"Unexpected error processing {resource_type}: {e}")
            return ProcessingResult(success=False, error_message=str(e))
        finally:
            # Release processing lock if this was a single reprocess request
            if not is_batch:
                resource_id = payload.get(f"{resource_type}_id")
                # Special case for bank_statement -> statement_id
                if resource_type == "bank_statement" and not resource_id:
                    resource_id = payload.get("statement_id")

                if resource_id:
                    try:
                        release_processing_lock(resource_type, int(resource_id))
                    except Exception as e:
                        self.logger.error(f"Failed to release lock for {resource_type} {resource_id}: {e}")

    def get_resource_type(self) -> str:
        """Get the resource type (e.g., 'expense', 'bank_statement')"""
        raise NotImplementedError

    async def process_single(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Hook for single document processing"""
        raise NotImplementedError

    async def process_batch(self, consumer, message, payload: Dict[str, Any]) -> ProcessingResult:
        """Hook for batch document processing"""
        raise NotImplementedError

    def extract_tenant_id(self, payload: Dict[str, Any]) -> Optional[int]:
        """Extract tenant ID from payload"""
        return payload.get("tenant_id")

    def is_batch_job(self, payload: Dict[str, Any]) -> bool:
        """Check if this is a batch job"""
        return payload.get("batch_job_id") is not None and payload.get("batch_file_id") is not None
