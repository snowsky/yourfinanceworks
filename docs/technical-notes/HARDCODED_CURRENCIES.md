# Hardcoded Currencies (Default Seed)

This app seeds a minimal set of currencies on first run for convenience. These are used by validation and UI selectors unless you add more via admin tools.

## Default seeded set

Code | Name              | Symbol | Decimals
---- | ----------------- | ------ | --------
USD  | US Dollar         | $      | 2
EUR  | Euro              | €      | 2
GBP  | British Pound     | £      | 2
CAD  | Canadian Dollar   | C$     | 2
AUD  | Australian Dollar | A$     | 2
JPY  | Japanese Yen      | ¥      | 0
CHF  | Swiss Franc       | CHF    | 2
CNY  | Chinese Yuan      | ¥      | 2
INR  | Indian Rupee      | ₹      | 2
BRL  | Brazilian Real    | R$     | 2

Source: initial seed in `api/db_init.py` (`SupportedCurrency`).

## Where currencies are validated/used
- Backend validation: `api/services/currency_service.py`
- API router: `api/routers/currency.py`
- Frontend selector: `ui/src/components/ui/currency-selector.tsx`

## How to add/edit currencies
- Preferred: Use the Currency API endpoints (create/update) exposed by `currency.py`.
- Alternatively: Extend the seed list in `api/db_init.py` for new deployments.
- Ensure `decimal_places` matches real-world usage (e.g., JPY uses 0 decimals).

## Notes
- Tenants can operate in multiple currencies; these entries govern formatting and validation only.
- UI may cache the list; refresh/reload after changes.
