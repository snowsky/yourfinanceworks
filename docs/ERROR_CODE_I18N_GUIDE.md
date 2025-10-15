# Frontend Error Code i18n Guide

## Overview

This project uses backend error codes (not user-facing English strings) for all API error responses. The frontend maps these codes to localized, user-friendly messages using the i18n system. This enables full internationalization (i18n) and a consistent user experience across all languages.

---

## How It Works

- The backend returns error codes in the `detail` field of error responses (see `api/constants/error_codes.py`).
- The frontend uses the `getErrorMessage(error, t)` helper to map these codes to localized messages using your translation files (`en.json`, `es.json`, `fr.json`, etc.).
- All error toasts and displays should use this helper for backend errors.

---

## Usage Example

**1. Import the helper and useTranslation:**
```js
import { getErrorMessage } from '@/lib/api';
import { useTranslation } from 'react-i18next';
```

**2. Use in error handling:**
```js
const { t } = useTranslation();
try {
  // ... API call
} catch (error) {
  toast.error(getErrorMessage(error, t));
}
```

---

## How to Add or Update Error Codes

1. **Add the error code to the backend** in `api/constants/error_codes.py` and use it in your backend logic.
2. **Add a translation** for the code in each i18n file (e.g., `en.json`, `es.json`, `fr.json`) under the `errors` section:
   ```json
   "errors": {
     "NEW_ERROR_CODE": "Your custom error message here."
   }
   ```
3. **Use `getErrorMessage(error, t)`** in your frontend error handling to display the localized message.

---

## Best Practices

- **Always use error codes for backend errors.** Never display raw backend strings to users.
- **Fallback:** If a code is not found in the i18n file, `getErrorMessage` will show the code or a generic error.
- **Custom UI errors:** For purely frontend errors (e.g., form validation), continue to use your existing i18n keys.
- **Keep translations in sync:** Whenever you add a new error code, update all language files.

---

## Benefits
- **Consistent, localized error messages for all users.**
- **Easy to add new languages or update error messages.**
- **Backend and frontend are decoupled for error handling.**

---

For more details, see the backend doc: `api/docs/BACKEND_ERROR_CODES_I18N.md`. 