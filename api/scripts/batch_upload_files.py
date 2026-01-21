#!/usr/bin/env python3
"""
Batch File Upload Script

This script uploads multiple files to the batch processing API endpoint.
It handles authentication, file validation, and provides progress feedback.

Usage:
    python batch_upload_files.py --files file1.pdf file2.jpg file3.pdf
    python batch_upload_files.py --directory /path/to/files
    python batch_upload_files.py --files *.pdf --export-destination 1
"""

import argparse
import os
import sys
import time
import glob
from pathlib import Path
from typing import List, Optional
import requests


class BatchFileUploader:
    """Client for uploading files to the batch processing API"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        api_key: str = None
    ):
        """
        Initialize the batch file uploader.
        
        Args:
            api_url: Base URL of the API
            api_key: API key for authentication (X-API-Key header)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set up API key authentication header
        if api_key:
            self.session.headers.update({'X-API-Key': api_key})
    
    def test_authentication(self) -> tuple[bool, Optional[str]]:
        """
        Test if the API key is valid by making a simple request.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to list jobs (should return 200 even if empty)
            url = f"{self.api_url}/api/v1/external-transactions/batch-processing/jobs"
            response = self.session.get(url)
            if response.status_code == 200:
                return True, None
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as e:
            return False, str(e)
    
    def validate_file(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate a file before upload.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        # Check if it's a file (not directory)
        if not os.path.isfile(file_path):
            return False, f"Not a file: {file_path}"
        
        # Check file size (max 20MB)
        file_size = os.path.getsize(file_path)
        max_size = 20 * 1024 * 1024  # 20MB
        if file_size > max_size:
            return False, f"File too large ({file_size / (1024*1024):.1f}MB): {file_path}"
        
        # Check file extension
        allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.csv'}
        ext = Path(file_path).suffix.lower()
        if ext not in allowed_extensions:
            return False, f"Invalid file type '{ext}': {file_path}"
        
        return True, None
    
    def upload_batch(
        self,
        file_paths: List[str],
        export_destination_id: Optional[int] = None,
        document_types: Optional[List[str]] = None,
        client_id: Optional[int] = None,
        webhook_url: Optional[str] = None,
        custom_fields: Optional[List[str]] = None
    ) -> dict:
        """
        Upload a batch of files for processing.
        
        Args:
            file_paths: List of file paths to upload
            export_destination_id: Optional ID of the export destination (uses tenant default if not specified)
            document_types: Optional list of document types (invoice, expense, statement) - one per file
            client_id: Optional client ID for invoice documents
            webhook_url: Optional webhook URL for completion notification
            custom_fields: Optional list of custom fields to include in export
            
        Returns:
            API response dictionary
            
        Raises:
            requests.HTTPError: If the API request fails
        """
        # Validate all files first
        print(f"\n📋 Validating {len(file_paths)} files...")
        valid_files = []
        for file_path in file_paths:
            is_valid, error = self.validate_file(file_path)
            if is_valid:
                valid_files.append(file_path)
                print(f"  ✓ {os.path.basename(file_path)}")
            else:
                print(f"  ✗ {error}")
        
        if not valid_files:
            raise ValueError("No valid files to upload")
        
        print(f"\n📤 Uploading {len(valid_files)} files to batch processing API...")
        
        # Prepare multipart form data
        files = []
        for file_path in valid_files:
            filename = os.path.basename(file_path)
            files.append(
                ('files', (filename, open(file_path, 'rb'), 'application/octet-stream'))
            )
        
        # Prepare form data
        data = {}
        
        if export_destination_id is not None:
            data['export_destination_id'] = export_destination_id
        
        if document_types:
            data['document_types'] = ','.join(document_types)
        
        if client_id is not None:
            data['client_id'] = client_id
        
        if webhook_url:
            data['webhook_url'] = webhook_url
        
        if custom_fields:
            data['custom_fields'] = ','.join(custom_fields)
        
        # Make API request
        url = f"{self.api_url}/api/v1/external-transactions/batch-processing/upload"
        
        try:
            response = self.session.post(url, files=files, data=data)
            response.raise_for_status()
            
            # Close all file handles
            for _, file_tuple in files:
                file_tuple[1].close()
            
            result = response.json()
            print(f"\n✅ Batch job created successfully!")
            print(f"   Job ID: {result.get('job_id')}")
            print(f"   Status: {result.get('status')}")
            print(f"   Total files: {result.get('total_files')}")
            
            return result
            
        except requests.HTTPError as e:
            print(f"\n❌ Upload failed: {e}")
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    detail_msg = error_detail.get('detail', 'Unknown error')
                    
                    # Parse and simplify common errors
                    if 'ForeignKeyViolation' in str(detail_msg) and 'client_id' in str(detail_msg):
                        # Extract client_id from error message
                        import re
                        match = re.search(r'client_id\)=\((\d+)\)', str(detail_msg))
                        if match:
                            invalid_client_id = match.group(1)
                            print(f"\n❌ Client ID {invalid_client_id} does not exist")
                            print("\n💡 Please create the client first:")
                            print("   1. Login to the web application")
                            print("   2. Go to Clients section")
                            print("   3. Create a new client")
                            print("   4. Use the client ID when uploading invoices")
                        else:
                            print(f"   Error: Invalid client_id - client does not exist")
                            print("\n💡 Please create the client in the web application first")
                    else:
                        # Show first line of error only
                        first_line = str(detail_msg).split('\n')[0]
                        print(f"   Error: {first_line}")
                except:
                    # Fallback to simple text response
                    print(f"   Response: {e.response.text[:200]}")

            # Additional hint for common port conflicts
            if e.response is not None and e.response.status_code == 404:
                import urllib.parse
                parsed_url = urllib.parse.urlparse(url)
                if parsed_url.port == 8000:
                    print("\n💡 Port Conflict Detected?")
                    print("   It seems you're hitting port 8000, but another service might be running there.")
                    print("   In this project, the API is often accessible via Nginx on port 8080.")
                    print("   Try adding --api-url http://localhost:8080 to your command.")
            sys.exit(1)
        finally:
            # Ensure all files are closed
            for _, file_tuple in files:
                try:
                    file_tuple[1].close()
                except:
                    pass

    def get_job_status(self, job_id: str) -> dict:
        """
        Get the status of a batch processing job.
        
        Args:
            job_id: Batch job ID
            
        Returns:
            Job status dictionary
        """
        url = f"{self.api_url}/api/v1/external-transactions/batch-processing/jobs/{job_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"\n❌ Authentication failed: Invalid or expired API key")
                print("\n💡 Make sure you're using a valid API key:")
                print("   - Check that the API key is correct")
                print("   - Verify the API key hasn't been revoked")
                print("   - Ensure you're using the same API key that created the job")
                sys.exit(1)
            elif e.response.status_code == 404:
                print(f"\n❌ Job not found: {job_id}")
                print("\n💡 Possible reasons:")
                print("   - Job ID is incorrect")
                print("   - Job was created by a different API key/tenant")
                print("   - Job has been deleted")
                sys.exit(1)
            raise

    def list_jobs(self, status: Optional[str] = None, limit: int = 20) -> dict:
        """
        List batch processing jobs.
        
        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            Dictionary with list of jobs
        """
        url = f"{self.api_url}/api/v1/external-transactions/batch-processing/jobs"
        params = {"limit": limit}
        if status:
            params["status_filter"] = status
            
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            print(f"\n❌ Failed to list jobs: {e}")
            if e.response is not None:
                print(f"   Response: {e.response.text[:200]}")
            sys.exit(1)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a batch processing job.
        
        Args:
            job_id: Batch job ID
            
        Returns:
            True if cancelled successfully
        """
        url = f"{self.api_url}/api/v1/external-transactions/batch-processing/jobs/{job_id}"
        
        try:
            response = self.session.delete(url)
            response.raise_for_status()
            result = response.json()
            print(f"\n✅ {result.get('message', 'Job cancelled successfully')}")
            return True
        except requests.HTTPError as e:
            print(f"\n❌ Failed to cancel job {job_id}: {e}")
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
                except:
                    print(f"   Response: {e.response.text[:200]}")
            return False

    def cancel_all_jobs(self) -> bool:
        """
        Cancel all active batch processing jobs.
        
        Returns:
            True if cancelled successfully
        """
        url = f"{self.api_url}/api/v1/external-transactions/batch-processing/jobs"
        
        try:
            response = self.session.delete(url)
            response.raise_for_status()
            result = response.json()
            print(f"\n✅ {result.get('message', 'All active jobs cancelled successfully')}")
            return True
        except requests.HTTPError as e:
            print(f"\n❌ Failed to cancel all jobs: {e}")
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
                except:
                    print(f"   Response: {e.response.text[:200]}")
            return False
    
    def monitor_job(self, job_id: str, poll_interval: int = 5):
        """
        Monitor a batch job until completion.
        
        Args:
            job_id: Batch job ID
            poll_interval: Seconds between status checks
        """
        print(f"\n🔄 Monitoring job {job_id}...")
        print("   Press Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                try:
                    status = self.get_job_status(job_id)
                except requests.HTTPError:
                    # Error already printed in get_job_status
                    return
                
                progress = status.get('progress', {})
                processed = progress.get('processed_files', 0)
                total = progress.get('total_files', 0)
                percentage = progress.get('progress_percentage', 0)
                job_status = status.get('status', 'unknown')
                
                # Print progress
                print(f"\r   Status: {job_status} | Progress: {processed}/{total} ({percentage:.1f}%)", end='', flush=True)
                
                # Check if completed
                if job_status in ['completed', 'failed', 'partial_failure']:
                    print()  # New line
                    
                    if job_status == 'completed':
                        print(f"\n✅ Job completed successfully!")
                        export_url = status.get('export', {}).get('export_file_url')
                        if export_url:
                            print(f"   Export URL: {export_url}")
                    elif job_status == 'failed':
                        print(f"\n❌ Job failed!")
                    else:
                        print(f"\n⚠️  Job completed with some failures")
                        print(f"   Successful: {progress.get('successful_files', 0)}")
                        print(f"   Failed: {progress.get('failed_files', 0)}")
                    
                    break
                
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏸️  Monitoring stopped (job continues in background)")


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Upload multiple files to batch processing API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload specific files
  python batch_upload_files.py --files invoice1.pdf invoice2.pdf receipt.jpg
  
  # Upload all files as expenses
  python batch_upload_files.py --files ~/Downloads/receipts/* --document-type expense
  
  # Upload all files as invoices
  python batch_upload_files.py --files *.pdf --document-type invoice
  
  # Upload all PDFs in a directory (auto-detect type)
  python batch_upload_files.py --files /path/to/files/*.pdf
  
  # Upload with custom export destination
  python batch_upload_files.py --files *.pdf --export-destination 2
  
  # Upload and monitor progress
  python batch_upload_files.py --files *.pdf --document-type expense --monitor
  
  # Upload with webhook notification
  python batch_upload_files.py --files *.pdf --webhook https://example.com/webhook
        """
    )
    
    # File selection arguments (not required if monitoring existing job)
    file_group = parser.add_mutually_exclusive_group(required=False)
    file_group.add_argument(
        '--files',
        nargs='+',
        help='List of files to upload (supports wildcards)'
    )
    file_group.add_argument(
        '--directory',
        help='Directory containing files to upload'
    )
    
    # API configuration
    parser.add_argument(
        '--api-url',
        default=os.getenv('API_URL', 'http://localhost:8080'),
        help='API base URL (default: http://localhost:8080)'
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv('API_KEY'),
        help='API key for authentication (X-API-Key header). Can also set API_KEY environment variable.'
    )
    
    # Batch processing options
    parser.add_argument(
        '--export-destination',
        type=int,
        default=None,
        help='Export destination ID (uses tenant default if not specified)'
    )
    parser.add_argument(
        '--document-type',
        choices=['invoice', 'expense', 'statement'],
        help='Document type to apply to all files (invoice, expense, or statement). If not specified, system will auto-detect.'
    )
    parser.add_argument(
        '--client-id',
        type=int,
        help='Client ID for invoice documents (required if document-type is invoice)'
    )
    parser.add_argument(
        '--webhook',
        help='Webhook URL for completion notification'
    )
    parser.add_argument(
        '--custom-fields',
        nargs='+',
        help='Custom fields to include in export (e.g., vendor amount date)'
    )
    
    # Monitoring and management options
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Monitor job progress until completion'
    )
    parser.add_argument(
        '--job-id',
        help='Job ID to monitor or cancel'
    )
    parser.add_argument(
        '--poll-interval',
        type=int,
        default=5,
        help='Seconds between status checks when monitoring (default: 5)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List recent batch jobs'
    )
    parser.add_argument(
        '--list-status',
        choices=['pending', 'processing', 'completed', 'failed', 'partial_failure', 'cancelled'],
        help='Filter listed jobs by status'
    )
    parser.add_argument(
        '--cancel',
        action='store_true',
        help='Cancel the job specified by --job-id'
    )
    parser.add_argument(
        '--cancel-all',
        action='store_true',
        help='Cancel all active batch jobs'
    )
    
    args = parser.parse_args()
    
    # If monitoring existing job, files are not required
    if args.job_id and args.monitor:
        if not args.api_key:
            print("❌ Error: API key required for authentication")
            print("   Provide via --api-key argument or set API_KEY environment variable")
            sys.exit(1)
        
        # Create uploader
        uploader = BatchFileUploader(
            api_url=args.api_url,
            api_key=args.api_key
        )
        
        # Test authentication before monitoring
        print("🔐 Testing API key authentication...")
        is_valid, error_msg = uploader.test_authentication()
        if not is_valid:
            print(f"❌ Authentication failed: {error_msg}")
            print("\n💡 To create a new API key:")
            print("   1. Login to the web app")
            print("   2. Go to Settings → API Keys")
            print("   3. Click 'Create API Key'")
            print("   4. Copy the generated key")
            sys.exit(1)
        print("✓ Authentication successful\n")
        
        # Monitor the existing job
        uploader.monitor_job(args.job_id, poll_interval=args.poll_interval)
        sys.exit(0)
    
    # Handle job listing
    if args.list:
        if not args.api_key:
            print("❌ Error: API key required for authentication")
            sys.exit(1)
        
        uploader = BatchFileUploader(api_url=args.api_url, api_key=args.api_key)
        result = uploader.list_jobs(status=args.list_status)
        
        jobs = result.get('jobs', [])
        if not jobs:
            print("\n📭 No batch jobs found.")
        else:
            print(f"\n📋 Recent Batch Jobs (Total: {result.get('total', 0)}):")
            print(f"{'Job ID':<38} {'Status':<15} {'Progress':<15} {'Created At'}")
            print("-" * 85)
            for job in jobs:
                progress = f"{job.get('processed_files', 0)}/{job.get('total_files', 0)}"
                created_at = job.get('created_at', 'Unknown').split('.')[0].replace('T', ' ')
                print(f"{job.get('job_id'):<38} {job.get('status'):<15} {progress:<15} {created_at}")
        sys.exit(0)

    # Handle job cancellation
    if args.cancel:
        if not args.job_id:
            print("❌ Error: --job-id is required for cancellation")
            sys.exit(1)
        if not args.api_key:
            print("❌ Error: API key required for authentication")
            sys.exit(1)
            
        uploader = BatchFileUploader(api_url=args.api_url, api_key=args.api_key)
        uploader.cancel_job(args.job_id)
        sys.exit(0)

    # Handle "cancel all"
    if args.cancel_all:
        if not args.api_key:
            print("❌ Error: API key required for authentication")
            sys.exit(1)
            
        uploader = BatchFileUploader(api_url=args.api_url, api_key=args.api_key)
        uploader.cancel_all_jobs()
        sys.exit(0)
    
    # Collect files (required unless monitoring existing job)
    if not args.files and not args.directory:
        print("❌ Error: Either --files or --directory is required for uploading")
        sys.exit(1)
    
    file_paths = []
    if args.files:
        # Expand wildcards
        for pattern in args.files:
            expanded = glob.glob(pattern)
            if expanded:
                file_paths.extend(expanded)
            else:
                file_paths.append(pattern)  # Keep as-is if no match
    elif args.directory:
        # Get all files from directory
        directory = Path(args.directory)
        if not directory.exists():
            print(f"❌ Directory not found: {args.directory}")
            sys.exit(1)
        
        for ext in ['.pdf', '.png', '.jpg', '.jpeg', '.csv']:
            file_paths.extend(directory.glob(f'*{ext}'))
            file_paths.extend(directory.glob(f'*{ext.upper()}'))
        
        file_paths = [str(f) for f in file_paths]
    
    if not file_paths:
        print("❌ No files found to upload")
        sys.exit(1)
    
    # Check for API key
    if not args.api_key:
        print("❌ Error: API key required for authentication")
        print("   Provide via --api-key argument or set API_KEY environment variable")
        print("\n💡 To create an API key:")
        print("   1. Login to the web app")
        print("   2. Go to Settings → API Keys (or External API)")
        print("   3. Click 'Create API Key'")
        print("   4. Copy the generated key")
        print("\n💡 Example usage:")
        print("   export API_KEY='ak_your-api-key-here'")
        print("   python batch_upload_files.py --files *.pdf")
        sys.exit(1)
    
    # Create uploader
    uploader = BatchFileUploader(
        api_url=args.api_url,
        api_key=args.api_key
    )
    
    # Prepare document types - apply same type to all files if specified
    document_types = None
    if args.document_type:
        document_types = [args.document_type] * len(file_paths)
        print(f"\n📝 Setting all files as type: {args.document_type}")
    
    try:
        # Upload batch
        upload_kwargs = {
            'file_paths': file_paths,
            'document_types': document_types,
            'client_id': args.client_id,
            'webhook_url': args.webhook,
            'custom_fields': args.custom_fields
        }
        
        # Only include export_destination_id if specified
        if args.export_destination is not None:
            upload_kwargs['export_destination_id'] = args.export_destination
        
        result = uploader.upload_batch(**upload_kwargs)
        
        # Monitor if requested
        if args.monitor:
            job_id = result.get('job_id')
            if job_id:
                uploader.monitor_job(job_id, poll_interval=args.poll_interval)
        else:
            print(f"\n💡 To monitor progress, run:")
            print(f"   python batch_upload_files.py --monitor --job-id {result.get('job_id')}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
