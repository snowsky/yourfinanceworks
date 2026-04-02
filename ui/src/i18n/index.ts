import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import en from './locales/en.json';
import es from './locales/es.json';
import fr from './locales/fr.json';
import de from './locales/de.json';

const resources = {
  en: {
    translation: en,
  },
  es: {
    translation: es,
  },
  fr: {
    translation: fr,
  },
  de: {
    translation: de,
  },
};

// Eagerly glob all plugin locale files from all known layouts:
//   plugins/<name>/plugin/ui/locales/<lang>.json  (standard layout)
//   plugins/<name>/locales/<lang>.json            (legacy flat layout)
//   plugins_dynamic/<name>/plugin/ui/locales/<lang>.json  (installed plugins)
//   plugins_dynamic/<name>/locales/<lang>.json    (installed plugins, flat)
const _pluginLocaleGlob = import.meta.glob<{ default: any }>([
  '../plugins/*/plugin/ui/locales/*.json',
  '../plugins/*/locales/*.json',
  '../plugins_dynamic/*/plugin/ui/locales/*.json',
  '../plugins_dynamic/*/locales/*.json',
], { eager: true });

// Build a lookup: pluginId → lang → translations
// Path examples:
//   ../plugins/investments/plugin/ui/locales/en.json  → pluginId=investments, lang=en
//   ../plugins_dynamic/surveys/plugin/ui/locales/en.json → pluginId=surveys, lang=en
const _pluginLocaleMap: Record<string, Record<string, any>> = {};
for (const [path, mod] of Object.entries(_pluginLocaleGlob)) {
  // Match both  plugins/<id>/plugin/ui/locales/<lang>.json
  // and         plugins/<id>/locales/<lang>.json
  const m = path.match(/plugins(?:_dynamic)?\/([^/]+)\/(?:plugin\/ui\/)?locales\/([^/]+)\.json$/);
  if (m) {
    const [, pluginId, lang] = m;
    if (!_pluginLocaleMap[pluginId]) _pluginLocaleMap[pluginId] = {};
    _pluginLocaleMap[pluginId][lang] = mod.default;
  }
}

// Plugin translation management
export interface PluginTranslations {
  [pluginId: string]: {
    [language: string]: any;
  };
}

// Load plugin translations dynamically
export const loadPluginTranslations = async (pluginId: string, languages: string[] = ['en', 'es', 'fr', 'de']) => {
  const pluginLocales = _pluginLocaleMap[pluginId];
  if (!pluginLocales) {
    console.warn(`No locale files found for plugin "${pluginId}"`);
    return {};
  }

  for (const lang of languages) {
    const data = pluginLocales[lang] ?? pluginLocales['en'];
    if (data) {
      i18n.addResourceBundle(lang, pluginId, data, true, true);
    }
  }

  return pluginLocales;
};

// Unload plugin translations
export const unloadPluginTranslations = (pluginId: string, languages: string[] = ['en', 'es', 'fr', 'de']) => {
  try {
    for (const lang of languages) {
      i18n.removeResourceBundle(lang, pluginId);
    }
  } catch (error) {
    console.error(`Failed to unload plugin translations for ${pluginId}:`, error);
  }
};

// Check if plugin translations are loaded
export const arePluginTranslationsLoaded = (pluginId: string, language: string = i18n.language): boolean => {
  return i18n.hasResourceBundle(language, pluginId);
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    // Do not force a language when using the language detector.
    // The detector will read from localStorage ('i18nextLng') or browser prefs.
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',

    interpolation: {
      escapeValue: false, // React already escapes values
    },

    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
    },
  });

export default i18n; 