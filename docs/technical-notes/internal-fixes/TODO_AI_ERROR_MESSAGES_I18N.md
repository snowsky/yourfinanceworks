# TODO: AI Configuration Error Messages Internationalization

## Overview
Currently, AI configuration error messages returned from the backend are hardcoded in English and not internationalized. This creates inconsistency in the user experience when the frontend is localized to other languages.

## Current Issues

### 1. Backend Error Messages (Hardcoded English)
**Location:** `api/routers/ai_config.py` - `_extract_meaningful_error()` function

**Current hardcoded messages:**
```python
# Add helpful suggestions for common errors
if "not found" in extracted.lower() and "model" in extracted.lower():
    extracted += ". Please check if the model is available in your Ollama installation."
elif "connection refused" in extracted.lower():
    extracted += ". Please check if the service is running and accessible."
elif "incorrect api key" in extracted.lower():
    extracted += ". Please verify your API key is correct."
```

**Other hardcoded messages:**
- `"Configuration test successful"`
- `"Configuration test failed: {error_message}"`
- `"AI configuration deleted successfully"`
- `"AI configuration marked as tested successfully"`

### 2. Error Message Categories Needing I18N

#### AI Configuration Test Errors
- Model not found errors
- Connection refused errors
- Authentication errors
- Rate limit errors
- General API errors

#### Success Messages
- Configuration test successful
- Configuration created/updated/deleted
- Configuration marked as tested

#### Validation Errors
- Missing required fields
- Invalid configuration values
- Provider-specific validation errors

## Proposed Solution

### Phase 1: Backend I18N Infrastructure
1. **Add i18n support to FastAPI backend**
   - Install `python-babel` or similar i18n library
   - Create message catalogs for supported languages
   - Add language detection from request headers

2. **Create error message constants**
   ```python
   # api/constants/error_messages.py
   class AIConfigErrorMessages:
       MODEL_NOT_FOUND = "ai_config.error.model_not_found"
       CONNECTION_REFUSED = "ai_config.error.connection_refused"
       INVALID_API_KEY = "ai_config.error.invalid_api_key"
       TEST_SUCCESSFUL = "ai_config.success.test_successful"
       # ... etc
   ```

3. **Create translation files**
   ```
   api/locales/
   ├── en/
   │   └── messages.po
   ├── de/
   │   └── messages.po
   ├── es/
   │   └── messages.po
   └── fr/
       └── messages.po
   ```

### Phase 2: Refactor Error Handling
1. **Update `_extract_meaningful_error()` function**
   ```python
   def _extract_meaningful_error(error_str: str, locale: str = "en") -> str:
       """Extract meaningful error message and return localized version."""
       # Extract error type
       error_type = _classify_error(error_str)
       
       # Return localized message
       return get_localized_message(error_type, locale)
   ```

2. **Add error classification**
   ```python
   def _classify_error(error_str: str) -> str:
       """Classify error into predefined categories."""
       if "not found" in error_str.lower() and "model" in error_str.lower():
           return AIConfigErrorMessages.MODEL_NOT_FOUND
       elif "connection refused" in error_str.lower():
           return AIConfigErrorMessages.CONNECTION_REFUSED
       # ... etc
   ```

### Phase 3: Frontend Integration
1. **Pass user locale to backend**
   - Add `Accept-Language` header to API requests
   - Update API client to include locale information

2. **Fallback handling**
   - If backend returns non-localized error, frontend can attempt translation
   - Maintain current `getErrorMessage(error, t)` as fallback

### Phase 4: Provider-Specific Messages
1. **Ollama-specific messages**
   - "Model '{model}' not found. Run 'ollama pull {model}' to download it."
   - "Ollama service not running. Start it with 'ollama serve'."

2. **OpenAI/OpenRouter-specific messages**
   - "Invalid API key. Check your API key at {provider_url}."
   - "Rate limit exceeded. Please try again later."

3. **Connection-specific messages**
   - "Cannot connect to {provider}. Check your network connection."
   - "Service timeout. The provider may be experiencing issues."

## Implementation Priority

### High Priority
- [ ] Model not found errors (most common user issue)
- [ ] Connection errors
- [ ] Authentication errors
- [ ] Test success/failure messages

### Medium Priority
- [ ] Configuration CRUD operation messages
- [ ] Validation error messages
- [ ] Provider-specific guidance

### Low Priority
- [ ] Advanced error details
- [ ] Debug information localization

## Files to Modify

### Backend
- `api/routers/ai_config.py` - Main error handling
- `api/schemas/ai_config.py` - Response schemas
- `api/constants/error_messages.py` - New file for message constants
- `api/utils/i18n.py` - New file for i18n utilities
- `api/locales/` - New directory for translation files

### Frontend
- `ui/src/lib/api.ts` - Add locale headers
- `ui/src/pages/Settings.tsx` - Update error handling
- `ui/src/i18n/locales/*.json` - Add fallback translations

## Benefits After Implementation
1. **Consistent UX** - All error messages in user's preferred language
2. **Better User Experience** - Localized, actionable error messages
3. **Maintainability** - Centralized error message management
4. **Extensibility** - Easy to add new languages and error types

## Migration Strategy
1. Implement backend i18n infrastructure
2. Migrate existing hardcoded messages to translation keys
3. Add translation files for supported languages
4. Update frontend to pass locale information
5. Test with different locales
6. Gradual rollout with fallback to English

## Notes
- Consider using the same i18n library/approach as the frontend for consistency
- Ensure error message keys are descriptive and follow naming conventions
- Include context information (provider name, model name) in localized messages
- Test error messages with different locales during development

## Related Issues
- Error messages should be user-friendly and actionable
- Consider adding links to documentation for common issues
- Maintain technical error details in logs while showing user-friendly messages in UI