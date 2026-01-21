# Backend Error Codes & i18n Integration

## Overview

This project now uses **error codes/keys** (not user-facing English strings) in all backend `HTTPException.detail` fields. This enables full internationalization (i18n) of error messages in the frontend, so users see errors in their preferred language.

---

## Why Use Error Codes?

- **Separation of concerns:** Backend is responsible for logic, not user-facing text.
- **i18n support:** UI can display localized error messages based on the user's language.
- **Consistency:** All errors are handled in a uniform way across the stack.
- **Maintainability:** Easy to update error messages or add new languages without backend changes.

---

## How It Works

### 1. Backend
- All `raise HTTPException(..., detail=...)` now use a code/key (e.g., `USER_NOT_FOUND`, `INCORRECT_PASSWORD`, `TENANT_CONTEXT_REQUIRED`).
- All codes are defined in `api/constants/error_codes.py`.
- Example:
  ```python
  from constants.error_codes import USER_NOT_FOUND
  raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
  ```

### 2. Frontend
- The UI receives the error code in the `detail` field of the error response.
- The UI maps this code to a localized message using its i18n system (e.g., `t('errors.USER_NOT_FOUND')`).
- Example mapping in a translation file:
  ```json
  "errors": {
    "USER_NOT_FOUND": "User does not exist. Please sign up first.",
    "INCORRECT_PASSWORD": "Incorrect password.",
    "TENANT_CONTEXT_REQUIRED": "Tenant context required. Please log in again."
  }
  ```

---

## How to Add or Update Error Codes

1. **Add a new code** to `api/constants/error_codes.py`:
   ```python
   NEW_ERROR_CODE = "NEW_ERROR_CODE"
   ```
2. **Use the code** in your backend logic:
   ```python
   raise HTTPException(status_code=400, detail=NEW_ERROR_CODE)
   ```
3. **Add translations** for the code in your frontend i18n files (e.g., `en.json`, `es.json`, etc.):
   ```json
   "errors": {
     "NEW_ERROR_CODE": "Your custom error message here."
   }
   ```

---

## Example: Full Flow

**Backend:**
```python
from constants.error_codes import CLIENT_ALREADY_EXISTS
raise HTTPException(status_code=400, detail=CLIENT_ALREADY_EXISTS)
```

**Frontend (React, using i18n):**
```js
// error.response.data.detail === 'CLIENT_ALREADY_EXISTS'
const errorMsg = t(`errors.${error.response.data.detail}`);
toast.error(errorMsg);
```

**Translation file (en.json):**
```json
"errors": {
  "CLIENT_ALREADY_EXISTS": "A client with this name and email already exists."
}
```

---

## Migration Notes
- All major backend endpoints and utilities now use error codes.
- If you see a user-facing English string in an error response, refactor it to use a code from `error_codes.py`.
- The UI must be updated to map all codes to user-friendly, localized messages.

---

## Benefits
- **Users see errors in their language**
- **Backend and frontend are decoupled**
- **Easy to add new languages or update error messages**

---

For questions or to add new codes, see `api/constants/error_codes.py` or contact the backend maintainers. 