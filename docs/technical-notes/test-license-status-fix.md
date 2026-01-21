# Test Plan: License Status 401 Fix

## Test Scenarios

### Scenario 1: Initial Load (Not Authenticated)
**Steps:**
1. Clear browser cache and localStorage
2. Open the application in a new browser/incognito window
3. Observe the network tab and console

**Expected Results:**
- ✅ Login page loads without errors
- ✅ No 401 errors in console
- ✅ No infinite refresh loop
- ✅ No calls to `/api/v1/license/status` endpoint
- ✅ FeatureContext uses safe defaults (all features disabled)

### Scenario 2: Successful Login
**Steps:**
1. Start from unauthenticated state
2. Enter valid credentials and click login
3. Observe the network tab and console

**Expected Results:**
- ✅ Login succeeds and redirects to dashboard
- ✅ `auth-changed` event is dispatched
- ✅ `/api/v1/license/status` is called AFTER authentication
- ✅ License status is fetched successfully (200 OK)
- ✅ Features are loaded correctly based on license
- ✅ No 401 errors

### Scenario 3: Logout
**Steps:**
1. Start from authenticated state (logged in)
2. Click logout button
3. Observe the network tab and console

**Expected Results:**
- ✅ Logout succeeds and redirects to login page
- ✅ `auth-changed` event is dispatched
- ✅ localStorage is cleared (token, user, selected_tenant_id)
- ✅ Features reset to safe defaults
- ✅ No API calls to `/api/v1/license/status`
- ✅ No errors in console

### Scenario 4: Session Expiry (Token Invalid)
**Steps:**
1. Start from authenticated state
2. Manually delete or corrupt the token in localStorage
3. Navigate to a protected page or make an API request
4. Observe the behavior

**Expected Results:**
- ✅ API returns 401 Unauthorized
- ✅ User is redirected to login page (only once)
- ✅ Toast message: "Session expired. Please log in again."
- ✅ localStorage is cleared
- ✅ No infinite redirect loop
- ✅ Features reset to safe defaults

### Scenario 5: Page Refresh (Authenticated)
**Steps:**
1. Login successfully
2. Navigate to dashboard
3. Refresh the page (F5 or Ctrl+R)
4. Observe the network tab

**Expected Results:**
- ✅ Page reloads successfully
- ✅ Token is still in localStorage
- ✅ `/api/v1/license/status` is called with valid token
- ✅ License status is fetched successfully
- ✅ Features are loaded correctly
- ✅ User remains authenticated

### Scenario 6: Cross-Tab Authentication
**Steps:**
1. Open app in Tab 1 (not authenticated)
2. Open app in Tab 2 (not authenticated)
3. Login in Tab 1
4. Observe Tab 2

**Expected Results:**
- ✅ Tab 2 detects storage change event
- ✅ Tab 2 refetches license status
- ✅ Tab 2 updates features
- ✅ Both tabs show consistent state

### Scenario 7: OAuth Login
**Steps:**
1. Start from unauthenticated state
2. Click "Login with Google" or "Login with Microsoft"
3. Complete OAuth flow
4. Observe the callback and redirect

**Expected Results:**
- ✅ OAuth callback processes successfully
- ✅ Token is stored in localStorage
- ✅ `auth-changed` event is dispatched
- ✅ User is redirected to dashboard
- ✅ `/api/v1/license/status` is called AFTER authentication
- ✅ Features are loaded correctly

### Scenario 8: Signup
**Steps:**
1. Start from unauthenticated state
2. Navigate to signup page
3. Complete signup form
4. Submit

**Expected Results:**
- ✅ Signup succeeds
- ✅ Token is stored in localStorage
- ✅ `auth-changed` event is dispatched
- ✅ User is redirected to dashboard
- ✅ `/api/v1/license/status` is called AFTER authentication
- ✅ Features are loaded correctly

## Console Checks

### Before Fix (Expected Issues)
```
❌ GET /api/v1/license/status 401 Unauthorized
❌ Session expired. Please log in again.
❌ [Infinite loop of above messages]
```

### After Fix (Expected Behavior)
```
✅ FeatureContext: No token found, using safe defaults
✅ [After login] GET /api/v1/license/status 200 OK
✅ FeatureContext: License status loaded successfully
```

## Network Tab Checks

### Unauthenticated State
- Should see NO requests to `/api/v1/license/status`

### After Login
- Should see ONE successful request to `/api/v1/license/status` with 200 OK
- Request should include `Authorization: Bearer <token>` header
- Request should include `X-Tenant-ID` header

### After Logout
- Should see NO requests to `/api/v1/license/status`

## Automated Test Commands

```bash
# Run UI tests (if available)
cd ui
npm test

# Run E2E tests (if available)
npm run test:e2e

# Check for TypeScript errors
npm run type-check

# Build to verify no compilation errors
npm run build
```

## Manual Testing Checklist

- [ ] Initial load without authentication
- [ ] Login with email/password
- [ ] Login with Google OAuth
- [ ] Login with Microsoft OAuth
- [ ] Signup new account
- [ ] Logout
- [ ] Session expiry (delete token)
- [ ] Page refresh while authenticated
- [ ] Cross-tab authentication
- [ ] Network errors (offline mode)

## Success Criteria

All test scenarios pass with:
- ✅ No 401 errors on unauthenticated pages
- ✅ No infinite redirect loops
- ✅ No infinite refresh loops
- ✅ Proper feature loading after authentication
- ✅ Proper feature reset after logout
- ✅ Consistent behavior across all authentication methods
