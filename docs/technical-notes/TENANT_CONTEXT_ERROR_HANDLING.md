# Tenant Context Error Handling Improvements

## Problem
Users were experiencing automatic logout with the error message:
```
"API request failed: Error: Tenant context required for this operation. Please ensure you are sending the correct tenant information."
```

This happened when:
1. User sessions expired (JWT token became invalid)
2. Tenant context was missing from API requests
3. The backend returned a 400 Bad Request instead of a proper authentication error

## Solution

### Backend Changes

#### 1. Updated Error Status Codes (`api/models/database.py`)
- **Before**: Missing tenant context returned `400 Bad Request`
- **After**: Missing tenant context returns `401 Unauthorized`

```python
# Before
raise HTTPException(
    status_code=400,
    detail="Tenant context required for this operation. Please ensure you are sending the correct tenant information."
)

# After  
raise HTTPException(
    status_code=401,
    detail="Tenant context required for this operation. Please ensure you are sending the correct tenant information."
)
```

#### 2. Updated Middleware Error Handling (`api/middleware/tenant_context_middleware.py`)
- **Before**: Tenant ID mismatch returned `403 Forbidden`
- **After**: Tenant ID mismatch returns `401 Unauthorized`

```python
# Before
return JSONResponse(
    status_code=status.HTTP_403_FORBIDDEN,
    content={"detail": "Tenant ID in header does not match authenticated user's tenant."}
)

# After
return JSONResponse(
    status_code=status.HTTP_401_UNAUTHORIZED,
    content={"detail": "Tenant context required for this operation. Please ensure you are sending the correct tenant information."}
)
```

#### 3. Enhanced Logging
Added more detailed logging to help debug tenant context issues:
- Logs user email and tenant ID when there's a mismatch
- Logs additional context about session expiry

### Frontend Changes

#### 1. Web UI (`ui/src/lib/api.ts`)
Enhanced error handling to detect tenant context errors and handle them as session expiry:

```typescript
// Handle 403 (forbidden) errors - could be permission or tenant context issues
if (response.status === 403) {
  // Check if it's a tenant context error
  if (errorData.detail && errorData.detail.includes('Tenant context required')) {
    // This is a session/tenant context issue - log out the user
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    toast.error('Session expired. Please log in again.');
    window.location.replace('/login');
    throw new Error('Session expired. Please log in again.');
  } else {
    // User is authenticated but lacks permissions - don't log out
    throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
  }
}

// Handle 400 errors that might be tenant context issues
if (response.status === 400 && errorData.detail && errorData.detail.includes('Tenant context required')) {
  // This is a session/tenant context issue - log out the user
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  toast.error('Session expired. Please log in again.');
  window.location.replace('/login');
  throw new Error('Session expired. Please log in again.');
}
```

#### 2. Mobile App (`mobile/src/services/api.ts`)
Similar improvements for the React Native mobile app:

```typescript
// Handle authentication errors
if (!config.isLogin && (response.status === 401 || response.status === 403)) {
  // Check if it's a tenant context error
  if (errorData.detail && errorData.detail.includes('Tenant context required')) {
    await this.removeToken();
    await this.removeUser();
    throw new Error('Session expired. Please log in again.');
  } else if (response.status === 401) {
    // 401 Unauthorized - token is invalid/expired
    await this.removeToken();
    await this.removeUser();
    throw new Error('Authentication failed. Please log in again.');
  } else {
    // 403 Forbidden - user lacks permissions
    throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
  }
}

// Handle 400 errors that might be tenant context issues
if (response.status === 400 && errorData.detail && errorData.detail.includes('Tenant context required')) {
  await this.removeToken();
  await this.removeUser();
  throw new Error('Session expired. Please log in again.');
}
```

## Benefits

1. **Consistent Error Handling**: All authentication-related errors now return 401 status codes
2. **Better User Experience**: Users get a clear "Session expired" message instead of technical error details
3. **Automatic Logout**: Users are automatically redirected to the login page when their session expires
4. **Improved Debugging**: Enhanced logging helps identify tenant context issues
5. **Cross-Platform**: Both web and mobile apps handle session expiry consistently

## Testing

A test script has been created at `api/scripts/test_tenant_context_handling.py` to verify that:
- Missing authentication returns 401
- Invalid tokens return 401  
- Missing tenant context returns 401

## Migration Notes

- **No Database Changes**: These are purely code changes, no database migration is required
- **Backward Compatible**: Existing API clients will continue to work, but will now receive 401 instead of 400 for authentication issues
- **Immediate Effect**: Changes take effect immediately after deployment

## Future Improvements

Consider implementing:
1. **Token Refresh**: Automatic token refresh before expiry
2. **Session Monitoring**: Proactive session validation
3. **Graceful Degradation**: Show warning before session expiry
4. **Remember Me**: Longer-lived refresh tokens for better UX 