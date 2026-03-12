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

// Plugin translation management
export interface PluginTranslations {
  [pluginId: string]: {
    [language: string]: any;
  };
}

// Load plugin translations dynamically
export const loadPluginTranslations = async (pluginId: string, languages: string[] = ['en', 'es', 'fr', 'de']) => {
  try {
    const translations: { [language: string]: any } = {};

    for (const lang of languages) {
      try {
        const module = await import(`../plugins/${pluginId}/locales/${lang}.json`);
        translations[lang] = module.default;
      } catch (error) {
        console.warn(`Failed to load ${lang} translations for plugin ${pluginId}:`, error);
        // Fallback to English if available
        if (lang !== 'en') {
          try {
            const englishModule = await import(`../plugins/${pluginId}/locales/en.json`);
            translations[lang] = englishModule.default;
          } catch (fallbackError) {
            console.warn(`Failed to load English fallback for plugin ${pluginId}:`, fallbackError);
          }
        }
      }
    }

    // Add translations to i18next resources
    for (const lang of languages) {
      if (translations[lang]) {
        i18n.addResourceBundle(lang, pluginId, translations[lang], true, true);
      }
    }

    return translations;
  } catch (error) {
    console.error(`Failed to load plugin translations for ${pluginId}:`, error);
    return {};
  }
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