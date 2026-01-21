# License Status 401 Error and UI Refresh Loop Fix

## Problem

The UI was experiencing a continuous refresh loop with 401 Unauthorized errors on the `/api/v1/license/status` endpoint. This was causing the application to be unusable.

### Root Cause

The `FeatureContext` component was attempting to fetch license status immediately on mount, even before the user was authenticated. The sequence was:

1. App loads and `FeatureProvider` wraps the entire application
2. `FeatureContext` immediately calls `/license/status` endpoint
3. Endpoint requires authentication (`get_current_user` dependency)
4. API returns 401 Unauthorized
5. `apiRequest` error handler clears localStorage and redirects to `/login`
6. Login page loads, which is also wrapped by `FeatureProvider`
7. Process repeats, creating an infinite loop

## Solution

### 1. Check Authentication Before API Call

Modified `FeatureContext.tsx` to check for authentication token before making the API request:

```typescript
const fetchFeatures = async () => {
  try {
    setLoading(true);
    setError(null);
    
    // Check if user is authenticated before making the API call
    const token = localStorage.getItem('token');
    if (!token) {
      // User not authenticated - use safe defaults
      setFeatures({ /* all features disabled */ });
      setLicenseStatus(null);
      setLoading(false);
      return;
    }
    
    // Proceed with API call only if authenticated
    const response = await api.get('/license/status');
    // ...
  }
}
```

### 2. Dispatch Auth Change Events

Added custom event dispatching to notify `FeatureContext` when authentication state changes:

**Login/Signup/OAuth:**
```typescript
localStorage.setItem('token', token);
localStorage.setItem('user', JSON.stringify(user));
// Dispatch custom event to notify FeatureContext
window.dispatchEvent(new Event('auth-changed'));
```

**Logout:**
```typescript
localStorage.removeItem('token');
localStorage.removeItem('user');
// Dispatch custom event to notify FeatureContext
window.dispatchEvent(new Event('auth-changed'));
```

### 3. Listen for Auth Changes

Updated `FeatureContext` to listen for authentication changes:

```typescript
useEffect(() => {
  fetchFeatures();
  
  // Listen for storage events (e.g., when token is set in another tab)
  const handleStorageChange = (e: StorageEvent) => {
    if (e.key === 'token') {
      fetchFeatures();
    }
  };
  
  // Listen for custom auth-changed event
  const handleAuthChange = () => {
    fetchFeatures();
  };
  
  window.addEventListener('storage', handleStorageChange);
  window.addEventListener('auth-changed', handleAuthChange);
  
  return () => {
    window.removeEventListener('storage', handleStorageChange);
    window.removeEventListener('auth-changed', handleAuthChange);
  };
}, []);
```

### 4. Prevent Redirect Loop

Added safeguard in `apiRequest` to prevent redirecting to login if already on login page:

```typescript
if (!config.isLogin && response.status === 401) {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem('selected_tenant_id');
  // Show toast and redirect to login only if not already on login page
  if (!window.location.pathname.includes('/login')) {
    toast.error('Session expired. Please log in again.');
    setTimeout(() => window.location.replace('/login'), 100);
  }
  throw new Error('Authentication failed. Please log in again.');
}
```

## Files Modified

1. `ui/src/contexts/FeatureContext.tsx` - Added token check and event listeners
2. `ui/src/pages/Login.tsx` - Dispatch auth-changed event after login
3. `ui/src/pages/Signup.tsx` - Dispatch auth-changed event after signup
4. `ui/src/pages/OAuthCallback.tsx` - Dispatch auth-changed event after OAuth
5. `ui/src/utils/auth.ts` - Dispatch auth-changed event on logout
6. `ui/src/components/layout/AppSidebar.tsx` - Dispatch auth-changed event on logout
7. `ui/src/components/layout/ProfessionalSidebar.tsx` - Dispatch auth-changed event on logout
8. `ui/src/hooks/useAuth.ts` - Dispatch auth-changed event on logout
9. `ui/src/lib/api.ts` - Prevent redirect loop on login page

## Testing

To verify the fix:

1. **Initial Load (Not Authenticated):**
   - Open the app in a new browser/incognito window
   - Should load login page without errors or refresh loops
   - No 401 errors in console

2. **After Login:**
   - Login with valid credentials
   - Should redirect to dashboard
   - License status should be fetched successfully
   - Features should be loaded correctly

3. **After Logout:**
   - Click logout
   - Should redirect to login page
   - Features should reset to defaults
   - No errors in console

4. **Session Expiry:**
   - Let token expire or manually delete it
   - Make an API request
   - Should redirect to login once (not loop)
   - Should show "Session expired" message

## Benefits

1. **No More Refresh Loop:** App loads correctly even when not authenticated
2. **Better UX:** No unnecessary API calls before authentication
3. **Proper State Management:** Features are properly reset on logout
4. **Cross-Tab Support:** Storage events ensure consistency across tabs
5. **Graceful Degradation:** Safe defaults when authentication is not available

## Future Improvements

Consider these enhancements:

1. Use React Context or state management library for auth state instead of localStorage events
2. Implement a proper auth state machine
3. Add retry logic for transient network errors
4. Cache license status with TTL to reduce API calls
