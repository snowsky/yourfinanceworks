"""
Batch Processing Service for handling batch file uploads and processing.

Orchestrates batch file processing operations including job creation,
file enqueueing to Kafka, progress tracking, and completion handling.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models_per_tenant import (
    BatchProcessingJob,
    BatchFileProcessing,
    ExportDestinationConfig
)
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)


class BatchProcessingService:
    """
    Service for orchestrating batch file processing operations.
    
    Handles job creation, file validation, Kafka enqueueing, progress tracking,
    and completion detection for batch document processing.
    """

    # File validation constants
    MAX_FILES_PER_BATCH = 50
    MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
    ALLOWED_FILE_TYPES = {'.pdf', '.png', '.jpg', '.jpeg', '.csv'}
    
    # Document type mapping
    DOCUMENT_TYPE_TOPICS = {
        'invoice': 'invoices_ocr',
        'expense': 'expense_ocr',
        'statement': 'bank_statements_ocr'
    }

    def __init__(self, db: Session):
        """
        Initialize the batch processing service.
        
        Args:
            db: Database session
        """
        self.db = db
        logger.info("BatchProcessingService initialized")

    def generate_job_id(self) -> str:
        """
        Generate a unique job ID using UUID4.
        
        Returns:
            String representation of UUID4
        """
        job_id = str(uuid.uuid4())
        logger.debug(f"Generated job ID: {job_id}")
        return job_id

    async def determine_document_type(self, filename: str, content: Optional[bytes] = None) -> str:
        """
        Determine document type from file extension and optionally content.
        
        First tries filename-based heuristics. If uncertain, falls back to
        LangChain + LLM-based classification using document content.
        
        Args:
            filename: Name of the file
            content: Optional file content for content-based detection
            
        Returns:
            Document type string ('invoice', 'expense', or 'statement')
        """
        filename_lower = filename.lower()
        
        # Heuristic-based detection from filename
        invoice_keywords = ['invoice', 'inv', 'bill']
        expense_keywords = ['expense', 'receipt', 'exp']
        statement_keywords = ['statement', 'bank', 'stmt']
        
        if any(keyword in filename_lower for keyword in invoice_keywords):
            doc_type = 'invoice'
        elif any(keyword in filename_lower for keyword in expense_keywords):
            doc_type = 'expense'
        elif any(keyword in filename_lower for keyword in statement_keywords):
            doc_type = 'statement'
        else:
            # Filename is uncertain - try LangChain-based classification if content is available
            if content:
                try:
                    doc_type = await self._classify_with_langchain(filename, content)
                    logger.info(f"LangChain classified '{filename}' as '{doc_type}'")
                except Exception as e:
                    logger.warning(f"LangChain classification failed for '{filename}': {e}. Defaulting to 'expense'")
                    doc_type = 'expense'
            else:
                # No content available and filename is uncertain - default to expense
                logger.debug(f"Filename '{filename}' is uncertain and no content available. Defaulting to 'expense'")
                doc_type = 'expense'
        
        logger.debug(f"Determined document type '{doc_type}' for file: {filename}")
        return doc_type
    
    async def _classify_with_langchain(self, filename: str, content: bytes) -> str:
        """
        Classify document type using LangChain and LLM.
        
        Args:
            filename: Name of the file
            content: File content bytes
            
        Returns:
            Document type string ('invoice', 'expense', or 'statement')
            
        Raises:
            Exception: If classification fails
        """
        import tempfile
        import os
        from pathlib import Path
        
        # Get AI configuration from core.settings (database) with fallback to environment variables
        # AIConfigService.get_ai_config() handles:
        # 1. First tries to get config from database (settings)
        # 2. Falls back to environment variables if database config not available
        # 3. Handles errors gracefully
        from core.services.ai_config_service import AIConfigService
        ai_config = AIConfigService.get_ai_config(self.db, component="ocr", require_ocr=False)
        
        if not ai_config:
            logger.warning("No AI configuration available for LangChain classification (neither from core.settings nor environment variables)")
            raise Exception("No AI configuration available")
        
        # Create temporary file for LangChain document loader
        file_ext = Path(filename).suffix.lower()
        temp_file = None
        try:
            # Write content to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
                tmp.write(content)
                temp_file = tmp.name
            
            # Load document using LangChain
            documents = self._load_document_with_langchain(temp_file)
            if not documents:
                raise Exception("Failed to extract text from document")
            
            # Extract text from documents (first 2000 chars for efficiency)
            text_content = "\n\n".join([doc.page_content for doc in documents[:3]])[:2000]
            
            # Classify using LLM
            doc_type = await self._classify_text_with_llm(text_content, ai_config)
            
            return doc_type
            
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
    
    def _load_document_with_langchain(self, file_path: str) -> List:
        """
        Load document using LangChain document loaders.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of Document objects
        """
        try:
            from langchain_community.document_loaders import (
                PyPDFLoader,
                PyMuPDFLoader,
                CSVLoader,
            )
            from langchain_core.documents import Document
        except ImportError:
            logger.warning("LangChain not available for document loading")
            raise Exception("LangChain not available")

        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == '.pdf':
                # Try PyMuPDF first (faster), fallback to PyPDFLoader
                try:
                    loader = PyMuPDFLoader(file_path)
                except Exception:
                    loader = PyPDFLoader(file_path)
                documents = loader.load()
            elif file_ext == '.csv':
                loader = CSVLoader(file_path)
                documents = loader.load()
            else:
                # For images, we can't extract text directly with standard loaders
                # Return empty list - classification will need to use vision model
                logger.warning(f"Unsupported file type for text extraction: {file_ext}")
                return []

            return documents

        except Exception as e:
            logger.error(f"Failed to load document with LangChain: {e}")
            raise

    async def _classify_text_with_llm(self, text: str, ai_config: Dict[str, Any]) -> str:
        """
        Classify document type using LLM.

        Args:
            text: Extracted text from document
            ai_config: AI configuration dictionary

        Returns:
            Document type string ('invoice', 'expense', or 'statement')
        """
        try:
            from litellm import completion
        except ImportError:
            logger.warning("LiteLLM not available for classification")
            raise Exception("LiteLLM not available")

        provider_name = ai_config.get("provider_name", "ollama")
        model_name = ai_config.get("model_name", "llama3.2-vision:11b")
        base_url = ai_config.get("provider_url")  # Can be None, LiteLLM will use defaults
        api_key = ai_config.get("api_key")

        # Classification prompt
        classification_prompt = f"""Analyze the following document text and classify it as one of these types:
