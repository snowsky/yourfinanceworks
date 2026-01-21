# Data Export & Import Guide

## Overview

The invoice management application provides comprehensive data export and import functionality for complete backup and restore operations.

## Export Functionality

### What Gets Exported

The export creates a SQLite database file containing **all** tenant data:

| Data Type | Table | Description |
|-----------|-------|-------------|
| Users | `users` | User accounts and profiles |
| Clients | `clients` | Customer information |
| Client Notes | `client_notes` | CRM notes and interactions |
| Invoices | `invoices` | Complete invoice records |
| Invoice Items | `invoice_items` | Line items for invoices |
| Invoice History | `invoice_history` | Change tracking |
| Payments | `payments` | Payment records |
| **Expenses** | `expenses` | Expense tracking records |
| **Expense Attachments** | `expense_attachments` | Receipt file metadata |
| **Bank Statements** | `bank_statements` | Bank statement files |
| **Bank Statement Transactions** | `bank_statement_transactions` | Individual transactions |
| Settings | `settings` | System configuration |
| Discount Rules | `discount_rules` | Pricing rules |
| Currencies | `supported_currencies` | Currency support |
| Currency Rates | `currency_rates` | Exchange rates |
| AI Configs | `ai_configs` | AI assistant settings |
| **Audit Logs** | `audit_logs` | System activity logs |
| **AI Chat History** | `ai_chat_history` | AI conversation history |
| Email Notifications | `email_notification_settings` | Notification preferences |

### File Attachments

**Important**: Physical attachment files (PDFs, images, receipts) are **NOT** included in the export. Only database metadata is exported:

- **Expenses**: `expense_attachments` table contains file metadata, but actual receipt files are not included
- **Bank Statements**: File metadata is in `bank_statements` table (`file_path`, `original_filename`, `stored_filename`)
- **Invoices**: Attachment metadata is in `invoices` table (`attachment_path`, `attachment_filename`)

## Import Functionality

### Process Overview

1. **Validation**: Checks file format and required tables
2. **Data Cleanup**: Removes existing data (preserves superusers)
3. **ID Mapping**: Maps old IDs to new IDs to maintain relationships
4. **Data Import**: Imports all tables with proper foreign key handling
5. **Verification**: Commits changes or rolls back on error

### ID Mapping

The import process maintains data relationships through ID mapping:

- `old_to_new_user_ids`: Maps user IDs
- `old_to_new_client_ids`: Maps client IDs  
- `old_to_new_invoice_ids`: Maps invoice IDs
- `old_to_new_expense_ids`: Maps expense IDs
- `old_to_new_statement_ids`: Maps bank statement IDs

### Data Relationships

The system properly handles these relationships during import:

- **Expenses** → Users (via `user_id`)
- **Expenses** → Invoices (via `invoice_id`)
- **Expense Attachments** → Expenses (via `expense_id`)
- **Bank Statement Transactions** → Bank Statements (via `statement_id`)
- **Bank Statement Transactions** → Invoices (via `invoice_id`)
- **Bank Statement Transactions** → Expenses (via `expense_id`)

## Usage

### Export Data

1. Navigate to **Settings** → **Export** tab
2. Click **Download Complete Backup**
3. Save the `.sqlite` file to a secure location

### Import Data

1. Navigate to **Settings** → **Export** tab
2. Click **Choose File** and select a `.sqlite` backup file
3. **Important**: Create a backup first using **Backup Current Data First**
4. Click **Import and Replace Data**

## File Structure

### Bank Statement Files

Bank statements have a **1:1 relationship** between database records and files:
- Each `BankStatement` record represents one uploaded file
- File metadata stored directly in the table (no separate attachment table)
- Actual files stored in `/attachments/tenant_X/bank_statements/`

### Expense Files

Expenses support **multiple attachments**:
- `ExpenseAttachment` table stores metadata for each file
- Multiple attachments can be linked to one expense
- Actual files stored in `/attachments/tenant_X/expenses/`

## Limitations

1. **Physical Files**: Attachment files are not included in export/import
2. **File Paths**: Imported records retain original file paths (files may not exist)
3. **Superusers**: Superuser accounts are never imported from backups
4. **Tenant Isolation**: Data remains isolated per tenant

## Best Practices

1. **Regular Backups**: Export data regularly for disaster recovery
2. **Test Imports**: Test restore process in development environment
3. **File Management**: Separately backup attachment files if needed
4. **Version Control**: Keep multiple backup versions with timestamps

## Technical Details

- **Export Format**: SQLite database with full schema
- **File Size**: Varies based on data volume (typically small without attachments)
- **Compatibility**: Works with any SQLite-compatible database tools
- **Security**: No sensitive authentication data included