# Popular Finance Software — Feature Ideas

Candidate features inspired by leading consumer/SMB finance apps (YNAB, Monarch, Copilot, Rocket Money, Personal Capital/Empower, Expensify, QuickBooks). Ordered roughly by leverage given the current codebase.

---

## 1. Subscription / Recurring-Charge Detection
**Inspiration:** Copilot Money, Rocket Money

Auto-cluster transactions by merchant + cadence (weekly/monthly/annual) and surface:
- Active subscription list with next-expected-charge date
- Price-change alerts ("Netflix went from $15.49 → $17.99")
- "Forgotten" subscriptions (low usage signal or unrecognized merchant)
- One-click cancel reminder / draft cancellation email

**Fit:** Builds on existing duplicate-transaction grouping logic (see [[project_duplicate_transaction_review]]). Cashflow service already aggregates transactions.

**Scope:** Medium. New service module + UI panel; reuses transaction/merchant normalization.

---

## 2. Budgets + Savings Goals
**Inspiration:** YNAB, Monarch Money

- Category-based budget envelopes with month-over-month rollover
- Savings goals tied to specific accounts (e.g. "Emergency fund: $10k by Dec 2026")
- Forecast: "on track / off track" projections using existing cashflow service
- Variance alerts (notification when category is X% over budget mid-month)

**Fit:** Plugs into cashflow service + notification service (both recently refactored). Expense categories already exist.

**Scope:** Large. New models (budgets, goals, allocations), routers, UI pages, notification triggers.

---

## 3. Net Worth + Account Aggregation
**Inspiration:** Personal Capital / Empower

- Unified timeline across cash, investments, liabilities
- Net-worth chart with month-over-month delta
- Asset allocation breakdown (cash / equities / real estate / debt)
- Integrate with existing `investments` plugin for portfolio value

**Fit:** Investments plugin already exists. Needs a "liabilities/loans" concept (credit cards, mortgages) and an aggregation service.

**Scope:** Medium-large. Mostly a read/aggregation layer over existing data + a new UI dashboard.

---

## Already Built — Skipping

- **Receipt OCR → drafted expense** — already implemented in `api/commercial/ai/services/ocr_service/` (~2.5k lines) with `POST /expenses/{id}/upload-receipt` and reprocess support. Possible polish work: mobile capture UX, bank-statement receipt detection (branch `feat/receipt-detection-in-bank-statements`).
- **Financial health score** — `api/core/services/financial_health_calculator.py` + `ui/src/components/gamification/FinancialHealthScore.tsx` already exist.

---

## Other Candidates (not yet evaluated)

- **Cash-flow forecasting beyond budgets** — Monte Carlo / scenario modeling
- **Bill negotiation reminders** — "Your internet bill is above avg for your area"
- **Tax category tagging + year-end export** — Schedule C / VAT-ready reports
- **Mileage tracking plugin** — GPS or manual entry for self-employed
- **Shared household accounts** — multi-user views with permission scoping
- **Custom report builder** — drag-and-drop pivot over transactions
- **Smart categorization rules** — "all transactions from Starbucks → Coffee"
