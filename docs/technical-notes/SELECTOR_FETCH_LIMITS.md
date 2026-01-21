## UI selector fetch limits

This document tracks hardcoded fetch limits used by UI selectors to avoid loading an excessive number of records while ensuring a smooth UX.

### Invoices selector on Expenses pages

- Location: `ui/src/lib/api.ts` → `linkApi.getInvoicesBasic`
- Current limit: 1000
- Rationale: Provide a large-enough list for typical tenants so “Link to Invoice” selectors are populated, without requiring additional pagination UI. Backed by the paginated `GET /invoices` endpoint using `skip`/`limit`.
- How to change: Update the `limit` passed to `invoiceApi.getInvoicesWithParams({ limit: 1000 })` and adjust this doc.

### Future improvements

- Replace hardcoded limits with server-provided counts and client-side lazy loading (typeahead) for very large datasets.
- Add a shared config for selector limits if multiple selectors require similar treatment.


