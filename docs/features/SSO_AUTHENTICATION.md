# SSO Authentication

YourFinanceWORKS supports Single Sign-On (SSO) to provide a seamless and secure login experience for your team using their existing corporate credentials.

## 🚀 Key Features

- **Multi-Provider Support**: Native integration with Google Workspace and Microsoft Azure AD (Entra ID).
- **Auto-Provisioning**: New users are automatically onboarded with a fresh organization upon their first login.
- **Invitation Integration**: Invited users can join their organization via SSO, automatically accepting their invitation and assuming their assigned role.
- **Unified Identity**: Link existing email-based accounts with SSO providers for simplified access management.
- **Enterprise Security**: Leverages robust OAuth 2.0 and OpenID Connect standards for secure authentication flows.

## ⚙️ Supported Providers

### 1. Google Workspace

Authenticate using your Google account. Ideal for teams using Google Workspace for email and collaboration.

### 2. Microsoft Azure AD (Entra ID)

Enterprise-grade integration with Microsoft identity systems. Supports both single-tenant (internal company use) and multi-tenant (SaaS/B2B) configurations.

## 🛠️ Configuration

SSO features are managed via environment variables and organization-level settings:

```bash
# Google SSO (Optional)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Azure AD SSO (Optional)
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=common # Use 'common' for multi-tenant

# Redis — required for reliable SSO state management across multiple workers
REDIS_URL=redis://redis:6379
```

## 🏗️ Infrastructure Requirements

### Redis (Required)

SSO uses a short-lived CSRF state token during every OAuth flow. This state is stored in **Redis** so it survives across API workers and container restarts. Without Redis the state is held in-memory and will be lost on any server restart, causing `400 Invalid or expired state` errors for users mid-flow.

Redis is included in `docker-compose.yml` and starts automatically. No additional setup is required for Docker deployments. The `REDIS_URL` environment variable is set to `redis://redis:6379` by the compose file.

For non-Docker deployments, ensure a Redis instance is reachable and set `REDIS_URL` accordingly. If `REDIS_URL` is unset the system falls back to in-memory state (safe for single-process development only).

## 🔒 License Gating & Security

- **SSO License Required**: Single Sign-On is an enterprise feature. Organizations must have a valid SSO license enabled to use these providers. The first user in a new installation (the super-admin) is always exempt and can sign up via SSO without a license.
- **CSRF Protection**: All authentication flows use short-lived, single-use state tokens stored in Redis to prevent cross-site request forgery.
- **Data Isolation**: Multi-tenant separation is maintained even when multiple users from the same identity provider join the platform.

---

### Pro Tips

- **Invite First**: For the best user experience, invite your team members via the **Team Management** tab before they log in with SSO. This ensures they join your organization immediately with the correct role.
- **Account Linking**: If you already have an email/password account, logging in with an SSO provider using the same email will automatically link your accounts.
- **Azure AD Manifests**: We recommend using the provided [Azure AD Guide](../technical-notes/AZURE_AD_SSO_IMPLEMENTATION.md) when registering your application in the Azure portal.
