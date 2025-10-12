import React, { useState, useEffect } from 'react';
import { logger } from '../utils/logger';
import { Invoice } from '../services/api';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTranslation } from 'react-i18next';
import DateTimePicker from '@react-native-community/datetimepicker';
import apiService, { CreateClientData, CreateInvoiceData, Client, Settings, DiscountRule } from '../services/api';
import { formatCurrency, getCurrencySymbol, parseCurrencyAmount } from '../utils/currency';
import { formatDate, safeParseDateString } from '../utils/date';
import EnhancedFileUpload from '../components/EnhancedFileUpload';
import { FileData } from '../components/FileUpload';

interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  price: number;
  amount: number;
}

interface NewInvoiceFormData {
  client_id: number;
  number: string;
  currency: string;
  date: string;
  due_date: string;
  status: string;
  paid_amount: number;
  items: InvoiceItem[];
  notes: string;
  is_recurring?: boolean;
  recurring_frequency?: string;
  discount_type?: string;
  discount_value?: number;
}

interface NewInvoiceScreenProps {
  clients: Client[];
  onSaveInvoice: (formData: CreateInvoiceData) => Promise<Invoice>;
  onNavigateBack: () => void;
}

const NewInvoiceScreen: React.FC<NewInvoiceScreenProps> = ({
  clients: propClients,
  onSaveInvoice,
  onNavigateBack,
}) => {
  const { t } = useTranslation();
  
  const getLocalDateString = (date: Date = new Date()) => {
    try {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    } catch (error) {
      console.error('Error in getLocalDateString:', error);
      return '2025-01-01'; // Fallback date
    }
  };

  // Convert date string to Date object
  const getDateFromString = (dateString: string): Date => {
    try {
      const [year, month, day] = dateString.split('-').map(Number);
      return new Date(year, month - 1, day);
    } catch (error) {
      console.error('Error converting date string:', error);
      return new Date();
    }
  };

  const [formData, setFormData] = useState<NewInvoiceFormData>({
    client_id: 0,
    number: '',
    currency: 'USD',
    date: getLocalDateString(),
    due_date: (() => {
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 30);
      return getLocalDateString(futureDate);
    })(),
    status: 'pending',
    paid_amount: 0,
    items: [{ id: 1, description: '', quantity: 1, price: 0, amount: 0 }],
    notes: '',
    is_recurring: false,
    recurring_frequency: 'monthly',
    discount_type: 'percentage',
    discount_value: 0,
  });

  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showClientModal, setShowClientModal] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showDueDatePicker, setShowDueDatePicker] = useState(false);
  

  const [showCurrencyModal, setShowCurrencyModal] = useState(false);
  const [currentDateField, setCurrentDateField] = useState<'date' | 'due_date'>('date');
  const [error, setError] = useState<string | null>(null);
  const [clients, setClients] = useState(propClients);
  const [showAddClientModal, setShowAddClientModal] = useState(false);
  const [addClientForm, setAddClientForm] = useState({ name: '', email: '', phone: '', address: '', preferred_currency: '' });
  const [addClientLoading, setAddClientLoading] = useState(false);
  const [addClientError, setAddClientError] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [tenantInfo, setTenantInfo] = useState<{ default_currency: string } | null>(null);
  const [appliedDiscountRule, setAppliedDiscountRule] = useState<DiscountRule | null>(null);

  // Attachment file management
  const [attachmentFiles, setAttachmentFiles] = useState<FileData[]>([]);
  const [uploadingAttachments, setUploadingAttachments] = useState(false);

  // Load settings and discount rules
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [settingsData, discountRulesData, tenantData] = await Promise.all([
          apiService.getSettings(),
          apiService.getDiscountRules(),
          apiService.getTenantInfo()
        ]);
        setSettings(settingsData);
        setDiscountRules(discountRulesData);
        setTenantInfo(tenantData);
        
        // Auto-generate invoice number
        if (settingsData?.invoice_settings) {
          const { prefix, next_number } = settingsData.invoice_settings;
          const invoiceNumber = `${prefix}${next_number}`;
          setFormData(prev => ({ ...prev, number: invoiceNumber }));
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  // Update addClientForm when tenant info is loaded
  useEffect(() => {
    if (tenantInfo && tenantInfo.default_currency) {
      setAddClientForm(prev => ({
        ...prev,
        preferred_currency: tenantInfo.default_currency
      }));
    }
  }, [tenantInfo]);

  // Ensure correct currency when modal opens
  useEffect(() => {
    if (showAddClientModal && tenantInfo) {
      setAddClientForm(prev => ({
        ...prev,
        preferred_currency: tenantInfo.default_currency || 'USD'
      }));
    }
  }, [showAddClientModal, tenantInfo]);

  const handleChange = (field: keyof NewInvoiceFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    if (error) setError(null);
  };

  const isValidDate = (dateString: string): boolean => {
    // Allow empty or partial dates during input
    if (!dateString || dateString.length < 10) {
      return dateString.length === 0 || /^\d{0,4}(-\d{0,2}(-\d{0,2})?)?$/.test(dateString);
    }

    // Check format first
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
      return false;
    }

    const [year, month, day] = dateString.split('-').map(Number);
    
    // Check basic ranges
    if (year < 1900 || year > 2100) return false;
    if (month < 1 || month > 12) return false;
    if (day < 1 || day > 31) return false;

    // Create date and check if it's valid (handles leap years, month lengths, etc.)
    try {
      const date = new Date(year, month - 1, day);
      if (isNaN(date.getTime())) {
        return false;
      }
      return date.getFullYear() === year && 
             date.getMonth() === month - 1 && 
             date.getDate() === day;
    } catch (error) {
      console.error('Date validation error:', error);
      return false;
    }
  };

  const handleDateChange = (field: 'date' | 'due_date', value: string) => {
    // Allow partial input for better UX
    let formattedValue = value;
    
    // Auto-format as user types
    if (value.length === 4 && !value.includes('-')) {
      formattedValue = value + '-';
    } else if (value.length === 7 && value.charAt(4) === '-' && value.charAt(6) !== '-') {
      formattedValue = value + '-';
    }
    
    // Remove any non-digit characters except hyphens
    formattedValue = formattedValue.replace(/[^\d-]/g, '');
    
    // Limit to 10 characters (YYYY-MM-DD)
    if (formattedValue.length > 10) {
      formattedValue = formattedValue.substring(0, 10);
    }

    handleChange(field, formattedValue);
  };

  const handleItemChange = (index: number, field: keyof InvoiceItem, value: any) => {
    const newItems = [...formData.items];
    newItems[index] = {
      ...newItems[index],
      [field]: value,
    };

    // Calculate amount for this item
    if (field === 'quantity' || field === 'price') {
      const quantity = field === 'quantity' ? value : newItems[index].quantity;
      const price = field === 'price' ? value : newItems[index].price;
      newItems[index].amount = quantity * price;
    }

    handleChange('items', newItems);
  };

  const addItem = () => {
    const newItem: InvoiceItem = {
      id: Date.now(),
      description: '',
      quantity: 1,
      price: 0,
      amount: 0,
    };
    handleChange('items', [...formData.items, newItem]);
  };

  const removeItem = (index: number) => {
    if ((formData.items || []).length > 1) {
      const newItems = (formData.items || []).filter((_, i) => i !== index);
      handleChange('items', newItems);
    }
  };

  const calculateSubtotal = () => {
    return formData.items.reduce((sum, item) => sum + item.amount, 0);
  };

  const calculateDiscount = () => {
    if (formData.discount_type === 'percentage') {
      return (calculateSubtotal() * (formData.discount_value || 0)) / 100;
    } else if (formData.discount_type === 'fixed') {
      return formData.discount_value || 0;
    }
    return 0;
  };

  const calculateTotal = () => {
    const subtotal = calculateSubtotal();
    const discount = calculateDiscount();
    return Math.max(0, subtotal - (discount || 0));
  };

  const applyDiscountRules = async () => {
    try {
      const subtotal = calculateSubtotal();
      if (subtotal > 0) {
        const discountCalculation = await apiService.calculateDiscount(subtotal, formData.currency);
        if (discountCalculation.discount_type !== 'none') {
          setAppliedDiscountRule(discountCalculation.applied_rule as DiscountRule);
          handleChange('discount_type', discountCalculation.discount_type);
          handleChange('discount_value', discountCalculation.discount_value);
        }
      }
    } catch (error) {
      console.error('Failed to apply discount rules:', error);
    }
  };

  const validateForm = (): boolean => {
    if (!formData.client_id) {
      setError('Please select a client');
      return false;
    }
    
    if (!formData.number.trim()) {
      setError('Invoice number is required');
      return false;
    }
    
    if (!formData.date) {
      setError('Invoice date is required');
      return false;
    }
    
    if (!formData.due_date) {
      setError('Due date is required');
      return false;
    }
    
    // Simple date comparison since date picker ensures valid dates
    const invoiceDate = getDateFromString(formData.date);
    const dueDate = getDateFromString(formData.due_date);
    
    if (dueDate < invoiceDate) {
      setError('Due date cannot be earlier than invoice date');
      return false;
    }
    if (formData.items.some(item => !item.description.trim())) {
      setError('All items must have a description');
      return false;
    }
    if (formData.items.some(item => item.price <= 0)) {
      setError('All items must have a price greater than 0');
      return false;
    }
    if (calculateTotal() <= 0) {
      setError('Invoice total must be greater than 0');
      return false;
    }
    if (formData.paid_amount > calculateTotal()) {
      setError('Paid amount cannot exceed invoice total');
      return false;
    }
    return true;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const invoiceData: CreateInvoiceData = {
        client_id: formData.client_id,
        amount: calculateTotal(),
        currency: formData.currency,
        date: formData.date,
        due_date: formData.due_date,
        status: formData.status as any,
        notes: formData.notes,
        items: formData.items.map(item => ({
          description: item.description,
          quantity: item.quantity,
          price: item.price,
        })),
        is_recurring: formData.is_recurring,
        recurring_frequency: formData.recurring_frequency,
        discount_type: formData.discount_type || 'percentage',
        discount_value: formData.discount_value || 0,
        paid_amount: formData.paid_amount,
      };

      const newInvoice = await onSaveInvoice(invoiceData);

      // Upload attachments if any
      if (attachmentFiles.length > 0) {
        setUploadingAttachments(true);
        try {
          await Promise.all(
            attachmentFiles.map(file => uploadAttachmentToInvoice(newInvoice.id, file))
          );
        } catch (uploadError) {
          console.error('Failed to upload attachments:', uploadError);
          Alert.alert('Warning', 'Invoice created but some attachments failed to upload. You can upload them later.');
        } finally {
          setUploadingAttachments(false);
        }
      }
    } catch (error: any) {
      setError(error.message || 'Failed to save invoice');
    } finally {
      setSubmitting(false);
    }
  };

  const uploadAttachmentToInvoice = async (invoiceId: number, file: FileData) => {
    const formData = new FormData();
    formData.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.type,
    } as any);

    // Make direct API call since we need to handle FormData
    const token = await AsyncStorage.getItem('auth_token');
    const userData = await AsyncStorage.getItem('user_data');
    const user = userData ? JSON.parse(userData) : null;
    const tenantId = user?.tenant_id;

    // Get the API base URL from the apiService
    const apiService = await import('../services/api');
    const API_BASE_URL = apiService.default.baseURL;

    const response = await fetch(`${API_BASE_URL}/invoices/${invoiceId}/upload-attachment`, {
      method: 'POST',
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...(tenantId && { 'X-Tenant-ID': tenantId }),
      },
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  };

  const handleFilesSelected = (files: FileData[]) => {
    setAttachmentFiles(prev => [...prev, ...files]);
  };

  const handleRemoveFile = (index: number) => {
    setAttachmentFiles(prev => prev.filter((_, i) => i !== index));
  };

  const formatCurrencyDisplay = (amount: number) => {
    return formatCurrency(amount, formData.currency);
  };

  const handleAddClient = async () => {
    if (!addClientForm.name.trim() || !addClientForm.email.trim()) {
      setAddClientError('Name and email are required');
      return;
    }
    setAddClientLoading(true);
    setAddClientError(null);

    try {
      // Ensure preferred_currency is set before creating client
      const clientData = {
        ...addClientForm,
        preferred_currency: addClientForm.preferred_currency || tenantInfo?.default_currency || 'USD'
      };
      logger.debug("Creating client with data", clientData);
      
      const newClient = await apiService.createClient(clientData);
      logger.debug("Created client", newClient);
      
      setClients(prev => [...prev, newClient]);
      setShowAddClientModal(false);
      setAddClientForm({ name: '', email: '', phone: '', address: '', preferred_currency: tenantInfo?.default_currency || 'USD' });
      
      // Auto-select the new client
      handleChange('client_id', newClient.id);
      
      // Set currency to client's preferred currency when client is created
      if (newClient.preferred_currency) {
        logger.debug("Setting currency to newly created client's preferred currency", newClient.preferred_currency);
        handleChange('currency', newClient.preferred_currency);
      }
    } catch (error: any) {
      setAddClientError(error.message || 'Failed to create client');
    } finally {
      setAddClientLoading(false);
    }
  };

  const selectedClient = clients.find(client => client.id === formData.client_id);

  const renderAddClientModal = () => (
    <Modal
      visible={showAddClientModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowAddClientModal(false)}
    >
      <TouchableOpacity 
        style={styles.modalOverlay}
        activeOpacity={1}
        onPress={() => setShowAddClientModal(false)}
      >
        <TouchableOpacity 
          style={[styles.modalContent, styles.addClientModalContent]}
          activeOpacity={1}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{t('clients.add_new_client')}</Text>
            <TouchableOpacity onPress={() => setShowAddClientModal(false)}>
              <Ionicons name="close" size={24} color="#6B7280" />
            </TouchableOpacity>
          </View>
          
          <ScrollView style={styles.addClientModalBody} showsVerticalScrollIndicator={false}>
            {/* Name Field */}
            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>{t('clients.client_name')} *</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="person-outline" size={20} color="#6B7280" style={styles.inputIcon} />
                <TextInput
                  style={styles.modalInput}
                  placeholder={t('clients.enter_name')}
                  value={addClientForm.name}
                  onChangeText={(text) => setAddClientForm(prev => ({ ...prev, name: text }))}
                  placeholderTextColor="#9CA3AF"
                />
              </View>
            </View>

            {/* Email Field */}
            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>{t('clients.client_email')} *</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="mail-outline" size={20} color="#6B7280" style={styles.inputIcon} />
                <TextInput
                  style={styles.modalInput}
                  placeholder={t('clients.enter_email')}
                  value={addClientForm.email}
                  onChangeText={(text) => setAddClientForm(prev => ({ ...prev, email: text }))}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  placeholderTextColor="#9CA3AF"
                />
              </View>
            </View>

            {/* Phone Field */}
            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>{t('clients.client_phone')} ({t('common.optional')})</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="call-outline" size={20} color="#6B7280" style={styles.inputIcon} />
                <TextInput
                  style={styles.modalInput}
                  placeholder={t('clients.enter_phone')}
                  value={addClientForm.phone}
                  onChangeText={(text) => setAddClientForm(prev => ({ ...prev, phone: text }))}
                  keyboardType="phone-pad"
                  placeholderTextColor="#9CA3AF"
                />
              </View>
            </View>

            {/* Address Field */}
            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>{t('clients.client_address')} ({t('common.optional')})</Text>
              <View style={[styles.inputContainer, styles.textAreaContainer]}>
                <Ionicons name="location-outline" size={20} color="#6B7280" style={[styles.inputIcon, styles.textAreaIcon]} />
                <TextInput
                  style={[styles.modalInput, styles.textAreaInput]}
                  placeholder={t('clients.enter_address')}
                  value={addClientForm.address}
                  onChangeText={(text) => setAddClientForm(prev => ({ ...prev, address: text }))}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                  placeholderTextColor="#9CA3AF"
                />
              </View>
            </View>

            {/* Preferred Currency Field */}
            <View style={styles.formField}>
              <Text style={styles.fieldLabel}>{t('clients.preferred_currency')}</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="card-outline" size={20} color="#6B7280" style={styles.inputIcon} />
                <Text style={styles.modalInput}>
                  {addClientForm.preferred_currency || tenantInfo?.default_currency || 'USD'}
                </Text>
              </View>
              <Text style={styles.fieldHint}>{t('clients.currency_hint')}</Text>
            </View>

            {addClientError && (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={20} color="#EF4444" />
                <Text style={styles.errorText}>{addClientError}</Text>
              </View>
            )}
          </ScrollView>

          <View style={styles.modalFooter}>
            <TouchableOpacity
              style={[styles.button, styles.cancelButton]}
              onPress={() => setShowAddClientModal(false)}
            >
              <Text style={styles.cancelButtonText}>{t('common.cancel')}</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.button, styles.primaryButton, addClientLoading && styles.buttonDisabled]}
              onPress={handleAddClient}
              disabled={addClientLoading}
            >
              {addClientLoading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="add" size={18} color="#FFFFFF" />
                  <Text style={styles.primaryButtonText}>{t('clients.add_client')}</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );

  const renderClientSelector = () => (
    <View style={styles.formGroup}>
      <Text style={styles.label}>{t('invoices.client')} *</Text>
      <View style={styles.clientSelectorContainer}>
        <TouchableOpacity
          style={[styles.selector, styles.clientSelector]}
          onPress={() => setShowClientModal(true)}
        >
          <View style={styles.clientSelectorContent}>
            <Ionicons name="person-outline" size={20} color="#6B7280" />
            <Text style={[selectedClient ? styles.selectorText : styles.placeholderText, styles.clientSelectorText]}>
              {selectedClient ? selectedClient.name : t('invoices.select_client')}
            </Text>
          </View>
          <Ionicons name="chevron-down" size={20} color="#6B7280" />
        </TouchableOpacity>
        
        <TouchableOpacity
          style={styles.addClientButton}
          onPress={() => setShowAddClientModal(true)}
        >
          <Ionicons name="add" size={20} color="#FFFFFF" />
          <Text style={styles.addClientText}>{t('invoices.add_new_client')}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  const renderDateSelector = () => (
    <View style={styles.formGroup}>
      <Text style={styles.label}>Invoice Date *</Text>
      <TouchableOpacity
        style={[styles.selector, loading && styles.buttonDisabled]}
        onPress={() => {
          if (loading) return;
          setShowDatePicker(true);
        }}
        disabled={loading}
      >
        <Text style={styles.selectorText}>
          {formatDate(formData.date)}
        </Text>
        <Ionicons name="calendar-outline" size={20} color="#6B7280" />
      </TouchableOpacity>
    </View>
  );

  const renderDueDateSelector = () => (
    <View style={styles.formGroup}>
      <Text style={styles.label}>Due Date *</Text>
      <TouchableOpacity
        style={[styles.selector, loading && styles.buttonDisabled]}
        onPress={() => {
          if (loading) return;
          setShowDueDatePicker(true);
        }}
        disabled={loading}
      >
        <Text style={styles.selectorText}>
          {formatDate(formData.due_date)}
        </Text>
        <Ionicons name="calendar-outline" size={20} color="#6B7280" />
      </TouchableOpacity>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <StatusBar style="dark" />
      <View style={styles.header}>
        <TouchableOpacity onPress={onNavigateBack} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('invoices.new_invoice')}</Text>
        <TouchableOpacity
          style={[styles.saveButton, submitting && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {renderClientSelector()}
        {renderDateSelector()}
        {renderDueDateSelector()}

        <View style={styles.formGroup}>
          <Text style={styles.label}>Invoice Number *</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g., INV-001"
            value={formData.number}
            onChangeText={(text) => handleChange('number', text)}
          />
        </View>

        <View style={styles.formGroup}>
          <Text style={styles.label}>Currency</Text>
          <TouchableOpacity
            style={styles.selector}
            onPress={() => setShowCurrencyModal(true)}
          >
            <View style={styles.currencyDisplay}>
              <Text style={styles.currencySymbol}>
                {getCurrencySymbol(formData.currency)}
              </Text>
              <Text style={styles.currencyCode}>{formData.currency}</Text>
            </View>
            <Ionicons name="chevron-down" size={20} color="#6B7280" />
          </TouchableOpacity>
        </View>

        <View style={styles.formGroup}>
          <Text style={styles.label}>Items *</Text>
          {formData.items.map((item, index) => (
            <View key={item.id || index} style={styles.itemContainer}>
              <View style={styles.itemHeader}>
                <Text style={styles.itemNumber}>Item {index + 1}</Text>
                {formData.items.length > 1 && (
                  <TouchableOpacity
                    onPress={() => removeItem(index)}
                    style={styles.removeItemButton}
                  >
                    <Ionicons name="trash-outline" size={16} color="#EF4444" />
                  </TouchableOpacity>
                )}
              </View>
              
              <TextInput
                style={styles.input}
                placeholder={t('invoices.item_description')}
                value={item.description}
                onChangeText={(text) => handleItemChange(index, 'description', text)}
              />
              
              <View style={styles.itemRow}>
                <View style={styles.itemField}>
                  <Text style={styles.itemLabel}>{t('invoices.quantity')}</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="1"
                    value={item.quantity.toString()}
                    onChangeText={(text) => handleItemChange(index, 'quantity', parseFloat(text) || 0)}
                    keyboardType="numeric"
                  />
                </View>
                
                <View style={styles.itemField}>
                  <Text style={styles.itemLabel}>{t('invoices.price')}</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="0.00"
                    value={item.price.toString()}
                    onChangeText={(text) => handleItemChange(index, 'price', parseFloat(text) || 0)}
                    keyboardType="numeric"
                  />
                </View>
              </View>
              
              <View style={styles.itemTotal}>
                <Text style={styles.itemTotalLabel}>{t('invoices.total')}:</Text>
                <Text style={styles.itemTotalAmount}>
                  {formatCurrencyDisplay(item.amount)}
                </Text>
              </View>
            </View>
          ))}
          
          <TouchableOpacity style={styles.addItemButton} onPress={addItem}>
            <Ionicons name="add-circle-outline" size={20} color="#3B82F6" />
            <Text style={styles.addItemText}>{t('invoices.add_item')}</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.summaryContainer}>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{t('invoices.subtotal')}:</Text>
            <Text style={styles.summaryValue}>
              {formatCurrencyDisplay(calculateSubtotal())}
            </Text>
          </View>
          
          {calculateDiscount() > 0 && (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>{t('invoices.discount')}:</Text>
              <Text style={styles.summaryValue}>
                -{formatCurrencyDisplay(calculateDiscount())}
              </Text>
            </View>
          )}
          
          <View style={[styles.summaryRow, styles.totalRow]}>
            <Text style={styles.totalLabel}>{t('invoices.total')}:</Text>
            <Text style={styles.totalValue}>
              {formatCurrencyDisplay(calculateTotal())}
            </Text>
          </View>
        </View>

        <View style={styles.formGroup}>
          <Text style={styles.label}>{t('invoices.notes')}</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            placeholder="Add any additional notes..."
            value={formData.notes}
            onChangeText={(text) => handleChange('notes', text)}
            multiline
            numberOfLines={3}
          />
        </View>

        {/* Attachments */}
        <EnhancedFileUpload
          title="Attachments"
          maxFiles={5}
          allowedTypes={['image/*', 'application/pdf']}
          onFilesSelected={handleFilesSelected}
          selectedFiles={attachmentFiles}
          onRemoveFile={handleRemoveFile}
          uploading={uploadingAttachments}
        />
      </ScrollView>

      {renderAddClientModal()}
      
      {/* Client Selection Modal */}
      <Modal
        visible={showClientModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowClientModal(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowClientModal(false)}
        >
          <TouchableOpacity 
            style={[styles.modalContent, styles.clientModalContent]}
            activeOpacity={1}
            onPress={(e) => e.stopPropagation()}
          >
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('invoices.select_client')}</Text>
              <TouchableOpacity onPress={() => setShowClientModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            <View style={styles.clientModalBody}>
              {clients.length === 0 ? (
                <View style={styles.emptyState}>
                  <Ionicons name="people-outline" size={48} color="#9CA3AF" />
                  <Text style={styles.emptyStateText}>{t('invoices.no_clients_found')}</Text>
                  <Text style={styles.emptyStateSubtext}>{t('invoices.add_client_to_get_started')}</Text>
                </View>
              ) : (
                <ScrollView style={styles.clientsList} showsVerticalScrollIndicator={false}>
                  {clients.map((client, index) => (
                    <TouchableOpacity
                      key={client.id}
                      style={[
                        styles.clientOption,
                        formData.client_id === client.id && styles.clientOptionSelected,
                        index === clients.length - 1 && styles.clientOptionLast
                      ]}
                      onPress={() => {
                        handleChange('client_id', client.id);
                        
                        // Set currency to client's preferred currency when client is selected
                        if (client.preferred_currency) {
                          logger.debug("Setting currency to selected client's preferred currency", client.preferred_currency);
                          handleChange('currency', client.preferred_currency);
                        }
                        
                        setShowClientModal(false);
                      }}
                    >
                      <View style={styles.clientInfo}>
                        <View style={styles.clientAvatar}>
                          <Ionicons name="person" size={20} color="#6B7280" />
                        </View>
                        <View style={styles.clientDetails}>
                          <Text style={styles.clientName}>{client.name}</Text>
                          <Text style={styles.clientEmail}>{client.email}</Text>
                          {client.preferred_currency && (
                            <Text style={styles.clientCurrency}>
                              Currency: {client.preferred_currency}
                            </Text>
                          )}
                        </View>
                      </View>
                      {formData.client_id === client.id && (
                        <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                      )}
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              )}
              
              <TouchableOpacity
                style={styles.addClientFromModal}
                onPress={() => {
                  setShowClientModal(false);
                  setShowAddClientModal(true);
                }}
              >
                <Ionicons name="add-circle" size={20} color="#3B82F6" />
                <Text style={styles.addClientFromModalText}>{t('invoices.add_new_client')}</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
      
      {/* Native Date Picker Modal */}
      <Modal
        visible={showDatePicker}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setShowDatePicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('invoices.select_date')}</Text>
              <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            <DateTimePicker
              value={getDateFromString(formData.date)}
              mode="date"
              display="spinner"
              onChange={(event, selectedDate) => {
                if (selectedDate) {
                  const dateString = getLocalDateString(selectedDate);
                  setFormData(prev => ({ ...prev, date: dateString }));
                }
                setShowDatePicker(false);
              }}
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={[styles.button, styles.cancelButton]}
                onPress={() => setShowDatePicker(false)}
              >
                <Text style={styles.cancelButtonText}>{t('common.cancel')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
      
      {/* Native Due Date Picker Modal */}
      <Modal
        visible={showDueDatePicker}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setShowDueDatePicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('invoices.select_due_date')}</Text>
              <TouchableOpacity onPress={() => setShowDueDatePicker(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            
            <DateTimePicker
              value={getDateFromString(formData.due_date)}
              mode="date"
              display="spinner"
              minimumDate={getDateFromString(formData.date)}
              onChange={(event, selectedDate) => {
                if (selectedDate) {
                  const dateString = getLocalDateString(selectedDate);
                  setFormData(prev => ({ ...prev, due_date: dateString }));
                }
                setShowDueDatePicker(false);
              }}
            />

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={[styles.button, styles.cancelButton]}
                onPress={() => setShowDueDatePicker(false)}
              >
                <Text style={styles.cancelButtonText}>{t('common.cancel')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
      
      {/* Currency Selection Modal */}
      <Modal
        visible={showCurrencyModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowCurrencyModal(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowCurrencyModal(false)}
        >
          <TouchableOpacity 
            style={styles.modalContent}
            activeOpacity={1}
            onPress={(e) => e.stopPropagation()}
          >
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('invoices.select_currency')}</Text>
              <TouchableOpacity onPress={() => setShowCurrencyModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>
            <View style={styles.currencyModalBody}>
              <Text style={styles.modalSubtitle}>{t('invoices.currency_selection_subtitle')}</Text>
              <ScrollView style={styles.currencyList} showsVerticalScrollIndicator={false}>
                {[
                  { code: 'USD', name: 'US Dollar', symbol: '$' },
                  { code: 'EUR', name: 'Euro', symbol: '€' },
                  { code: 'GBP', name: 'British Pound', symbol: '£' },
                  { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$' },
                  { code: 'AUD', name: 'Australian Dollar', symbol: 'A$' },
                  { code: 'JPY', name: 'Japanese Yen', symbol: '¥' }
                ].map((currency, index) => (
                  <TouchableOpacity
                    key={currency.code}
                    style={[
                      styles.currencyOption,
                      formData.currency === currency.code && styles.currencyOptionSelected,
                      index === 5 && styles.currencyOptionLast
                    ]}
                    onPress={() => {
                      handleChange('currency', currency.code);
                      setShowCurrencyModal(false);
                    }}
                  >
                    <View style={styles.currencyInfo}>
                      <View style={styles.currencySymbol}>
                        <Text style={styles.currencySymbolText}>{currency.symbol}</Text>
                      </View>
                      <View style={styles.currencyDetails}>
                        <Text style={styles.currencyCode}>{currency.code}</Text>
                        <Text style={styles.currencyName}>{currency.name}</Text>
                      </View>
                    </View>
                    {formData.currency === currency.code && (
                      <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                    )}
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
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
  content: {
    flex: 1,
    padding: 20,
  },

  errorText: {
    color: '#EF4444',
    fontSize: 14,
  },
  formGroup: {
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
  selector: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  selectorText: {
    fontSize: 16,
    color: '#111827',
  },
  placeholderText: {
    fontSize: 16,
    color: '#9CA3AF',
  },
  clientSelectorContainer: {
    gap: 12,
  },
  clientSelector: {
    flex: 1,
  },
  clientSelectorContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  clientSelectorText: {
    marginLeft: 8,
    flex: 1,
  },
  addClientButton: {
    backgroundColor: '#3B82F6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    shadowColor: '#3B82F6',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  addClientText: {
    marginLeft: 8,
    fontSize: 14,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  currencySelector: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    padding: 12,
  },

  itemContainer: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  itemNumber: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  removeItemButton: {
    padding: 4,
  },
  itemRow: {
    flexDirection: 'row',
    gap: 12,
  },
  itemField: {
    flex: 1,
  },
  itemLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  itemTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  itemTotalLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  itemTotalAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#111827',
  },
  addItemButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderWidth: 2,
    borderColor: '#3B82F6',
    borderStyle: 'dashed',
    borderRadius: 8,
    marginTop: 8,
  },
  addItemText: {
    marginLeft: 8,
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  summaryContainer: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  totalRow: {
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    paddingTop: 8,
    marginTop: 8,
  },
  totalLabel: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#111827',
  },
  totalValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#10B981',
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
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
  statusOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  statusOptionSelected: {
    backgroundColor: '#f0f9ff',
  },
  statusOptionText: {
    fontSize: 16,
    color: '#333',
  },
  statusOptionTextSelected: {
    color: '#007AFF',
    fontWeight: '600',
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
  clientModalContent: {
    maxHeight: '85%',
    minHeight: '60%',
  },
  clientModalBody: {
    flex: 1,
    padding: 20,
  },
  clientsList: {
    flex: 1,
    marginBottom: 16,
  },
  clientOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
    backgroundColor: '#FFFFFF',
  },
  clientOptionSelected: {
    backgroundColor: '#F0F9FF',
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
  },
  clientOptionLast: {
    borderBottomWidth: 0,
  },
  clientInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  clientAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  clientDetails: {
    flex: 1,
  },
  clientName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 2,
  },
  clientEmail: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 2,
  },
  clientCurrency: {
    fontSize: 12,
    color: '#9CA3AF',
    fontStyle: 'italic',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  emptyStateText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 12,
    marginBottom: 4,
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
  },
  addClientFromModal: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#E2E8F0',
    borderStyle: 'dashed',
  },
  addClientFromModalText: {
    marginLeft: 8,
    fontSize: 16,
    color: '#3B82F6',
    fontWeight: '600',
  },
  addClientModalContent: {
    maxHeight: '90%',
    minHeight: '70%',
  },
  addClientModalBody: {
    flex: 1,
    padding: 20,
  },
  formField: {
    marginBottom: 20,
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  fieldHint: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 4,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  textAreaContainer: {
    alignItems: 'flex-start',
    paddingVertical: 16,
  },
  inputIcon: {
    marginRight: 12,
  },
  textAreaIcon: {
    marginTop: 2,
  },
  modalInput: {
    flex: 1,
    fontSize: 16,
    color: '#111827',
    minHeight: 20,
  },
  textAreaInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: 8,
    padding: 12,
    marginTop: 8,
  },
  modalFooter: {
    flexDirection: 'row',
    padding: 20,
    paddingTop: 16,
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
    backgroundColor: '#FFFFFF',
  },
  primaryButton: {
    backgroundColor: '#3B82F6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: '#3B82F6',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  modalBackdrop: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  dateModalContent: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 8,
  },
  dateModalBody: {
    paddingHorizontal: 20,
    paddingBottom: 0,
    maxHeight: 200,
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 16,
    lineHeight: 20,
  },
  currencyModalBody: {
    flex: 1,
    padding: 20,
  },
  currencyList: {
    flex: 1,
  },
  currencyOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
    backgroundColor: '#FFFFFF',
  },
  currencyOptionSelected: {
    backgroundColor: '#F0F9FF',
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
  },
  currencyOptionLast: {
    borderBottomWidth: 0,
  },
  currencyInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  currencySymbol: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  currencySymbolText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  currencyDetails: {
    flex: 1,
  },
  currencyCode: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 2,
  },
  currencyName: {
    fontSize: 14,
    color: '#6B7280',
  },
  errorHint: {
    color: '#EF4444',
  },
  currencyDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
  },

});

export default NewInvoiceScreen;
