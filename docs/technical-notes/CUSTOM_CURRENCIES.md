# Custom Currencies Feature

This feature allows users to add their own custom currencies, including cryptocurrencies like Bitcoin and Ethereum, to the invoice application.

## Features

- **Add Custom Currencies**: Users can create new currencies with custom codes, names, symbols, and decimal places
- **Edit Currencies**: Modify existing custom currencies
- **Activate/Deactivate**: Toggle currencies on/off without deleting them
- **Delete Currencies**: Remove currencies (only if not used in invoices or payments)
- **Automatic Display**: Custom currencies are automatically used in currency selectors and displays

## How to Use

### Adding Custom Currencies

1. Navigate to **Settings** → **Currencies** tab
2. Click **"Add Currency"** button
3. Fill in the required information:
   - **Currency Code**: 3-letter code (e.g., BTC, ETH)
   - **Currency Name**: Full name (e.g., Bitcoin, Ethereum)
   - **Symbol**: Currency symbol (e.g., ₿, Ξ)
   - **Decimal Places**: Number of decimal places (e.g., 8 for Bitcoin, 18 for Ethereum)
   - **Active**: Toggle to enable/disable the currency
4. Click **"Create"** to save

### Managing Currencies

- **Edit**: Click the edit icon to modify currency details
- **Toggle Active**: Use the switch to enable/disable currencies
- **Delete**: Click the trash icon to remove currencies (only if not in use)

## Example Custom Currencies

The system comes with four pre-configured cryptocurrencies:

| Code | Name | Symbol | Decimal Places |
|------|------|--------|----------------|
| BTC | Bitcoin | ₿ | 8 |
| ETH | Ethereum | Ξ | 18 |
| XRP | Ripple | XRP | 6 |
| SOL | Solana | ◎ | 9 |

## Technical Details

### Database Schema

Custom currencies are stored in the `supported_currencies` table:

```sql
CREATE TABLE supported_currencies (
    id INTEGER PRIMARY KEY,
    code VARCHAR UNIQUE NOT NULL,
    name VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    decimal_places INTEGER DEFAULT 2,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints

- `GET /currency/supported` - Get all supported currencies
- `POST /currency/custom` - Create a new custom currency
- `PUT /currency/custom/{id}` - Update a custom currency
- `DELETE /currency/custom/{id}` - Delete a custom currency

### Frontend Components

- `CurrencyManager` - Main component for managing currencies in settings
- `CurrencyDisplay` - Updated to show custom currency symbols
- `CurrencySelector` - Updated to include custom currencies in dropdowns

## Setup Instructions

### 1. Run Database Migration

If you haven't already, run the currency support migration:

```bash
cd api
python scripts/add_currency_support.py
```

### 2. Add Example Currencies

Run the script to add example cryptocurrencies:

```bash
cd api
python scripts/add_custom_currencies.py
```

### 3. Restart the Application

Restart both the API and frontend to ensure all changes are loaded.

## Usage Examples

### Creating a Bitcoin Invoice

1. Go to **Invoices** → **New Invoice**
2. Select **BTC** from the currency dropdown
3. Enter amount (e.g., 0.001 BTC)
4. The invoice will display as "₿0.00100000"

### Creating an Ethereum Invoice

1. Go to **Invoices** → **New Invoice**
2. Select **ETH** from the currency dropdown
3. Enter amount (e.g., 0.5 ETH)
4. The invoice will display as "Ξ0.500000000000000000"

### Creating a Solana Invoice

1. Go to **Invoices** → **New Invoice**
2. Select **SOL** from the currency dropdown
3. Enter amount (e.g., 1.5 SOL)
4. The invoice will display as "◎1.500000000"

## Best Practices

1. **Currency Codes**: Use standard 3-letter codes when possible
2. **Symbols**: Use Unicode symbols for better display
3. **Decimal Places**: Set appropriate decimal places for the currency
4. **Testing**: Test currency display before using in production
5. **Backup**: Keep backups of custom currency configurations

## Troubleshooting

### Currency Not Displaying

- Check if the currency is marked as "Active"
- Verify the currency code is correct
- Check browser console for any errors

### Cannot Delete Currency

- Ensure the currency is not used in any invoices or payments
- Check if there are any pending transactions

### Symbol Not Showing

- Verify the symbol is a valid Unicode character
- Check if the font supports the symbol
- Try using a different symbol if needed

## Future Enhancements

- Exchange rate integration for custom currencies
- Bulk currency import/export
- Currency conversion features
- Historical exchange rate tracking
- Integration with cryptocurrency APIs 