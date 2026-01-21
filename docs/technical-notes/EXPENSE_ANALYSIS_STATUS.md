# Expense Analysis Status Documentation

## Overview

The expense system uses two different status tracking mechanisms that can cause confusion:

1. **Import Workflow Status** - UI-only status for file import process
2. **OCR Analysis Status** - Backend status for OCR processing lifecycle

## Import Workflow Status (UI Only)

Used in `ExpensesImport.tsx` for tracking file import progress:

- **pending** - Files selected but import not started
- **creating** - Creating base expense record
- **uploading** - Uploading attachment file
- **queued** - File uploaded, expense created, ready for OCR
- **error** - Import process failed
- **done** - Import process completed

## OCR Analysis Status (Backend)

Used in the database `analysis_status` field for OCR processing:

- **not_started** - Initial state when expense is created
- **pending** - Reserved for future use (not currently used in OCR flow)
- **queued** - Expense queued for OCR processing (attachment uploaded)
- **processing** - OCR worker actively processing the attachment
- **done** - OCR analysis completed successfully
- **failed** - OCR analysis failed
- **cancelled** - OCR analysis was cancelled

## Status Flow

```
File Import Flow:
pending → creating → uploading → queued → done/error

OCR Analysis Flow:
not_started → queued → processing → done/failed/cancelled
```

## Key Differences

**"pending"** (Import):
- UI-only status in import workflow
- Indicates files are selected but import hasn't started
- Not part of OCR analysis lifecycle

**"queued"** (OCR):
- Backend status indicating expense is ready for OCR processing
- Attachment has been uploaded successfully
- OCR task published to Kafka or scheduled for inline processing
- Waiting for OCR worker to process

## Process Again Functionality

For expenses with `analysis_status` of "pending" or "queued", users can trigger reprocessing:

- **API Endpoint**: `POST /api/v1/expenses/{expense_id}/reprocess`
- **UI Button**: "Process Again" button in expense details
- **Action**: Requeues the expense for OCR analysis using the latest attachment

## Troubleshooting

- If an expense shows "Pending" in UI but has attachments, check the `analysis_status` field
- "queued" status that persists may indicate OCR worker issues
- Use the "Process Again" button to retry stuck OCR jobs