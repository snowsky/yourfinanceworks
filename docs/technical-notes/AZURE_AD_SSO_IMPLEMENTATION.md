# Azure AD SSO Implementation Guide

## Overview

Microsoft Azure AD/Entra ID Single Sign-On (SSO) has been successfully implemented in the invoice application. This allows users to authenticate using their Microsoft work or school accounts, providing seamless integration with enterprise identity systems.

## Features Implemented

### ✅ Backend Implementation
- **MSAL Integration**: Uses Microsoft Authentication Library (MSAL) for secure OAuth 2.0 flows
- **Database Schema**: Extended user models with Azure AD fields (`azure_ad_id`, `azure_tenant_id`)
- **Authentication Endpoints**: 
  - `/api/v1/auth/azure/login` - Initiates Azure AD authentication
  - `/api/v1/auth/azure/callback` - Handles OAuth callback and user creation
- **Multi-tenant Support**: Supports both single-tenant and multi-tenant Azure AD configurations
- **User Provisioning**: Automatic user and tenant creation for new Azure AD users
- **Account Linking**: Links existing users with Azure AD accounts

### ✅ Frontend Implementation
- **Login UI**: Added Microsoft login button with official branding
- **Multi-language Support**: Translations for English, French, Spanish, and German
- **OAuth Flow**: Seamless redirect-based authentication flow
- **Error Handling**: Proper error messages and fallback mechanisms

### ✅ Configuration
- **Environment Variables**: Configurable via Docker Compose and environment files
- **Security**: CSRF protection with state management
- **Logging**: Comprehensive logging for debugging and monitoring

## Configuration

### Environment Variables

Add these environment variables to your `.env` file or Docker Compose configuration:

```bash
# Azure AD OAuth Configuration
AZURE_CLIENT_ID=your-azure-app-client-id
AZURE_CLIENT_SECRET=your-azure-app-client-secret
AZURE_TENANT_ID=common  # Use 'common' for multi-tenant, or specific tenant ID
```

### Azure AD App Registration

1. **Register Application in Azure Portal**:
   - Go to Azure Portal → Azure Active Directory → App registrations
   - Click "New registration"
   - Name: "Invoice App"
   - Supported account types: Choose based on your needs
   - Redirect URI: `https://your-domain.com/api/v1/auth/azure/callback`

2. **Configure Authentication**:
   - Add redirect URIs for all environments (dev, staging, prod)
   - Enable ID tokens under "Implicit grant and hybrid flows"

