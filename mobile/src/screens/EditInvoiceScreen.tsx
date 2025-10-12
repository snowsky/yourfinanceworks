import React, { useState, useEffect } from 'react';
import { logger } from '../utils/logger';
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
import apiService, { CreateClientData, Invoice } from '../services/api';
import EnhancedFileUpload from '../components/EnhancedFileUpload';
import { FileData } from '../components/FileUpload';

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
  attachment_filename?: string | null;
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
    date: (() => {
      try {
        if (invoice.date) {
          const dateObj = new Date(invoice.date);
          if (!isNaN(dateObj.getTime())) {
            return dateObj.toISOString().split('T')[0];
          }
        }
        return new Date().toISOString().split('T')[0];
      } catch (error) {
        logger.warn('Invalid date value for invoice.date, using current date:', error);
        return new Date().toISOString().split('T')[0];
      }
    })(),
    dueDate: (() => {
      try {
        if (invoice.due_date) {
          const dateObj = new Date(invoice.due_date);
          if (!isNaN(dateObj.getTime())) {
            return dateObj.toISOString().split('T')[0];
          }
        }
        return new Date().toISOString().split('T')[0];
      } catch (error) {
        logger.warn('Invalid date value for invoice.due_date, using current date:', error);
        return new Date().toISOString().split('T')[0];
      }
    })(),
    status: invoice.status,
    paidAmount: invoice.total_paid || 0,
    items: (() => {
      const items = invoice.items || [];
      logger.debug('Processing invoice items for formData', {
        originalItems: items,
        itemsCount: items.length,
        descriptions: items.map(item => item.description)
      });

      // If no items or all items have invalid prices, create a default item
      if (items.length === 0 || items.every(item => !item.price || item.price <= 0)) {
        logger.debug('Creating default item due to no items or invalid prices');
        return [{ id: Date.now(), description: '', quantity: 1, price: 1, amount: 1 }];
      }
      // Otherwise, ensure all items have valid values
      const processedItems = items.map(item => ({
        ...item,
        quantity: item.quantity || 1,
        price: item.price || 1, // Ensure price is at least 1
        amount: (item.quantity || 1) * (item.price || 1) // Ensure amount is calculated
      }));

      logger.debug('Processed items for formData', {
        processedItemsCount: processedItems.length,
        descriptions: processedItems.map(item => item.description)
      });

      return processedItems;
    })(),
    notes: invoice.notes || '',
  });

  // Attachment file management
  const [attachmentFiles, setAttachmentFiles] = useState<FileData[]>([]);
  const [uploadingAttachments, setUploadingAttachments] = useState(false);
  const [filesToDelete, setFilesToDelete] = useState<Set<number>>(new Set()); // Track files marked for deletion by index
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [fileToDeleteIndex, setFileToDeleteIndex] = useState<number | null>(null);

  // Check if invoice is paid and should be protected from editing
  const isPaidInvoice = invoice.status === 'paid' || invoice.status === 'partially_paid';
  const isFullyPaidInvoice = isPaidInvoice && invoice.total_paid >= (invoice.amount || 0);
  const isInvoiceProtected = isFullyPaidInvoice;

  // Function to refresh invoice data from server
  const refreshInvoiceData = async () => {
    try {
      const updatedInvoice = await apiService.getInvoice(invoice.id);
    logger.debug('Starting refreshInvoiceData');      logger.debug('Refreshed invoice data after update:', updatedInvoice);

      // Update form data with refreshed invoice
      logger.debug('API response received, processing dates');      setFormData(prev => ({
        ...prev,
        client: updatedInvoice.client_id.toString(),
        invoiceNumber: updatedInvoice.number,
        currency: updatedInvoice.currency || 'USD',
        date: (() => {
          try {
            if (updatedInvoice.date) {
              const dateObj = new Date(updatedInvoice.date);
              if (!isNaN(dateObj.getTime())) {
                return dateObj.toISOString().split('T')[0];
              }
            }
            return new Date().toISOString().split('T')[0];
          } catch (error) {
            logger.warn('Invalid date value for updatedInvoice.date, using current date:', error);
            return new Date().toISOString().split('T')[0];
          }
        })(),
        dueDate: (() => {
          try {
            if (updatedInvoice.due_date) {
              const dateObj = new Date(updatedInvoice.due_date);
              if (!isNaN(dateObj.getTime())) {
                return dateObj.toISOString().split('T')[0];
              }
            }
            return new Date().toISOString().split('T')[0];
          } catch (error) {
            logger.warn('Invalid date value for updatedInvoice.due_date, using current date:', error);
            return new Date().toISOString().split('T')[0];
          }
        })(),        status: updatedInvoice.status,
        paidAmount: updatedInvoice.total_paid || 0,
        items: updatedInvoice.items || [],
        notes: updatedInvoice.notes || '',
      }));

      // Clear files to delete and reset attachment state
      setFilesToDelete(new Set());
      setAttachmentFiles([]);

      // Update attachment info
      if (updatedInvoice.has_attachment || updatedInvoice.attachment_filename) {
        setAttachmentInfo({
          has_attachment: true,
          filename: updatedInvoice.attachment_filename || null
        });
      } else {
        setAttachmentInfo(null);
      }

      logger.debug('Invoice data refreshed successfully');
    } catch (error) {
      logger.error('Failed to refresh invoice data:', error);
    }
  };

  // Debug invoice data
  useEffect(() => {
    logger.debug('Invoice data received', {
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

  // Debug formData changes
  useEffect(() => {
    logger.debug('FormData updated', {
      formDataItemsCount: formData.items.length,
      formDataItemDescriptions: formData.items.map(item => ({
        id: item.id,
        description: item.description,
        descriptionLength: item.description?.length || 0
      }))
    });
  }, [formData.items]);

  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showClientModal, setShowClientModal] = useState(false);
  const [showDateModal, setShowDateModal] = useState(false);
  const [showDueDateModal, setShowDueDateModal] = useState(false);
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showCurrencyModal, setShowCurrencyModal] = useState(false);
  const [currentDateField, setCurrentDateField] = useState<'date' | 'dueDate'>('date');
  const [error, setError] = useState<string | null>(null);
  const [clients, setClients] = useState(propClients);
  const [showAddClientModal, setShowAddClientModal] = useState(false);
  const [addClientForm, setAddClientForm] = useState({ name: '', email: '', phone: '', address: '' });
  const [addClientLoading, setAddClientLoading] = useState(false);
  const [addClientError, setAddClientError] = useState<string | null>(null);
  const [loadingAttachments, setLoadingAttachments] = useState(false);
  const [attachmentInfo, setAttachmentInfo] = useState<{ has_attachment: boolean; filename: string | null } | null>(null);

  // Debug modal states
  useEffect(() => {
    logger.debug('Modal states changed', {
      showClientModal,
      showAddClientModal,
      clientsCount: clients.length
    });
  }, [showClientModal, showAddClientModal, clients.length]);

  // Load existing attachment when invoice changes
  useEffect(() => {
    const loadAttachment = async () => {
      if (invoice.id) {
        try {
          setLoadingAttachments(true);
          const attachmentInfo = await apiService.getInvoiceAttachmentInfo(invoice.id);
          logger.debug('Loaded attachment info', attachmentInfo);

          // Check if invoice has an attachment
          if (attachmentInfo.has_attachment) {
            // Convert API attachment format to FileData format
            const fileData: FileData = {
              uri: `/invoices/${invoice.id}/download-attachment`, // Use download endpoint as URI
              name: attachmentInfo.filename,
              type: attachmentInfo.content_type,
              size: attachmentInfo.size_bytes,
              isExisting: true,
              attachmentId: invoice.id // Use invoice ID as attachment ID for single attachment
            };

            setAttachmentFiles([fileData]); // Single attachment, so array with one item
          } else {
            // No attachment exists
            setAttachmentFiles([]);
          }

          // Clear any pending deletions when loading fresh data
          setFilesToDelete(new Set());
        } catch (error) {
          logger.error('Failed to load attachment', error);
          // Don't show error to user, just log it - attachment loading failure shouldn't block invoice editing
          setAttachmentFiles([]);
          setFilesToDelete(new Set());
        } finally {
          setLoadingAttachments(false);
        }
      }
    };

    loadAttachment();
  }, [invoice.id]);



  const handleChange = (field: keyof EditInvoiceFormData, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    if (error) setError(null);
  };

  const handleItemChange = (index: number, field: keyof InvoiceItem, value: any) => {
    logger.debug('handleItemChange called', { index, field, value, currentItems: formData.items });
    
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

    logger.debug('Updated item', newItems[index]);
    logger.debug('All items after change', newItems.map(item => ({
      id: item.id,
      description: item.description,
      quantity: item.quantity,
      price: item.price
    })));
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
    if ((formData.items || []).length > 1) {
      const newItems = (formData.items || []).filter((_, i) => i !== index);
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
    logger.debug('Validating form', {
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
    if (formData.items.some(item => item.quantity < 0.01)) {
      setError('All items must have a quantity greater than 0');
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
    logger.debug('Starting handleUpdate for invoice:', invoice.id);      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      logger.debug('Sending update data', {
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

      // Prepare update data - include attachment deletion if needed
      let updateData = {
        ...formData,
        // Map field names to match API expectations
        client_id: parseInt(formData.client),
        amount: calculateTotal(),
        due_date: formData.dueDate,
        paid_amount: formData.paidAmount
      };

      // Remove fields that don't match API interface
      delete (updateData as any).client;
      delete (updateData as any).invoiceNumber;
      delete (updateData as any).dueDate;
      delete (updateData as any).paidAmount;

      logger.debug('Field mapping completed', {
        originalPaidAmount: formData.paidAmount,
        mappedPaidAmount: updateData.paid_amount,
        updateDataKeys: Object.keys(updateData),
        updateDataSnippet: {
          client_id: updateData.client_id,
          amount: updateData.amount,
          paid_amount: updateData.paid_amount,
          status: updateData.status
        }
      });

      // If we have files marked for deletion, include attachment_filename: null in the update
      if (filesToDelete.size > 0) {
        updateData = {
          ...updateData,
          attachment_filename: null
        };
        logger.debug('Attachment deletion flag added', { attachment_filename: updateData.attachment_filename });
      }

      logger.debug('Sending update to API', {
        invoiceId: invoice.id,
        updateData: updateData,
        paidAmount: updateData.paid_amount, // Specifically log paid_amount
        formPaidAmount: formData.paidAmount, // Log original form value
        itemsInUpdate: updateData.items?.map(item => ({
          id: item.id,
          description: item.description,
          quantity: item.quantity,
          price: item.price
        }))
      });

      await onUpdateInvoice(invoice.id, updateData);

      // Upload attachments if any (excluding files marked for deletion)
      const filesToUpload = attachmentFiles.filter((_, index) => !filesToDelete.has(index));
      if (filesToUpload.length > 0) {
      logger.debug('About to call onUpdateInvoice');        setUploadingAttachments(true);
        try {
      logger.debug('API call completed, about to refresh invoice data');
      await Promise.all(
        filesToUpload.map(file => uploadAttachmentToInvoice(invoice.id, file))
      );
      logger.debug('About to call refreshInvoiceData');          logger.error('Failed to upload attachments', uploadError);
          Alert.alert('Warning', 'Invoice updated but some attachments failed to upload. You can upload them later.');
        } finally {
          setUploadingAttachments(false);
        }
      }

      // Log successful attachment deletion (if any)
      if (filesToDelete.size > 0) {
        logger.info('Successfully marked attachments for deletion in invoice update');
        // Clear the deletion marks after successful update
        setFilesToDelete(new Set());
      }

      // Refresh invoice data from server to show the latest state
      await refreshInvoiceData();
    } catch (error: any) {
      logger.error('Update error', error);
      setError(error.message || 'Failed to update invoice');
      // Clear filesToDelete on error so user can try again
      setFilesToDelete(new Set());
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
    // For invoices, only allow one attachment - replace existing with new
    if (files.length > 0) {
      setAttachmentFiles([files[0]]); // Take only the first file
    }
  };

  const handleRemoveFile = (index: number) => {
    // Show confirmation modal instead of immediately deleting
    setFileToDeleteIndex(index);
    setShowDeleteConfirm(true);
  };

  const confirmDeleteFile = () => {
    if (fileToDeleteIndex === null) return;

    const index = fileToDeleteIndex;
    const fileToRemove = attachmentFiles[index];

    // Mark file for deletion (don't actually delete from backend yet)
    setFilesToDelete(prev => new Set([...prev, index]));

    // Close modal and reset state
    setShowDeleteConfirm(false);
    setFileToDeleteIndex(null);

    logger.info('File marked for deletion', { fileName: fileToRemove?.name, index });
  };

  const cancelDeleteFile = () => {
    setShowDeleteConfirm(false);
    setFileToDeleteIndex(null);
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
    logger.debug('Rendering add client modal', { visible: showAddClientModal });
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
    logger.debug('Rendering client selector modal', { visible: showClientModal, clientsCount: clients.length });
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
            {['pending', 'paid', 'overdue', 'draft'].map(status => {
              const isDisabled = isInvoiceProtected && status !== 'paid';
              return (
                <TouchableOpacity
                  key={status}
                  style={[
                    styles.statusOption,
                    formData.status === status && styles.statusOptionSelected,
                    isDisabled && styles.statusOptionDisabled
                  ]}
                  onPress={() => {
                    if (!isDisabled) {
                      handleChange('status', status);
                      setShowStatusModal(false);
                    }
                  }}
                  disabled={isDisabled}
                >
                <Text style={[
                  styles.statusOptionText,
                  formData.status === status && styles.statusOptionTextSelected
                ]}>{formatStatus(status)}</Text>
                  {formData.status === status && (
                    <Ionicons name="checkmark" size={20} color="#007AFF" />
                  )}
                </TouchableOpacity>
              );
            })}
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
          style={[styles.saveButton, (submitting || isInvoiceProtected) && styles.saveButtonDisabled]}
          onPress={handleUpdate}
          disabled={submitting || isInvoiceProtected}
        >
          {submitting ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.saveButtonText}>Update</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Warning banner for protected invoices */}
      {isInvoiceProtected && (
        <View style={styles.warningBanner}>
          <Ionicons name="warning" size={20} color="#92400E" />
          <Text style={styles.warningText}>
            This invoice has been paid and is protected from editing to maintain financial integrity.
          </Text>
        </View>
      )}

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
            <TouchableOpacity
              style={styles.selectorButton}
              onPress={() => setShowCurrencyModal(true)}
            >
              <Text style={styles.selectorText}>{formData.currency}</Text>
              <Ionicons name="chevron-down" size={16} color="#666" />
            </TouchableOpacity>
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
                    style={[styles.removeItemButton, isInvoiceProtected && styles.removeItemButtonDisabled]}
                    onPress={() => removeItem(index)}
                    disabled={isInvoiceProtected}
                  >
                    <Ionicons
                      name="trash-outline"
                      size={16}
                      color={isInvoiceProtected ? "#9CA3AF" : "#EF4444"}
                    />
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
                    onChangeText={(value) => handleItemChange(index, 'quantity', value === '' ? 0 : parseFloat(value) || 0)}
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
          
          <TouchableOpacity
            style={[styles.addItemButton, isInvoiceProtected && styles.addItemButtonDisabled]}
            onPress={addItem}
            disabled={isInvoiceProtected}
          >
            <Ionicons name="add" size={20} color={isInvoiceProtected ? "#9CA3AF" : "#007AFF"} />
            <Text style={[styles.addItemText, isInvoiceProtected && styles.addItemTextDisabled]}>
              Add Item
            </Text>
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

        {/* Attachments */}
        <EnhancedFileUpload
          title="Attachment"
          maxFiles={1}
          allowedTypes={['image/*', 'application/pdf']}
          onFilesSelected={handleFilesSelected}
          selectedFiles={attachmentFiles}
          onRemoveFile={handleRemoveFile}
          uploading={uploadingAttachments}
        />

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
              <Text style={styles.modalTitle}>Select Currency</Text>
              <TouchableOpacity onPress={() => setShowCurrencyModal(false)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <View style={styles.modalBody}>
              {['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'].map(currency => (
                <TouchableOpacity
                  key={currency}
                  style={[
                    styles.statusOption,
                    formData.currency === currency && styles.statusOptionSelected
                  ]}
                  onPress={() => {
                    handleChange('currency', currency);
                    setShowCurrencyModal(false);
                  }}
                >
                  <Text style={[
                    styles.statusOptionText,
                    formData.currency === currency && styles.statusOptionTextSelected
                  ]}>{currency}</Text>
                  {formData.currency === currency && (
                    <Ionicons name="checkmark" size={20} color="#007AFF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        visible={showDeleteConfirm}
        transparent
        animationType="fade"
        onRequestClose={cancelDeleteFile}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.deleteModalContent}>
            <Text style={styles.deleteModalTitle}>Delete Attachment</Text>
            <Text style={styles.deleteModalMessage}>
              Are you sure you want to delete this attachment? It will be permanently removed when you save the invoice.
            </Text>

            <View style={styles.deleteModalButtons}>
              <TouchableOpacity
                style={[styles.deleteModalButton, styles.cancelButton]}
                onPress={cancelDeleteFile}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.deleteModalButton, styles.confirmButton]}
                onPress={confirmDeleteFile}
              >
                <Text style={styles.confirmButtonText}>Mark for Deletion</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  addItemButtonDisabled: {
    backgroundColor: '#F9FAFB',
    borderColor: '#E5E7EB',
  },
  addItemTextDisabled: {
    color: '#9CA3AF',
  },
  removeItemButtonDisabled: {
    backgroundColor: '#F9FAFB',
    borderColor: '#E5E7EB',
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
  statusOptionDisabled: {
    opacity: 0.5,
    backgroundColor: '#F9FAFB',
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
  deleteModalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 24,
    marginHorizontal: 32,
    alignItems: 'center',
  },
  deleteModalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 12,
  },
  deleteModalMessage: {
    fontSize: 16,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 22,
  },
  deleteModalButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  deleteModalButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButton: {
    backgroundColor: '#F3F4F6',
  },
  confirmButton: {
    backgroundColor: '#EF4444',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  confirmButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF3C7',
    borderWidth: 1,
    borderColor: '#F59E0B',
    borderRadius: 8,
    padding: 12,
    marginHorizontal: 20,
    marginBottom: 16,
  },
  warningText: {
    flex: 1,
    fontSize: 14,
    color: '#92400E',
    marginLeft: 8,
    lineHeight: 20,
  },
});

export default EditInvoiceScreen; 