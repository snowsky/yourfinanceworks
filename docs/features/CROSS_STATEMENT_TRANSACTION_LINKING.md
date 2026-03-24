# Cross-Statement Transaction Linking

Link transactions across bank statements to track inter-account transfers and foreign exchange conversions with a clear audit trail.

## Overview

When you move money between two accounts — or convert currency between them — the same real-world event shows up as a transaction in each account's statement. Without linking, it looks like an unexplained outflow in one statement and an unexplained inflow in the other.

Cross-statement linking lets you associate those two transactions so the system knows they are two sides of the same event. Once linked, each transaction shows a badge in the Reference column that you can click to jump directly to the matching transaction in the other statement.

## Link Types

| Type | When to use |
|------|-------------|
| **Transfer** | Moving money between two accounts in the same currency (e.g. chequing → savings) |
| **FX Conversion** | Converting currency between accounts (e.g. USD → CAD) |

## How to Link Two Transactions

1. Open **Statements** and expand the statement that contains one side of the transfer.
2. Find the transaction row (debit or credit) that represents the transfer.
3. Click the **Actions** menu (⋯) for that row and choose **Link Transfer**.
4. **Step 1 — Pick statement**: A searchable list of all other statements appears. Select the statement that holds the matching transaction.
5. **Step 2 — Pick transaction**: The transactions from the selected statement load. For Transfer links, the list is pre-filtered to the complementary type (if your source is a debit, credits are shown first). Select the matching transaction.
6. **Step 3 — Confirm**: Review the two-column summary showing both sides. Choose the link type (Transfer or FX Conversion) and optionally add a note. Click **Link Transfer** to save.

Once saved, both transactions immediately show a badge in the Reference column.

## Reference Column Badges

| Badge | Meaning |
|-------|---------|
| `↔ TRF #N` | Linked as a Transfer; N is the ID of the paired transaction |
| `↔ FX #N` | Linked as an FX Conversion |

Clicking the badge opens the paired statement and highlights the linked transaction row in blue for 3 seconds so it is easy to spot.

## How to Unlink

1. Find either transaction that has a TRF or FX badge.
2. Click the **Actions** menu (⋯) and choose **Unlink Transfer**.
3. Confirm the prompt. The link is removed from both sides simultaneously.

## Notes and Constraints

- **One link per transaction.** Each transaction can only be linked to one other transaction. The "Link Transfer" action is disabled if the transaction is already linked.
- **Both transactions must belong to the same tenant.** You cannot link across organizations.
- **Links cascade on deletion.** If either linked transaction is deleted (or the statement is re-imported, which replaces all transactions), the link is automatically removed from both sides. Finalize your transaction data before creating links.
- **Re-importing a statement removes all existing links** for that statement's transactions because re-import replaces all transaction records with new ones.

## API Endpoints

For integrations and the REST Tools API:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/statements/transactions/links` | Create a link between two transactions |
| `DELETE` | `/statements/transactions/links/{link_id}` | Remove a link |

### Create Link — Request Body

```json
{
  "transaction_a_id": 101,
  "transaction_b_id": 205,
  "link_type": "transfer",
  "notes": "Monthly savings transfer"
}
```

The pair is normalized internally (`a_id = min, b_id = max`) so submitting the IDs in either order produces the same result and duplicate links are rejected with `409 Conflict`.

### Transaction Response — Linked Transfer Field

When fetching a statement (`GET /statements/{id}`), each transaction includes:

```json
{
  "id": 101,
  "date": "2025-06-15",
  "description": "TFR TO SAVINGS",
  "amount": 1500.00,
  "transaction_type": "debit",
  "linked_transfer": {
    "id": 42,
    "link_type": "transfer",
    "notes": "Monthly savings transfer",
    "linked_transaction_id": 205,
    "linked_statement_id": 8,
    "linked_statement_filename": "Savings_June_2025.pdf",
    "created_at": "2025-06-20T10:30:00Z"
  }
}
```

`linked_transfer` is `null` when no link exists.
