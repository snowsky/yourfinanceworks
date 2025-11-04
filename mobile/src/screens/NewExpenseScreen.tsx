import React, { useState } from 'react';
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
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTranslation } from 'react-i18next';
import apiService, { Expense } from '../services/api';
import FileUpload, { FileData } from '../components/FileUpload';

interface NewExpenseScreenProps {
  onNavigateBack: () => void;
  onExpenseCreated: (expense: Expense) => void;
}

const EXPENSE_CATEGORIES = [
  'General', 'Office Supplies', 'Travel', 'Meals', 'Transportation',
  'Marketing', 'Software', 'Equipment', 'Utilities', 'Professional Services'
];

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];

const PAYMENT_METHODS = [
  'Cash', 'Credit Card', 'Debit Card', 'Bank Transfer', 'Check', 'Other'
];

const NewExpenseScreen: React.FC<NewExpenseScreenProps> = ({
  onNavigateBack,
  onExpenseCreated,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showCurrencyModal, setShowCurrencyModal] = useState(false);
  const [showPaymentMethodModal, setShowPaymentMethodModal] = useState(false);
  const [receiptFiles, setReceiptFiles] = useState<FileData[]>([]);

  const [formData, setFormData] = useState({
    amount: '',
    currency: 'USD',
    expense_date: new Date().toISOString().split('T')[0],
    category: 'General',
    vendor: '',
    payment_method: '',
    reference_number: '',
    notes: '',
    status: 'recorded' as const,
  });

  const handleSubmit = async () => {
    // Allow saving without amount if there's a receipt attachment (matching web behavior)
    if (receiptFiles.length === 0 && (!formData.amount || parseFloat(formData.amount) <= 0)) {
      Alert.alert('Error', 'Please enter a valid amount or upload a receipt');
      return;
    }

    // If amount is provided, validate it
    if (formData.amount && (isNaN(parseFloat(formData.amount)) || parseFloat(formData.amount) <= 0)) {
      Alert.alert('Error', 'Please enter a valid amount greater than 0');
      return;
    }

    if (!formData.category) {
      Alert.alert('Error', 'Please select a category');
      return;
    }

    setLoading(true);
    try {
      const expenseData = {
        ...formData,
        amount: formData.amount && formData.amount.trim() !== '' ? parseFloat(formData.amount) : undefined,
      };

      const newExpense = await apiService.createExpense(expenseData);

      // Upload receipt if selected
      if (receiptFiles.length > 0) {
        setUploadingReceipt(true);
        try {
          await uploadReceiptToExpense(newExpense.id, receiptFiles[0]);
        } catch (uploadError) {
          console.error('Failed to upload receipt:', uploadError);
          // Don't block the success flow for upload failures
          Alert.alert('Warning', 'Expense created but receipt upload failed. You can upload it later.');
        } finally {
          setUploadingReceipt(false);
        }
      }

      Alert.alert('Success', 'Expense created successfully', [
        {
          text: 'OK',
          onPress: () => {
            onExpenseCreated(newExpense);
            onNavigateBack();
          },
        },
      ]);
    } catch (error) {
      console.error('Failed to create expense:', error);
      // Show actual error message instead of generic one
      const errorMessage = error instanceof Error ? error.message : 'Failed to create expense';
      Alert.alert('Error', errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const uploadReceiptToExpense = async (expenseId: number, file: FileData) => {
    // Use the same API service for consistency
    const formData = new FormData();
    formData.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.type,
    } as any);

    // Make direct fetch call since we need FormData
    const token = await AsyncStorage.getItem('auth_token');
    const userData = await AsyncStorage.getItem('user_data');
    const user = userData ? JSON.parse(userData) : null;
    const tenantId = user?.tenant_id;

    // Get the API base URL from the apiService
    const apiService = await import('../services/api');
    const API_BASE_URL = apiService.default.baseURL;

    const response = await fetch(`${API_BASE_URL}/expenses/${expenseId}/upload-receipt`, {
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
    setReceiptFiles(files);
  };

  const handleRemoveFile = (index: number) => {
    setReceiptFiles(prev => prev.filter((_, i) => i !== index));
  };


  const CategoryModal = () => (
    <Modal
      visible={showCategoryModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowCategoryModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>Select Category</Text>
          
          {EXPENSE_CATEGORIES.map((category) => (
            <TouchableOpacity
              key={category}
              style={[
                styles.modalOption,
                formData.category === category && styles.modalOptionActive
              ]}
              onPress={() => {
                setFormData(prev => ({ ...prev, category }));
                setShowCategoryModal(false);
              }}
            >
              <Text style={styles.modalOptionText}>{category}</Text>
              {formData.category === category && (
                <Ionicons name="checkmark" size={20} color="#10B981" />
              )}
            </TouchableOpacity>
          ))}

          <TouchableOpacity
            style={styles.modalCloseButton}
            onPress={() => setShowCategoryModal(false)}
          >
            <Text style={styles.modalCloseButtonText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  const CurrencyModal = () => (
    <Modal
      visible={showCurrencyModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowCurrencyModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>Select Currency</Text>
          
          {CURRENCIES.map((currency) => (
            <TouchableOpacity
              key={currency}
              style={[
                styles.modalOption,
                formData.currency === currency && styles.modalOptionActive
              ]}
              onPress={() => {
                setFormData(prev => ({ ...prev, currency }));
                setShowCurrencyModal(false);
              }}
            >
              <Text style={styles.modalOptionText}>{currency}</Text>
              {formData.currency === currency && (
                <Ionicons name="checkmark" size={20} color="#10B981" />
              )}
            </TouchableOpacity>
          ))}

          <TouchableOpacity
            style={styles.modalCloseButton}
            onPress={() => setShowCurrencyModal(false)}
          >
            <Text style={styles.modalCloseButtonText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  const PaymentMethodModal = () => (
    <Modal
      visible={showPaymentMethodModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowPaymentMethodModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>Select Payment Method</Text>
          
          {PAYMENT_METHODS.map((method) => (
            <TouchableOpacity
              key={method}
              style={[
                styles.modalOption,
                formData.payment_method === method && styles.modalOptionActive
              ]}
              onPress={() => {
                setFormData(prev => ({ ...prev, payment_method: method }));
                setShowPaymentMethodModal(false);
              }}
            >
              <Text style={styles.modalOptionText}>{method}</Text>
              {formData.payment_method === method && (
                <Ionicons name="checkmark" size={20} color="#10B981" />
              )}
            </TouchableOpacity>
          ))}

          <TouchableOpacity
            style={styles.modalCloseButton}
            onPress={() => setShowPaymentMethodModal(false)}
          >
            <Text style={styles.modalCloseButtonText}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>New Expense</Text>
        <TouchableOpacity
          style={[styles.saveButton, loading && styles.saveButtonDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.saveButtonText}>Save</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.form}>
          {/* Amount and Currency */}
          <View style={styles.row}>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Amount{receiptFiles.length === 0 ? ' *' : ''}</Text>
              <TextInput
                style={styles.input}
                value={formData.amount}
                onChangeText={(text) => setFormData(prev => ({ ...prev, amount: text }))}
                placeholder="0.00"
                keyboardType="numeric"
              />
            </View>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>Currency</Text>
              <TouchableOpacity
                style={styles.selector}
                onPress={() => setShowCurrencyModal(true)}
              >
                <Text style={styles.selectorText}>{formData.currency}</Text>
                <Ionicons name="chevron-down" size={16} color="#9CA3AF" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Date */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Date</Text>
            <TextInput
              style={styles.input}
              value={formData.expense_date}
              onChangeText={(text) => setFormData(prev => ({ ...prev, expense_date: text }))}
              placeholder="YYYY-MM-DD"
            />
          </View>

          {/* Category */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Category *</Text>
            <TouchableOpacity
              style={styles.selector}
              onPress={() => setShowCategoryModal(true)}
            >
              <Text style={styles.selectorText}>{formData.category}</Text>
              <Ionicons name="chevron-down" size={16} color="#9CA3AF" />
            </TouchableOpacity>
          </View>

          {/* Vendor */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Vendor</Text>
            <TextInput
              style={styles.input}
              value={formData.vendor}
              onChangeText={(text) => setFormData(prev => ({ ...prev, vendor: text }))}
              placeholder="Enter vendor name"
            />
          </View>

          {/* Payment Method */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Payment Method</Text>
            <TouchableOpacity
              style={styles.selector}
              onPress={() => setShowPaymentMethodModal(true)}
            >
              <Text style={styles.selectorText}>
                {formData.payment_method || 'Select payment method'}
              </Text>
              <Ionicons name="chevron-down" size={16} color="#9CA3AF" />
            </TouchableOpacity>
          </View>

          {/* Reference Number */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Reference Number</Text>
            <TextInput
              style={styles.input}
              value={formData.reference_number}
              onChangeText={(text) => setFormData(prev => ({ ...prev, reference_number: text }))}
              placeholder="Enter reference number"
            />
          </View>

          {/* Notes */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Notes</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              value={formData.notes}
              onChangeText={(text) => setFormData(prev => ({ ...prev, notes: text }))}
              placeholder="Enter notes"
              multiline
              numberOfLines={4}
              textAlignVertical="top"
            />
          </View>

          {/* Receipt Upload */}
          <FileUpload
            title="Receipt"
            maxFiles={1}
            allowedTypes={['image/jpeg', 'image/png', 'image/jpg', 'image/heic', 'image/heif']}
            onFilesSelected={handleFilesSelected}
            selectedFiles={receiptFiles}
            onRemoveFile={handleRemoveFile}
            uploading={uploadingReceipt}
          />
        </View>
      </ScrollView>

      <CategoryModal />
      <CurrencyModal />
      <PaymentMethodModal />
    </View>
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
    backgroundColor: '#9CA3AF',
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
  scrollView: {
    flex: 1,
  },
  form: {
    padding: 20,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  inputGroup: {
    marginBottom: 20,
    flex: 1,
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
    height: 100,
    textAlignVertical: 'top',
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
    width: '80%',
    maxHeight: '70%',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 20,
    textAlign: 'center',
  },
  modalOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 8,
  },
  modalOptionActive: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  modalOptionText: {
    fontSize: 16,
    color: '#374151',
    fontWeight: '500',
    flex: 1,
  },
  modalCloseButton: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 16,
  },
  modalCloseButtonText: {
    fontSize: 16,
    color: '#374151',
    fontWeight: '600',
    textAlign: 'center',
  },
});

export default NewExpenseScreen;