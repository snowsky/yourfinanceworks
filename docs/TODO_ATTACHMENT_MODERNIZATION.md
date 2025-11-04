# Attachment System Modernization TODO

## Overview
The system currently uses a hybrid approach supporting both legacy and modern attachment systems. This document outlines the steps to fully modernize the attachment system.

## Current Status ✅

### What's Working (Modern System)
- ✅ Modern attachment models exist (`InvoiceAttachment`, `ExpenseAttachment`, `ItemAttachment`)
- ✅ Modern attachment tables are being used in database
- ✅ Migration script completed and working
- ✅ Modern attachment counting and operations work correctly
- ✅ Legacy file cleanup is handled properly
- ✅ Bank statements use `file_path` (no migration needed)

### What's Still Legacy (Hybrid Support)
- ⚠️ API responses still include legacy fields (`attachment_filename`, `receipt_filename`)
- ⚠️ Frontend expects legacy fields in TypeScript interfaces
- ⚠️ Schemas include legacy fields for backward compatibility
- ⚠️ Some debug logging still references legacy fields

## Migration Phases

### Phase 1: Backend API Modernization (Medium Priority)

#### 1.1 Update Invoice Responses
- [ ] Remove legacy `attachment_filename` from invoice responses
- [ ] Update `get_attachment_info()` to only use modern attachments
- [ ] Add proper attachment objects to invoice responses
- [ ] Update invoice schemas to remove legacy fields

**Files to update:**
- `api/routers/invoices.py` - Response building
- `api/schemas/invoice.py` - Remove legacy fields
- `api/models/models_per_tenant.py` - Consider deprecating legacy columns

#### 1.2 Update Expense Responses  
- [ ] Remove legacy `receipt_filename` from expense responses
- [ ] Update expense list/detail endpoints to use modern attachments
- [ ] Update expense schemas to remove legacy fields

**Files to update:**
- `api/routers/expenses.py` - Response building
- `api/schemas/expense.py` - Remove `receipt_filename` field
- `api/models/models_per_tenant.py` - Consider deprecating legacy columns

#### 1.3 Clean Up Debug Logging
- [ ] Remove debug logs that reference legacy attachment fields
- [ ] Update logging to use modern attachment information

**Files to update:**
- `api/routers/invoices.py` - Lines 1139-1153 (debug logging)

### Phase 2: Frontend Modernization (High Priority)

#### 2.1 Update TypeScript Interfaces
- [ ] Remove `attachment_filename` from Invoice interface
- [ ] Remove `receipt_filename` from Expense interface  
- [ ] Add proper attachment objects to interfaces
- [ ] Update API response mapping

**Files to update:**
- `ui/src/lib/api.ts` - Lines 89, 395, 1404, 1436, 1488, 1501, 1505
- `ui/src/lib/api.ts` - Lines 1749, 1823 (function signatures)

#### 2.2 Update UI Components
- [ ] Update invoice components to use modern attachment data
- [ ] Update expense components to use modern attachment data
- [ ] Update file upload components if needed
- [ ] Test attachment display and download functionality

**Files to check:**
- `ui/src/pages/Settings.tsx`
- `ui/src/pages/Statements.tsx`
- `mobile/src/screens/NewExpenseScreen.tsx`
- `mobile/src/components/EnhancedFileUpload.tsx`

### Phase 3: Database Schema Cleanup (Low Priority)

#### 3.1 Deprecate Legacy Columns
- [ ] Add migration to mark legacy columns as deprecated
- [ ] Add database constraints to prevent new legacy data
- [ ] Monitor for any remaining legacy field usage

**Legacy columns to deprecate:**
- `invoices.attachment_path`
- `invoices.attachment_filename`  
- `expenses.receipt_path`
- `expenses.receipt_filename`

#### 3.2 Final Cleanup (Future)
- [ ] Create migration to remove legacy columns entirely
- [ ] Update all remaining references
- [ ] Full system testing

## Testing Strategy

### Before Each Phase
- [ ] Run migration script to ensure no legacy data exists
- [ ] Backup database
- [ ] Test current attachment functionality

### After Each Phase  
- [ ] Test attachment upload/download
- [ ] Test attachment display in UI
- [ ] Test attachment deletion
- [ ] Test invoice/expense creation with attachments
- [ ] Test mobile app functionality
- [ ] Verify no broken API responses

## Risk Assessment

### Low Risk ✅
- Backend API changes (Phase 1) - Well isolated
- Migration script improvements
- Debug logging cleanup

### Medium Risk ⚠️  
- Frontend interface changes (Phase 2) - May break UI
- Schema changes (Phase 3.1) - Database modifications

### High Risk 🚨
- Removing legacy columns (Phase 3.2) - Irreversible
- Breaking API compatibility

## Implementation Notes

### Current Hybrid Approach Benefits
- Backward compatibility maintained
- Gradual migration possible
- No breaking changes for existing users
- Safe fallback to legacy data if needed

### Migration Script Status
- ✅ Script completed and tested
- ✅ Handles tenant databases correctly
- ✅ Supports dry-run mode
- ✅ Proper error handling and logging
- ✅ Ready for production use

### Recommended Timeline
1. **Phase 1** (Backend) - 1-2 weeks
2. **Phase 2** (Frontend) - 2-3 weeks  
3. **Phase 3.1** (Schema deprecation) - 1 week
4. **Phase 3.2** (Final cleanup) - Future release

## Decision: Current Status
**Recommendation: Keep hybrid approach for now**

The current system is working well with the hybrid approach. The modern attachment system is fully functional, and the legacy fields provide safe backward compatibility. Consider implementing phases only when:

1. Legacy fields cause confusion or maintenance burden
2. New features require modern-only attachment system
3. Database storage optimization is needed
4. API simplification is prioritized

## Files Modified During Migration
- ✅ `api/scripts/migrate_legacy_attachments.py` - Completed migration script
- ✅ `api/routers/invoices.py` - Updated `get_attachment_info()` to prioritize modern attachments

---
*Last updated: November 3, 2025*
*Status: Migration script completed, system in stable hybrid state*