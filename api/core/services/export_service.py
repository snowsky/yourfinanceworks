"""
Export Service for batch file processing results.

Handles CSV generation from processed batch files and uploading to various
cloud storage destinations (S3, Azure, GCS, Google Drive).
"""

import csv
import io
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.models.models_per_tenant import (
    BatchProcessingJob,
    BatchFileProcessing,
    ExportDestinationConfig
)
from core.services.export_destination_service import ExportDestinationService
from core.utils.audit import log_audit_event

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for generating CSV exports and uploading to configured destinations.
    
    Handles CSV generation from batch processing results and uploads to
    various cloud storage providers with retry logic.
    """

    # CSV column definitions by document type
    CSV_COLUMNS_EXPENSE = [
        'file_name',
        'original_filename',
        'cloud_file_url',
        'document_type',
        'status',
        'vendor',
        'amount',
        'currency',
        'date',
        'tax_amount',
        'category',
        'line_items',
        'attachment_paths',
        'error_message'
    ]
    
    CSV_COLUMNS_INVOICE = [
        'file_name',
        'original_filename',
        'cloud_file_url',
        'document_type',
        'status',
        'invoice_number',
        'client_name',
        'amount',
        'subtotal',
        'currency',
        'due_date',
        'discount',
        'items',
        'attachment_paths',
        'error_message'
    ]
    
    CSV_COLUMNS_STATEMENT = [
        'file_name',
        'original_filename',
        'cloud_file_url',
        'document_type',
        'status',
        'account_number',
        'statement_date',
        'transactions_count',
        'total_debits',
        'total_credits',
        'currency',
        'transactions',
        'attachment_paths',
        'error_message'
    ]

    # Retry configuration
    MAX_EXPORT_RETRIES = 5
    RETRY_DELAYS = [2, 4, 8, 16, 32]  # Exponential backoff in seconds

    def __init__(self, db: Session):
        """
        Initialize the export service.
        
        Args:
            db: Tenant database session
        """
        self.db = db
        logger.info("ExportService initialized")

    def generate_csv_filename(self, job_id: str) -> str:
        """
        Generate CSV filename with timestamp.
        
        Args:
            job_id: Batch job ID
            
        Returns:
            CSV filename string
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"batch_export_{job_id}_{timestamp}.csv"
        
        logger.debug(f"Generated CSV filename: {filename}")
        return filename

    def generate_csv(
        self,
        job_id: str,
        custom_fields: Optional[List[str]] = None
    ) -> bytes:
        """
        Generate CSV content from processed batch files.
        
        Queries all BatchFileProcessing records for the job and builds CSV
        with extracted data. Handles comma-separated attachment paths and
        serializes line_items as JSON. Escapes special characters per RFC 4180.
        
        Args:
            job_id: Batch job ID
            custom_fields: Optional list of fields to include (uses all if None)
            
        Returns:
            CSV content as bytes
            
        Raises:
            ValueError: If job not found or no files to export
        """
        try:
            # Get batch job
            batch_job = self.db.query(BatchProcessingJob).filter(
                BatchProcessingJob.job_id == job_id
            ).first()
            
            if not batch_job:
                raise ValueError(f"Batch job {job_id} not found")
            
            # Query all batch file processing records for this job
            batch_files = self.db.query(BatchFileProcessing).filter(
                BatchFileProcessing.job_id == job_id
            ).order_by(BatchFileProcessing.id).all()
            
            if not batch_files:
                raise ValueError(f"No files found for batch job {job_id}")
            
            # Determine columns based on actual document types in the files
            # Check what document types are actually present in the batch files
            actual_doc_types = set()
            for bf in batch_files:
                if bf.document_type:
                    actual_doc_types.add(bf.document_type)
            
            logger.info(f"Actual document types in batch files: {actual_doc_types}")
            
            # Choose column set based on primary document type
            if 'invoice' in actual_doc_types:
                default_columns = self.CSV_COLUMNS_INVOICE
                logger.info("Using invoice columns")
            elif 'statement' in actual_doc_types:
                default_columns = self.CSV_COLUMNS_STATEMENT
                logger.info("Using statement columns")
            else:
                default_columns = self.CSV_COLUMNS_EXPENSE
                logger.info("Using expense columns (default)")
            
            # Determine columns to include
            if custom_fields:
                # Validate custom fields
                invalid_fields = [f for f in custom_fields if f not in default_columns]
                if invalid_fields:
                    logger.warning(
                        f"Invalid custom fields ignored: {', '.join(invalid_fields)}"
                    )
                columns = [f for f in custom_fields if f in default_columns]
            else:
                columns = default_columns
            
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=columns,
                quoting=csv.QUOTE_MINIMAL,
                escapechar='\\',
                lineterminator='\n'
            )
            
            # Write header
            writer.writeheader()
            
            # Write data rows
            for batch_file in batch_files:
                row = self._build_csv_row(batch_file, columns)
                writer.writerow(row)
            
            # Get CSV content as bytes
            csv_content = output.getvalue().encode('utf-8')
            output.close()
            
            logger.info(
                f"Generated CSV for job {job_id}: {len(batch_files)} rows, "
                f"{len(csv_content)} bytes"
            )
            
            return csv_content
            
        except Exception as e:
            logger.error(f"Failed to generate CSV for job {job_id}: {e}")
            raise

    def _build_csv_row(
        self,
        batch_file: BatchFileProcessing,
        columns: List[str]
    ) -> Dict[str, str]:
        """
        Build a CSV row from a BatchFileProcessing record.
        
        Args:
            batch_file: BatchFileProcessing record
            columns: List of columns to include
            
        Returns:
            Dictionary with column values
        """
        # Extract data from extracted_data JSON field
        extracted_data = batch_file.extracted_data or {}
        
        # Build row with all possible columns (expense, invoice, and statement fields)
        row_data = {
            # Common fields
            'file_name': batch_file.original_filename or '',
            'original_filename': batch_file.original_filename or '',
            'cloud_file_url': batch_file.cloud_file_url or '',
            'document_type': batch_file.document_type or '',
            'status': batch_file.status or '',
            'attachment_paths': self._format_attachment_paths(batch_file),
            'error_message': batch_file.error_message or '',
            
            # Expense fields
            'vendor': extracted_data.get('vendor', ''),
            'amount': self._format_number(extracted_data.get('amount') or extracted_data.get('total_amount')),
            'currency': extracted_data.get('currency', ''),
            'date': self._format_date(extracted_data.get('date')),
            'tax_amount': self._format_number(extracted_data.get('tax_amount')),
            'category': extracted_data.get('category', ''),
            'line_items': self._serialize_line_items(extracted_data.get('line_items')),
            
            # Invoice fields
            'invoice_number': extracted_data.get('invoice_number', ''),
            'client_name': extracted_data.get('bills_to', extracted_data.get('client_name', '')),
            'subtotal': self._format_number((extracted_data.get('total_amount') or 0) - (extracted_data.get('total_discount') or 0)),
            'due_date': self._format_date(extracted_data.get('due_date')),
            'discount': self._format_number(extracted_data.get('total_discount')),
            'items': self._serialize_line_items(extracted_data.get('items', extracted_data.get('line_items'))),
            
            # Statement fields
            'account_number': extracted_data.get('account_number', ''),
            'statement_date': self._format_date(extracted_data.get('statement_date')),
            'transactions_count': str(extracted_data.get('transaction_count', extracted_data.get('transactions_count', ''))),
            'total_debits': self._format_number(extracted_data.get('total_debits')),
            'total_credits': self._format_number(extracted_data.get('total_credits')),
            'transactions': self._serialize_transactions(extracted_data.get('transactions', [])),
        }
        
        # Return only requested columns
        return {col: row_data.get(col, '') for col in columns}

    def _format_number(self, value: Any) -> str:
        """
        Format a number value for CSV.
        
        Args:
            value: Number value (int, float, or string)
            
        Returns:
            Formatted number string
        """
        if value is None:
            return ''
        
        try:
            # Convert to float and format
            num = float(value)
            return f"{num:.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _format_date(self, value: Any) -> str:
        """
        Format a date value for CSV.
        
        Args:
            value: Date value (string, datetime, or date)
            
        Returns:
            Formatted date string (ISO 8601)
        """
        if value is None:
            return ''
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        
        try:
            # Try to parse as datetime
            from dateutil import parser
            dt = parser.parse(str(value))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return str(value)

    def _serialize_line_items(self, line_items: Any) -> str:
        """
        Serialize line items as JSON string for CSV.
        
        Args:
            line_items: Line items list or dict
            
        Returns:
            JSON string representation
        """
        if not line_items:
            return '[]'
        
        try:
            # Serialize as compact JSON
            return json.dumps(line_items, separators=(',', ':'))
        except Exception as e:
            logger.warning(f"Failed to serialize line items: {e}")
            return '[]'
    
    def _serialize_transactions(self, transactions: Any) -> str:
        """
        Serialize bank statement transactions as JSON string for CSV.
        
        Args:
            transactions: Transactions list
            
        Returns:
            JSON string representation
        """
        if not transactions:
            return '[]'
        
        try:
            # Serialize as compact JSON
            return json.dumps(transactions, separators=(',', ':'))
        except Exception as e:
            logger.warning(f"Failed to serialize transactions: {e}")
            return '[]'

    def _format_attachment_paths(self, batch_file: BatchFileProcessing) -> str:
        """
        Format attachment paths as comma-separated string.
        
        Handles both file_path and cloud_file_url, preferring cloud URLs.
        
        Args:
            batch_file: BatchFileProcessing record
            
        Returns:
            Comma-separated attachment paths
        """
        paths = []
        
        # Prefer cloud URL if available
        if batch_file.cloud_file_url:
            paths.append(batch_file.cloud_file_url)
        elif batch_file.file_path:
            paths.append(batch_file.file_path)
        
        # Check extracted_data for additional attachment paths
        if batch_file.extracted_data:
            extracted_paths = batch_file.extracted_data.get('attachment_paths')
            if extracted_paths:
                if isinstance(extracted_paths, str):
                    # Already comma-separated
                    if extracted_paths not in paths:
                        paths.append(extracted_paths)
                elif isinstance(extracted_paths, list):
                    # List of paths
                    for path in extracted_paths:
                        if path and path not in paths:
                            paths.append(str(path))
        
        return ','.join(paths)

    async def upload_to_s3(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Upload CSV to AWS S3 and generate presigned URL.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            Presigned S3 URL (24 hour expiry)
            
        Raises:
            Exception: If upload fails
        """
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Get decrypted credentials with environment variable fallback
            import os
            dest_service = ExportDestinationService(self.db, tenant_id)
            credentials = dest_service.get_decrypted_credentials(destination_config.id)
            
            # Extract S3 configuration with environment fallback
            access_key_id = credentials.get('access_key_id', '').strip() or os.getenv('AWS_S3_ACCESS_KEY_ID', '')
            secret_access_key = credentials.get('secret_access_key', '').strip() or os.getenv('AWS_S3_SECRET_ACCESS_KEY', '')
            region = credentials.get('region', '').strip() or os.getenv('AWS_S3_REGION', 'us-east-1')
            bucket_name = credentials.get('bucket_name', '').strip() or os.getenv('AWS_S3_BUCKET_NAME', '')
            path_prefix = credentials.get('path_prefix', '').strip()
            
            using_env_fallback = not credentials.get('access_key_id')
            if using_env_fallback:
                logger.info("Using environment variables for S3 credentials")
            
            if not all([access_key_id, secret_access_key, bucket_name]):
                raise ValueError("Missing required S3 credentials (check export destination or environment variables)")
            
            # Log credential info for debugging (without exposing secrets)
            logger.debug(
                f"S3 credentials: access_key_id length={len(access_key_id)}, "
                f"secret_key length={len(secret_access_key)}, "
                f"region={region}, bucket={bucket_name}"
            )
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region
            )
            
            # Build S3 key with path prefix
            if path_prefix:
                if not path_prefix.endswith('/'):
                    path_prefix += '/'
                s3_key = f"{path_prefix}{filename}"
            else:
                s3_key = filename
            
            # Detect content type from filename
            import mimetypes
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                # Default to text/csv for backward compatibility (this method was originally for CSV exports)
                content_type = 'text/csv'
            
            # Upload file to S3
            logger.info(f"Uploading to S3: bucket={bucket_name}, key={s3_key}, content_type={content_type}")
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=csv_content,
                ContentType=content_type,
                Metadata={
                    'tenant_id': str(tenant_id),
                    'upload_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Generate presigned URL (24 hour expiry)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=86400  # 24 hours
            )
            
            logger.info(f"Successfully uploaded to S3: {s3_key}")
            
            return presigned_url
            
        except NoCredentialsError:
            logger.error("Invalid AWS credentials")
            raise Exception("Invalid AWS credentials")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"S3 upload failed ({error_code}): {error_msg}")
            raise Exception(f"S3 upload failed: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    async def upload_to_azure(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Upload CSV to Azure Blob Storage and generate SAS URL.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            SAS URL for download (24 hour expiry)
            
        Raises:
            Exception: If upload fails
        """
        try:
            from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
            from azure.core.exceptions import AzureError
            
            # Get decrypted credentials
            dest_service = ExportDestinationService(self.db, tenant_id)
            credentials = dest_service.get_decrypted_credentials(destination_config.id)
            
            # Extract Azure configuration
            container_name = credentials.get('container_name')
            path_prefix = credentials.get('path_prefix', '')
            
            if not container_name:
                raise ValueError("Missing required Azure container name")
            
            # Create blob service client
            if 'connection_string' in credentials:
                blob_service_client = BlobServiceClient.from_connection_string(
                    credentials['connection_string']
                )
                # Extract account name from connection string for SAS generation
                account_name = None
                account_key = None
                for part in credentials['connection_string'].split(';'):
                    if part.startswith('AccountName='):
                        account_name = part.split('=', 1)[1]
                    elif part.startswith('AccountKey='):
                        account_key = part.split('=', 1)[1]
            else:
                account_name = credentials.get('account_name')
                account_key = credentials.get('account_key')
                account_url = f"https://{account_name}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=account_key
                )
            
            if not account_name or not account_key:
                raise ValueError("Missing required Azure account credentials")
            
            # Build blob name with path prefix
            if path_prefix:
                if not path_prefix.endswith('/'):
                    path_prefix += '/'
                blob_name = f"{path_prefix}{filename}"
            else:
                blob_name = filename
            
            # Get container client
            container_client = blob_service_client.get_container_client(container_name)
            
            # Upload blob
            logger.info(f"Uploading to Azure: container={container_name}, blob={blob_name}")
            
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                csv_content,
                overwrite=True,
                content_settings=ContentSettings(content_type='text/csv'),
                metadata={
                    'tenant_id': str(tenant_id),
                    'upload_timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Generate SAS URL (24 hour expiry)
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            
            sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
            
            logger.info(f"Successfully uploaded to Azure: {blob_name}")
            
            return sas_url
            
        except AzureError as e:
            logger.error(f"Azure upload failed: {e}")
            raise Exception(f"Azure upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to upload to Azure: {e}")
            raise

    async def upload_to_gcs(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Upload CSV to Google Cloud Storage and generate signed URL.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            Signed GCS URL (24 hour expiry)
            
        Raises:
            Exception: If upload fails
        """
        try:
            from google.cloud import storage
            from google.oauth2 import service_account
            from google.api_core.exceptions import GoogleAPIError
            import json
            
            # Get decrypted credentials
            dest_service = ExportDestinationService(self.db, tenant_id)
            credentials = dest_service.get_decrypted_credentials(destination_config.id)
            
            # Extract GCS configuration
            bucket_name = credentials.get('bucket_name')
            path_prefix = credentials.get('path_prefix', '')
            
            if not bucket_name:
                raise ValueError("Missing required GCS bucket name")
            
            # Parse service account credentials
            if 'service_account_json' in credentials:
                service_account_info = json.loads(credentials['service_account_json'])
                credentials_obj = service_account.Credentials.from_service_account_info(
                    service_account_info
                )
            else:
                # Use project_id and credentials
                credentials_info = json.loads(credentials['credentials'])
                credentials_obj = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
            
            # Create storage client
            storage_client = storage.Client(
                credentials=credentials_obj,
                project=credentials_obj.project_id
            )
            
            # Build blob name with path prefix
            if path_prefix:
                if not path_prefix.endswith('/'):
                    path_prefix += '/'
                blob_name = f"{path_prefix}{filename}"
            else:
                blob_name = filename
            
            # Get bucket and blob
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Upload file
            logger.info(f"Uploading to GCS: bucket={bucket_name}, blob={blob_name}")
            
            blob.upload_from_string(
                csv_content,
                content_type='text/csv'
            )
            
            # Set metadata
            blob.metadata = {
                'tenant_id': str(tenant_id),
                'upload_timestamp': datetime.now(timezone.utc).isoformat()
            }
            blob.patch()
            
            # Generate signed URL (24 hour expiry)
            signed_url = blob.generate_signed_url(
                version='v4',
                expiration=timedelta(hours=24),
                method='GET'
            )
            
            logger.info(f"Successfully uploaded to GCS: {blob_name}")
            
            return signed_url
            
        except GoogleAPIError as e:
            logger.error(f"GCS upload failed: {e}")
            raise Exception(f"GCS upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            raise

    async def upload_to_google_drive(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Upload CSV to Google Drive and set file permissions.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            Google Drive file URL
            
        Raises:
            Exception: If upload fails
        """
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaInMemoryUpload
            from google.oauth2.credentials import Credentials
            from googleapiclient.errors import HttpError
            
            # Get decrypted credentials
            dest_service = ExportDestinationService(self.db, tenant_id)
            credentials = dest_service.get_decrypted_credentials(destination_config.id)
            
            # Extract Google Drive configuration
            oauth_token = credentials.get('oauth_token')
            refresh_token = credentials.get('refresh_token')
            folder_id = credentials.get('folder_id')
            
            if not all([oauth_token, folder_id]):
                raise ValueError("Missing required Google Drive credentials")
            
            # Create credentials object
            creds = Credentials(
                token=oauth_token,
                refresh_token=refresh_token
            )
            
            # Build Drive API service
            service = build('drive', 'v3', credentials=creds)
            
            # Prepare file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': 'text/csv',
                'properties': {
                    'tenant_id': str(tenant_id),
                    'upload_timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Create media upload
            media = MediaInMemoryUpload(
                csv_content,
                mimetype='text/csv',
                resumable=True
            )
            
            # Upload file
            logger.info(f"Uploading to Google Drive: folder={folder_id}, file={filename}")
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink,webContentLink'
            ).execute()
            
            file_id = file.get('id')
            
            # Set file permissions for sharing (anyone with link can view)
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            # Get shareable link
            file_url = file.get('webViewLink') or file.get('webContentLink')
            
            if not file_url:
                # Fallback to constructing URL
                file_url = f"https://drive.google.com/file/d/{file_id}/view"
            
            logger.info(f"Successfully uploaded to Google Drive: {file_id}")
            
            return file_url
            
        except HttpError as e:
            logger.error(f"Google Drive upload failed: {e}")
            raise Exception(f"Google Drive upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}")
            raise

    async def upload_to_local(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Save CSV to local file system.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            Local file path (as URL-like string)
            
        Raises:
            Exception: If save fails
        """
        try:
            import os
            from pathlib import Path
            
            # Get local path from config
            config = destination_config.config or {}
            base_path = config.get('path', '/exports')
            
            # Extract directory from filename (job_id/filename format)
            # filename is like: a557d10d-fd4d-4195-8462-969ceaba09e5/batch_export_...csv
            file_parts = filename.split('/')
            if len(file_parts) > 1:
                # Has subdirectory
                subdir = '/'.join(file_parts[:-1])
                actual_filename = file_parts[-1]
                local_dir = Path(base_path) / f"tenant_{tenant_id}" / subdir
            else:
                # No subdirectory
                actual_filename = filename
                local_dir = Path(base_path) / f"tenant_{tenant_id}"
            
            # Create all parent directories
            local_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = local_dir / actual_filename
            file_path.write_bytes(csv_content)
            
            logger.info(f"Successfully saved to local storage: {file_path}")
            
            # Return file path as URL-like string
            return f"file://{file_path}"
            
        except Exception as e:
            logger.error(f"Failed to save to local storage: {e}")
            raise Exception(f"Local storage save failed: {str(e)}")

    async def upload_with_retry(
        self,
        csv_content: bytes,
        destination_config: ExportDestinationConfig,
        filename: str,
        tenant_id: int
    ) -> str:
        """
        Upload CSV to destination with retry logic.
        
        Retries upload up to 5 times with exponential backoff on failure.
        Logs each retry attempt and marks job as failed if all retries exhausted.
        
        Args:
            csv_content: CSV content as bytes
            destination_config: Export destination configuration
            filename: CSV filename
            tenant_id: Tenant identifier
            
        Returns:
            URL to uploaded file
            
        Raises:
            Exception: If all retries are exhausted
        """
        destination_type = destination_config.destination_type
        last_error = None
        
        for attempt in range(self.MAX_EXPORT_RETRIES):
            try:
                logger.info(
                    f"Upload attempt {attempt + 1}/{self.MAX_EXPORT_RETRIES} "
                    f"to {destination_type}"
                )
                
                # Call appropriate upload method based on destination type
                if destination_type == 's3':
                    url = await self.upload_to_s3(
                        csv_content, destination_config, filename, tenant_id
                    )
                elif destination_type == 'azure':
                    url = await self.upload_to_azure(
                        csv_content, destination_config, filename, tenant_id
                    )
                elif destination_type == 'gcs':
                    url = await self.upload_to_gcs(
                        csv_content, destination_config, filename, tenant_id
                    )
                elif destination_type == 'google_drive':
                    url = await self.upload_to_google_drive(
                        csv_content, destination_config, filename, tenant_id
                    )
                elif destination_type == 'local':
                    url = await self.upload_to_local(
                        csv_content, destination_config, filename, tenant_id
                    )
                else:
                    raise ValueError(f"Unknown destination type: {destination_type}")
                
                # Success - return URL
                logger.info(
                    f"Upload successful on attempt {attempt + 1} to {destination_type}"
                )
                return url
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Upload attempt {attempt + 1} failed: {str(e)}"
                )
                
                # If not the last attempt, wait before retrying
                if attempt < self.MAX_EXPORT_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    
                    import asyncio
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        error_msg = f"Upload failed after {self.MAX_EXPORT_RETRIES} attempts: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)

    async def generate_and_export_results(
        self,
        batch_job: BatchProcessingJob
    ) -> Dict[str, Any]:
        """
        Generate CSV from job files and export to configured destination.
        
        This is the main orchestration method that:
        1. Generates CSV from processed files
        2. Determines destination type from job configuration
        3. Calls appropriate upload method with retry logic
        4. Updates BatchProcessingJob with export_file_url and export_completed_at
        5. Updates job status to "completed" or "partial_failure"
        
        Args:
            batch_job: BatchProcessingJob instance
            
        Returns:
            Dictionary with export results
            
        Raises:
            ValueError: If export destination not found
            Exception: If export fails after all retries
        """
        try:
            job_id = batch_job.job_id
            tenant_id = batch_job.tenant_id
            
            logger.info(f"Starting export for batch job {job_id}")
            
            # Get export destination configuration
            if not batch_job.export_destination_config_id:
                raise ValueError(
                    f"No export destination configured for job {job_id}"
                )
            
            destination_config = self.db.query(ExportDestinationConfig).filter(
                and_(
                    ExportDestinationConfig.id == batch_job.export_destination_config_id,
                    ExportDestinationConfig.tenant_id == tenant_id
                )
            ).first()
            
            if not destination_config:
                raise ValueError(
                    f"Export destination {batch_job.export_destination_config_id} "
                    f"not found for tenant {tenant_id}"
                )
            
            # If destination is inactive, try to use default destination
            if not destination_config.is_active:
                logger.warning(
                    f"Export destination {destination_config.name} (ID: {destination_config.id}) is not active. "
                    f"Attempting to use default destination."
                )
                default_destination = self.db.query(ExportDestinationConfig).filter(
                    and_(
                        ExportDestinationConfig.tenant_id == tenant_id,
                        ExportDestinationConfig.is_active == True,
                        ExportDestinationConfig.is_default == True
                    )
                ).first()
                
                if default_destination:
                    logger.info(
                        f"Using default destination: {default_destination.name} (ID: {default_destination.id})"
                    )
                    destination_config = default_destination
                else:
                    raise ValueError(
                        f"Export destination {destination_config.name} is not active "
                        f"and no default destination configured"
                    )
            
            # Generate CSV from job files
            logger.info(f"Generating CSV for job {job_id}")
            
            csv_content = self.generate_csv(
                job_id=job_id,
                custom_fields=batch_job.custom_fields
            )
            
            # Generate filename
            csv_filename = self.generate_csv_filename(job_id)
            
            # Save CSV to job folder
            base_dir = os.getenv("BATCH_FILES_DIR", "api/batch_files")
            job_dir = os.path.join(base_dir, f"tenant_{tenant_id}", job_id)
            csv_path = os.path.join(job_dir, csv_filename)
            
            try:
                # Create job directory if it doesn't exist
                os.makedirs(job_dir, exist_ok=True)
                
                with open(csv_path, 'wb') as f:
                    f.write(csv_content)
                logger.info(f"Saved CSV to job folder: {csv_path}")
            except Exception as e:
                logger.warning(f"Failed to save CSV to job folder: {e}")
            
            # Upload to destination with retry logic (include job_id in cloud path)
            cloud_filename = f"{job_id}/{csv_filename}"
            logger.info(
                f"Uploading CSV to {destination_config.destination_type} "
                f"destination: {destination_config.name}"
            )
            
            export_url = await self.upload_with_retry(
                csv_content=csv_content,
                destination_config=destination_config,
                filename=cloud_filename,
                tenant_id=tenant_id
            )
            
            # Update batch job with export results
            batch_job.export_file_url = export_url
            batch_job.export_file_key = cloud_filename
            batch_job.export_completed_at = datetime.now(timezone.utc)
            
            # Determine final job status
            if batch_job.failed_files > 0:
                batch_job.status = "partial_failure"
            else:
                batch_job.status = "completed"
            
            batch_job.completed_at = datetime.now(timezone.utc)
            batch_job.updated_at = datetime.now(timezone.utc)
            
            # Commit changes
            self.db.commit()
            self.db.refresh(batch_job)
            
            logger.info(
                f"Export completed for job {job_id}: "
                f"status={batch_job.status}, "
                f"url={export_url}"
            )
            
            # AUDIT: Log successful export operation
            try:
                # Try to get API client info for better audit logging
                user_email_display = f"user_{batch_job.user_id}@tenant_{tenant_id}"
                try:
                    from core.models.api_models import APIClient
                    from core.models.database import SessionLocal
                    # Query APIClient using a fresh session (master and tenant DB are the same)
                    query_db = SessionLocal()
                    try:
                        logger.debug(f"Querying APIClient with client_id={batch_job.api_client_id}")
                        api_client = query_db.query(APIClient).filter(
                            APIClient.client_id == batch_job.api_client_id
                        ).first()
                        if api_client and api_client.user:
                            user_email_display = f"{api_client.api_key_prefix}*** ({api_client.user.email})"
                            logger.debug(f"Found API client: {user_email_display}")
                        else:
                            logger.debug(f"API client not found or no user: api_client={api_client}")
                    finally:
                        query_db.close()
                except Exception as e:
                    logger.debug(f"Could not fetch API client info for audit log: {e}", exc_info=True)
                
                log_audit_event(
                    db=self.db,
                    user_id=batch_job.user_id,
                    user_email=user_email_display,
                    action="EXPORT",
                    resource_type="batch_processing_job",
                    resource_id=job_id,
                    resource_name=f"Batch Job {job_id}",
                    details={
                        "destination_type": destination_config.destination_type,
                        "destination_name": destination_config.name,
                        "total_files": batch_job.total_files,
                        "successful_files": batch_job.successful_files,
                        "failed_files": batch_job.failed_files,
                        "export_filename": cloud_filename,
                        "final_status": batch_job.status,
                        "api_client_id": batch_job.api_client_id
                    },
                    status="success"
                )
            except Exception as e:
                logger.warning(f"Failed to log audit event for export: {e}")
            
            return {
                "job_id": job_id,
                "status": batch_job.status,
                "export_url": export_url,
                "export_filename": cloud_filename,
                "destination_type": destination_config.destination_type,
                "destination_name": destination_config.name,
                "total_files": batch_job.total_files,
                "successful_files": batch_job.successful_files,
                "failed_files": batch_job.failed_files,
                "export_completed_at": batch_job.export_completed_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to export results for job {batch_job.job_id}: {e}")
            
            # Update job status to failed
            batch_job.status = "failed"
            batch_job.completed_at = datetime.now(timezone.utc)
            batch_job.updated_at = datetime.now(timezone.utc)
            
            # Store error message in a way that can be retrieved
            # (could add an error_message field to BatchProcessingJob model)
            
            self.db.commit()
            
            # AUDIT: Log failed export operation
            try:
                # Try to get API client info for better audit logging
                user_email_display = f"user_{batch_job.user_id}@tenant_{batch_job.tenant_id}"
                try:
                    from core.models.api_models import APIClient
                    from core.models.database import SessionLocal
                    # Query APIClient using a fresh session (master and tenant DB are the same)
                    query_db = SessionLocal()
                    try:
                        api_client = query_db.query(APIClient).filter(
                            APIClient.client_id == batch_job.api_client_id
                        ).first()
                        if api_client and api_client.user:
                            user_email_display = f"{api_client.api_key_prefix}*** ({api_client.user.email})"
                    finally:
                        query_db.close()
                except Exception as query_error:
                    logger.debug(f"Could not fetch API client info for audit log: {query_error}")
                
                log_audit_event(
                    db=self.db,
                    user_id=batch_job.user_id,
                    user_email=user_email_display,
                    action="EXPORT",
                    resource_type="batch_processing_job",
                    resource_id=batch_job.job_id,
                    resource_name=f"Batch Job {batch_job.job_id}",
                    details={
                        "destination_type": batch_job.export_destination_type,
                        "total_files": batch_job.total_files,
                        "successful_files": batch_job.successful_files,
                        "failed_files": batch_job.failed_files,
                        "error": str(e),
                        "api_client_id": batch_job.api_client_id
                    },
                    status="failure",
                    error_message=str(e)
                )
            except Exception as audit_error:
                logger.warning(f"Failed to log audit event for failed export: {audit_error}")
            
            raise
