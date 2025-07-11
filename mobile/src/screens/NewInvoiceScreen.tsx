import React, { useState, useEffect } from 'react';
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
import apiService, { CreateClientData, CreateInvoiceData, Client, Settings, DiscountRule } from '../services/api';
import { formatCurrency, getCurrencySymbol, parseCurrencyAmount } from '../utils/currency';
import { formatDate, safeParseDateString } from '../utils/date';

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
  clients: Array<{
    id: number;
    name: string;
    email: string;
  }>;
  onSaveInvoice: (formData: CreateInvoiceData) => Promise<void>;
  onNavigateBack: () => void;
}

const NewInvoiceScreen: React.FC<NewInvoiceScreenProps> = ({
  clients: propClients,
  onSaveInvoice,
  onNavigateBack,
}) => {
  const [formData, setFormData] = useState<NewInvoiceFormData>({
    client_id: 0,
    number: '',
    currency: 'USD',
    date: new Date().toISOString().split('T')[0],
    due_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
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
  const [showDateModal, setShowDateModal] = useState(false);
  const [showDueDateModal, setShowDueDateModal] = useState(false);
  const [currentDateField, setCurrentDateField] = useState<'date' | 'due_date'>('date');
  const [error, setError] = useState<string | null>(null);
  const [clients, setClients] = useState(propClients);
  const [showAddClientModal, setShowAddClientModal] = useState(false);
  const [addClientForm, setAddClientForm] = useState({ name: '', email: '', phone: '', address: '', preferred_currency: 'USD' });
  const [addClientLoading, setAddClientLoading] = useState(false);
  const [addClientError, setAddClientError] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [appliedDiscountRule, setAppliedDiscountRule] = useState<DiscountRule | null>(null);

  // Load settings and discount rules
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [settingsData, discountRulesData] = await Promise.all([
          apiService.getSettings(),
          apiService.getDiscountRules()
        ]);
        setSettings(settingsData);
        setDiscountRules(discountRulesData);
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    };
    loadSettings();
  }, []);

  const handleChange = (field: keyof NewInvoiceFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    if (error) setError(null);
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
    if (formData.items.length > 1) {
      const newItems = formData.items.filter((_, i) => i !== index);
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
      
      await onSaveInvoice(invoiceData);
    } catch (error: any) {
      setError(error.message || 'Failed to save invoice');
    } finally {
      setSubmitting(false);
    }
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
      const newClient = await apiService.createClient(addClientForm);
      setClients(prev => [...prev, newClient]);
      setShowAddClientModal(false);
      setAddClientForm({ name: '', email: '', phone: '', address: '', preferred_currency: 'USD' });
      
      // Auto-select the new client
      handleChange('client_id', newClient.id);
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
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>Add New Client</Text>
          
          <TextInput
            style={styles.input}
            placeholder="Client Name"
            value={addClientForm.name}
            onChangeText={(text) => setAddClientForm(prev => ({ ...prev, name: text }))}
          />
          
          <TextInput
            style={styles.input}
            placeholder="Email"
            value={addClientForm.email}
            onChangeText={(text) => setAddClientForm(prev => ({ ...prev, email: text }))}
            keyboardType="email-address"
          />
          
          <TextInput
            style={styles.input}
            placeholder="Phone (optional)"
            value={addClientForm.phone}
            onChangeText={(text) => setAddClientForm(prev => ({ ...prev, phone: text }))}
            keyboardType="phone-pad"
          />
          
          <TextInput
            style={styles.input}
            placeholder="Address (optional)"
            value={addClientForm.address}
            onChangeText={(text) => setAddClientForm(prev => ({ ...prev, address: text }))}
            multiline
          />

          {addClientError && (
            <Text style={styles.errorText}>{addClientError}</Text>
          )}

          <View style={styles.modalButtons}>
            <TouchableOpacity
              style={[styles.button, styles.cancelButton]}
              onPress={() => setShowAddClientModal(false)}
            >
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.button, styles.saveButton]}
              onPress={handleAddClient}
              disabled={addClientLoading}
            >
              {addClientLoading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.saveButtonText}>Add Client</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

  const renderClientSelector = () => (
    <View style={styles.formGroup}>
      <Text style={styles.label}>Client *</Text>
      <TouchableOpacity
        style={styles.selector}
        onPress={() => setShowClientModal(true)}
      >
        <Text style={selectedClient ? styles.selectorText : styles.placeholderText}>
          {selectedClient ? selectedClient.name : 'Select a client'}
        </Text>
        <Ionicons name="chevron-down" size={20} color="#6B7280" />
      </TouchableOpacity>
      
      <TouchableOpacity
        style={styles.addClientButton}
        onPress={() => setShowAddClientModal(true)}
      >
        <Ionicons name="add-circle-outline" size={16} color="#3B82F6" />
        <Text style={styles.addClientText}>Add New Client</Text>
      </TouchableOpacity>
    </View>
  );

  const renderDateSelector = () => (
    <View style={styles.formGroup}>
      <Text style={styles.label}>Invoice Date *</Text>
      <TouchableOpacity
        style={styles.selector}
        onPress={() => {
          setCurrentDateField('date');
          setShowDateModal(true);
        }}
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
        style={styles.selector}
        onPress={() => {
          setCurrentDateField('due_date');
          setShowDueDateModal(true);
        }}
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
        <Text style={styles.headerTitle}>New Invoice</Text>
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
          <View style={styles.currencySelector}>
            <Text style={styles.currencySymbol}>
              {getCurrencySymbol(formData.currency)}
            </Text>
            <Text style={styles.currencyCode}>{formData.currency}</Text>
          </View>
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
                placeholder="Description"
                value={item.description}
                onChangeText={(text) => handleItemChange(index, 'description', text)}
              />
              
              <View style={styles.itemRow}>
                <View style={styles.itemField}>
                  <Text style={styles.itemLabel}>Quantity</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="1"
                    value={item.quantity.toString()}
                    onChangeText={(text) => handleItemChange(index, 'quantity', parseInt(text) || 0)}
                    keyboardType="numeric"
                  />
                </View>
                
                <View style={styles.itemField}>
                  <Text style={styles.itemLabel}>Price</Text>
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
                <Text style={styles.itemTotalLabel}>Total:</Text>
                <Text style={styles.itemTotalAmount}>
                  {formatCurrencyDisplay(item.amount)}
                </Text>
              </View>
            </View>
          ))}
          
          <TouchableOpacity style={styles.addItemButton} onPress={addItem}>
            <Ionicons name="add-circle-outline" size={20} color="#3B82F6" />
            <Text style={styles.addItemText}>Add Item</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.summaryContainer}>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Subtotal:</Text>
            <Text style={styles.summaryValue}>
              {formatCurrencyDisplay(calculateSubtotal())}
            </Text>
          </View>
          
          {calculateDiscount() > 0 && (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Discount:</Text>
              <Text style={styles.summaryValue}>
                -{formatCurrencyDisplay(calculateDiscount())}
              </Text>
            </View>
          )}
          
          <View style={[styles.summaryRow, styles.totalRow]}>
            <Text style={styles.totalLabel}>Total:</Text>
            <Text style={styles.totalValue}>
              {formatCurrencyDisplay(calculateTotal())}
            </Text>
          </View>
        </View>

        <View style={styles.formGroup}>
          <Text style={styles.label}>Notes (optional)</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            placeholder="Add any additional notes..."
            value={formData.notes}
            onChangeText={(text) => handleChange('notes', text)}
            multiline
            numberOfLines={3}
          />
        </View>
      </ScrollView>

      {renderAddClientModal()}
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
  errorContainer: {
    backgroundColor: '#FEF2F2',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FECACA',
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
  addClientButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  addClientText: {
    marginLeft: 4,
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
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
  currencySymbol: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginRight: 8,
  },
  currencyCode: {
    fontSize: 16,
    color: '#6B7280',
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

export default NewInvoiceScreen; 