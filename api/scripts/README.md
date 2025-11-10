# API Scripts Documentation

This directory contains various utility scripts for managing and interacting with the API system. Below you'll find documentation for the most commonly used scripts and their purposes.

## Table of Contents

- [Quick Start](#quick-start)
- [File Upload Scripts](#file-upload-scripts)
- [Database Migration Scripts](#database-migration-scripts)
- [Testing Scripts](#testing-scripts)
- [Maintenance Scripts](#maintenance-scripts)
- [Development Scripts](#development-scripts)

## Quick Start

Most scripts are designed to be run within the Docker container environment. Use the following pattern:

```bash
# For scripts that communicate with the API
docker compose exec api python scripts/SCRIPT_NAME.py --arguments

# For scripts that work directly with the database
docker compose exec api python scripts/SCRIPT_NAME.py

# For shell scripts
docker compose exec api bash scripts/SCRIPT_NAME.sh
```

## File Upload Scripts

### batch_upload_files.py

The primary script for uploading multiple files to the batch processing system.

#### Basic Usage

```bash
docker compose exec api python scripts/batch_upload_files.py --document-type $DOC_TYPE --files PATH_TO_FILES --api-key $API_KEY
```

#### Required Parameters

- `--document-type`: Type of document (`invoice`, `expense`, `statement`)
- `--files`: Path to files or directory containing files
- `--api-key`: API key for authentication

#### Special Requirements

- **For invoice documents**: You must also include `--client-id`
  ```bash
  docker compose exec api python scripts/batch_upload_files.py --document-type invoice --client-id 123 --files path/to/invoices.pdf --api-key $API_KEY
  ```

#### Common Examples

```bash
# Upload a single expense file
docker compose exec api python scripts/batch_upload_files.py --document-type expense --files receipt.pdf --api-key $API_KEY

# Upload multiple PDF files as expenses
docker compose exec api python scripts/batch_upload_files.py --document-type expense --files *.pdf --api-key $API_KEY

# Upload all files from a directory
docker compose exec api python scripts/batch_upload_files.py --document-type expense --files /path/to/receipts/ --api-key $API_KEY

# Upload invoice with client ID
docker compose exec api python scripts/batch_upload_files.py --document-type invoice --client-id 123 --files invoice.pdf --api-key $API_KEY

# Upload and monitor progress
docker compose exec api python scripts/batch_upload_files.py --document-type expense --files *.pdf --api-key $API_KEY --monitor
```

#### Advanced Options

```bash
# With custom export destination
docker compose exec api python scripts/batch_upload_files.py --document-type expense --export-destination 2 --files *.pdf --api-key $API_KEY

# With webhook notification
docker compose exec api python scripts/batch_upload_files.py --document-type expense --files *.pdf --api-key $API_KEY --webhook https://example.com/webhook

# Monitor existing job
docker compose exec api python scripts/batch_upload_files.py --monitor --job-id JOB_ID --api-key $API_KEY
```

### simple_batch_upload.py

A simpler version of the batch upload script for basic use cases.

```bash
docker compose exec api python scripts/simple_batch_upload.py --files path/to/files --api-key $API_KEY
```

## Database Migration Scripts

### migrate_database.py

Main database migration script.

```bash
docker compose exec api python scripts/migrate_database.py
```

### run_all_migrations.py

Runs all pending database migrations.

```bash
docker compose exec api python scripts/run_all_migrations.py
```

### direct_migration.py

For direct database migrations when standard migration fails.

```bash
docker compose exec api python scripts/direct_migration.py
```

### postgresql_migration.py

PostgreSQL-specific migration operations.

```bash
docker compose exec api python scripts/postgresql_migration.py
```

## Testing Scripts

### test_simple_endpoint.py

Test basic API connectivity and functionality.

```bash
docker compose exec api python scripts/test_simple_endpoint.py
```

### test_auth.py

Test authentication system.

```bash
docker compose exec api python scripts/test_auth.py
```

### test_api_key_functionality.py

Test API key creation and validation.

```bash
docker compose exec api python scripts/test_api_key_functionality.py
```

### test_invoice.py

Test invoice processing functionality.

```bash
docker compose exec api python scripts/test_invoice.py
```

### test_inventory.py

Test inventory management functionality.

```bash
docker compose exec api python scripts/test_inventory.py
```

### test_ocr_integration.py

Test OCR (Optical Character Recognition) integration.

```bash
docker compose exec api python scripts/test_ocr_integration.py
```

### test_payments.py

Test payment processing functionality.

```bash
docker compose exec api python scripts/test_payments.py
```

## Maintenance Scripts

### check_migration_status.py

Check the status of database migrations.

```bash
docker compose exec api python scripts/check_migration_status.py
```

### check_user_role.py

Verify and fix user role assignments.

```bash
docker compose exec api python scripts/check_user_role.py
```

### cleanup_duplicate_clients.py

Remove duplicate client records.

```bash
docker compose exec api python scripts/cleanup_duplicate_clients.py
```

### cleanup_currencies.py

Clean up and standardize currency data.

```bash
docker compose exec api python scripts/cleanup_currencies.py
```

### reindex_search_data.py

Reindex search data for improved search performance.

```bash
docker compose exec api python scripts/reindex_search_data.py
```

## Development Scripts

### create_test_user.py

Create test users for development and testing.

```bash
docker compose exec api python scripts/create_test_user.py
```

### create_super_user.py

Create administrator users.

```bash
docker compose exec api python scripts/create_super_user.py
```

### create_batch_api_key.py

Generate batch processing API keys.

```bash
docker compose exec api python scripts/create_batch_api_key.py
```

### test_env_vars.py

Verify environment variable configuration.

```bash
docker compose exec api python scripts/test_env_vars.py
```

## Encryption and Security Scripts

### init_encryption.py

Initialize encryption system.

```bash
docker compose exec api python scripts/init_encryption.py
```

### check_encryption_env.py

Check encryption environment configuration.

```bash
docker compose exec api/python scripts/check_encryption_env.py
```

### fix_encrypted_data_display.py

Fix display issues with encrypted data.

```bash
docker compose exec api python scripts/fix_encrypted_data_display.py
```

## Cloud Storage Scripts

### setup_cloud_storage.py

Configure cloud storage providers.

```bash
docker compose exec api python scripts/setup_cloud_storage.py
```

### manage_cloud_storage_config.py

Manage cloud storage configuration settings.

```bash
docker compose exec api python scripts/manage_cloud_storage_config.py
```

### cloud_storage_deployment_check.py

Verify cloud storage deployment status.

```bash
docker compose exec api python scripts/cloud_storage_deployment_check.py
```

## File Processing Scripts

### migrate_legacy_attachments.py

Migrate legacy attachment files to new storage system.

```bash
docker compose exec api python scripts/migrate_legacy_attachments.py
```

### index_attachments.py

Index attachment files for search functionality.

```bash
docker compose exec api python scripts/index_attachments.py
```

### validate_cloud_storage_config.py

Validate cloud storage configuration.

```bash
docker compose exec api python scripts/validate_cloud_storage_config.py
```

## AI and OCR Scripts

### init_ai_config_master.py

Initialize AI configuration system.

```bash
docker compose exec api python scripts/init_ai_config_master.py
```

### update_ai_config.py

Update AI configuration settings.

```bash
docker compose exec api python scripts/update_ai_config.py
```

### trigger_ocr_reprocess.py

Trigger reprocessing of OCR data.

```bash
docker compose exec api python scripts/trigger_ocr_reprocess.py
```

## Getting Help

For most scripts, you can get detailed help by running:

```bash
docker compose exec api python scripts/SCRIPT_NAME.py --help
```

This will show all available options, parameters, and usage examples for that specific script.

## Error Handling

If you encounter issues:

1. Check the script help output with `--help`
2. Verify all required environment variables are set
3. Ensure the API service is running
4. Check log files for detailed error messages
5. Verify file permissions and paths

## Environment Variables

Many scripts use environment variables for configuration. Common variables include:

- `API_KEY`: API authentication key
- `API_URL`: API base URL (default: http://localhost:8000)
- `DOC_TYPE`: Document type (invoice, expense, statement)
- Database connection variables
- Encryption keys and settings

Refer to the main API documentation for complete environment variable reference.