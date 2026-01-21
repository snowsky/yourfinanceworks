## Expense labels

Labels allow categorizing expenses with one or more short tags.

### Data model

- Legacy single label: `Expense.label` (string, nullable)
- New multi-labels: `Expense.labels` (JSON array of strings, nullable)

Migration backfills `labels` from `label` when present.

### Validation rules

- Maximum of 10 labels per expense
- Each label must be a non-empty string after trimming
- Duplicates are removed (case-sensitive)

### API behavior

- Create/Update accepts either `label` or `labels`
- Server normalizes `labels` according to the rules above
- Filtering `GET /expenses?label=foo` matches legacy `label` via ILIKE and also matches within `labels` array

### UI

- Current UI edits a single `label` inline. Multi-label UI can be introduced later to manage the `labels` array explicitly.


