import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Menu, Button, Divider } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import Icon from 'react-native-vector-icons/MaterialIcons';

interface LanguageSwitcherProps {
  style?: any;
}

const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ style }) => {
  const { t, i18n } = useTranslation();
  const [visible, setVisible] = React.useState(false);

  const openMenu = () => setVisible(true);
  const closeMenu = () => setVisible(false);

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    closeMenu();
  };

  const languages = [
    { code: 'en', name: t('settings.languages.en'), flag: '🇺🇸' },
    { code: 'es', name: t('settings.languages.es'), flag: '🇪🇸' },
    { code: 'fr', name: t('settings.languages.fr'), flag: '🇫🇷' },
  ];

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0];

  return (
    <View style={[styles.container, style]}>
      <Menu
        visible={visible}
        onDismiss={closeMenu}
        anchor={
          <Button
            mode="outlined"
            onPress={openMenu}
            icon={() => <Icon name="language" size={20} color="#666" />}
            contentStyle={styles.buttonContent}
            labelStyle={styles.buttonLabel}
          >
            {currentLanguage.flag} {currentLanguage.name}
          </Button>
        }
        contentStyle={styles.menuContent}
      >
        {languages.map((language, index) => (
          <React.Fragment key={language.code}>
            <Menu.Item
              onPress={() => changeLanguage(language.code)}
              title={`${language.flag} ${language.name}`}
              titleStyle={[
                styles.menuItemTitle,
                i18n.language === language.code && styles.activeLanguage
              ]}
            />
            {index < languages.length - 1 && <Divider />}
          </React.Fragment>
        ))}
      </Menu>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  buttonLabel: {
    fontSize: 14,
    marginLeft: 4,
  },
  menuContent: {
    backgroundColor: 'white',
    borderRadius: 8,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  menuItemTitle: {
    fontSize: 16,
  },
  activeLanguage: {
    fontWeight: 'bold',
    color: '#2196F3',
  },
});

export default LanguageSwitcher;