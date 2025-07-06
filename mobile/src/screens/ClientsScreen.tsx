import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import apiService, { Client, CreateClientData } from '../services/api';

interface ClientsScreenProps {
  clients: Client[];
  onNavigateBack: () => void;
  onClientAdded: (client: Client) => void;
  onClientUpdated: (client: Client) => void;
  onClientDeleted: (clientId: number) => void;
}

const ClientsScreen: React.FC<ClientsScreenProps> = ({
  clients,
  onNavigateBack,
  onClientAdded,
  onClientUpdated,
  onClientDeleted,
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [addForm, setAddForm] = useState({
    name: '',
    email: '',
    phone: '',
    address: '',
  });

  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    phone: '',
    address: '',
  });

  const handleAddClient = async () => {
    if (!addForm.name.trim() || !addForm.email.trim()) {
      setError('Name and email are required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const newClient = await apiService.createClient(addForm as CreateClientData);
      onClientAdded(newClient);
      setShowAddModal(false);
      setAddForm({ name: '', email: '', phone: '', address: '' });
      Alert.alert('Success', 'Client added successfully!');
    } catch (error: any) {
      setError(error.message || 'Failed to add client');
    } finally {
      setLoading(false);
    }
  };

  const handleEditClient = async () => {
    if (!selectedClient || !editForm.name.trim() || !editForm.email.trim()) {
      setError('Name and email are required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const updatedClient = await apiService.updateClient(selectedClient.id, editForm);
      onClientUpdated(updatedClient);
      setShowEditModal(false);
      setSelectedClient(null);
      Alert.alert('Success', 'Client updated successfully!');
    } catch (error: any) {
      setError(error.message || 'Failed to update client');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClient = (client: Client) => {
    Alert.alert(
      'Delete Client',
      `Are you sure you want to delete ${client.name}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await apiService.deleteClient(client.id);
              onClientDeleted(client.id);
              Alert.alert('Success', 'Client deleted successfully!');
            } catch (error: any) {
              Alert.alert('Error', error.message || 'Failed to delete client');
            }
          },
        },
      ]
    );
  };

  const openEditModal = (client: Client) => {
    setSelectedClient(client);
    setEditForm({
      name: client.name,
      email: client.email,
      phone: client.phone || '',
      address: client.address || '',
    });
    setShowEditModal(true);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const renderAddModal = () => (
    <Modal
      visible={showAddModal}
      transparent
      animationType="slide"
      onRequestClose={() => setShowAddModal(false)}
    >
      <KeyboardAvoidingView 
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Add New Client</Text>
            <TouchableOpacity onPress={() => setShowAddModal(false)}>
              <Ionicons name="close" size={24} color="#666" />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
            {error && <Text style={styles.errorText}>{error}</Text>}
            <TextInput
              style={styles.input}
              placeholder="Name*"
              value={addForm.name}
              onChangeText={(text) => setAddForm(prev => ({ ...prev, name: text }))}
            />
            <TextInput
              style={styles.input}
              placeholder="Email*"
              value={addForm.email}
              onChangeText={(text) => setAddForm(prev => ({ ...prev, email: text }))}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <TextInput
              style={styles.input}
              placeholder="Phone"
              value={addForm.phone}
              onChangeText={(text) => setAddForm(prev => ({ ...prev, phone: text }))}
              keyboardType="phone-pad"
            />
            <TextInput
              style={styles.input}
              placeholder="Address"
              value={addForm.address}
              onChangeText={(text) => setAddForm(prev => ({ ...prev, address: text }))}
              multiline
              numberOfLines={3}
            />
            <TouchableOpacity
              style={[styles.saveButton, loading && styles.saveButtonDisabled]}
              onPress={handleAddClient}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.saveButtonText}>Add Client</Text>
              )}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

  const renderEditModal = () => (
    <Modal
      visible={showEditModal}
      transparent
      animationType="slide"
      onRequestClose={() => setShowEditModal(false)}
    >
      <KeyboardAvoidingView 
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Edit Client</Text>
            <TouchableOpacity onPress={() => setShowEditModal(false)}>
              <Ionicons name="close" size={24} color="#666" />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
            {error && <Text style={styles.errorText}>{error}</Text>}
            <TextInput
              style={styles.input}
              placeholder="Name*"
              value={editForm.name}
              onChangeText={(text) => setEditForm(prev => ({ ...prev, name: text }))}
            />
            <TextInput
              style={styles.input}
              placeholder="Email*"
              value={editForm.email}
              onChangeText={(text) => setEditForm(prev => ({ ...prev, email: text }))}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <TextInput
              style={styles.input}
              placeholder="Phone"
              value={editForm.phone}
              onChangeText={(text) => setEditForm(prev => ({ ...prev, phone: text }))}
              keyboardType="phone-pad"
            />
            <TextInput
              style={styles.input}
              placeholder="Address"
              value={editForm.address}
              onChangeText={(text) => setEditForm(prev => ({ ...prev, address: text }))}
              multiline
              numberOfLines={3}
            />
            <TouchableOpacity
              style={[styles.saveButton, loading && styles.saveButtonDisabled]}
              onPress={handleEditClient}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.saveButtonText}>Update Client</Text>
              )}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={onNavigateBack} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Clients</Text>
        <TouchableOpacity onPress={() => setShowAddModal(true)} style={styles.addButton}>
          <Ionicons name="add" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Content */}
      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {clients.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="people-outline" size={64} color="#ccc" />
            <Text style={styles.emptyStateText}>No clients yet</Text>
            <Text style={styles.emptyStateSubtext}>Add your first client to get started</Text>
            <TouchableOpacity
              style={styles.emptyStateButton}
              onPress={() => setShowAddModal(true)}
            >
              <Text style={styles.emptyStateButtonText}>Add Client</Text>
            </TouchableOpacity>
          </View>
        ) : (
          clients.map((client) => (
            <View key={client.id} style={styles.clientCard}>
              <View style={styles.clientInfo}>
                <Text style={styles.clientName}>{client.name}</Text>
                <Text style={styles.clientEmail}>{client.email}</Text>
                {client.phone && (
                  <Text style={styles.clientPhone}>{client.phone}</Text>
                )}
                {client.address && (
                  <Text style={styles.clientAddress}>{client.address}</Text>
                )}
                <View style={styles.clientStats}>
                  <Text style={styles.clientStat}>
                    Balance: {formatCurrency(client.balance)}
                  </Text>
                  <Text style={styles.clientStat}>
                    Paid: {formatCurrency(client.paid_amount)}
                  </Text>
                </View>
              </View>
              <View style={styles.clientActions}>
                <TouchableOpacity
                  style={styles.actionButton}
                  onPress={() => openEditModal(client)}
                >
                  <Ionicons name="pencil" size={20} color="#007AFF" />
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.actionButton, styles.deleteButton]}
                  onPress={() => handleDeleteClient(client)}
                >
                  <Ionicons name="trash" size={20} color="#FF3B30" />
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {renderAddModal()}
      {renderEditModal()}
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
    paddingTop: 60,
    paddingBottom: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  backButton: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
  },
  addButton: {
    padding: 8,
  },
  content: {
    flex: 1,
    padding: 20,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyStateText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#666',
    marginTop: 16,
  },
  emptyStateSubtext: {
    fontSize: 14,
    color: '#999',
    marginTop: 8,
    textAlign: 'center',
  },
  emptyStateButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 20,
  },
  emptyStateButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  clientCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  clientInfo: {
    flex: 1,
  },
  clientName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  clientEmail: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  clientPhone: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  clientAddress: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  clientStats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  clientStat: {
    fontSize: 12,
    color: '#888',
    fontWeight: '500',
  },
  clientActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 12,
  },
  actionButton: {
    padding: 8,
    marginLeft: 8,
  },
  deleteButton: {
    // Additional styling if needed
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    width: '90%',
    maxHeight: '80%',
    minHeight: 400,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  modalBody: {
    padding: 20,
    paddingBottom: 40,
  },
  input: {
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    fontSize: 16,
  },
  saveButton: {
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  saveButtonDisabled: {
    backgroundColor: '#ccc',
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  errorText: {
    color: '#FF3B30',
    fontSize: 14,
    marginBottom: 16,
  },
});

export default ClientsScreen; 