# Refactoring TODO

Large files to split into focused modules, ranked by size and impact.

## Completed

| File | Lines | Result |
|------|-------|--------|
| `ui/src/lib/api.ts` | 4,246 | → 22 domain modules in `ui/src/lib/api/` (branch: `api-ts-refactoring`) |
| `api/MCP/tools.py` | 4,396 | → 19 mixin classes in `api/MCP/tools/` (branch: `tools-py-refactoring`) |
| `api/core/routers/invoices.py` | 3,640 | → 6 modules in `api/core/routers/invoices/`: `crud`, `attachments`, `history`, `pdf_email`, `reviews`, `_shared` (branch: `refactoring-2nd-phase-1`) |
| `ui/src/pages/SuperAdmin.tsx` | 1,653 | → 4 tab modules in `ui/src/pages/SuperAdmin/`: `TenantsTab`, `UsersTab`, `DatabasesTab`, `AnomaliesTab` + shared `types.ts` |
| `api/commercial/ai_bank_statement/router.py` | 1,782 | → 4 modules in `api/commercial/ai_bank_statement/routers/`: `upload`, `crud`, `transactions`, `processing` + `_shared` |
| `api/commercial/batch_processing/service.py` | 1,822 | → 8 mixin modules in `api/commercial/batch_processing/services/`: `validation`, `classification`, `storage`, `job_creation`, `kafka`, `progress`, `retry`, `cancellation` + `_shared` |
| `api/commercial/reporting/router.py` | 1,904 | → 5 modules in `api/commercial/reporting/routers/`: `generate`, `templates`, `scheduled`, `history`, `performance` + `_shared` |
| `ui/src/pages/Expenses.tsx` | 1,902 | → 7 modules in `ui/src/pages/Expenses/`: `ExpenseFilters`, `BulkActionsToolbar`, `ExpenseTable`, `RecycleBinSection`, `ExpenseEditDialog`, `AttachmentPreviewDialog`, `types` |
| `api/workers/ocr_consumer.py` | 1,940 | → 5 modules in `api/workers/ocr/`: `expense_handler`, `bank_statement_handler`, `invoice_handler`, `base_handler`, `consumer` + `_shared` |
| `api/core/routers/auth.py` | 1,996 | → 5 modules in `api/core/routers/auth/`: `login_register`, `password`, `invites`, `sso` + `_shared` |
| `api/core/services/license_service.py` | 2,004 | → 3 mixin modules in `api/core/services/license_service/`: `validation`, `features`, `activation` + `_shared` |
| `api/core/routers/super_admin.py` | 2,072 | → 3 modules in `api/core/routers/super_admin/`: `tenants`, `users`, `system` + `_shared` |
| `api/core/services/storage_monitoring_service.py` | 2,176 | → 4 mixin modules in `api/core/services/storage_monitoring_service/`: `health`, `metrics`, `alerts`, `reports` + `_shared` |
| `api/commercial/workflows/approvals/router.py` | 2,262 | → 4 modules in `api/commercial/workflows/approvals/routers/`: `expense_approvals`, `invoice_approvals`, `delegations`, `_shared` |
| `api/commercial/ai/router.py` | 2,299 | → 3 modules in `api/commercial/ai/routers/`: `invoice_analysis`, `chat`, `client_notes` + `_shared`; `chat` further split into `chat_models`, `auth_client`, `action_handlers`, `intent_handlers`, `chat_history` (chat.py: 1,949 → 331 lines) |


## Remaining

| Priority | Lines | File | Approach |
|----------|-------|------|----------|
| 2 | 2,942 | `ui/src/pages/Statements.tsx` | Extract sub-components: table, filters, detail modal, charts |
| 3 | 2,770 | `api/core/services/statement_service.py` | Split by responsibility: CRUD, extraction, reconciliation, export |
| 4 | 2,689 | `api/core/routers/expenses.py` | Same pattern as invoices router |
| 5 | 2,450 | `api/MCP/server.py` | Split tool registration from server lifecycle |
| 6 | 2,326 | `api/commercial/ai/services/ocr_service.py` | Split by document type / processing stage |

