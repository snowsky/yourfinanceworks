# License Management API Documentation

## Overview

The License Management API provides customer-side endpoints for managing software licenses, trial periods, and feature availability. This API is part of the feature licensing and modularization system.

## Base URL

```
/api/v1/license
```

## Authentication

All endpoints require authentication using a Bearer token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## Endpoints

### 1. Get License Status

Get comprehensive information about the current license and trial status.

**Endpoint:** `GET /license/status`

**Response:**
```json
{
  "installation_id": "7df0a9b6-6379-4278-ac00-81d66ed51005",
  "license_status": "trial",
  "is_licensed": false,
  "is_trial": true,
  "trial_info": {
    "is_trial": true,
    "trial_active": true,
    "trial_start_date": "2025-11-17T01:17:09.594526+00:00",
    "trial_end_date": "2025-12-17T01:17:09.594526+00:00",
    "days_remaining": 29,
    "in_grace_period": false,
    "grace_period_end": null
  },
  "license_info": null,
  "enabled_features": ["all"],
  "has_all_features": true
}
```

**Fields:**
- `installation_id`: Unique identifier for this installation
- `license_status`: Current status (`trial`, `active`, `expired`)
- `is_licensed`: Whether a valid license is active
- `is_trial`: Whether in trial mode
- `trial_info`: Detailed trial information
  - `trial_active`: Whether trial is still active
  - `days_remaining`: Days left in trial period
  - `in_grace_period`: Whether in grace period after trial expiration
- `license_info`: License details (only when licensed)
- `enabled_features`: List of enabled feature IDs (or `["all"]` during trial)
- `has_all_features`: Whether all features are available

### 2. Get Feature Availability

Get a list of all features with their availability status.

**Endpoint:** `GET /license/features`

**Response:**
```json
{
  "features": [
    {
      "id": "ai_invoice",
      "name": "AI Invoice Processing",
      "description": "AI-powered invoice data extraction and processing",
      "category": "ai",
      "enabled": true
    },
    {
      "id": "ai_expense",
      "name": "AI Expense Processing",
      "description": "AI-powered expense OCR and categorization",
      "category": "ai",
      "enabled": true
    }
    // ... more features
  ],
  "trial_status": {
    "is_trial": true,
    "trial_active": true,
    "trial_start_date": "2025-11-17T01:17:09.594526+00:00",
    "trial_end_date": "2025-12-17T01:17:09.594526+00:00",
    "days_remaining": 29,
    "in_grace_period": false,
    "grace_period_end": null
  },
  "license_status": "trial"
}
```

**Feature Categories:**
- `ai`: AI-powered features (invoice processing, expense OCR, etc.)
- `integration`: Third-party integrations (Slack, tax services, etc.)
- `advanced`: Advanced features (batch processing, inventory, approvals, etc.)

### 3. Validate License Key

Validate a license key without activating it. Useful for pre-validation in the UI.

**Endpoint:** `POST /license/validate`

**Request Body:**
```json
{
  "license_key": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response:**
```json
{
  "valid": true,
  "message": "License key is valid",
  "payload": {
    "customer_email": "customer@example.com",
    "customer_name": "John Doe",
    "organization_name": "Acme Corp",
    "features": ["ai_invoice", "ai_expense", "batch_processing"],
    "iat": 1700000000,
    "exp": 1731536000,
    "license_type": "commercial"
  },
  "error": null,
  "error_code": null
}
```

**Error Response:**
```json
{
  "valid": false,
  "message": "Invalid license signature",
  "payload": null,
  "error": "Invalid license signature",
  "error_code": "INVALID_SIGNATURE"
}
```

**Error Codes:**
- `EXPIRED`: License has expired
- `INVALID_SIGNATURE`: License signature is invalid
- `MALFORMED`: License key is malformed
- `VERIFICATION_ERROR`: General verification error

### 4. Activate License

Activate a license key for this installation.

**Endpoint:** `POST /license/activate`

**Request Body:**
```json
{
  "license_key": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response:**
```json
{
  "success": true,
  "message": "License activated successfully",
  "features": ["ai_invoice", "ai_expense", "batch_processing"],
  "expires_at": "2025-11-17T01:17:09.594526+00:00",
  "error": null
}
```

**Error Response (400):**
```json
{
  "detail": {
    "error": "ACTIVATION_FAILED",
    "message": "License has expired",
    "details": "License has expired"
  }
}
```

### 5. Deactivate License

Deactivate the current license and revert to trial mode.

**Endpoint:** `DELETE /license/deactivate`

**Response:**
```json
{
  "success": true,
  "message": "License deactivated successfully"
}
```

## Trial Period

- **Duration:** 30 days from first installation
- **Grace Period:** 7 days after trial expiration
- **Features:** All features are available during trial and grace period
- **Auto-activation:** Trial starts automatically on first API call

## License Key Format

License keys are JWT tokens signed with RSA-256. They contain:

- `customer_email`: Customer email address
- `customer_name`: Customer name
- `organization_name`: Organization name
- `features`: Array of licensed feature IDs
- `iat`: Issued at timestamp
- `exp`: Expiration timestamp
- `license_type`: Type of license (e.g., "commercial", "trial")

## Feature IDs

### AI Features
- `ai_invoice`: AI Invoice Processing
- `ai_expense`: AI Expense Processing
- `ai_bank_statement`: AI Bank Statement Processing
- `ai_chat`: AI Chat Assistant

### Integration Features
- `tax_integration`: Tax Service Integration
- `slack_integration`: Slack Integration
- `cloud_storage`: Cloud Storage (AWS S3, Azure Blob, GCP)
- `sso`: SSO Authentication (Google, Azure AD)

### Advanced Features
- `batch_processing`: Batch File Processing
- `inventory`: Inventory Management
- `approvals`: Approval Workflows
- `reporting`: Advanced Reporting
- `advanced_search`: Advanced Search

## Testing

A test script is available to verify all endpoints:

```bash
bash api/scripts/test_license_endpoints.sh
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request data or license activation failed
- `401 Unauthorized`: Missing or invalid authentication token
- `500 Internal Server Error`: Server error

Error responses include a `detail` field with error information.

## Security

- License keys are validated using RSA-256 signature verification
- Public key is embedded in the application
- Private key is kept secure on the license server
- All validation attempts are logged for audit purposes
- License validation results are cached for 1 hour for performance

## Requirements Mapping

This implementation satisfies the following requirements:

- **Requirement 1.7**: License Validation API
  - GET /license/status - View organization's licenses
  - POST /license/activate - Activate license
  - POST /license/validate - Check specific feature licensing
  - GET /license/features - Feature availability status

- **Requirement 1.8**: UI Feature Visibility
  - GET /license/features - Returns licensed features for frontend
  - Includes trial status and expiration information
  - Provides feature metadata for UI rendering
