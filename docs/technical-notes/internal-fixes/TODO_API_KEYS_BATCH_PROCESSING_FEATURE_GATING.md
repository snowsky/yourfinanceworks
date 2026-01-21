# TODO: API Keys and Batch Processing Feature Gating

## Overview
The `api_keys` and `batch_processing` features need to be properly gated with license checks to ensure only licensed users can access these premium features.

## Current Status
- ✅ AI features (ai_invoice, ai_expense, ai_bank_statement) - Feature gating implemented
- ❌ API Keys feature - Not yet gated
- ❌ Batch Processing feature - Not yet gated

## Features to Gate

### 1. API Keys Feature (`api_keys`)

**Backend Endpoints to Protect:**
- `POST /api/v1/external-api-auth/clients` - Create API client
- `GET /api/v1/external-api-auth/clients` - List API clients
- `PUT /api/v1/external-api-auth/clients/{client_id}` - Update API client
- `DELETE /api/v1/external-api-auth/clients/{client_id}` - Delete API client
- `POST /api/v1/external-api-auth/clients/{client_id}/regenerate-secret` - Regenerate secret

**Files to Update:**
- `api/routers/external_api_auth.py` - Add `@require_feature("api_keys")` decorator to endpoints

**Frontend Components to Gate:**
- `ui/src/components/APIClientManagement/APIClientManagement.tsx` - Wrap with FeatureGate or show disabled state
- Settings page API Keys tab - Show upgrade prompt when feature not available

**Implementation Steps:**
1. Add `@require_feature("api_keys")` to all API client management endpoints
2. Wrap API Keys management UI with FeatureGate component
3. Show informational message when feature is not available
4. Test with license that doesn't include api_keys feature

### 2. Batch Processing Feature (`batch_processing`)

**Backend Endpoints to Protect:**
- `POST /api/v1/batch-processing/jobs` - Create batch job
- `GET /api/v1/batch-processing/jobs` - List batch jobs
- `GET /api/v1/batch-processing/jobs/{job_id}` - Get batch job details
- `POST /api/v1/batch-processing/jobs/{job_id}/files` - Upload files to batch job
- `POST /api/v1/batch-processing/jobs/{job_id}/start` - Start batch processing
- `DELETE /api/v1/batch-processing/jobs/{job_id}` - Delete batch job

**Files to Update:**
- `api/routers/batch_processing.py` - Add `@require_feature("batch_processing")` decorator to endpoints

**Frontend Components to Gate:**
- Batch upload UI components
- Batch processing status pages
- Any "Import Multiple" or "Bulk Upload" buttons

**Implementation Steps:**
1. Add `@require_feature("batch_processing")` to all batch processing endpoints
2. Identify all frontend entry points for batch processing
3. Wrap with FeatureGate or show disabled state with tooltip
4. Update documentation to reflect feature requirements
5. Test with license that doesn't include batch_processing feature

## Related Features

These features are interconnected:
- **API Keys** enable external integrations and programmatic access
- **Batch Processing** is often used via API for bulk operations
- Both are typically "Business" or "Enterprise" tier features

## Testing Checklist

### API Keys Feature
- [ ] Create license without api_keys feature
- [ ] Verify API endpoints return 403 Forbidden
- [ ] Verify UI shows disabled state or upgrade prompt
- [ ] Verify error messages are user-friendly
- [ ] Test with license that includes api_keys feature

### Batch Processing Feature
- [ ] Create license without batch_processing feature
- [ ] Verify batch processing endpoints return 403 Forbidden
- [ ] Verify UI hides or disables batch upload options
- [ ] Verify error messages are user-friendly
- [ ] Test with license that includes batch_processing feature

## Priority
**Medium-High** - These are premium features that should be properly monetized through licensing.

## Estimated Effort
- API Keys gating: 2-3 hours
- Batch Processing gating: 3-4 hours
- Testing: 2 hours
- **Total: 7-9 hours**

## Notes
- Consider whether batch processing should be split into separate features:
  - `batch_expense_processing`
  - `batch_invoice_processing`
  - `batch_statement_processing`
- API Keys might need rate limiting based on license tier
- Document which license tiers include these features in FEATURE_MATRIX.md

## References
- Feature gate implementation: `api/utils/feature_gate.py`
- Frontend FeatureGate component: `ui/src/components/FeatureGate.tsx`
- Feature context: `ui/src/contexts/FeatureContext.tsx`
- Existing implementations: Invoice PDF import, Bank Statement upload, Expense receipt processing
