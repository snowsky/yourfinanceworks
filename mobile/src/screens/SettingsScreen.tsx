import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';

interface SettingsScreenProps {
  onNavigateBack: () => void;
  onSignOut: () => void;
}

const SettingsScreen: React.FC<SettingsScreenProps> = ({
  onNavigateBack,
  onSignOut,
}) => {
  const handleSignOut = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: onSignOut,
        },
      ]
    );
  };

  const SettingItem: React.FC<{
    title: string;
    value?: string;
    onPress?: () => void;
    showArrow?: boolean;
    icon?: string;
  }> = ({ title, value, onPress, showArrow = false, icon }) => (
    <TouchableOpacity
      style={styles.settingItem}
      onPress={onPress}
      disabled={!onPress}
    >
      {icon && (
        <View style={styles.settingIcon}>
          <Ionicons name={icon as any} size={20} color="#6B7280" />
        </View>
      )}
      <View style={styles.settingContent}>
        <Text style={styles.settingTitle}>{title}</Text>
        {value && <Text style={styles.settingValue}>{value}</Text>}
      </View>
      {showArrow && <Ionicons name="chevron-forward" size={20} color="#6B7280" />}
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <SettingItem
            title="Name"
            value="John Doe"
            icon="person-outline"
          />
          <SettingItem
            title="Email"
            value="john.doe@example.com"
            icon="mail-outline"
          />
          <SettingItem
            title="Organization"
            value="Acme Corp"
            icon="business-outline"
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Company</Text>
          <SettingItem
            title="Company Name"
            value="Acme Corporation"
            icon="business-outline"
          />
          <SettingItem
            title="Company Email"
            value="contact@acme.com"
            icon="mail-outline"
          />
          <SettingItem
            title="Default Currency"
            value="USD"
            icon="cash-outline"
          />
          <SettingItem
            title="Tax Rate"
            value="8.5%"
            icon="calculator-outline"
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>App</Text>
          <SettingItem
            title="Version"
            value="1.0.0"
            icon="information-circle-outline"
          />
          <SettingItem
            title="About"
            onPress={() => Alert.alert('About', 'Invoice App Mobile v1.0.0\n\nA comprehensive invoice management solution for mobile devices.')}
            showArrow
            icon="help-circle-outline"
          />
          <SettingItem
            title="Privacy Policy"
            onPress={() => Alert.alert('Privacy Policy', 'Privacy policy will be displayed here.')}
            showArrow
            icon="shield-checkmark-outline"
          />
          <SettingItem
            title="Terms of Service"
            onPress={() => Alert.alert('Terms of Service', 'Terms of service will be displayed here.')}
            showArrow
            icon="document-text-outline"
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Support</Text>
          <SettingItem
            title="Help & Support"
            onPress={() => Alert.alert('Support', 'Help and support information will be displayed here.')}
            showArrow
            icon="help-buoy-outline"
          />
          <SettingItem
            title="Contact Us"
            onPress={() => Alert.alert('Contact', 'Contact information will be displayed here.')}
            showArrow
            icon="call-outline"
          />
        </View>

        <View style={styles.section}>
          <TouchableOpacity
            style={[styles.settingItem, styles.logoutButton]}
            onPress={handleSignOut}
          >
            <View style={styles.settingIcon}>
              <Ionicons name="log-out-outline" size={20} color="#EF4444" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.logoutText}>Sign Out</Text>
            </View>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 50,
    paddingBottom: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  backButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  headerSpacer: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  section: {
    backgroundColor: '#fff',
    marginTop: 20,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#e5e7eb',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    padding: 16,
    paddingBottom: 8,
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  settingIcon: {
    width: 24,
    marginRight: 12,
    alignItems: 'center',
  },
  settingContent: {
    flex: 1,
  },
  settingTitle: {
    fontSize: 16,
    color: '#333',
    marginBottom: 2,
  },
  settingValue: {
    fontSize: 14,
    color: '#666',
  },
  logoutButton: {
    justifyContent: 'flex-start',
  },
  logoutText: {
    fontSize: 16,
    color: '#EF4444',
    fontWeight: '600',
  },
});

export default SettingsScreen; 