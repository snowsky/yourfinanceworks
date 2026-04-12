# Mobile Workspace

This workspace is designed for multiple standalone mobile apps, starting with `expenses`.

## Structure

- `apps/expenses`: Expo app focused on fast expense capture
- `packages/mobile-core`: shared utilities, config, and types for future apps

## Why this layout

It keeps each app independently shippable to the App Store or Play Store while still allowing reuse across apps later, such as:

- authentication helpers
- API clients
- shared expense/accounting types
- design tokens and primitives

## Local development

From this directory:

```bash
npm install
npm run dev:expenses
```

Then scan the QR code with Expo Go or open the iOS/Android simulator.

The first app lives at `apps/expenses` and currently includes:

- login with bearer-token auth
- Google SSO via backend OAuth flow and app deep link callback
- secure session storage
- expense timeline/inbox/insights reads
- voice parsing call to `/api/v1/expenses/parse-voice`
- camera capture placeholder flow for receipt upload

### Backend URL

By default the Expo app uses:

```txt
http://localhost:8000/api/v1
```

You can override that with:

```bash
EXPO_PUBLIC_API_URL=http://YOUR_MACHINE_IP:8000/api/v1 npm run dev:expenses
```

If you test on a physical phone, `localhost` will not point to your computer. Use your machine's LAN IP instead.

### Google SSO for mobile

The mobile app uses the backend Google OAuth flow and redirects back into the app using the `yfw-expenses://` scheme.

If needed, allow additional redirect prefixes with:

```bash
MOBILE_OAUTH_REDIRECT_PREFIXES="yfw-expenses://,exp://"
```

## Future apps

When you add a second app later, create `apps/<name>` and import shared pieces from `packages/mobile-core`.
