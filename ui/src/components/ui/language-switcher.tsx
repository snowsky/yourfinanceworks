import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select';
import { Globe } from 'lucide-react';

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
];

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const [currentLanguage, setCurrentLanguage] = useState<string>('en');

  // Get the current language from i18n and ensure it's a valid option
  useEffect(() => {
    const detectedLanguage = i18n.language;
    const normalizedLanguage = (detectedLanguage || 'en').split('-')[0];
    // Ensure the detected language is one of our supported languages
    const supportedLanguages = languages.map(lang => lang.code);
    const validLanguage = supportedLanguages.includes(normalizedLanguage) ? normalizedLanguage : 'en';
    setCurrentLanguage(validLanguage);
  }, [i18n.language]);

  const handleLanguageChange = (languageCode: string) => {
    setCurrentLanguage(languageCode);
    i18n.changeLanguage(languageCode);
  };

  // Find the current language display name
  const currentLangData = languages.find(lang => lang.code === currentLanguage);
  const displayValue = currentLangData ? `${currentLangData.flag} ${currentLangData.name}` : 'English';

  return (
    <div className="flex items-center gap-2">
      <Globe className="h-4 w-4 text-muted-foreground" />
      <Select value={currentLanguage} onValueChange={handleLanguageChange}>
        <SelectTrigger className="w-[140px] bg-background text-foreground border-border">
          <SelectValue placeholder={displayValue}>
            {displayValue}
          </SelectValue>
        </SelectTrigger>
        <SelectContent
          className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-lg"
          style={{ zIndex: 9999 }}
        >
          {languages.map((language) => (
            <SelectItem
              key={language.code}
              value={language.code}
              className="text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span>{language.flag}</span>
                <span>{language.name}</span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
} 