import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Modal, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

const languages = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
];

const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();
  const [showModal, setShowModal] = useState(false);

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];
  
  console.log('LanguageSwitcher rendering, current language:', i18n.language, currentLanguage);
  console.log('i18n object:', i18n);
  console.log('Available languages:', languages);

  const handleLanguageChange = async (languageCode: string) => {
    try {
      console.log('Changing language to:', languageCode);
      await i18n.changeLanguage(languageCode);
      console.log('Language changed successfully to:', i18n.language);
      setShowModal(false);
    } catch (error) {
      console.error('Error changing language:', error);
    }
  };

  return (
    <View>
      <TouchableOpacity
        style={styles.selector}
        onPress={() => setShowModal(true)}
      >
        <View style={styles.currentLanguage}>
          <Text style={styles.flag}>{currentLanguage.flag}</Text>
          <Text style={styles.languageName}>{currentLanguage.name}</Text>
        </View>
        <Ionicons name="chevron-down" size={20} color="#6B7280" />
      </TouchableOpacity>

      <Modal
        visible={showModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowModal(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowModal(false)}
        >
          <TouchableOpacity 
            style={styles.modalContent}
            activeOpacity={1}
            onPress={(e) => e.stopPropagation()}
          >
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Language</Text>
              <TouchableOpacity onPress={() => setShowModal(false)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <View style={styles.modalBody}>
              {languages.map(language => (
                <TouchableOpacity
                  key={language.code}
                  style={[
                    styles.languageOption,
                    i18n.language === language.code && styles.languageOptionSelected
                  ]}
                  onPress={() => handleLanguageChange(language.code)}
                >
                  <View style={styles.languageInfo}>
                    <Text style={styles.flag}>{language.flag}</Text>
                    <Text style={[
                      styles.languageOptionText,
                      i18n.language === language.code && styles.languageOptionTextSelected
                    ]}>
                      {language.name}
                    </Text>
                  </View>
                  {i18n.language === language.code && (
                    <Ionicons name="checkmark" size={20} color="#007AFF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  selector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    padding: 12,
  },
  currentLanguage: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  flag: {
    fontSize: 20,
    marginRight: 8,
  },
  languageName: {
    fontSize: 16,
    color: '#111827',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '80%',
    minHeight: '50%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  modalBody: {
    padding: 20,
  },
  languageOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  languageOptionSelected: {
    backgroundColor: '#f0f9ff',
  },
  languageInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  languageOptionText: {
    fontSize: 16,
    color: '#333',
  },
  languageOptionTextSelected: {
    color: '#007AFF',
    fontWeight: '600',
  },
});

export default LanguageSwitcher;