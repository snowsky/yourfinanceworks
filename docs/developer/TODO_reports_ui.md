# Reports UI — Missing Wiring

The backend reporting API and frontend components are fully implemented but
`ui/src/pages/Reports.tsx` only renders `<ReportGenerator />` (report type
selection). Everything below needs to be wired into the page.

## Current state

| Area | Backend route | API client | UI component | Wired into page |
|------|--------------|------------|--------------|-----------------|
| Report types | `GET /reports/types` | `reportApi.getReportTypes` | `ReportTypeSelector` | ✅ |
| Generate report | `POST /reports/generate` | `reportApi.generateReport` | — | ❌ |
| Preview report | `POST /reports/preview` | `reportApi.previewReport` | `ReportPreview` | ❌ |
| Templates list | `GET /reports/templates` | `reportApi.getTemplates` | `TemplateManager` | ❌ |
| Create template | `POST /reports/templates` | `reportApi.createTemplate` | `TemplateForm` | ❌ |
| Delete template | `DELETE /reports/templates/{id}` | `reportApi.deleteTemplate` | `TemplateManager` | ❌ |
| Generate from template | `POST /reports/generate` | `reportApi.generateReport` | `TemplateBasedReportGenerator`, `TemplateGenerateDialog` | ❌ |
| Share template | — | — | `TemplateSharing` | ❌ |
| Scheduled reports | `GET /reports/scheduled` | `reportApi.getScheduledReports` | `ScheduledReportsManager` | ❌ |
| Create schedule | `POST /reports/scheduled` | `reportApi.createScheduledReport` | `ScheduledReportForm` | ❌ |
| Update schedule | `PUT /reports/scheduled/{id}` | `reportApi.updateScheduledReport` | `ScheduledReportDetails` | ❌ |
| Delete schedule | `DELETE /reports/scheduled/{id}` | `reportApi.deleteScheduledReport` | `ScheduledReportsManager` | ❌ |
| Report history | `GET /reports/history` | `reportApi.getHistory` | `ReportHistory` | ❌ |
| Download report | `GET /reports/download/{id}` | `reportApi.downloadReport` | `ReportHistory` | ❌ |
| Regenerate report | `POST /reports/regenerate/{id}` | `reportApi.regenerateReport` | `ReportRegeneration` | ❌ |
| Share report | — | — | `ReportSharing` | ❌ |
| Export format selector | — | — | `ExportFormatSelector` | ❌ |
| Report filters | — | — | `ReportFilters` | ❌ |

## What needs to be done

### 1. Add tabs to `Reports.tsx`

`Reports.tsx` should become a tabbed layout:

```
[ Generate ] [ Templates ] [ Scheduled ] [ History ]
```

Suggested tab structure:

- **Generate** — current `<ReportGenerator />` plus `<ReportFilters />`,
  `<ExportFormatSelector />`, and `<ReportPreview />`
- **Templates** — `<TemplateManager />` with create/edit/delete/share
- **Scheduled** — `<ScheduledReportsManager />` with form and details panels
- **History** — `<ReportHistory />` with download and regenerate actions

### 2. Wire generate flow end-to-end

`ReportGenerator` only selects a type. It needs to:
- Render `<ReportFilters />` after a type is selected
- Render `<ExportFormatSelector />`
- Call `reportApi.generateReport` on submit
- Show `<ReportPreview />` for JSON results
- Show a download link for PDF/CSV (poll history or use the returned URL)

### 3. Template-based generation

`TemplateBasedReportGenerator` and `TemplateGenerateDialog` exist but are
not reachable. Add a **"Generate from template"** action inside `TemplateManager`.

### 4. Missing API client functions

These backend routes have no frontend client method yet:

| Route | Missing client function |
|-------|------------------------|
| `PUT /reports/templates/{id}` | `reportApi.updateTemplate` |
| `DELETE /reports/history/{id}` | `reportApi.deleteReport` (stub exists, commented out in `ReportHistory.tsx:205`) |

### 5. Performance / admin endpoints (optional)

These are admin-only and low priority for the user-facing UI:

- `GET /reports/performance/cache/stats`
- `DELETE /reports/performance/cache`
- `GET /reports/performance/query/stats`
- `GET /reports/storage/stats`
- `POST /reports/cleanup/expired`
- `POST /reports/cleanup/orphaned`

Could be added to the SuperAdmin page under a **Reports** section.

## Relevant files

| File | Role |
|------|------|
| `ui/src/pages/Reports.tsx` | Entry point — needs tabs added |
| `ui/src/components/reports/ReportGenerator.tsx` | Type selector only |
| `ui/src/components/reports/ReportFilters.tsx` | Filter form (unused) |
| `ui/src/components/reports/ExportFormatSelector.tsx` | Format picker (unused) |
| `ui/src/components/reports/ReportPreview.tsx` | JSON preview (unused) |
| `ui/src/components/reports/TemplateManager.tsx` | Template CRUD (unused) |
| `ui/src/components/reports/TemplateForm.tsx` | Create/edit form (unused) |
| `ui/src/components/reports/TemplateGenerateDialog.tsx` | Generate from template (unused) |
| `ui/src/components/reports/TemplateBasedReportGenerator.tsx` | Template generation flow (unused) |
| `ui/src/components/reports/TemplateSharing.tsx` | Sharing UI (unused) |
| `ui/src/components/reports/ScheduledReportsManager.tsx` | Scheduled list (unused) |
| `ui/src/components/reports/ScheduledReportForm.tsx` | Create/edit schedule (unused) |
| `ui/src/components/reports/ScheduledReportDetails.tsx` | Schedule details (unused) |
| `ui/src/components/reports/ReportHistory.tsx` | History + download (unused) |
| `ui/src/components/reports/ReportRegeneration.tsx` | Regenerate action (unused) |
| `ui/src/components/reports/ReportSharing.tsx` | Share report (unused) |
| `ui/src/lib/api/reports.ts` | API client (mostly complete) |
