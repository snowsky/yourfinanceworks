# TODO: Duplicate Detection Unit Tests

Branch: `duplicate-detection-expense-statement`

## Tests to write

### 1. `test_duplicate_detection.py` — `api/tests/`

#### `TestCleanAndDeduplicateTransactions` (pure function, no DB)
- [ ] Empty list returns empty list
- [ ] Single transaction → unchanged
- [ ] Exact duplicates (date + desc + amount) → deduplicated to 1
- [ ] Near-duplicate with differing amount → both kept
- [ ] Near-duplicate with differing description → both kept
- [ ] Near-duplicate with differing date → both kept
- [ ] Amount rounding: `10.001` and `10.00` treated as same key (round to 2dp)
- [ ] Output is sorted by date ascending
- [ ] Preserves extra fields (category, balance, etc.) on survivors

#### `TestFindCrossStatementDuplicateGroups` (mocked DB)
- [ ] No transactions → returns `[]`
- [ ] Transactions all within one statement → not flagged
- [ ] Same (date, desc, amount) across 2 statements → 1 group returned
- [ ] Same (date, desc, amount) across 3 statements → 1 group with 3 entries
- [ ] Different amounts, same date/desc → not flagged
- [ ] Different descriptions, same date/amount → not flagged
- [ ] Description case/whitespace normalization (`"  AMAZON  "` vs `"amazon"`)
- [ ] Already-linked pair (full pair) → group excluded
- [ ] Already-linked pair (partial: 2 linked, 1 unlinked) → group still returned
- [ ] Soft-deleted statement transactions excluded

#### `TestFindPotentialExpenseDuplicates` (mocked DB → `get_potential_expense_duplicates`)
- [ ] No expenses → `[]`
- [ ] Single expense → `[]`
- [ ] Same amount + vendor + date → 1 group
- [ ] Same amount + vendor, dates outside window → not flagged
- [ ] Same amount, different vendor → not flagged (vendor comparison post-decryption)
- [ ] Different amounts, same vendor + date → not flagged
- [ ] `date_window_days` param respected (3 vs 14)
- [ ] Deleted expenses excluded (`is_deleted == True`)

#### `TestFileHashDuplicateDetection` (upload router — integration-style)
- [ ] Uploading same file bytes twice → second response includes `duplicate_of`
- [ ] Uploading different file bytes → `duplicate_of` is `null`
- [ ] Soft-deleted statement with same hash → NOT flagged as duplicate

## Running the tests

```bash
cd api
pytest tests/test_duplicate_detection.py -v
```

Or with coverage:
```bash
pytest tests/test_duplicate_detection.py -v --tb=short --cov=core.services.transaction_link_service --cov=core.services.statement_service
```