- invoice: A document requesting payment for goods/services provided (bills, invoices, bills of sale)
- expense: A receipt or expense record showing a purchase or payment made (receipts, purchase records)
- statement: A bank or financial statement showing account transactions (bank statements, account summaries)

Document text (first 2000 characters):
{text[:2000]}

Respond with ONLY one word: invoice, expense, or statement. Do not include any explanation or additional text."""

        # Prepare LLM call using LiteLLM format
        # LiteLLM handles provider prefixes automatically, but we can be explicit
        if provider_name == "ollama":
            model = model_name
        elif provider_name == "openai":
            model = model_name  # LiteLLM defaults to OpenAI if no prefix
        elif provider_name == "anthropic":
            model = f"anthropic/{model_name}"
        elif provider_name == "openrouter":
            model = f"openrouter/{model_name}"
        else:
            # For other providers, use provider/model format
            model = f"{provider_name}/{model_name}"
        
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": classification_prompt}],
            "max_tokens": 10,
            "temperature": 0.1,  # Low temperature for consistent classification
        }

        # Add API key if provided
        if api_key:
            kwargs["api_key"] = api_key
        
        # Add API base URL if provided (LiteLLM will use defaults if not set)
        if base_url:
            kwargs["api_base"] = base_url

        # Call LLM (run in thread pool to avoid blocking)
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: completion(**kwargs))

        # Extract classification from response
        if hasattr(response, 'choices') and len(response.choices) > 0:
            classification = response.choices[0].message.content.strip().lower()
        else:
            classification = str(response).strip().lower()

        # Normalize response
        if 'invoice' in classification:
            return 'invoice'
        elif 'expense' in classification or 'receipt' in classification:
            return 'expense'
        elif 'statement' in classification:
            return 'statement'
        else:
            # Default fallback
            logger.warning(f"Unclear LLM classification: '{classification}'. Defaulting to 'expense'")
            return 'expense'

    def get_file_extension(self, filename: str) -> str:
        """
        Get file extension from filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            File extension including the dot (e.g., '.pdf')
        """
        import os
        _, ext = os.path.splitext(filename)
        return ext.lower()

    def validate_file_type(self, filename: str) -> bool:
        """
        Validate if file type is allowed.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file type is allowed, False otherwise
        """
        ext = self.get_file_extension(filename)
        is_valid = ext in self.ALLOWED_FILE_TYPES
        
        if not is_valid:
            logger.warning(f"Invalid file type '{ext}' for file: {filename}")
        
        return is_valid

    def validate_file_size(self, file_size: int) -> bool:
        """
        Validate if file size is within limits.
        
        Args:
            file_size: Size of file in bytes
            
        Returns:
            True if file size is valid, False otherwise
        """
        is_valid = file_size <= self.MAX_FILE_SIZE_BYTES
        
        if not is_valid:
            logger.warning(
                f"File size {file_size} bytes exceeds maximum "
                f"{self.MAX_FILE_SIZE_BYTES} bytes"
            )
        
        return is_valid

    def validate_batch_size(self, file_count: int) -> bool:
        """
        Validate if batch size is within limits.
        
        Args:
            file_count: Number of files in batch
            
        Returns:
            True if batch size is valid, False otherwise
        """
        is_valid = 0 < file_count <= self.MAX_FILES_PER_BATCH
        
        if not is_valid:
            logger.warning(
                f"Batch size {file_count} exceeds maximum "
                f"{self.MAX_FILES_PER_BATCH} files"
            )
        
        return is_valid

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
        api_client: Optional[Any] = None
    ) -> BatchProcessingJob:
        """
        Create a new batch processing job and prepare files for processing.
        
        Args:
            files: List of file dictionaries with 'content', 'filename', 'size' keys
            tenant_id: Tenant identifier
            user_id: User creating the job
            api_client_id: API client identifier
            export_destination_id: ID of export destination configuration
            document_types: Optional list of document types (auto-detect if not provided)
            custom_fields: Optional list of fields to include in export
            webhook_url: Optional webhook URL for completion notification
            api_client: Optional APIClient object for audit logging
            
        Returns:
            Created BatchProcessingJob instance
            
        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate batch size
            if not self.validate_batch_size(len(files)):
                raise ValueError(
                    f"Batch size must be between 1 and {self.MAX_FILES_PER_BATCH} files. "
                    f"Received {len(files)} files."
                )
            
            # Validate export destination exists and is active
            export_destination = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == export_destination_id,
                    ExportDestinationConfig.tenant_id == tenant_id,
                    ExportDestinationConfig.is_active == True
                )
            ).first()
            
            # If specified destination not found, try to use default destination
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
            
            # Validate files
            for idx, file_info in enumerate(files):
                filename = file_info.get('filename', f'file_{idx}')
                file_size = file_info.get('size', 0)
                
                # Validate file type
                if not self.validate_file_type(filename):
                    ext = self.get_file_extension(filename)
                    raise ValueError(
                        f"File '{filename}' has invalid type '{ext}'. "
                        f"Allowed types: {', '.join(self.ALLOWED_FILE_TYPES)}"
                    )
                
                # Validate file size
                if not self.validate_file_size(file_size):
                    raise ValueError(
                        f"File '{filename}' size {file_size} bytes exceeds maximum "
                        f"{self.MAX_FILE_SIZE_BYTES} bytes ({self.MAX_FILE_SIZE_BYTES // (1024*1024)}MB)"
                    )
            
            # Generate unique job ID
            job_id = self.generate_job_id()
            
            # Determine document types if not provided
            if not document_types:
                document_types = []
                for file_info in files:
                    filename = file_info.get('filename', '')
                    # Pass content for LangChain classification if filename is uncertain
                    doc_type = await self.determine_document_type(filename, content=file_info.get('content'))
                    if doc_type not in document_types:
                        document_types.append(doc_type)

            # Normalize document_types list to match number of files
            # If document_types is provided, map by index (one type per file)
            # If only one type provided, apply to all files
            # If not provided or auto-detected, use filename-based detection per file
            file_document_types = []
            if document_types:
                if len(document_types) == 1:
                    # Single type provided: apply to all files
                    file_document_types = [document_types[0]] * len(files)
                elif len(document_types) == len(files):
                    # Same number of types as files: map by index
                    file_document_types = document_types
                else:
                    # Mismatch: raise error
                    raise ValueError(
                        f"Number of document types ({len(document_types)}) must match "
                        f"number of files ({len(files)}) or be 1 (applied to all files). "
                        f"Provided types: {', '.join(document_types)}"
                    )
            else:
                # Auto-detect for each file (async list comprehension)
                file_document_types = []
                for idx, file_info in enumerate(files):
                    # Pass content for LangChain classification if filename is uncertain
                    doc_type = await self.determine_document_type(
                        file_info.get('filename', f'file_{idx}'),
                        content=file_info.get('content')
                    )
                    file_document_types.append(doc_type)
                # Update document_types list for job record
                document_types = list(set(file_document_types))
            
            # Create BatchProcessingJob record
            batch_job = BatchProcessingJob(
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                api_client_id=api_client_id,
                document_types=document_types,
                client_id=client_id,
                total_files=len(files),
                export_destination_type=export_destination.destination_type,
                export_destination_config_id=export_destination_id,
                custom_fields=custom_fields,
                webhook_url=webhook_url,
                status="pending",
                processed_files=0,
                successful_files=0,
                failed_files=0,
                progress_percentage=0.0
            )
            
            self.db.add(batch_job)
            self.db.flush()  # Get the ID without committing
            
            # Store files to tenant-specific storage and create BatchFileProcessing records
            stored_files = []
            for idx, file_info in enumerate(files):
                try:
                    filename = file_info.get('filename', f'file_{idx}')
                    file_content = file_info.get('content')
                    file_size = file_info.get('size', len(file_content) if file_content else 0)
                    
                    # Use the mapped document type for this file
                    doc_type = file_document_types[idx]
                    
                    # Generate stored filename
                    stored_filename = self._generate_stored_filename(
                        job_id, idx, filename
                    )
                    
                    # Store file to tenant-specific directory
                    file_path = self._store_file_to_disk(
                        file_content,
                        tenant_id,
                        job_id,
                        stored_filename
                    )
                    
                    # Create BatchFileProcessing record
                    batch_file = BatchFileProcessing(
                        job_id=job_id,
                        original_filename=filename,
                        stored_filename=stored_filename,
                        file_path=file_path,
                        file_size=file_size,
                        document_type=doc_type,
                        status="pending",
                        retry_count=0
                    )
                    
                    self.db.add(batch_file)
                    self.db.flush()  # Get the batch_file.id
                    stored_files.append(batch_file)
                    
                    logger.info(
                        f"Stored file {idx+1}/{len(files)}: {filename} -> {file_path}"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to store file {filename}: {e}")
                    # Clean up already stored files
                    self._cleanup_stored_files(stored_files)
                    raise ValueError(f"Failed to store file '{filename}': {str(e)}")
            
            # Commit all changes
            self.db.commit()
            self.db.refresh(batch_job)
            
            logger.info(
                f"Created batch job {job_id} with {len(files)} files "
                f"for tenant {tenant_id}"
            )
            
            # Upload files to cloud storage if export destination is configured
            if export_destination:
                logger.info(f"Uploading {len(stored_files)} files to cloud storage")
                import asyncio
                
                async def upload_files_to_cloud():
                    for batch_file in stored_files:
                        try:
                            cloud_url = await self._upload_file_to_cloud(
                                file_path=batch_file.file_path,
                                original_filename=batch_file.original_filename,
                                destination_config=export_destination,
                                tenant_id=tenant_id,
                                job_id=job_id
                            )
                            
                            if cloud_url:
                                batch_file.cloud_file_url = cloud_url
                                logger.info(f"Uploaded {batch_file.original_filename} to cloud")
                        except Exception as e:
                            logger.warning(
                                f"Failed to upload {batch_file.original_filename} to cloud: {e}"
                            )
                    
                    # Commit cloud URLs
                    self.db.commit()
                
                # Run cloud upload asynchronously
                try:
                    asyncio.create_task(upload_files_to_cloud())
                except RuntimeError:
                    # If no event loop is running, run synchronously
                    import asyncio
                    asyncio.run(upload_files_to_cloud())
            
            # AUDIT: Log batch job creation
            try:
                # Ensure tenant context is set for encryption
                from core.models.database import set_tenant_context
                set_tenant_context(tenant_id)

                # Build user email display for audit log
                # For API key auth, include both the API key prefix and the associated user's email
                if api_client and hasattr(api_client, 'api_key_prefix') and hasattr(api_client, 'user'):
                    user_email_display = f"{api_client.api_key_prefix}*** ({api_client.user.email})" if api_client.user else f"{api_client.api_key_prefix}*** (user_{user_id})"
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
                # Don't let audit logging failure affect the batch job creation
                pass

            return batch_job

        except Exception as e:
            logger.error(f"Failed to create batch job: {e}")
            self.db.rollback()
            raise

    def _generate_stored_filename(
        self,
        job_id: str,
        file_index: int,
        original_filename: str
    ) -> str:
        """
        Generate a unique stored filename for a batch file.

        Args:
            job_id: Batch job ID
            file_index: Index of file in batch
            original_filename: Original filename

        Returns:
            Stored filename string
        """
        import os
        from datetime import datetime

        # Get file extension
        _, ext = os.path.splitext(original_filename)

        # Generate filename: job_id_index_timestamp.ext
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        stored_filename = f"{job_id}_{file_index:03d}_{timestamp}{ext}"

        return stored_filename

    def _store_file_to_disk(
        self,
        file_content: bytes,
        tenant_id: int,
        job_id: str,
        stored_filename: str
    ) -> str:
        """
        Store file to tenant-specific directory on disk.

        Args:
            file_content: File content as bytes
            tenant_id: Tenant identifier
            job_id: Batch job ID
            stored_filename: Filename to store as

        Returns:
            Full file path where file was stored

        Raises:
            IOError: If file storage fails
        """
        import os

        # Create tenant-specific batch directory
        base_dir = os.getenv("BATCH_FILES_DIR", "api/batch_files")
        tenant_dir = os.path.join(base_dir, f"tenant_{tenant_id}", job_id)

        # Create directory if it doesn't exist
        os.makedirs(tenant_dir, exist_ok=True)

        # Full file path
        file_path = os.path.join(tenant_dir, stored_filename)

        # Write file to disk
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
        """
        Upload a file to cloud storage destination.

        Args:
            file_path: Local file path
            original_filename: Original filename
            destination_config: Export destination configuration
            tenant_id: Tenant identifier
            job_id: Batch job ID

        Returns:
            Cloud file URL if successful, None otherwise
        """
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Generate cloud filename with job_id prefix
            cloud_filename = f"{job_id}/{original_filename}"

            # Import export service for cloud upload
            from core.services.export_service import ExportService
            export_service = ExportService(self.db)

            destination_type = destination_config.destination_type

            # Upload to appropriate cloud storage
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
            else:
                logger.warning(f"Unknown destination type: {destination_type}")
                return None

            logger.info(f"Uploaded file to cloud: {original_filename} -> {url}")
            return url

        except Exception as e:
            logger.error(f"Failed to upload file to cloud: {e}")
            return None

    def _cleanup_stored_files(self, batch_files: List[BatchFileProcessing]) -> None:
        """
        Clean up stored files on disk after a failed batch job creation.

        Args:
            batch_files: List of BatchFileProcessing records with file paths
        """
        import os

        for batch_file in batch_files:
            if batch_file.file_path and os.path.exists(batch_file.file_path):
                try:
                    os.remove(batch_file.file_path)
                    logger.debug(f"Cleaned up file: {batch_file.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up file {batch_file.file_path}: {e}")

    async def enqueue_files_to_kafka(self, job_id: str) -> Dict[str, Any]:
        """
        Enqueue all files in a batch job to appropriate Kafka topics.

        Args:
            job_id: Batch job ID

        Returns:
            Dictionary with enqueueing results

        Raises:
            ValueError: If job not found
        """
        try:
            # Get batch job
            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == job_id
            ).first()

            if not batch_job:
                raise ValueError(f"Batch job {job_id} not found")

            # Get all pending files for this job
            batch_files = self.db.query(BatchFileProcessing).filter(
                and_(
                    BatchFileProcessing.job_id == job_id,
                    BatchFileProcessing.status == "pending"
                )
            ).all()

            if not batch_files:
                logger.warning(f"No pending files found for job {job_id}")
                return {
                    "job_id": job_id,
                    "enqueued": 0,
                    "failed": 0,
                    "files": []
                }

            # Update job status to processing
            batch_job.status = "processing"
            self.db.commit()

            # Enqueue each file
            enqueued_count = 0
            failed_count = 0
            results = []

            for batch_file in batch_files:
                try:
                    # Determine Kafka topic based on document type
                    topic = self._get_kafka_topic_for_document_type(
                        batch_file.document_type
                    )

                    # Publish message to Kafka
                    message_id = await self._publish_to_kafka(
                        topic=topic,
                        job_id=job_id,
                        file_id=batch_file.id,
                        file_path=batch_file.file_path,
                        original_filename=batch_file.original_filename,
                        file_size=batch_file.file_size,
                        tenant_id=batch_job.tenant_id,
                        user_id=batch_job.user_id,
                        document_type=batch_file.document_type
                    )

                    # Update batch file with Kafka info
                    batch_file.kafka_topic = topic
                    batch_file.kafka_message_id = message_id
                    batch_file.status = "processing"
                    batch_file.processing_started_at = datetime.now(timezone.utc)

                    enqueued_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "filename": batch_file.original_filename,
                        "topic": topic,
                        "message_id": message_id,
                        "status": "enqueued"
                    })

                    logger.info(
                        f"Enqueued file {batch_file.id} ({batch_file.original_filename}) "
                        f"to topic {topic}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to enqueue file {batch_file.id} "
                        f"({batch_file.original_filename}): {e}"
                    )

                    # Update file status to failed
                    batch_file.status = "failed"
                    batch_file.error_message = f"Failed to enqueue: {str(e)}"

                    failed_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "filename": batch_file.original_filename,
                        "status": "failed",
                        "error": str(e)
                    })

            # Commit all updates
            self.db.commit()

            logger.info(
                f"Enqueued {enqueued_count} files, {failed_count} failed "
                f"for job {job_id}"
            )

            return {
                "job_id": job_id,
                "enqueued": enqueued_count,
                "failed": failed_count,
                "files": results
            }

        except Exception as e:
            logger.error(f"Failed to enqueue files for job {job_id}: {e}")
            self.db.rollback()
            raise

    def _get_kafka_topic_for_document_type(self, document_type: str) -> str:
        """
        Get Kafka topic name for a document type.

        Args:
            document_type: Document type ('invoice', 'expense', 'statement')

        Returns:
            Kafka topic name

        Raises:
            ValueError: If document type is unknown
        """
        # Get topic from environment variable or use default
        if document_type == 'invoice':
            topic = os.getenv('KAFKA_INVOICE_TOPIC', 'invoices_ocr')
        elif document_type == 'expense':
            topic = os.getenv('KAFKA_OCR_TOPIC', 'expense_ocr')
        elif document_type == 'statement':
            topic = os.getenv('KAFKA_BANK_TOPIC', 'bank_statements_ocr')
        else:
            raise ValueError(f"Unknown document type: {document_type}")

        logger.debug(f"Mapped document type '{document_type}' to topic '{topic}'")
        return topic

    async def _publish_to_kafka(
        self,
        topic: str,
        job_id: str,
        file_id: int,
        file_path: str,
        original_filename: str,
        file_size: int,
        tenant_id: int,
        user_id: int,
        document_type: str
    ) -> str:
        """
        Publish a message to Kafka with retry logic.

        Args:
            topic: Kafka topic name
            job_id: Batch job ID
            file_id: Batch file processing ID
            file_path: Path to file
            original_filename: Original filename
            file_size: File size in bytes
            tenant_id: Tenant identifier
            user_id: User identifier (owner of the batch job)
            document_type: Document type

        Returns:
            Message ID (UUID)

        Raises:
            Exception: If publishing fails after retries
        """
        import json

        # Generate message ID
        message_id = str(uuid.uuid4())

        # Construct message payload
        message = {
            "batch_job_id": job_id,
            "batch_file_id": file_id,
            "file_path": file_path,
            "original_filename": original_filename,
            "file_size": file_size,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "document_type": document_type,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": 0
        }

        # Try to get Kafka producer
        try:
            from core.services.ocr_service import _get_kafka_producer_for

            producer, _ = _get_kafka_producer_for(
                f"KAFKA_{document_type.upper()}_TOPIC",
                topic
            )

            if not producer:
                raise Exception("Kafka producer not available")

            # Publish message with retry logic
            max_retries = 3
            retry_delay = 1.0  # seconds

            for attempt in range(max_retries):
                try:
                    payload = json.dumps(message).encode('utf-8')
                    key = f"{tenant_id}_{job_id}_{file_id}"
                    
                    producer.produce(
                        topic,
                        value=payload,
                        key=key
                    )

                    # Flush to ensure message is sent
                    remaining = producer.flush(timeout=10.0)

                    if remaining == 0:
                        logger.debug(
                            f"Published message {message_id} to topic {topic} "
                            f"(attempt {attempt + 1})"
                        )
                        return message_id
                    else:
                        raise Exception(
                            f"Failed to flush message, {remaining} messages remaining"
                        )

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Kafka publish attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        import asyncio
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise

            raise Exception(f"Failed to publish to Kafka after {max_retries} attempts")

        except Exception as e:
            logger.error(f"Failed to publish message to Kafka topic {topic}: {e}")
            raise

    async def process_file_completion(
        self,
        file_id: int,
        extracted_data: Optional[Dict[str, Any]] = None,
        status: str = "completed",
        error_message: Optional[str] = None,
        created_record_id: Optional[int] = None,
        record_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process completion of a single file and update job progress.

        Args:
            file_id: Batch file processing ID
            extracted_data: Extracted data from OCR processing
            status: File status ('completed' or 'failed')
            error_message: Error message if status is 'failed'
            created_record_id: ID of created Invoice/Expense/BankStatement record
            record_type: Type of created record ('invoice', 'expense', 'statement')

        Returns:
            Dictionary with completion results and job status

        Raises:
            ValueError: If file not found
        """
        try:
            # Get batch file
            batch_file = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.id == file_id
            ).first()

            if not batch_file:
                raise ValueError(f"Batch file {file_id} not found")

            # Get associated job
            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == batch_file.job_id
            ).first()

            if not batch_job:
                raise ValueError(f"Batch job {batch_file.job_id} not found")

            # Check if this file was already counted (to avoid double-counting retries)
            was_already_processed = batch_file.status in ["completed", "failed"]
            
            # Update batch file record
            batch_file.status = status
            batch_file.completed_at = datetime.now(timezone.utc)

            if extracted_data:
                batch_file.extracted_data = extracted_data

            if error_message:
                batch_file.error_message = error_message

            # Store created record ID
            if created_record_id and record_type:
                if record_type == 'invoice':
                    batch_file.created_invoice_id = created_record_id
                elif record_type == 'expense':
                    batch_file.created_expense_id = created_record_id
                elif record_type == 'statement':
                    batch_file.created_statement_id = created_record_id
                logger.info(f"Linked batch file {file_id} to {record_type} record {created_record_id}")

            # Update job progress counters (only if not already counted)
            if not was_already_processed:
                batch_job.processed_files += 1

                if status == "completed":
                    batch_job.successful_files += 1
                elif status == "failed":
                    batch_job.failed_files += 1
            else:
                # File was retried - update success/failure counts
                logger.info(f"File {file_id} was retried - updating success/failure counts only")
                if status == "completed":
                    # Was failed before, now succeeded
                    if batch_job.failed_files > 0:
                        batch_job.failed_files -= 1
                    batch_job.successful_files += 1
                elif status == "failed":
                    # Was completed before, now failed (unlikely but handle it)
                    if batch_job.successful_files > 0:
                        batch_job.successful_files -= 1
                    batch_job.failed_files += 1

            # Calculate progress percentage
            if batch_job.total_files > 0:
                batch_job.progress_percentage = (
                    batch_job.processed_files / batch_job.total_files
                ) * 100.0

            # Update job timestamp
            batch_job.updated_at = datetime.now(timezone.utc)

            # Commit changes
            self.db.commit()
            self.db.refresh(batch_job)

            logger.info(
                f"Processed file completion: file_id={file_id}, status={status}, "
                f"job_progress={batch_job.processed_files}/{batch_job.total_files} "
                f"({batch_job.progress_percentage:.1f}%)"
            )

            # Check if all files are processed
            all_processed = batch_job.processed_files >= batch_job.total_files

            if all_processed:
                logger.info(
                    f"All files processed for job {batch_job.job_id}. "
                    f"Successful: {batch_job.successful_files}, "
                    f"Failed: {batch_job.failed_files}"
                )

                # Trigger export if there are successful files
                if batch_job.successful_files > 0:
                    await self._trigger_export(batch_job)
                else:
                    # Mark job as failed if all files failed
                    batch_job.status = "failed"
                    batch_job.completed_at = datetime.now(timezone.utc)
                    self.db.commit()

            return {
                "file_id": file_id,
                "job_id": batch_job.job_id,
                "file_status": status,
                "job_status": batch_job.status,
                "progress": {
                    "processed": batch_job.processed_files,
                    "total": batch_job.total_files,
                    "successful": batch_job.successful_files,
                    "failed": batch_job.failed_files,
                    "percentage": batch_job.progress_percentage
                },
                "all_processed": all_processed
            }

        except Exception as e:
            logger.error(f"Failed to process file completion for file {file_id}: {e}")
            self.db.rollback()
            raise

    async def _trigger_export(self, batch_job: BatchProcessingJob) -> None:
        """
        Trigger export process for a completed batch job.

        This method will be called by the BatchCompletionMonitor service
        or directly when all files are processed.

        Args:
            batch_job: Completed batch job
        """
        try:
            logger.info(f"Triggering export for job {batch_job.job_id}")

            # Import ExportService here to avoid circular imports
            from core.services.export_service import ExportService

            # Create export service instance
            export_service = ExportService(self.db)

            # Generate and export results
            export_result = await export_service.generate_and_export_results(batch_job)

            logger.info(
                f"Export completed for job {batch_job.job_id}: "
                f"status={export_result['status']}, "
                f"url={export_result['export_url']}"
            )

        except Exception as e:
            logger.error(f"Failed to trigger export for job {batch_job.job_id}: {e}")
            # Re-raise to allow caller to handle
            raise

    def get_job_status(self, job_id: str, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a batch job.

        Enforces tenant isolation by filtering on tenant_id.

        Args:
            job_id: Batch job ID
            tenant_id: Tenant identifier for security check

        Returns:
            Dictionary with job status or None if not found
        """
        try:
            # Get batch job with tenant isolation
            batch_job = self.db.query(BatchProcessingJob).filter(
                and_(
                    BatchProcessingJob.job_id == job_id,
                    BatchProcessingJob.tenant_id == tenant_id  # Tenant isolation
                )
            ).first()

            if not batch_job:
                return None

            # Get all files for this job
            batch_files = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.job_id == job_id
            ).order_by(BatchFileProcessing.created_at).all()

            # Build file details
            files_detail = []
            for batch_file in batch_files:
                file_info = {
                    "id": batch_file.id,
                    "filename": batch_file.original_filename,
                    "document_type": batch_file.document_type,
                    "status": batch_file.status,
                    "file_size": batch_file.file_size,
                    "retry_count": batch_file.retry_count,
                    "created_at": batch_file.created_at.isoformat() if batch_file.created_at else None,
                    "completed_at": batch_file.completed_at.isoformat() if batch_file.completed_at else None
                }

                if batch_file.extracted_data:
                    file_info["extracted_data"] = batch_file.extracted_data

                if batch_file.error_message:
                    file_info["error_message"] = batch_file.error_message

                files_detail.append(file_info)

            # Build job status response
            job_status = {
                "job_id": batch_job.job_id,
                "status": batch_job.status,
                "progress": {
                    "total_files": batch_job.total_files,
                    "processed_files": batch_job.processed_files,
                    "successful_files": batch_job.successful_files,
                    "failed_files": batch_job.failed_files,
                    "progress_percentage": batch_job.progress_percentage
                },
                "export": {
                    "destination_type": batch_job.export_destination_type,
                    "export_file_url": batch_job.export_file_url,
                    "export_completed_at": batch_job.export_completed_at.isoformat() if batch_job.export_completed_at else None
                },
                "timestamps": {
                    "created_at": batch_job.created_at.isoformat() if batch_job.created_at else None,
                    "updated_at": batch_job.updated_at.isoformat() if batch_job.updated_at else None,
                    "completed_at": batch_job.completed_at.isoformat() if batch_job.completed_at else None
                },
                "files": files_detail
            }
            
            return job_status
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            raise

    async def retry_failed_file(
        self,
        file_id: int,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retry processing a failed file with exponential backoff.
        
        Args:
            file_id: Batch file processing ID
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Dictionary with retry results
            
        Raises:
            ValueError: If file not found or not in failed state
        """
        try:
            # Get batch file
            batch_file = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.id == file_id
            ).first()
            
            if not batch_file:
                raise ValueError(f"Batch file {file_id} not found")
            
            # Check if file is in a retryable state
            if batch_file.status not in ["failed", "processing"]:
                raise ValueError(
                    f"File {file_id} is in status '{batch_file.status}' "
                    f"and cannot be retried"
                )
            
            # Check retry count
            if batch_file.retry_count >= max_retries:
                logger.warning(
                    f"File {file_id} has reached maximum retry attempts "
                    f"({batch_file.retry_count}/{max_retries}). "
                    f"Marking as permanently failed."
                )
                
                batch_file.status = "failed"
                batch_file.error_message = (
                    f"Permanently failed after {batch_file.retry_count} retry attempts. "
                    f"Last error: {batch_file.error_message}"
                )
                self.db.commit()
                
                return {
                    "file_id": file_id,
                    "status": "permanently_failed",
                    "retry_count": batch_file.retry_count,
                    "max_retries": max_retries,
                    "message": "Maximum retry attempts reached"
                }
            
            # Increment retry count
            batch_file.retry_count += 1
            
            # Calculate exponential backoff delay (1s, 2s, 4s)
            backoff_delay = 2 ** (batch_file.retry_count - 1)  # 1, 2, 4 seconds
            
            logger.info(
                f"Retrying file {file_id} (attempt {batch_file.retry_count}/{max_retries}) "
                f"after {backoff_delay}s backoff"
            )
            
            # Apply backoff delay
            import asyncio
            await asyncio.sleep(backoff_delay)
            
            # Reset file status to pending for retry
            batch_file.status = "pending"
            batch_file.processing_started_at = None
            batch_file.completed_at = None
            
            # Clear previous error message
            previous_error = batch_file.error_message
            batch_file.error_message = None
            
            self.db.commit()
            
            # Get batch job
            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == batch_file.job_id
            ).first()
            
            if not batch_job:
                raise ValueError(f"Batch job {batch_file.job_id} not found")
            
            # Re-enqueue file to Kafka
            try:
                topic = self._get_kafka_topic_for_document_type(
                    batch_file.document_type
                )
                
                message_id = await self._publish_to_kafka(
                    topic=topic,
                    job_id=batch_file.job_id,
                    file_id=batch_file.id,
                    file_path=batch_file.file_path,
                    original_filename=batch_file.original_filename,
                    file_size=batch_file.file_size,
                    tenant_id=batch_job.tenant_id,
                    user_id=batch_job.user_id,
                    document_type=batch_file.document_type
                )
                
                # Update batch file with new Kafka info
                batch_file.kafka_topic = topic
                batch_file.kafka_message_id = message_id
                batch_file.status = "processing"
                batch_file.processing_started_at = datetime.now(timezone.utc)
                
                self.db.commit()
                
                logger.info(
                    f"Successfully retried file {file_id} "
                    f"(attempt {batch_file.retry_count}/{max_retries})"
                )
                
                return {
                    "file_id": file_id,
                    "status": "retrying",
                    "retry_count": batch_file.retry_count,
                    "max_retries": max_retries,
                    "backoff_delay": backoff_delay,
                    "kafka_topic": topic,
                    "kafka_message_id": message_id,
                    "previous_error": previous_error
                }
                
            except Exception as e:
                logger.error(f"Failed to re-enqueue file {file_id}: {e}")
                
                # Mark as failed with retry error
                batch_file.status = "failed"
                batch_file.error_message = (
                    f"Retry attempt {batch_file.retry_count} failed: {str(e)}. "
                    f"Previous error: {previous_error}"
                )
                self.db.commit()
                
                raise
            
        except Exception as e:
            logger.error(f"Failed to retry file {file_id}: {e}")
            self.db.rollback()
            raise

    async def retry_all_failed_files(
        self,
        job_id: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retry all failed files in a batch job.
        
        Args:
            job_id: Batch job ID
            max_retries: Maximum number of retry attempts per file
            
        Returns:
            Dictionary with retry results for all files
        """
        try:
            # Get all failed files for this job
            failed_files = self.db.query(BatchFileProcessing).filter(
                and_(
                    BatchFileProcessing.job_id == job_id,
                    BatchFileProcessing.status == "failed",
                    BatchFileProcessing.retry_count < max_retries
                )
            ).all()
            
            if not failed_files:
                logger.info(f"No retryable failed files found for job {job_id}")
                return {
                    "job_id": job_id,
                    "retried": 0,
                    "skipped": 0,
                    "failed": 0,
                    "files": []
                }
            
            logger.info(
                f"Retrying {len(failed_files)} failed files for job {job_id}"
            )
            
            # Retry each file
            retried_count = 0
            skipped_count = 0
            failed_count = 0
            results = []
            
            for batch_file in failed_files:
                try:
                    result = await self.retry_failed_file(
                        batch_file.id,
                        max_retries=max_retries
                    )
                    
                    if result["status"] == "retrying":
                        retried_count += 1
                    elif result["status"] == "permanently_failed":
                        skipped_count += 1
                    
                    results.append(result)
                    
                except Exception as e:
                    logger.error(
                        f"Failed to retry file {batch_file.id}: {e}"
                    )
                    failed_count += 1
                    results.append({
                        "file_id": batch_file.id,
                        "status": "retry_failed",
                        "error": str(e)
                    })
            
            logger.info(
                f"Retry results for job {job_id}: "
                f"retried={retried_count}, skipped={skipped_count}, "
                f"failed={failed_count}"
            )
            
            return {
                "job_id": job_id,
                "retried": retried_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "files": results
            }
            
        except Exception as e:
            logger.error(f"Failed to retry failed files for job {job_id}: {e}")
            raise

    def should_retry_file(
        self,
        batch_file: BatchFileProcessing,
        max_retries: int = 3
    ) -> bool:
        """
        Determine if a file should be retried based on retry count.
        
        Args:
            batch_file: Batch file processing record
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if file should be retried, False otherwise
        """
        if batch_file.status != "failed":
            return False
        
        if batch_file.retry_count >= max_retries:
            return False
        
        return True

    def get_retry_delay(self, retry_count: int) -> float:
        """
        Calculate exponential backoff delay for retry.
        
        Args:
            retry_count: Current retry count (1-based)
            
        Returns:
            Delay in seconds (1s, 2s, 4s for retries 1, 2, 3)
        """
        # Exponential backoff: 2^(n-1) where n is retry count
        # retry_count=1 -> 1s, retry_count=2 -> 2s, retry_count=3 -> 4s
        delay = 2 ** (retry_count - 1)
        return float(delay)
