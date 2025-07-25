# Invoice Management Mobile App

A React Native mobile application for invoice management with full internationalization support.

## 🌍 Multi-Language Support

The mobile app now includes comprehensive internationalization (i18n) support with the same translations as the web UI.

### Supported Languages
- **English (en)** - Default language
- **Spanish (es)** - Español  
- **French (fr)** - Français

### Features
- **Automatic Language Detection** - Detects device language on first launch
- **Persistent Language Selection** - Saves user's language preference using AsyncStorage
- **Language Switcher** - Easy language switching in Settings screen
- **Shared Translations** - Reuses translation files from the web UI for consistency

### How to Use

1. **Automatic Detection**: The app automatically detects your device language on first launch
2. **Manual Selection**: Go to Settings → Language to change the language manually
3. **Persistent Storage**: Your language preference is saved and restored on app restart

### Implementation Details

The i18n system uses:
- `i18next` and `react-i18next` for translation management
- `expo-localization` for device language detection
- `@react-native-async-storage/async-storage` for persistent storage
- Sync script to copy translation files from `ui/src/i18n/locales/`

### Adding New Languages

To add a new language:
1. Add the translation file to `ui/src/i18n/locales/`
2. Update the language list in `src/components/LanguageSwitcher.tsx`
3. The mobile app will automatically use the new translations

### Translation Keys

The mobile app uses the same translation keys as the web UI. Common patterns:

```typescript
// Basic usage
const { t } = useTranslation();
<Text>{t('common.save')}</Text>

// With variables
<Text>{t('dashboard.welcome', { name: userName })}</Text>

// Nested keys
<Text>{t('settings.company_info')}</Text>
```

## 🚀 Setup

### Prerequisites
- Node.js 18+
- Expo CLI
- iOS Simulator (for iOS development on macOS)
- Android Studio (for Android development)

### Installation

1. **Navigate to mobile directory**:
   ```bash
   cd mobile
   ```

2. **Sync translation files**:
   ```bash
   npm run sync-translations
   ```

3. **Install dependencies**:
   ```bash
   npm install
   ```

4. **Start development server**:
   ```bash
   npm start
   ```

5. **Run on device/simulator**:
   ```bash
   # iOS (macOS only)
   npm run ios
   
   # Android
   npm run android
   ```

### Dependencies Added for i18n

```json
{
  "expo-localization": "~16.0.0",
  "i18next": "^23.7.16",
  "react-i18next": "^14.0.0"
}
```

## 📱 Features

- **Multi-language Support** - English, Spanish, and French
- **Invoice Management** - Create, edit, and manage invoices
- **Client Management** - Add and manage client information
- **Payment Tracking** - Track payments and invoice status
- **Settings Management** - Configure company and invoice settings
- **User Management** - Manage organization users
- **Audit Logging** - Track system activities
- **Responsive Design** - Optimized for mobile devices

## 🔧 Development

### File Structure

```
src/
├── i18n/
│   └── index.ts              # i18n configuration
├── components/
│   └── LanguageSwitcher.tsx  # Language selection component
├── screens/                  # App screens
├── services/                 # API services
└── utils/
    └── i18n.ts              # Legacy i18n (redirects to new setup)
```

### Key Components

- **LanguageSwitcher**: Dropdown component for language selection
- **i18n/index.ts**: Main i18n configuration with AsyncStorage persistence
- **Settings Screen**: Includes language switcher and translated content

### Testing Languages

1. Change device language in simulator/device settings
2. Use the language switcher in the Settings screen
3. Restart the app to test persistence

## 🌐 Translation Management

The mobile app syncs translation files from the web UI using a sync script:
- Source: `ui/src/i18n/locales/`
- Target: `mobile/src/i18n/locales/`
- Files: `en.json`, `es.json`, `fr.json`

Sync translations with:
```bash
npm run sync-translations
```

This approach ensures:
- **Single source of truth** for translations in the UI folder
- **Metro bundler compatibility** (no symbolic link issues)
- **Easy synchronization** with a simple npm script

## 📦 Building for Production

```bash
# Build for iOS
eas build --platform ios --profile production

# Build for Android
eas build --platform android --profile production

# Submit to app stores
eas submit --platform ios
eas submit --platform android
```

## 🔍 Troubleshooting

### Language Not Changing
1. Check if AsyncStorage is working properly
2. Restart the app after language change
3. Verify translation keys exist in all language files

### Missing Translations
1. Check if the key exists in all language files
2. Verify the key path is correct
3. Check console for i18next warnings

### Performance Issues
1. Ensure translations are not loaded synchronously
2. Check for memory leaks in language switching
3. Monitor AsyncStorage usage

## 🤝 Contributing

When adding new features:
1. Add translation keys to all language files in the UI folder
2. Use `useTranslation` hook for all user-facing text
3. Test with all supported languages
4. Update this README if adding new i18n features