3. **API Permissions**:
   - Add Microsoft Graph permissions:
     - `openid` (Sign users in)
     - `email` (View users' email address)
     - `profile` (View users' basic profile)

4. **Client Secret**:
   - Go to "Certificates & secrets"
   - Create a new client secret
   - Copy the secret value (shown only once)

### Docker Compose Configuration

The Azure AD environment variables are already configured in `docker-compose.yml`:

```yaml
environment:
  # Azure AD OAuth (optional)
  - AZURE_CLIENT_ID=${AZURE_CLIENT_ID:-}
  - AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET:-}
  - AZURE_TENANT_ID=${AZURE_TENANT_ID:-common}
```

## Database Schema Changes

### New Fields Added

**MasterUser Model**:
```python
azure_ad_id = Column(String, unique=True, nullable=True)      # Azure AD Object ID
azure_tenant_id = Column(String, nullable=True)              # Azure AD Tenant ID
```

**TenantUser Model** (per-tenant databases):
```python
azure_ad_id = Column(String, unique=True, nullable=True)      # Azure AD Object ID  
azure_tenant_id = Column(String, nullable=True)              # Azure AD Tenant ID
```

### Migration

Since you mentioned rebuilding from 0, the schema changes will be applied automatically when creating new databases. For existing databases, run:

```bash
# Inside the API container
python -m alembic upgrade head
```

## User Flow

### New User Registration via Azure AD

1. User clicks "Sign in with Microsoft" on login page
2. Redirected to Azure AD login page
3. User authenticates with Microsoft credentials
4. Azure AD redirects back with authorization code
5. Backend exchanges code for access token and ID token
6. User information extracted from ID token claims
7. New tenant created automatically for the user
8. User account created in both master and tenant databases
9. JWT token issued and user redirected to dashboard

### Existing User Login via Azure AD

1. User clicks "Sign in with Microsoft"
2. Azure AD authentication flow (steps 1-6 above)
3. System finds existing user by email or Azure AD ID
4. Azure AD ID linked to existing account if not already linked
5. JWT token issued and user logged in

## Security Features

### CSRF Protection
- State parameter used in OAuth flow to prevent CSRF attacks
- State tokens expire after 10 minutes
- State validation on callback

### Token Security
- ID tokens validated using MSAL library
- Access tokens used only for initial user info retrieval
- JWT tokens issued for application sessions

### Multi-tenant Isolation
- Each user gets their own tenant database
- Azure AD tenant ID stored for audit and compliance
- Complete data separation between organizations

## API Endpoints

### Azure AD Login Initiation
```http
GET /api/v1/auth/azure/login?next=/dashboard
```

**Parameters**:
- `next` (optional): Redirect URL after successful login

**Response**: Redirect to Azure AD authorization URL

### Azure AD Callback
```http
GET /api/v1/auth/azure/callback?code=...&state=...
```

**Parameters**:
- `code`: Authorization code from Azure AD
- `state`: CSRF protection state token

**Response**: Redirect to UI with JWT token

## Error Handling

### Common Error Scenarios

1. **Azure AD Not Configured**: Returns 503 Service Unavailable
2. **Invalid Authorization Code**: Returns 400 Bad Request
3. **Missing User Email**: Returns 400 Bad Request
4. **Database Errors**: Returns 500 Internal Server Error
5. **CSRF Attack**: Returns 400 Bad Request (invalid state)

### Logging

All Azure AD authentication events are logged with appropriate levels:
- INFO: Successful logins
- WARNING: Configuration issues
- ERROR: Authentication failures

## Testing

### Manual Testing

1. **Configure Azure AD app** with localhost redirect URI
2. **Set environment variables** in development
3. **Start application** and navigate to login page
4. **Click Microsoft login button** and verify flow
5. **Check user creation** in database

### Test Scenarios

- [ ] New user registration via Azure AD
- [ ] Existing user login via Azure AD  
- [ ] Account linking for existing email
- [ ] Multi-tenant Azure AD support
- [ ] Error handling for invalid codes
- [ ] CSRF protection validation

## Troubleshooting

### Common Issues

1. **"Azure AD SSO is not configured"**
   - Check `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` environment variables
   - Verify MSAL library is installed

2. **"Invalid redirect URI"**
   - Ensure redirect URI in Azure AD app matches your domain
   - Check for HTTP vs HTTPS mismatches

3. **"Failed to exchange code"**
   - Verify client secret is correct and not expired
   - Check Azure AD app permissions

4. **"Azure AD account has no email"**
   - Ensure user has email address in Azure AD
   - Check API permissions include `email` scope

### Debug Mode

Enable debug logging by setting:
```bash
DEBUG=True
```

This will provide detailed logs of the OAuth flow and token exchange.

## Future Enhancements

### Planned Features
- [ ] Azure AD group-based role mapping
- [ ] Conditional access policy support
- [ ] Azure AD B2B guest user support
- [ ] Admin consent for organization-wide deployment

### Integration Opportunities
- [ ] Microsoft Graph API integration
- [ ] Office 365 calendar integration
- [ ] SharePoint document storage
- [ ] Teams notifications

## Compliance & Security

### Enterprise Requirements Met
- ✅ OAuth 2.0 / OpenID Connect standards compliance
- ✅ Multi-tenant architecture support
- ✅ Audit logging for authentication events
- ✅ Secure token handling and validation
- ✅ CSRF protection mechanisms

### Recommended Policies
- Use specific tenant ID in production (not 'common')
- Implement conditional access policies in Azure AD
- Regular rotation of client secrets
- Monitor authentication logs for anomalies

## Support

For issues related to Azure AD SSO implementation:

1. Check application logs for detailed error messages
2. Verify Azure AD app configuration matches documentation
3. Test with a simple Azure AD account first
4. Consult Microsoft documentation for Azure AD specific issues

---

**Implementation Status**: ✅ Complete  
**Last Updated**: September 2025  
**Dependencies**: MSAL 1.31.0, FastAPI, PostgreSQL
