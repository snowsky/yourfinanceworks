# Invoice AI Assistant fixes — 2026-11-13

Fixed active-tenant propagation into fallback API calls; routed chat writes through explicit confirmation; tied asynchronous responses and prompt-job polling to stable message IDs; added bounded, retained, user-scoped conversation context.

Pre-merge review also fixed explicit request delegation for statement tools and the missing authenticated invoice-creation method.

## Validation

- Isolated backend regressions: 13 passed (`pytest --noconftest api/tests/test_assistant_safety.py`). Uses mocked external dependencies and a real SQLite query for history isolation/retention.
- Assistant/onboarding UI tests: 22 passed in 6 files.
- ESLint for the new assistant test and confirmation card: passed. The existing assistant file still has legacy lint violations.
- Changed Python modules parse successfully; `git diff --check` passes.
- Full UI run: 46 failed files, 75 passed; 340 failed tests, 724 passed, 7 skipped; worker exit errors also reported. This is not a green full-suite result.
- Production build blocked by unresolved `@/api/statements`, `@/lib/publicUsage`, and `@/lib/visitor` imports from the linked `yfw-statement-tools` plugin.
- Application TypeScript check also reports repository-wide errors (log: `/private/tmp/invoice-assistant-app-types.log`), including existing unused declarations in the assistant. No type errors were reported for the new test or confirmation card.
- Full local backend suite cannot load its application fixture because the available test environment lacks `uvicorn`.
- No deployment or live-browser/provider validation performed.

Detailed local logs: `/private/tmp/invoice-assistant-ui-suite.log`, `/private/tmp/invoice-assistant-build.log`, `/private/tmp/invoice-assistant-backend-suite.log`, `/private/tmp/invoice-assistant-lint.log`.

## Failing UI test files

- `src/__tests__/ExpenseApprovalIntegration.test.tsx`
- `src/__tests__/InvoiceWorkflow.integration.test.tsx`
- `src/components/__tests__/ApprovalDashboard.test.tsx`
- `src/components/__tests__/ApprovalHistoryTimeline.test.tsx`
- `src/components/__tests__/ApprovalReportsPage.test.tsx`
- `src/components/__tests__/ExpenseApprovalStatus.test.tsx`
- `src/components/__tests__/ExportFormatSelector.test.tsx`
- `src/components/__tests__/InvoicesClone.test.tsx`
- `src/components/__tests__/PendingApprovalsList.test.tsx`
- `src/components/__tests__/ReportFilters.test.tsx`
- `src/components/__tests__/ReportGenerator.test.tsx`
- `src/components/__tests__/ReportHistory.test.tsx`
- `src/components/__tests__/ReportPreview.test.tsx`
- `src/components/__tests__/ReportRegeneration.test.tsx`
- `src/components/__tests__/ReportSharing.test.tsx`
- `src/components/__tests__/ReportTypeSelector.test.tsx`
- `src/components/__tests__/ScheduledReportDetails.test.tsx`
- `src/components/__tests__/ScheduledReportForm.test.tsx`
- `src/components/__tests__/TemplateBasedReportGenerator.test.tsx`
- `src/components/__tests__/TemplateForm.test.tsx`
- `src/components/__tests__/TemplateGenerateDialog.test.tsx`
- `src/components/cookie-consent/__tests__/ConsentBanner.test.tsx`
- `src/components/cookie-consent/__tests__/CookieConsentBanner.test.tsx`
- `src/components/cookie-consent/__tests__/PreferencesModal.test.tsx`
- `src/components/cookie-consent/__tests__/accessibility/AccessibilityCompliance.test.tsx`
- `src/components/cookie-consent/__tests__/comprehensive/BasicTestSuite.test.tsx`
- `src/components/cookie-consent/__tests__/comprehensive/ComprehensiveTestSuite.test.tsx`
- `src/components/cookie-consent/__tests__/e2e/CookieConsentE2E.test.tsx`
- `src/components/cookie-consent/__tests__/gdpr/GDPRCompliance.test.tsx`
- `src/components/dashboard/__tests__/QuickActions.test.tsx`
- `src/components/help/__tests__/ApprovalHelpTooltips.test.tsx`
- `src/components/investments/__tests__/FileUploadComponents.test.tsx`
- `src/components/investments/__tests__/FileUploadIntegration.test.tsx`
- `src/components/invoices/__tests__/InvoiceFormClientEdit.test.tsx`
- `src/components/notifications/__tests__/ApprovalNotificationPreferences.test.tsx`
- `src/components/plugins/__tests__/PluginErrorBoundary.test.tsx`
- `src/components/reminders/__tests__/ReminderCard.test.tsx`
- `src/contexts/__tests__/PluginContext.test.tsx`
- `src/contexts/__tests__/PluginInitializationOrder.property.test.tsx`
- `src/hooks/__tests__/useAttachmentManagement.test.ts`
- `src/hooks/__tests__/useClientManagement.test.ts`
- `src/hooks/__tests__/useInvoiceForm.test.ts`
- `src/hooks/__tests__/useNotifications.test.ts`
- `src/utils/__tests__/formatDate.test.ts`
