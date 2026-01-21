# Azure AD SSO Testing Guide

## Quick Setup for Testing

### Step 1: Create Azure AD Test Application

1. **Go to Azure Portal** (https://portal.azure.com)
2. **Navigate to**: Azure Active Directory → App registrations → New registration
3. **Fill in**:
   - Name: `Invoice App Test`
   - Supported account types: `Accounts in any organizational directory (Any Azure AD directory - Multitenant)`
   - Redirect URI: `http://localhost:8080/api/v1/auth/azure/callback`

4. **After creation, note down**:
   - Application (client) ID
   - Directory (tenant) ID

### Step 2: Configure Authentication

1. **Go to**: Authentication → Platform configurations → Add a platform → Web
2. **Add redirect URIs**:
   ```
   http://localhost:8080/api/v1/auth/azure/callback
   http://localhost:3000/api/v1/auth/azure/callback
   ```
3. **Enable**: ID tokens (used for implicit and hybrid flows)

### Step 3: Create Client Secret

1. **Go to**: Certificates & secrets → New client secret
2. **Description**: `Test Secret`
3. **Expires**: 6 months
4. **Copy the Value** (shown only once!)

### Step 4: Set API Permissions

1. **Go to**: API permissions → Add a permission → Microsoft Graph → Delegated permissions
2. **Add these permissions**:
   - `openid`
   - `email` 
   - `profile`
3. **Click**: Grant admin consent (if you're admin)

## Environment Configuration

Create a `.env.local` file in your project root:

```bash
# Azure AD Test Configuration
AZURE_CLIENT_ID=your-application-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
AZURE_TENANT_ID=common
UI_BASE_URL=http://localhost:8080
```

## Testing Scenarios

### ✅ Test 1: Basic Authentication Flow
**Goal**: Verify the complete OAuth flow works

**Steps**:
1. Start your application
2. Navigate to login page
3. Click "Sign in with Microsoft"
4. Should redirect to Microsoft login
5. Enter test Microsoft account credentials
6. Should redirect back and create user

**Expected Result**: User logged in successfully, new tenant created

### ✅ Test 2: New User Registration
**Goal**: Test automatic user and tenant creation

**Prerequisites**: Use an email that doesn't exist in your system

**Steps**:
1. Complete Test 1 with new email
2. Check database for new user record
3. Verify `azure_ad_id` and `azure_tenant_id` are populated
4. Confirm new tenant was created

**Expected Result**: New MasterUser and TenantUser records created

### ✅ Test 3: Existing User Account Linking
**Goal**: Test linking Azure AD to existing account

**Prerequisites**: Create a user manually with same email as Azure AD account

**Steps**:
1. Create user via regular signup with email `test@yourdomain.com`
2. Use Azure AD login with same email
3. Should link accounts instead of creating duplicate

**Expected Result**: Existing user gets `azure_ad_id` populated

### ✅ Test 4: Error Handling
**Goal**: Test various error scenarios

**Test Cases**:
- Invalid client secret (should show configuration error)
- Cancelled authentication (user clicks cancel on Microsoft page)
- Network issues during token exchange

### ✅ Test 5: Multi-language Support
**Goal**: Verify UI translations work

**Steps**:
1. Change language to French/Spanish/German
2. Verify "Sign in with Microsoft" button shows correct translation
3. Test authentication flow in different languages

## Debug Testing

### Enable Debug Logging

Add to your environment:
```bash
DEBUG=True
LOG_LEVEL=DEBUG
```

### Check Logs

Monitor these log entries:
- Azure AD client initialization
- Authorization URL generation
- Token exchange process
- User creation/linking
- JWT token generation

### Database Verification

After successful login, check these tables:
```sql
-- Master database
SELECT email, azure_ad_id, azure_tenant_id FROM master_users WHERE email = 'test@example.com';

-- Tenant database  
SELECT email, azure_ad_id, azure_tenant_id FROM users WHERE email = 'test@example.com';
```

## Common Issues & Solutions

### Issue 1: "Azure AD SSO is not configured"
**Cause**: Missing environment variables
**Solution**: Verify `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` are set

### Issue 2: "Invalid redirect URI"
**Cause**: Redirect URI mismatch
**Solution**: Ensure Azure AD app has exact redirect URI: `http://localhost:8080/api/v1/auth/azure/callback`

### Issue 3: "AADSTS50011: The reply URL specified in the request does not match"
**Cause**: URL mismatch between request and Azure AD configuration
**Solution**: Double-check redirect URIs in Azure AD app registration

### Issue 4: "Failed to exchange code"
**Cause**: Invalid client secret or expired secret
**Solution**: Generate new client secret in Azure AD

### Issue 5: "Azure AD account has no email"
**Cause**: User account missing email claim
**Solution**: Ensure user has email in Azure AD profile

## Test Accounts

### Option 1: Use Your Own Microsoft Account
- Any @outlook.com, @hotmail.com, or work account
- Easiest for initial testing

### Option 2: Create Test Users in Azure AD
- Go to Azure AD → Users → New user
- Create test users with known credentials
- Better for comprehensive testing

### Option 3: Use Microsoft Developer Program
- Free Office 365 developer tenant
- Comes with sample users
- Best for enterprise scenario testing

## Automated Testing Script

Here's a simple test script you can run:

```bash
#!/bin/bash
# test-azure-sso.sh

echo "🧪 Testing Azure AD SSO Configuration..."

# Check environment variables
if [ -z "$AZURE_CLIENT_ID" ]; then
    echo "❌ AZURE_CLIENT_ID not set"
    exit 1
fi

if [ -z "$AZURE_CLIENT_SECRET" ]; then
    echo "❌ AZURE_CLIENT_SECRET not set"  
    exit 1
fi

echo "✅ Environment variables configured"

# Test Azure AD endpoints
echo "🔍 Testing Azure AD login endpoint..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/auth/azure/login

echo "✅ Azure AD SSO testing setup complete!"
echo "👉 Navigate to http://localhost:8080 and test the Microsoft login button"
```

## Success Criteria

Your Azure AD implementation is working correctly if:

- ✅ Microsoft login button appears on login page
- ✅ Clicking button redirects to Microsoft login
- ✅ Successful authentication creates user and tenant
- ✅ User can access dashboard after login
- ✅ Database contains Azure AD user information
- ✅ Existing users can link their Azure AD accounts
- ✅ Error scenarios are handled gracefully
- ✅ Translations work in all supported languages

## Next Steps After Testing

Once basic testing passes:

1. **Test with real enterprise Azure AD tenant**
2. **Configure production redirect URIs**
3. **Set up monitoring and alerting**
4. **Document for end users**
5. **Consider implementing additional SSO providers**

---

**Happy Testing!** 🚀

If you encounter any issues, check the application logs first, then refer to the troubleshooting section above.
