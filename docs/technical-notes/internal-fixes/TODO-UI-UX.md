# TODO: UI/UX Design Improvements

Scope
- Bank Statements list and detail, Invoice/Expense creation from transactions, error/retry flows, and link indicators.

Priorities
- Status clarity: show human-friendly status chips (Processing, Processed, Failed) with tooltips explaining next actions.
- Retry UX: persistent "Process again" CTA for Failed; show inline spinner + disabled state during retry.
- One-time actions: clearly disable "Invoice" / "Expense" create when already linked; add tooltip "Already linked" with quick link.
- Link visibility: display linked Invoice Number (e.g., INV-20250814-0001) and Expense ID/Number as badges; add "Open" and "Copy" actions.
- Copy behavior: copy invoice number instead of numeric id; confirm via transient toast.
- Empty-state design: when extracted_count = 0 (and LLM reachable), show helpful empty-state messaging and a CTA to manually add rows.
- Error surfaces: show inline error banners when LLM unreachable, with guidance to start provider and retry.
- Confirmation flows: confirm destructive actions (delete statement, replace transactions) with clear impact text.
- Loading states: skeletons/placeholders for lists and table rows; optimistic UI for row edits.
- Accessibility: semantic buttons/links, focus management after dialogs, ARIA labels, keyboard navigation for table actions.
- Responsive layout: ensure actions row wraps cleanly on small screens; avoid overflow.
- i18n: wrap new strings; avoid hard-coded labels.
- Consistency: align button variants (outline/destructive), icon sizes, spacing.
- Navigation: add deep-link to related invoice/expense views in the app.

Interaction details
- Disable create buttons immediately on click; keep disabled after successful link (no flicker).
- Persist transaction link server-side, then refresh row to confirm; handle failure gracefully without losing disabled state.
- Show reason when action is disabled (tooltip or helper text).

Acceptance criteria
- Users cannot create duplicate invoice/expense for the same transaction; UI communicates the reason.
- Failed statements show an obvious retry path and do not appear as processed.
- Linked items display their identifiers and provide quick actions (open, copy).
- All new UI elements pass basic a11y checks and have tests.

Tracking
- Files: `ui/src/pages/Statements.tsx`, `ui/src/components/...`, `ui/src/lib/api.ts`.
- Backend: ensure APIs return identifiers needed for UI (invoice number, expense id/number, link flags).
