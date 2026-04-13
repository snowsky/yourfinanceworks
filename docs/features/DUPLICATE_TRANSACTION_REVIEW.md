# Duplicate Transaction Review & Delete

Review and resolve duplicate transactions detected across bank statements directly from the Statements page, without having to navigate to each statement individually.

## Overview

When the same transaction (matching date, description, and amount) appears in more than one uploaded statement, the system flags it as a potential duplicate. The duplicate warning banner now includes a **Review & Delete** button per group, letting you pick which copy to keep and permanently delete the rest in a guided two-step modal.

## How It Works

### 1. Duplicate Detection

The backend scans all non-deleted statements and groups transactions that share identical:
- **Date**
- **Description** (normalized, case-insensitive)
- **Amount** (rounded to 2 decimal places)

Groups are only shown if they span **at least two different statements** and are **not already linked** via a TransactionLink (transfer or FX conversion).

### 2. Warning Banner

When duplicates are detected, a yellow warning banner appears at the top of the Statements list view (not shown when a statement is open). It shows the total number of duplicate groups and collapses by default.

### 3. Review & Delete Flow

Each group in the expanded banner has a red **Review & Delete** button in its header row.

**Step 1 — Select which transaction to keep**

A modal opens showing all transactions in the group. Each row displays:
- Description
- Date · Amount · Source statement filename

Select the transaction to **keep** using the radio buttons. All others will be marked for deletion. The footer shows how many will be deleted.

**Step 2 — Confirm deletion**

A confirmation screen lists the transactions that will be permanently deleted (with description, date, amount, and filename). Click **Confirm Delete** to proceed, or **Back** to change your selection.

After deletion:
- A success toast confirms how many transactions were removed.
- The duplicate groups panel refreshes automatically.

## Implementation Reference

| Layer | File | Notes |
|-------|------|-------|
| Frontend component | `ui/src/pages/Statements/DuplicateTransactionPanel.tsx` | `ReviewModal` + panel with per-group button |
| Frontend API client | `ui/src/lib/api/bank-statements.ts` | `bankStatementApi.deleteTransaction(statementId, transactionId)` |
| Backend endpoint | `api/commercial/ai_bank_statement/routers/transactions.py` | `DELETE /{statement_id}/transactions/{transaction_id}` |
| Duplicate detection service | `api/core/services/transaction_link_service.py` | `find_cross_statement_duplicate_groups()` |
| Duplicate detection API | `api/commercial/ai_bank_statement/routers/transactions.py` | `GET /statements/transactions/duplicates` |

### Key Design Decisions

- **No new backend endpoints** — reuses the existing single-transaction delete endpoint, called in a loop for each duplicate to remove.
- **Cache invalidation** — the `['duplicate-transactions']` TanStack Query cache key is invalidated on success so the panel updates without a page reload.
- **Two-step confirmation** — prevents accidental bulk deletion; the confirm screen names every transaction being deleted.
- **Feature-gated** — the panel only renders when the `ai_bank_statement` feature flag is enabled.

## Development History

- **Branch:** `feat/duplicate-transaction-review-delete`
- **Base branch:** `fix/upload-modal-buttons-clipped`
- **Date:** 2026-04-12
- **Scope:** Frontend-only change (`DuplicateTransactionPanel.tsx`); no schema or API changes required.
