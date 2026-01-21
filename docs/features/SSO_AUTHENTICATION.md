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
```

## 🔒 License Gating & Security

- **SSO License Required**: Single Sign-On is an enterprise feature. Organizations must have a valid SSO license enabled to use these providers.
- **CSRF Protection**: All authentication flows use encrypted state management to prevent cross-site request forgery.
- **Data Isolation**: Multi-tenant separation is maintained even when multiple users from the same identity provider join the platform.

---

### Pro Tips

- **Invite First**: For the best user experience, invite your team members via the **Team Management** tab before they log in with SSO. This ensures they join your organization immediately with the correct role.
- **Account Linking**: If you already have an email/password account, logging in with an SSO provider using the same email will automatically link your accounts.
- **Azure AD Manifests**: We recommend using the provided [Azure AD Guide](../technical-notes/AZURE_AD_SSO_IMPLEMENTATION.md) when registering your application in the Azure portal.
