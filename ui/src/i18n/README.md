# Multi-Language Support Guide

This guide explains how to use the internationalization (i18n) system in the invoice app.

## Overview

The app supports 3 languages:
- **English (en)** - Default language
- **Spanish (es)** - Español
- **French (fr)** - Français  

## How It Works

### 1. Language Detection
The app automatically detects the user's preferred language from:
- Browser language settings
- Previously selected language (stored in localStorage)
- Falls back to English if no preference is found

### 2. Language Switching
Users can change the language using the language switcher in the sidebar:
- Click the globe icon in the sidebar footer
- Select from the dropdown menu
- Language preference is saved and persists across sessions

## Using Translations in Components

### Basic Usage

```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  
  return (
    <div>
      <h1>{t('common.title')}</h1>
      <p>{t('common.description')}</p>
      <button>{t('common.save')}</button>
    </div>
  );
}
```

### With Variables

```tsx
const { t } = useTranslation();

// Simple variable
<p>{t('welcome.message', { name: userName })}</p>

// Multiple variables
<p>{t('invoice.total', { amount: 100, currency: 'USD' })}</p>
```

### Pluralization

```tsx
// English: "1 invoice" vs "2 invoices"
<p>{t('invoices.count', { count: invoiceCount })}</p>
```

## Translation File Structure

Translation files are located in `ui/src/i18n/locales/`:

```
locales/
├── en.json    # English (default)
├── es.json    # Spanish
└── fr.json    # French
```

### Translation Keys

Keys are organized hierarchically:

```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete"
  },
  "navigation": {
    "dashboard": "Dashboard",
    "invoices": "Invoices"
  },
  "invoices": {
    "title": "Invoices",
    "new_invoice": "New Invoice",
    "status": {
      "draft": "Draft",
      "paid": "Paid"
    }
  }
}
```

## Available Translation Keys

### Common Actions
- `common.save` - Save button
- `common.cancel` - Cancel button
- `common.delete` - Delete button
- `common.edit` - Edit button
- `common.add` - Add button
- `common.search` - Search placeholder
- `common.loading` - Loading text

### Navigation
- `navigation.dashboard` - Dashboard menu
- `navigation.invoices` - Invoices menu
- `navigation.expenses` - Expenses menu
- `navigation.bank_statements` - Bank Statements menu
- `navigation.clients` - Clients menu
- `navigation.payments` - Payments menu
- `navigation.settings` - Settings menu
- `navigation.users` - Users menu
- `navigation.super_admin` - Super Admin menu
- `navigation.audit_log` - Audit Log menu
- `navigation.analytics` - Analytics menu

### Authentication
- `auth.login` - Login button
- `auth.signup` - Sign up button
- `auth.logout` - Logout button
- `auth.email` - Email field
- `auth.password` - Password field

### Invoices
- `invoices.title` - Invoices page title
- `invoices.new_invoice` - New invoice button
- `invoices.invoice_number` - Invoice number field
- `invoices.status.draft` - Draft status
- `invoices.status.paid` - Paid status
- `invoices.status.overdue` - Overdue status

### Clients
- `clients.title` - Clients page title
- `clients.new_client` - New client button
- `clients.client_name` - Client name field
- `clients.client_email` - Client email field

### Payments
- `payments.title` - Payments page title
- `payments.payment_method` - Payment method field
- `payments.payment_methods.cash` - Cash payment
- `payments.payment_methods.credit_card` - Credit card payment

### Settings
- `settings.title` - Settings page title
- `settings.company_info` - Company information section
- `settings.company_name` - Company name field

### Currencies
- `currency.USD` - US Dollar
- `currency.EUR` - Euro
- `currency.GBP` - British Pound
- `currency.CNY` - Chinese Yuan
- And 100+ more currencies...

## Adding New Translations

### 1. Add the key to all language files

**English (en.json):**
```json
{
  "new_section": {
    "new_key": "English text"
  }
}
```

**Spanish (es.json):**
```json
{
  "new_section": {
    "new_key": "Texto en español"
  }
}
```

**French (fr.json):**
```json
{
  "new_section": {
    "new_key": "Texte en français"
  }
}
```



### 2. Use in your component

```tsx
const { t } = useTranslation();
return <div>{t('new_section.new_key')}</div>;
```

## Best Practices

### 1. Use Descriptive Keys
```json
// Good
"invoices.status.overdue": "Overdue"

// Avoid
"status1": "Overdue"
```

### 2. Group Related Keys
```json
{
  "invoices": {
    "title": "Invoices",
    "new": "New Invoice",
    "edit": "Edit Invoice",
    "delete": "Delete Invoice"
  }
}
```

### 3. Use Variables for Dynamic Content
```tsx
// Instead of concatenating strings
<p>Invoice #{invoiceNumber} for {clientName}</p>

// Use translation with variables
<p>{t('invoices.details', { 
  number: invoiceNumber, 
  client: clientName 
})}</p>
```

### 4. Handle Missing Translations
```tsx
// The t() function will show the key if translation is missing
// You can also provide a fallback
const text = t('some.key', { defaultValue: 'Fallback text' });
```

## Testing Translations

### 1. Switch Languages
- Use the language switcher in the sidebar
- Test all supported languages
- Verify text doesn't overflow or break layout

### 2. Check for Missing Keys
- Look for keys displayed as-is (e.g., "common.missing_key")
- Add missing translations to all language files

### 3. Test Dynamic Content
- Verify variables are properly substituted
- Check pluralization works correctly
- Test with different data types

## Troubleshooting

### Translation Not Working
1. Check if the key exists in all language files
2. Verify the key path is correct
3. Make sure `useTranslation()` is imported and used
4. Check browser console for errors

### Language Not Switching
1. Verify the language switcher is working
2. Check localStorage for saved language preference
3. Refresh the page after switching languages

### Missing Translations
1. Add the missing key to all language files
2. Use consistent naming conventions
3. Test with all supported languages

## Advanced Features

### Interpolation
```tsx
// Translation: "Hello {{name}}, you have {{count}} messages"
<p>{t('welcome.message', { name: 'John', count: 5 })}</p>
```

### Pluralization
```tsx
// Translation: "1 message" vs "{{count}} messages"
<p>{t('messages.count', { count: messageCount })}</p>
```

### Context
```tsx
// Different translations based on context
<p>{t('common.save', { context: 'invoice' })}</p>
```

## Performance Tips

1. **Lazy Loading**: Only load translations when needed
2. **Caching**: Translations are cached in localStorage
3. **Bundle Size**: Consider code-splitting for large translation files
4. **Tree Shaking**: Remove unused translation keys

## Future Enhancements

- Add more languages (German, Italian, Japanese, etc.)
- Implement RTL (Right-to-Left) language support
- Add translation management interface
- Support for custom user translations
- Automatic translation suggestions 