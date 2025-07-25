import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  TextInput,
  ActivityIndicator,
  Modal,
  Switch,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import apiService, { Settings, DiscountRule, DiscountRuleCreate, DiscountRuleUpdate } from '../services/api';
import LanguageSwitcher from '../components/LanguageSwitcher';

interface SettingsScreenProps {
  onNavigateBack: () => void;
  onNavigateToUsers: () => void;
  onNavigateToAuditLog: () => void;
  onSignOut: () => void;
}

interface CompanyInfo {
  name: string;
  email: string;
  phone: string;
  address: string;
  tax_id: string;
  logo?: string;
}

interface InvoiceSettings {
  prefix: string;
  next_number: string;
  terms: string;
  notes?: string;
  send_copy: boolean;
  auto_reminders: boolean;
}

interface EmailSettings {
  provider: string;
  from_name: string;
  from_email: string;
  enabled: boolean;
  aws_access_key_id: string;
  aws_secret_access_key: string;
  aws_region: string;
  azure_connection_string: string;
  mailgun_api_key: string;
  mailgun_domain: string;
}

const SettingsScreen: React.FC<SettingsScreenProps> = ({
  onNavigateBack,
  onNavigateToUsers,
  onNavigateToAuditLog,
  onSignOut,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('company');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [showDiscountRuleModal, setShowDiscountRuleModal] = useState(false);
  const [editingDiscountRule, setEditingDiscountRule] = useState<DiscountRule | null>(null);
  const [newDiscountRule, setNewDiscountRule] = useState<DiscountRuleCreate>({
    name: "",
    min_amount: 0,
    discount_type: "percentage",
    discount_value: 0,
    is_active: true,
    priority: 0,
    currency: "USD",
  });

  const [companyInfo, setCompanyInfo] = useState<CompanyInfo>({
    name: "",
    email: "",
    phone: "",
    address: "",
    tax_id: "",
  });

  const [invoiceSettings, setInvoiceSettings] = useState<InvoiceSettings>({
    prefix: "INV-",
    next_number: "0001",
    terms: "Payment due within 30 days from the date of invoice.\nLate payments are subject to a 1.5% monthly finance charge.",
    notes: "Thank you for your business!",
    send_copy: true,
    auto_reminders: true,
  });

  const [emailSettings, setEmailSettings] = useState<EmailSettings>({
    provider: "aws_ses",
    from_name: "Your Company",
    from_email: "noreply@yourcompany.com",
    enabled: false,
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_region: "us-east-1",
    azure_connection_string: "",
    mailgun_api_key: "",
    mailgun_domain: "",
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const [settingsData, discountRulesData] = await Promise.all([
        apiService.getSettings(),
        apiService.getDiscountRules()
      ]);
      
      setSettings(settingsData);
      setDiscountRules(discountRulesData);
      
      if (settingsData.company_info) {
        setCompanyInfo(settingsData.company_info);
      }
      
      if (settingsData.invoice_settings) {
        setInvoiceSettings(settingsData.invoice_settings);
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      Alert.alert('Error', 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const settingsData = {
        company_info: companyInfo,
        invoice_settings: invoiceSettings
      };
      
      console.log('Saving settings:', settingsData);
      const result = await apiService.updateSettings(settingsData);
      console.log('Settings save result:', result);
      Alert.alert('Success', 'Settings saved successfully!');
    } catch (error) {
      console.error('Failed to save settings:', error);
      Alert.alert('Error', `Failed to save settings: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

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

  const handleCreateDiscountRule = async () => {
    try {
      const newRule = await apiService.createDiscountRule(newDiscountRule);
      setDiscountRules(prev => [...prev, newRule]);
      setShowDiscountRuleModal(false);
      setNewDiscountRule({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
      });
      Alert.alert('Success', 'Discount rule created successfully!');
    } catch (error) {
      console.error('Failed to create discount rule:', error);
      Alert.alert('Error', 'Failed to create discount rule');
    }
  };

  const handleUpdateDiscountRule = async () => {
    if (!editingDiscountRule) return;
    
    try {
      const ruleData: DiscountRuleUpdate = {
        name: editingDiscountRule.name,
        min_amount: editingDiscountRule.min_amount,
        discount_type: editingDiscountRule.discount_type,
        discount_value: editingDiscountRule.discount_value,
        is_active: editingDiscountRule.is_active,
        priority: editingDiscountRule.priority,
        currency: editingDiscountRule.currency,
      };
      
      const updatedRule = await apiService.updateDiscountRule(editingDiscountRule.id, ruleData);
      
      setDiscountRules(prev => prev.map(rule => 
        rule.id === updatedRule.id ? updatedRule : rule
      ));
      setShowDiscountRuleModal(false);
      setEditingDiscountRule(null);
      Alert.alert('Success', 'Discount rule updated successfully!');
    } catch (error) {
      console.error('Failed to update discount rule:', error);
      Alert.alert('Error', 'Failed to update discount rule');
    }
  };

  const handleDeleteDiscountRule = async (id: number) => {
    Alert.alert(
      'Delete Discount Rule',
      'Are you sure you want to delete this discount rule?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await apiService.deleteDiscountRule(id);
              setDiscountRules(prev => (prev || []).filter(rule => rule.id !== id));
              Alert.alert('Success', 'Discount rule deleted successfully!');
            } catch (error) {
              console.error('Failed to delete discount rule:', error);
              Alert.alert('Error', 'Failed to delete discount rule');
            }
          },
        },
      ]
    );
  };

  const TabButton = ({ title, value, icon }: { title: string; value: string; icon: string }) => (
    <TouchableOpacity
      style={[styles.tabButton, activeTab === value && styles.activeTabButton]}
      onPress={() => setActiveTab(value)}
    >
      <Ionicons 
        name={icon as any} 
        size={20} 
        color={activeTab === value ? '#3B82F6' : '#6B7280'} 
      />
      <Text style={[styles.tabText, activeTab === value && styles.activeTabText]}>
        {title}
      </Text>
    </TouchableOpacity>
  );

  const renderCompanyInfo = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>{t('settings.company_info')}</Text>
      
      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.company_name')}</Text>
        <TextInput
          style={styles.input}
          value={companyInfo.name}
          onChangeText={(text) => setCompanyInfo(prev => ({ ...prev, name: text }))}
          placeholder={t('settings.company_name')}
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('common.email')}</Text>
        <TextInput
          style={styles.input}
          value={companyInfo.email}
          onChangeText={(text) => setCompanyInfo(prev => ({ ...prev, email: text }))}
          placeholder={t('auth.email_placeholder')}
          keyboardType="email-address"
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('clients.client_phone')}</Text>
        <TextInput
          style={styles.input}
          value={companyInfo.phone}
          onChangeText={(text) => setCompanyInfo(prev => ({ ...prev, phone: text }))}
          placeholder={t('clients.client_phone')}
          keyboardType="phone-pad"
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.tax_id')}</Text>
        <TextInput
          style={styles.input}
          value={companyInfo.tax_id}
          onChangeText={(text) => setCompanyInfo(prev => ({ ...prev, tax_id: text }))}
          placeholder={t('settings.tax_id')}
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('clients.client_address')}</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={companyInfo.address}
          onChangeText={(text) => setCompanyInfo(prev => ({ ...prev, address: text }))}
          placeholder={t('clients.client_address')}
          multiline
          numberOfLines={3}
        />
      </View>
    </View>
  );

  const renderInvoiceSettings = () => (
    <View style={styles.tabContent}>
      <Text style={styles.sectionTitle}>{t('settings.invoice_settings')}</Text>
      
      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.invoice_prefix')}</Text>
        <TextInput
          style={styles.input}
          value={invoiceSettings.prefix}
          onChangeText={(text) => setInvoiceSettings(prev => ({ ...prev, prefix: text }))}
          placeholder="e.g., INV-"
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.next_invoice_number')}</Text>
        <TextInput
          style={styles.input}
          value={invoiceSettings.next_number}
          onChangeText={(text) => setInvoiceSettings(prev => ({ ...prev, next_number: text }))}
          placeholder="e.g., 0001"
          keyboardType="numeric"
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.default_terms')}</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={invoiceSettings.terms}
          onChangeText={(text) => setInvoiceSettings(prev => ({ ...prev, terms: text }))}
          placeholder={t('settings.default_terms')}
          multiline
          numberOfLines={4}
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>{t('settings.default_notes')}</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={invoiceSettings.notes || ''}
          onChangeText={(text) => setInvoiceSettings(prev => ({ ...prev, notes: text }))}
          placeholder={t('settings.default_notes')}
          multiline
          numberOfLines={2}
        />
      </View>

      <View style={styles.switchGroup}>
        <View style={styles.switchItem}>
          <View style={styles.switchContent}>
            <Text style={styles.switchLabel}>{t('settings.send_copy')}</Text>
            <Text style={styles.switchDescription}>{t('settings.send_copy_description')}</Text>
          </View>
          <Switch
            value={invoiceSettings.send_copy}
            onValueChange={(value) => setInvoiceSettings(prev => ({ ...prev, send_copy: value }))}
          />
        </View>

        <View style={styles.switchItem}>
          <View style={styles.switchContent}>
            <Text style={styles.switchLabel}>{t('settings.auto_reminders')}</Text>
            <Text style={styles.switchDescription}>{t('settings.auto_reminders_description')}</Text>
          </View>
          <Switch
            value={invoiceSettings.auto_reminders}
            onValueChange={(value) => setInvoiceSettings(prev => ({ ...prev, auto_reminders: value }))}
          />
        </View>
      </View>
    </View>
  );

  const renderDiscountRules = () => (
    <View style={styles.tabContent}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{t('settings.discount_rules')}</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => {
            setEditingDiscountRule(null);
            setShowDiscountRuleModal(true);
          }}
        >
          <Ionicons name="add" size={20} color="#FFFFFF" />
          <Text style={styles.addButtonText}>{t('settings.tabs.add_rule')}</Text>
        </TouchableOpacity>
      </View>

      {discountRules.map((rule) => (
        <View key={rule.id} style={styles.ruleItem}>
          <View style={styles.ruleContent}>
            <Text style={styles.ruleName}>{rule.name}</Text>
            <Text style={styles.ruleDetails}>
              Min: ${rule.min_amount} | {rule.discount_type === 'percentage' ? `${rule.discount_value}%` : `$${rule.discount_value}`}
            </Text>
            <Text style={styles.ruleCurrency}>Currency: {rule.currency}</Text>
          </View>
          <View style={styles.ruleActions}>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={() => {
                setEditingDiscountRule(rule);
                setShowDiscountRuleModal(true);
              }}
            >
              <Ionicons name="create-outline" size={16} color="#3B82F6" />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={() => handleDeleteDiscountRule(rule.id)}
            >
              <Ionicons name="trash-outline" size={16} color="#EF4444" />
            </TouchableOpacity>
          </View>
        </View>
      ))}

      {discountRules.length === 0 && (
        <View style={styles.emptyState}>
          <Ionicons name="pricetag-outline" size={48} color="#9CA3AF" />
          <Text style={styles.emptyStateText}>{t('settings.no_discount_rules_configured')}</Text>
          <Text style={styles.emptyStateSubtext}>{t('settings.create_discount_rules_to_apply_discounts')}</Text>
        </View>
      )}
    </View>
  );

  const renderDiscountRuleModal = () => (
    <Modal
      visible={showDiscountRuleModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowDiscountRuleModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>
            {editingDiscountRule ? t('settings.tabs.edit_discount_rule') : t('settings.tabs.create_discount_rule')}
          </Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t('settings.tabs.rule_name')}</Text>
            <TextInput
              style={styles.input}
              value={editingDiscountRule ? editingDiscountRule.name : newDiscountRule.name}
                             onChangeText={(text: string) => {
                 if (editingDiscountRule) {
                   setEditingDiscountRule((prev: DiscountRule | null) => prev ? { ...prev, name: text } : null);
                 } else {
                   setNewDiscountRule((prev: DiscountRuleCreate) => ({ ...prev, name: text }));
                 }
               }}
              placeholder={t('settings.rule_name_placeholder')}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t('settings.tabs.min_amount')}</Text>
            <TextInput
              style={styles.input}
              value={String(editingDiscountRule ? editingDiscountRule.min_amount : newDiscountRule.min_amount)}
                             onChangeText={(text: string) => {
                 const value = parseFloat(text) || 0;
                 if (editingDiscountRule) {
                   setEditingDiscountRule((prev: DiscountRule | null) => prev ? { ...prev, min_amount: value } : null);
                 } else {
                   setNewDiscountRule((prev: DiscountRuleCreate) => ({ ...prev, min_amount: value }));
                 }
               }}
              placeholder="0.00"
              keyboardType="numeric"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t('settings.tabs.discount_type')}</Text>
            <View style={styles.radioGroup}>
              <TouchableOpacity
                style={[
                  styles.radioButton,
                  (editingDiscountRule ? editingDiscountRule.discount_type : newDiscountRule.discount_type) === 'percentage' && styles.radioButtonActive
                ]}
                                 onPress={() => {
                   if (editingDiscountRule) {
                     setEditingDiscountRule((prev: DiscountRule | null) => prev ? { ...prev, discount_type: 'percentage' } : null);
                   } else {
                     setNewDiscountRule((prev: DiscountRuleCreate) => ({ ...prev, discount_type: 'percentage' }));
                   }
                 }}
              >
                <Text style={styles.radioButtonText}>{t('settings.tabs.discount_type_percentage')}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.radioButton,
                  (editingDiscountRule ? editingDiscountRule.discount_type : newDiscountRule.discount_type) === 'fixed' && styles.radioButtonActive
                ]}
                                 onPress={() => {
                   if (editingDiscountRule) {
                     setEditingDiscountRule((prev: DiscountRule | null) => prev ? { ...prev, discount_type: 'fixed' } : null);
                   } else {
                     setNewDiscountRule((prev: DiscountRuleCreate) => ({ ...prev, discount_type: 'fixed' }));
                   }
                 }}
              >
                <Text style={styles.radioButtonText}>{t('settings.tabs.discount_type_fixed')}</Text>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>{t('settings.tabs.discount_value')}</Text>
            <TextInput
              style={styles.input}
              value={String(editingDiscountRule ? editingDiscountRule.discount_value : newDiscountRule.discount_value)}
                             onChangeText={(text: string) => {
                 const value = parseFloat(text) || 0;
                 if (editingDiscountRule) {
                   setEditingDiscountRule((prev: DiscountRule | null) => prev ? { ...prev, discount_value: value } : null);
                 } else {
                   setNewDiscountRule((prev: DiscountRuleCreate) => ({ ...prev, discount_value: value }));
                 }
               }}
              placeholder="0.00"
              keyboardType="numeric"
            />
          </View>

          <View style={styles.modalButtons}>
            <TouchableOpacity
              style={[styles.button, styles.cancelButton]}
              onPress={() => setShowDiscountRuleModal(false)}
            >
              <Text style={styles.cancelButtonText}>{t('common.cancel')}</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.button, styles.saveButton]}
              onPress={editingDiscountRule ? handleUpdateDiscountRule : handleCreateDiscountRule}
            >
              <Text style={styles.saveButtonText}>
                {editingDiscountRule ? t('common.update') : t('settings.create')}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>{t('settings.loading')}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('settings.title')}</Text>
        <TouchableOpacity
          style={[styles.saveButton, saving && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.saveButtonText}>{t('common.save')}</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.tabBar}>
        <TabButton title={t('settings.tabs.company')} value="company" icon="business-outline" />
        <TabButton title={t('settings.tabs.invoices')} value="invoices" icon="document-text-outline" />
        <TabButton title={t('settings.tabs.discount_rules')} value="discounts" icon="pricetag-outline" />
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {activeTab === 'company' && renderCompanyInfo()}
        {activeTab === 'invoices' && renderInvoiceSettings()}
        {activeTab === 'discounts' && renderDiscountRules()}

        <View style={styles.section}>
          <View style={styles.settingItem}>
            <View style={styles.settingIcon}>
              <Ionicons name="language-outline" size={20} color="#3B82F6" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.settingText}>{t('settings.language')}</Text>
            </View>
            <LanguageSwitcher style={{ marginLeft: 'auto' }} />
          </View>
          
          <TouchableOpacity style={styles.settingItem} onPress={onNavigateToUsers}>
            <View style={styles.settingIcon}>
              <Ionicons name="people-outline" size={20} color="#3B82F6" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.settingText}>{t('users.title')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>
          
          <TouchableOpacity style={styles.settingItem} onPress={onNavigateToAuditLog}>
            <View style={styles.settingIcon}>
              <Ionicons name="document-text-outline" size={20} color="#3B82F6" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.settingText}>{t('auditLog.title')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.settingItem, styles.logoutButton]}
            onPress={handleSignOut}
          >
            <View style={styles.settingIcon}>
              <Ionicons name="log-out-outline" size={20} color="#EF4444" />
            </View>
            <View style={styles.settingContent}>
              <Text style={styles.logoutText}>{t('auth.logout')}</Text>
            </View>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {renderDiscountRuleModal()}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
  },
  saveButton: {
    backgroundColor: '#10B981',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  saveButtonDisabled: {
    backgroundColor: '#6B7280',
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  tabButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 8,
  },
  activeTabButton: {
    borderBottomWidth: 2,
    borderBottomColor: '#3B82F6',
  },
  tabText: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
  activeTabText: {
    color: '#3B82F6',
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  tabContent: {
    padding: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#111827',
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  switchGroup: {
    marginTop: 20,
  },
  switchItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  switchContent: {
    flex: 1,
    marginRight: 16,
  },
  switchLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 4,
  },
  switchDescription: {
    fontSize: 14,
    color: '#6B7280',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3B82F6',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    gap: 4,
  },
  addButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  ruleItem: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    flexDirection: 'row',
    alignItems: 'center',
  },
  ruleContent: {
    flex: 1,
  },
  ruleName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 4,
  },
  ruleDetails: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 2,
  },
  ruleCurrency: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  ruleActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    padding: 8,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyStateText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginTop: 12,
    marginBottom: 4,
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    paddingHorizontal: 20,
  },
  section: {
    backgroundColor: '#FFFFFF',
    marginTop: 20,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#E5E7EB',
  },
  settingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
  },
  settingIcon: {
    width: 24,
    marginRight: 12,
    alignItems: 'center',
  },
  settingContent: {
    flex: 1,
  },
  settingText: {
    fontSize: 16,
    color: '#374151',
    fontWeight: '500',
  },
  logoutButton: {
    justifyContent: 'flex-start',
  },
  logoutText: {
    fontSize: 16,
    color: '#EF4444',
    fontWeight: '600',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 20,
    width: '90%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 20,
    textAlign: 'center',
  },
  radioGroup: {
    flexDirection: 'row',
    gap: 12,
  },
  radioButton: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 6,
    padding: 12,
    alignItems: 'center',
  },
  radioButtonActive: {
    borderColor: '#3B82F6',
    backgroundColor: '#EFF6FF',
  },
  radioButtonText: {
    fontSize: 14,
    color: '#374151',
    fontWeight: '500',
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
  },
  button: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 8,
  },
  cancelButton: {
    backgroundColor: '#F3F4F6',
  },
  cancelButtonText: {
    color: '#374151',
    fontWeight: '600',
  },
});

export default SettingsScreen; 