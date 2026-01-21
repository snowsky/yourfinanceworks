# TODO: Expense Status Refactoring

## Backend - Expense Status Values
- [x] Update API schema to support: `recorded`, `pending`, `submitted`, `reimbursed`
- [ ] Add validation for expense status values in API endpoints
- [ ] Update database migration if needed for status column constraints

## UI - Expense Status Column
- [x] Add Status column to expenses table
- [x] Add status selector in new expense form
- [ ] Add status selector in edit expense form
- [ ] Add status filter in expenses list
- [ ] Update expense status translations in i18n files

## Analysis Status Issues
### Backend
- [ ] Fix analysis_status logic in expense creation (currently sets 'pending' in status field)
- [ ] Separate expense.status from expense.analysis_status properly
- [ ] Update expense router to handle analysis_status vs status correctly

### UI
- [ ] Fix "Analyzed" column to show analysis_status properly
- [ ] Remove frontend logic that determines status based on analysis_status
- [ ] Update status display to use backend expense.status field only
- [ ] Add separate analysis status display if needed

## Current Issues
1. Backend sets expense.status='pending' for imported attachments, but this should be analysis_status
2. UI "Analyzed" column mixes analysis_status and expense.status logic
3. Missing status selector in edit form
4. No status filtering capability
5. Expense status and analysis status are conflated

## Expected Behavior
- `expense.status`: Business status (recorded/pending/submitted/reimbursed)
- `expense.analysis_status`: OCR/AI processing status (not_started/queued/processing/done/failed/cancelled)
- UI should display both separately and clearly