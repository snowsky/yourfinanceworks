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
import apiService, { CreateClientData } from '../services/api';

interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  price: number;
  amount: number;
}

interface Client {
  id: number;
  name: string;
  email: string;
}

interface Invoice {
  id: number;
  number: string;
  client_name: string;
  client_id: number;
  due_date: string;
  amount: number;
  total_paid: number;
  status: string;
  currency: string;
  notes?: string;
  items?: InvoiceItem[];
}

interface EditInvoiceFormData {
  client: string;
  invoiceNumber: string;
  currency: string;
  date: string;
  dueDate: string;
  status: string;
  paidAmount: number;
  items: InvoiceItem[];
  notes: string;
}

interface EditInvoiceScreenProps {
  invoice: Invoice;
  clients: Array<{
    id: number;
    name: string;
    email: string;
  }>;
  onUpdateInvoice: (invoiceId: number, formData: EditInvoiceFormData) => Promise<void>;
  onNavigateBack: () => void;
}

const EditInvoiceScreen: React.FC<EditInvoiceScreenProps> = ({
  invoice,
  clients: propClients,
  onUpdateInvoice,
  onNavigateBack,
}) => {
  const [formData, setFormData] = useState<EditInvoiceFormData>({
    client: invoice.client_id.toString(),
    invoiceNumber: invoice.number,
    currency: invoice.currency || 'USD',
    date: new Date().toISOString().split('T')[0], // Use current date as default
    dueDate: invoice.due_date,
    status: invoice.status,
    paidAmount: invoice.total_paid || 0,
    items: (() => {
      const items = invoice.items || [];
      // If no items or all items have invalid prices, create a default item
      if (items.length === 0 || items.every(item => !item.price || item.price <= 0)) {
        return [{ id: Date.now(), description: '', quantity: 1, price: 1, amount: 1 }];
      }
      // Otherwise, ensure all items have valid values
      return items.map(item => ({
        ...item,
        quantity: item.quantity || 1,
        price: item.price || 1, // Ensure price is at least 1
        amount: (item.quantity || 1) * (item.price || 1) // Ensure amount is calculated
      }));
    })(),
    notes: invoice.notes || '',
  });

  // Debug invoice data
  useEffect(() => {
    console.log('Invoice data received:', {
      id: invoice.id,
      notes: invoice.notes,
      notesType: typeof invoice.notes,
      notesLength: invoice.notes?.length,
      items: invoice.items,
      itemsCount: invoice.items?.length || 0,
      calculatedTotal: (invoice.items || []).reduce((sum, item) => sum + (item.quantity * item.price), 0),
      itemDetails: invoice.items?.map(item => ({
        id: item.id,
        description: item.description,
        quantity: item.quantity,
        price: item.price,
        amount: item.amount
      }))
    });
  }, [invoice]);

  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showClientModal, setShowClientModal] = useState(false);
  const [showDateModal, setShowDateModal] = useState(false);
  const [showDueDateModal, setShowDueDateModal] = useState(false);
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [currentDateField, setCurrentDateField] = useState<'date' | 'dueDate'>('date');
  const [error, setError] = useState<string | null>(null);
  const [clients, setClients] = useState(propClients);
  const [showAddClientModal, setShowAddClientModal] = useState(false);
  const [addClientForm, setAddClientForm] = useState({ name: '', email: '', phone: '', address: '' });
  const [addClientLoading, setAddClientLoading] = useState(false);
  const [addClientError, setAddClientError] = useState<string | null>(null);

  // Debug modal states
  useEffect(() => {
    console.log('Modal states changed:', {
      showClientModal,
      showAddClientModal,
      clientsCount: clients.length
    });
  }, [showClientModal, showAddClientModal, clients.length]);



  const handleChange = (field: keyof EditInvoiceFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    if (error) setError(null);
  };

  const handleItemChange = (index: number, field: keyof InvoiceItem, value: any) => {
    console.log('handleItemChange called:', { index, field, value, currentItems: formData.items });
    
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

    console.log('Updated item:', newItems[index]);
    handleChange('items', newItems);
  };

  const addItem = () => {
    const newItem: InvoiceItem = {
      id: Date.now(),
      description: '',
      quantity: 1,
      price: 1,
      amount: 1,
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

  const calculateTotal = () => {
    return calculateSubtotal();
  };

  const ensureValidPrices = () => {
    const updatedItems = formData.items.map(item => ({
      ...item,
      price: item.price <= 0 ? 1 : item.price,
      amount: item.quantity * (item.price <= 0 ? 1 : item.price)
    }));
    handleChange('items', updatedItems);
  };

  const validateForm = (): boolean => {
    console.log('Validating form:', {
      client: formData.client,
      invoiceNumber: formData.invoiceNumber,
      date: formData.date,
      dueDate: formData.dueDate,
      notes: formData.notes,
      items: formData.items,
      total: calculateTotal(),
      paidAmount: formData.paidAmount
    });

    if (!formData.client) {
      setError('Please select a client');
      return false;
    }
    if (!formData.invoiceNumber.trim()) {
      setError('Invoice number is required');
      return false;
    }
    if (!formData.date) {
      setError('Invoice date is required');
      return false;
    }
    if (!formData.dueDate) {
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
      if (formData.items.every(item => item.price <= 0)) {
        // Automatically fix prices if they're all zero
        ensureValidPrices();
        setError('Prices have been automatically set to 1. Please review and adjust as needed.');
        return false;
      } else {
        setError('Invoice total must be greater than 0');
      }
      return false;
    }
    if (formData.paidAmount > calculateTotal()) {
      setError('Paid amount cannot exceed invoice total');
      return false;
    }
    return true;
  };

  const handleUpdate = async () => {
    if (!validateForm()) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      console.log('Sending update data:', {
        invoiceId: invoice.id,
        formData: formData,
        items: formData.items,
        itemDescriptions: formData.items.map(item => ({
          id: item.id,
          description: item.description,
          descriptionLength: item.description.length,
          descriptionType: typeof item.description
        }))
      });
      await onUpdateInvoice(invoice.id, formData);
    } catch (error: any) {
      console.error('Update error:', error);
      setError(error.message || 'Failed to update invoice');
    } finally {
      setSubmitting(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: formData.currency,
    }).format(amount);
  };

  const formatStatus = (status: string) => {
    return status.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const handleAddClient = async () => {
    if (!addClientForm.name.trim() || !addClientForm.email.trim()) {
      setAddClientError('Name and email are required');
      return;
    }
    setAddClientLoading(true);
    setAddClientError(null);
    try {
      const newClient = await apiService.createClient(addClientForm as CreateClientData);
      setClients(prev => [...prev, newClient]);
      setFormData(prev => ({ ...prev, client: newClient.id.toString() }));
      setShowAddClientModal(false);
      setAddClientForm({ name: '', email: '', phone: '', address: '' });
    } catch (error: any) {
      setAddClientError(error.message || 'Failed to add client');
    } finally {
      setAddClientLoading(false);
    }
  };

  const renderAddClientModal = () => {
    console.log('Rendering add client modal, visible:', showAddClientModal);
    return (
      <Modal
        visible={showAddClientModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowAddClientModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add New Client</Text>
              <TouchableOpacity onPress={() => setShowAddClientModal(false)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <View style={styles.modalBody}>
              {addClientError && <Text style={styles.errorText}>{addClientError}</Text>}
              <TextInput
                style={styles.input}
                placeholder="Name*"
                value={addClientForm.name}
                onChangeText={v => setAddClientForm(f => ({ ...f, name: v }))}
              />
              <TextInput
                style={styles.input}
                placeholder="Email*"
                value={addClientForm.email}
                onChangeText={v => setAddClientForm(f => ({ ...f, email: v }))}
                keyboardType="email-address"
                autoCapitalize="none"
              />
              <TextInput
                style={styles.input}
                placeholder="Phone"
                value={addClientForm.phone}
                onChangeText={v => setAddClientForm(f => ({ ...f, phone: v }))}
                keyboardType="phone-pad"
              />
              <TextInput
                style={styles.input}
                placeholder="Address"
                value={addClientForm.address}
                onChangeText={v => setAddClientForm(f => ({ ...f, address: v }))}
              />
              <TouchableOpacity
                style={[styles.saveButton, addClientLoading && styles.saveButtonDisabled]}
                onPress={handleAddClient}
                disabled={addClientLoading}
              >
                {addClientLoading ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.saveButtonText}>Add Client</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    );
  };

  const renderClientSelector = () => {
    console.log('Rendering client selector modal, visible:', showClientModal, 'clients count:', clients.length);
    return (
      <Modal
        visible={showClientModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowClientModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Client</Text>
              <TouchableOpacity onPress={() => setShowClientModal(false)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={true}>
              {clients.map(client => (
                <TouchableOpacity
                  key={client.id}
                  style={styles.clientOption}
                  onPress={() => {
                    handleChange('client', client.id.toString());
                    setShowClientModal(false);
                  }}
                >
                  <Text style={styles.clientName}>{client.name}</Text>
                  <Text style={styles.clientEmail}>{client.email}</Text>
                </TouchableOpacity>
              ))}
              <TouchableOpacity
                style={styles.addClientButton}
                              onPress={() => {
                setShowClientModal(false); // Close the client selector modal first
                setTimeout(() => {
                  setShowAddClientModal(true); // Then open the add client modal
                }, 100);
              }}
                activeOpacity={0.7}
              >
                <Ionicons name="person-add-outline" size={20} color="#007AFF" />
                <Text style={styles.addClientText}>New Client</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    );
  };

  const renderDateSelector = () => (
    <Modal
      visible={showDateModal || showDueDateModal}
      transparent
      animationType="slide"
      onRequestClose={() => {
        setShowDateModal(false);
        setShowDueDateModal(false);
      }}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>
              Select {currentDateField === 'date' ? 'Invoice' : 'Due'} Date
            </Text>
            <TouchableOpacity
              onPress={() => {
                setShowDateModal(false);
                setShowDueDateModal(false);
              }}
            >
              <Ionicons name="close" size={24} color="#666" />
            </TouchableOpacity>
          </View>
          <View style={styles.modalBody}>
            <Text style={styles.dateInfo}>
              Date picker would be implemented here with a proper date picker component
            </Text>
            <TouchableOpacity
              style={styles.dateButton}
              onPress={() => {
                setShowDateModal(false);
                setShowDueDateModal(false);
              }}
            >
              <Text style={styles.dateButtonText}>Use Current Date</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

  const renderStatusSelector = () => (
    <Modal
      visible={showStatusModal}
      transparent
      animationType="slide"
      onRequestClose={() => setShowStatusModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Select Status</Text>
            <TouchableOpacity onPress={() => setShowStatusModal(false)}>
              <Ionicons name="close" size={24} color="#666" />
            </TouchableOpacity>
          </View>
          <View style={styles.modalBody}>
            {['pending', 'paid', 'overdue', 'draft'].map(status => (
              <TouchableOpacity
                key={status}
                style={[
                  styles.statusOption,
                  formData.status === status && styles.statusOptionSelected
                ]}
                onPress={() => {
                  handleChange('status', status);
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  formData.status === status && styles.statusOptionTextSelected
                ]}>{formatStatus(status)}</Text>
                {formData.status === status && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>
    </Modal>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Edit Invoice</Text>
        <TouchableOpacity
          style={[styles.saveButton, submitting && styles.saveButtonDisabled]}
          onPress={handleUpdate}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.saveButtonText}>Update</Text>
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        {error && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Invoice Details</Text>
          
          {/* Client Selection */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Client *</Text>
            <TouchableOpacity
              style={styles.selectorButton}
              onPress={() => setShowClientModal(true)}
            >
              <Text style={formData.client ? styles.selectorText : styles.placeholderText}>
                {formData.client
                  ? clients.find(c => c.id.toString() === formData.client)?.name || 'Select Client'
                  : 'Select Client'
                }
              </Text>
              <Ionicons name="chevron-down" size={16} color="#666" />
            </TouchableOpacity>
          </View>

          {/* Invoice Number */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Invoice Number *</Text>
            <TextInput
              style={styles.input}
              value={formData.invoiceNumber}
              onChangeText={(value) => handleChange('invoiceNumber', value)}
              placeholder="e.g., INV-001"
              autoCapitalize="characters"
            />
          </View>

          {/* Currency */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Currency</Text>
            <View style={styles.currencyContainer}>
              <Text style={styles.currencyText}>{formData.currency}</Text>
            </View>
          </View>

          {/* Invoice Date */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Invoice Date *</Text>
            <TouchableOpacity
              style={styles.selectorButton}
              onPress={() => {
                setCurrentDateField('date');
                setShowDateModal(true);
              }}
            >
              <Text style={styles.selectorText}>{formData.date}</Text>
              <Ionicons name="calendar-outline" size={16} color="#666" />
            </TouchableOpacity>
          </View>

          {/* Due Date */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Due Date *</Text>
            <TouchableOpacity
              style={styles.selectorButton}
              onPress={() => {
                setCurrentDateField('dueDate');
                setShowDueDateModal(true);
              }}
            >
              <Text style={styles.selectorText}>{formData.dueDate}</Text>
              <Ionicons name="calendar-outline" size={16} color="#666" />
            </TouchableOpacity>
          </View>

          {/* Status */}
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Status</Text>
            <TouchableOpacity
              style={styles.selectorButton}
              onPress={() => setShowStatusModal(true)}
            >
              <Text style={styles.selectorText}>{formatStatus(formData.status)}</Text>
              <Ionicons name="chevron-down" size={16} color="#666" />
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Invoice Items</Text>
          
          {formData.items.map((item, index) => (
            <View key={item.id || index} style={styles.itemContainer}>
              <View style={styles.itemHeader}>
                <Text style={styles.itemNumber}>Item {index + 1}</Text>
                {formData.items.length > 1 && (
                  <TouchableOpacity
                    style={styles.removeItemButton}
                    onPress={() => removeItem(index)}
                  >
                    <Ionicons name="trash-outline" size={16} color="#EF4444" />
                  </TouchableOpacity>
                )}
              </View>
              
              <View style={styles.inputContainer}>
                <Text style={styles.label}>Description *</Text>
                <TextInput
                  style={styles.input}
                  value={item.description}
                  onChangeText={(value) => handleItemChange(index, 'description', value)}
                  placeholder="Item description"
                />
              </View>
              
              <View style={styles.itemRow}>
                <View style={[styles.inputContainer, styles.halfWidth]}>
                  <Text style={styles.label}>Quantity</Text>
                  <TextInput
                    style={styles.input}
                    value={item.quantity.toString()}
                    onChangeText={(value) => handleItemChange(index, 'quantity', parseInt(value) || 0)}
                    keyboardType="numeric"
                    placeholder="1"
                  />
                </View>
                
                <View style={[styles.inputContainer, styles.halfWidth]}>
                  <Text style={styles.label}>Price *</Text>
                  <TextInput
                    style={styles.input}
                    value={item.price.toString()}
                    onChangeText={(value) => handleItemChange(index, 'price', parseFloat(value) || 0)}
                    keyboardType="numeric"
                    placeholder="0.00"
                  />
                </View>
              </View>
              
              <View style={styles.itemAmount}>
                <Text style={styles.amountLabel}>Amount:</Text>
                <Text style={styles.amountValue}>{formatCurrency(item.amount)}</Text>
              </View>
            </View>
          ))}
          
          <TouchableOpacity style={styles.addItemButton} onPress={addItem}>
            <Ionicons name="add" size={20} color="#007AFF" />
            <Text style={styles.addItemText}>Add Item</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Payment</Text>
          
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Paid Amount</Text>
            <TextInput
              style={styles.input}
              value={formData.paidAmount.toString()}
              onChangeText={(value) => handleChange('paidAmount', parseFloat(value) || 0)}
              keyboardType="numeric"
              placeholder="0.00"
            />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notes</Text>
          
          <View style={styles.inputContainer}>
            <TextInput
              style={[styles.input, styles.textArea]}
              value={formData.notes}
              onChangeText={(value) => handleChange('notes', value)}
              placeholder="Additional notes..."
              multiline
              numberOfLines={4}
              textAlignVertical="top"
            />
          </View>
        </View>

        <View style={styles.summarySection}>
          <Text style={styles.summaryTitle}>Invoice Summary</Text>
          
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Subtotal:</Text>
            <Text style={styles.summaryValue}>{formatCurrency(calculateSubtotal())}</Text>
          </View>
          
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Total:</Text>
            <Text style={styles.summaryTotal}>{formatCurrency(calculateTotal())}</Text>
          </View>
          
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Paid:</Text>
            <Text style={styles.summaryValue}>{formatCurrency(formData.paidAmount)}</Text>
          </View>
          
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Outstanding:</Text>
            <Text style={[
              styles.summaryValue,
              { color: calculateTotal() - formData.paidAmount > 0 ? '#F59E0B' : '#10B981' }
            ]}>
              {formatCurrency(calculateTotal() - formData.paidAmount)}
            </Text>
          </View>
        </View>
      </ScrollView>

      {renderClientSelector()}
      {renderAddClientModal()}
      {renderDateSelector()}
      {renderStatusSelector()}
    </KeyboardAvoidingView>
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
  saveButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
  },
  saveButtonDisabled: {
    backgroundColor: '#ccc',
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  errorContainer: {
    backgroundColor: '#fee',
    borderColor: '#fcc',
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    margin: 20,
  },
  errorText: {
    color: '#c33',
    fontSize: 14,
  },
  section: {
    backgroundColor: '#fff',
    margin: 20,
    marginBottom: 10,
    borderRadius: 12,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
  },
  inputContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  textArea: {
    height: 100,
    paddingTop: 12,
  },
  selectorButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  selectorText: {
    fontSize: 16,
    color: '#333',
  },
  placeholderText: {
    fontSize: 16,
    color: '#999',
  },
  currencyContainer: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#f9f9f9',
  },
  currencyText: {
    fontSize: 16,
    color: '#333',
    fontWeight: '600',
  },
  itemContainer: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    backgroundColor: '#f9f9f9',
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  itemNumber: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  removeItemButton: {
    padding: 4,
  },
  itemRow: {
    flexDirection: 'row',
    gap: 12,
  },
  halfWidth: {
    flex: 1,
  },
  itemAmount: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  amountLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
  },
  amountValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  addItemButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#007AFF',
    borderStyle: 'dashed',
    borderRadius: 8,
    padding: 16,
    marginTop: 8,
  },
  addItemText: {
    marginLeft: 8,
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '600',
  },
  summarySection: {
    backgroundColor: '#fff',
    margin: 20,
    marginBottom: 40,
    borderRadius: 12,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryLabel: {
    fontSize: 16,
    color: '#666',
  },
  summaryValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  summaryTotal: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
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
  clientOption: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  clientName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  clientEmail: {
    fontSize: 14,
    color: '#666',
  },
  dateInfo: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 20,
  },
  dateButton: {
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  dateButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
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
  addClientButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f0f9ff',
    borderWidth: 2,
    borderColor: '#007AFF',
    borderStyle: 'solid',
    borderRadius: 8,
    padding: 16,
    marginTop: 16,
    marginBottom: 8,
  },
  addClientText: {
    marginLeft: 8,
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '600',
  },
});

export default EditInvoiceScreen; 