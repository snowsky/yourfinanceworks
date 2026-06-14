# Finances Tab "What's Included" Intro Card — Design Spec

**Date:** 2026-06-14
**Status:** Approved (design)
**Branch:** `feat/finances-hub-networth` (PR #407 — same branch as the Finances hub)

## Problem

The new `/finances` hub has two tabs (Cash Flow, Net Worth) whose labels don't convey what
each actually includes or pulls from. New users won't know that Cash Flow forecasts from
invoices/expenses/bank patterns, or that Net Worth combines bank + investments + liabilities.

## Goal

A small, dismissible "What's included" card at the top of each tab, summarizing the tab's
data sources and outputs. Persistent dismissal per tab (localStorage) so returning users
aren't nagged.

## Component

`ui/src/components/finances/FinancesTabIntro.tsx`:

```
interface FinancesTabIntroProps {
  storageKey: string;     // e.g. 'finances_intro_cashflow_dismissed'
  title: string;          // e.g. "What's in Cash Flow"
  description: string;     // one-line purpose
  sources: string[];       // bullet items (sources)
  output: string;          // the "⇒ ..." outcome line
}
```

- On mount, reads `localStorage.getItem(storageKey)`; if `=== 'true'`, renders `null`.
- Renders a compact `ProfessionalCard` (muted/info styling): an `Info` icon, the `title`
  (small heading), the `description` (muted), a tight inline list of `sources` (e.g.
  middot-separated or small badges), and the `output` line emphasized. A small "×" button
  (aria-label "Dismiss") sets `localStorage[storageKey] = 'true'` and hides the card
  (local `useState` so it disappears immediately without a reload).
- Pure presentational + localStorage; no API calls.

## Placement

In `ui/src/pages/Finances.tsx`, inside each `TabsContent`, rendered ABOVE the existing tab
body component (`CashFlowTabContent` / `NetWorthTabContent` stay unchanged):

- Cash Flow tab — storageKey `finances_intro_cashflow_dismissed`,
  title "What's in Cash Flow",
  description "Projects money in and out so you can see your runway and plan ahead.",
  sources ["Unpaid invoices (money in)", "Recorded & recurring expenses (money out)",
  "Recurring bank-statement patterns"],
  output "Forecast, runway & scenario planning".
- Net Worth tab — storageKey `finances_intro_networth_dismissed`,
  title "What's in Net Worth",
  description "Combines everything you own and owe into one number, tracked over time.",
  sources ["Bank balances (from statements)", "Investment portfolios (current value)",
  "Liabilities you add (cards, loans, mortgages)"],
  output "Net worth, per-account breakdown & trend".

## Testing (Vitest/RTL)

`ui/src/components/finances/__tests__/FinancesTabIntro.test.tsx`:
- Renders the title, each source, and the output when not dismissed.
- Clicking "×" hides the card and writes `localStorage[storageKey] = 'true'`.
- When `localStorage[storageKey]` is pre-set to `'true'`, the component renders nothing.
- (Clear localStorage in `beforeEach`.)

The existing `Finances.test.tsx` stays green (the intro renders alongside the mocked tab
bodies; its presence doesn't conflict with existing assertions). `tsc -p tsconfig.app.json
--noEmit` clean for the new/edited files.

## Out of scope

No backend, no i18n keys (inline strings, matching the hub), no per-user server-side
persistence (localStorage only, like the existing onboarding/tour dismissals).

## Files

- New: `ui/src/components/finances/FinancesTabIntro.tsx`,
  `ui/src/components/finances/__tests__/FinancesTabIntro.test.tsx`
- Modified: `ui/src/pages/Finances.tsx` (render the intro in each TabsContent)
