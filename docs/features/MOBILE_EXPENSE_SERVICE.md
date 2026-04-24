# Mobile Expense Service

The mobile expense service lets an external mobile client, such as `yfw-mobile`, connect directly to a specific YourFinanceWORKS organization for receipt capture and expense entry.

## Overview

This feature adds an organization-bound mobile expense API under `/api/v1/mobile/expenses/*`. Each enabled organization receives a hidden mobile app binding through normal organization settings. The mobile client sends its configured `app_id`, and the API resolves that value to exactly one active organization.

The service is intentionally separate from the plugin system and from `yfw-expense`. It is designed as a direct integration path for the mobile app while preserving the tenant and role boundaries used by the main application.

## What It Provides

- **Organization-bound app IDs**: Each enabled mobile app ID maps to one active organization.
- **Mobile config lookup**: The mobile app can fetch branding, signup behavior, default role, and allowed auth methods before rendering its auth flow.
- **Scoped signup**: New mobile signups are created inside the configured organization only.
- **Existing-user membership handling**: Existing users can be added to the configured organization without changing their primary organization.
- **Password login**: Mobile password login returns a normal bearer token plus a user response bound to the configured organization.
- **Session lookup**: Authenticated mobile clients can verify the current user against the app's configured organization.

## API Surface

Base path:

```text
/api/v1/mobile/expenses
```

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/config?app_id=...` | Resolve app configuration and branding for the mobile client. |
| `POST` | `/auth/signup` | Create a new account or attach an existing account to the configured organization. |
| `POST` | `/auth/login` | Sign in an existing member of the configured organization. |
| `GET` | `/auth/me?app_id=...` | Return the current authenticated user in the configured organization context. |

## Configuration

Admins configure the mobile expense service from the Expenses settings area. The configuration is stored in organization settings under the `expense_mobile_app` key.

Available settings:

| Setting | Description |
| --- | --- |
| `enabled` | Turns the mobile expense service on or off for the organization. |
| `app_id` | Hidden identifier used by the mobile app to bind to the organization. Required when enabled. |
| `signup_enabled` | Allows or blocks mobile self-signup for the organization. |
| `default_role` | Role assigned to mobile-created users. Limited to `user` or `viewer`. |
| `allowed_auth_methods.password` | Enables password signup and login. |
| `allowed_auth_methods.google` | Reserved config flag for Google auth support. |
| `allowed_auth_methods.microsoft` | Reserved config flag for Microsoft auth support. |
| `branding.title` | Mobile-facing title, defaulting to the organization name. |
| `branding.subtitle` | Mobile-facing subtitle. |
| `branding.accent_color` | Mobile UI accent color. |
| `branding.logo_url` | Mobile logo URL, defaulting to the organization logo when available. |

Enabled `app_id` values must be unique across active organizations. Attempts to reuse an enabled app ID return a conflict error.

## Signup And Login Rules

Mobile signup is intentionally conservative:

- Signup must be enabled for the configured organization.
- Password signup requires password auth to be enabled.
- New users are created in the resolved organization with the configured default role.
- Existing users must provide their current password before membership is added or reactivated.
- Existing users keep their primary organization unchanged.
- Only `user` and `viewer` are accepted as default mobile roles.
- Disabled users cannot sign up or log in through the mobile endpoint.

Mobile login requires the account to already be a member of the resolved organization. A valid password for an account in another organization is not enough by itself; membership must exist.

## Tenant Context

The mobile endpoints resolve organization context from `app_id` rather than from the caller's current browser session. Once authenticated, responses are built with the user bound to the resolved tenant so the mobile client receives the expected organization role and organization list.

This keeps mobile capture flows organization-specific without changing the user's primary tenant association in the master user record.

## Validation And Tests

The feature includes focused backend tests for:

- mobile config resolution
- signup behavior
- existing-user organization membership
- duplicate enabled app ID validation

The implementation was introduced in commit `982699471f092ca4b25fd17188e344e18b43eaa1`.
