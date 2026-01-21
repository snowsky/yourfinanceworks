## BMO Bank Statement Regex Extraction (Fallback)

This document describes the BMO-specific regex fallback used to extract transactions when the LLM returns no results. The implementation resides in `api/services/statement_service.py` inside `_regex_extract_transactions`.

### Targeted Layout

Typical BMO transaction rows look like:

```
Apr 05 Pre-Authorized Payment No Fee, CANACT BUS/ENT 1,031.22 64,145.83
Apr 05 Direct Deposit, PEERIDEA INC MSP/DIV 431.89 64,577.72
Apr 21 ABM Deposit, 499 TERRY FOX 1,759.56 71,006.07
Apr 28 Plan Fee 6.00 71,669.02
Apr 28 Deposit Contents fee, CHQ 1 @ $0.20 0.20 74,024.63
Apr 28 Transaction Fee, DISCOUNT 02 AT $0.60 1.20 74,023.43
```

Pattern characteristics:
- Date appears as `Mon dd` (e.g., `Apr 05`), sometimes as `YYYY-MM-DD` or `MM/DD/YYYY`.
- Description follows the date.
- Two numeric fields near the end: penultimate is the transaction amount; last is the resulting balance.

### Year Inference

The year is inferred from the statement header if present, e.g., `Apr 28, 2023`. If no header year is detected, the current year is used.

Regex used for header year:
```
(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+(\d{4})
```

### Line Skipping

We ignore header/footer and non-transaction lines using keywords such as:
```
opening balance, closing totals, number of items processed, (we're|were) making changes,
your plan, summary of account, business account #, business name:, transit number,
for the period ending, page, statement period:, account summary
```

### Date Detection (at line start)

Three formats are supported:
```
^([A-Za-z]{3,})\s+(\d{1,2})\b\s+(?<rest>.+)$          # Mon dd ...
^(?<date>\d{4}-\d{2}-\d{2})\s+(?<rest>.+)$            # YYYY-MM-DD ...
^(?<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?<rest>.+)$ # MM/DD/YYYY or MM-DD-YYYY ...
```

For `Mon dd` format, the month string is mapped to a numeric month and combined with the inferred year to form `YYYY-MM-DD`.

### Amount and Balance Parsing

We search for currency-like numbers within the remainder of the line:
```
amount_pattern = -?\$?\d[\d,]*\.\d{2}
```

- The last match is treated as the balance.
- The penultimate match is treated as the transaction amount.
- The description is the substring before the penultimate number (trimmed and whitespace-normalized).

### Debit/Credit Inference

Rules:
- If the parsed amount has a leading `-`, it is a debit.
- Otherwise, use keyword heuristics on the description:
  - Debit keywords: `payment`, `fee`, `withdrawal`, `bill`, `purchase`, `transfer out`, `pos `
  - Credit keywords: `deposit`, `direct deposit`, `refund`, `transfer in`, `credit`
- If no heuristic matches, non-negative amounts default to credit.
- Final stored `amount` is negative for debits and positive for credits.

### Output Fields

Each extracted transaction has:
```
{
  "date": YYYY-MM-DD,
  "description": string,
  "amount": number,          # signed; negative for debit
  "transaction_type": "debit" | "credit",
  "balance": number | null
}
```

### Limitations

- Assumes the penultimate numeric token is the transaction amount and the last one is the balance.
- Requires two numeric tokens to be present; rows with only one numeric field are skipped.
- Year inference depends on a detectable header; otherwise the current year is used.

### Implementation Reference

See `api/services/statement_service.py`, function `_regex_extract_transactions` for the latest implementation.


