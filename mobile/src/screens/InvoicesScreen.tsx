import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Modal,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';

interface Invoice {
  id: number;
  number: string;
  client_name: string;
  date: string;
  due_date: string;
  amount: number;
  paid_amount: number;
  status: string;
}

interface InvoicesScreenProps {
  invoices: Array<{
    id: number;
    number: string;
    client_name: string;
    due_date: string;
    amount: number;
    total_paid: number;
    status: string;
  }>;
  onNavigateToNewInvoice: () => void;
  onNavigateToEditInvoice: (invoiceId: number) => void;
  onNavigateBack: () => void;
}

const InvoicesScreen: React.FC<InvoicesScreenProps> = ({
  invoices: propInvoices,
  onNavigateToNewInvoice,
  onNavigateToEditInvoice,
  onNavigateBack,
}) => {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showStatusModal, setShowStatusModal] = useState(false);

  // Use invoices from props instead of fetching
  const invoices = propInvoices;

  const onRefresh = async () => {
    setRefreshing(true);
    // In a real app, this would refresh the invoices from the API
    await new Promise(resolve => setTimeout(resolve, 500));
    setRefreshing(false);
  };

  const filteredInvoices = (invoices || []).filter((invoice: any) => {
    const matchesSearch = 
      invoice.number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      invoice.client_name.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || invoice.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const formatStatus = (status: string) => {
    return status.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid':
        return '#10B981';
      case 'pending':
        return '#F59E0B';
      case 'draft':
        return '#6B7280';
      case 'overdue':
        return '#EF4444';
      default:
        return '#6B7280';
    }
  };

  const getStatusBackground = (status: string) => {
    switch (status) {
      case 'paid':
        return '#D1FAE5';
      case 'pending':
        return '#FEF3C7';
      case 'draft':
        return '#F3F4F6';
      case 'overdue':
        return '#FEE2E2';
      default:
        return '#F3F4F6';
    }
  };

  const renderInvoiceItem = ({ item }: { item: any }) => {
    const outstandingBalance = item.amount - (item.total_paid || 0);
    
    return (
      <TouchableOpacity
        style={styles.invoiceCard}
        onPress={() => onNavigateToEditInvoice(item.id)}
      >
        <View style={styles.invoiceHeader}>
          <View style={styles.invoiceNumberContainer}>
            <Ionicons name="document-text-outline" size={16} color="#6B7280" />
            <Text style={styles.invoiceNumber}>{item.number}</Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: getStatusBackground(item.status) }]}>
            <Text style={[styles.statusText, { color: getStatusColor(item.status) }]}>
              {formatStatus(item.status)}
            </Text>
          </View>
        </View>
        
        <Text style={styles.clientName}>{item.client_name}</Text>
        
        <View style={styles.invoiceDetails}>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Date:</Text>
            <Text style={styles.detailValue}>{item.date}</Text>
          </View>
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Due Date:</Text>
            <Text style={styles.detailValue}>{item.due_date}</Text>
          </View>
        </View>
        
        <View style={styles.amountContainer}>
          <View style={styles.amountRow}>
            <Text style={styles.amountLabel}>Total:</Text>
            <Text style={styles.totalAmount}>${item.amount.toFixed(2)}</Text>
          </View>
          <View style={styles.amountRow}>
            <Text style={styles.amountLabel}>Paid:</Text>
            <Text style={styles.paidAmount}>${(item.total_paid || 0).toFixed(2)}</Text>
          </View>
          <View style={styles.amountRow}>
            <Text style={styles.amountLabel}>Outstanding:</Text>
            <Text style={[
              styles.outstandingAmount,
              { color: outstandingBalance > 0 ? '#F59E0B' : '#10B981' }
            ]}>
              ${outstandingBalance.toFixed(2)}
            </Text>
          </View>
        </View>
      </TouchableOpacity>
    );
  };



  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Invoices</Text>
        <TouchableOpacity style={styles.addButton} onPress={onNavigateToNewInvoice}>
          <Ionicons name="add" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <View style={styles.searchContainer}>
        <View style={styles.searchInputContainer}>
          <Ionicons name="search" size={20} color="#6B7280" style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search invoices..."
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
        </View>
        
        <View style={styles.filterContainer}>
          <Ionicons name="filter" size={20} color="#6B7280" />
          <TouchableOpacity
            style={styles.filterButton}
            onPress={() => setShowStatusModal(true)}
          >
            <Text style={styles.filterText}>
              {statusFilter === 'all' ? 'All Statuses' : formatStatus(statusFilter)}
            </Text>
            <Ionicons name="chevron-down" size={16} color="#6B7280" />
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        data={filteredInvoices}
        renderItem={renderInvoiceItem}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="document-text-outline" size={48} color="#9CA3AF" />
            <Text style={styles.emptyText}>No invoices found</Text>
            <Text style={styles.emptySubtext}>
              {searchQuery || statusFilter !== 'all' 
                ? 'Try adjusting your search or filters'
                : 'Create your first invoice to get started'
              }
            </Text>
          </View>
        }
      />

      {/* Status Filter Modal */}
      <Modal
        visible={showStatusModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowStatusModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Filter by Status</Text>
              <TouchableOpacity onPress={() => setShowStatusModal(false)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <View style={styles.modalBody}>
              <TouchableOpacity
                style={[
                  styles.statusOption,
                  statusFilter === 'all' && styles.statusOptionSelected
                ]}
                onPress={() => {
                  setStatusFilter('all');
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  statusFilter === 'all' && styles.statusOptionTextSelected
                ]}>All Statuses</Text>
                {statusFilter === 'all' && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[
                  styles.statusOption,
                  statusFilter === 'paid' && styles.statusOptionSelected
                ]}
                onPress={() => {
                  setStatusFilter('paid');
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  statusFilter === 'paid' && styles.statusOptionTextSelected
                ]}>Paid</Text>
                {statusFilter === 'paid' && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[
                  styles.statusOption,
                  statusFilter === 'pending' && styles.statusOptionSelected
                ]}
                onPress={() => {
                  setStatusFilter('pending');
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  statusFilter === 'pending' && styles.statusOptionTextSelected
                ]}>Pending</Text>
                {statusFilter === 'pending' && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[
                  styles.statusOption,
                  statusFilter === 'overdue' && styles.statusOptionSelected
                ]}
                onPress={() => {
                  setStatusFilter('overdue');
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  statusFilter === 'overdue' && styles.statusOptionTextSelected
                ]}>Overdue</Text>
                {statusFilter === 'overdue' && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[
                  styles.statusOption,
                  statusFilter === 'draft' && styles.statusOptionSelected
                ]}
                onPress={() => {
                  setStatusFilter('draft');
                  setShowStatusModal(false);
                }}
              >
                <Text style={[
                  styles.statusOptionText,
                  statusFilter === 'draft' && styles.statusOptionTextSelected
                ]}>Draft</Text>
                {statusFilter === 'draft' && (
                  <Ionicons name="checkmark" size={20} color="#007AFF" />
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
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
  addButton: {
    padding: 8,
  },
  searchContainer: {
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  searchInputContainer: {
    position: 'relative',
    marginBottom: 12,
  },
  searchIcon: {
    position: 'absolute',
    left: 12,
    top: 12,
    zIndex: 1,
  },
  searchInput: {
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    paddingHorizontal: 40,
    paddingVertical: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  filterContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 6,
    backgroundColor: '#fff',
  },
  filterText: {
    fontSize: 14,
    color: '#333',
    marginRight: 4,
  },
  listContainer: {
    padding: 20,
  },
  invoiceCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  invoiceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  invoiceNumberContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  invoiceNumber: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginLeft: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  clientName: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  invoiceDetails: {
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  detailLabel: {
    fontSize: 12,
    color: '#666',
  },
  detailValue: {
    fontSize: 12,
    color: '#333',
    fontWeight: '500',
  },
  amountContainer: {
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
    paddingTop: 12,
  },
  amountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  amountLabel: {
    fontSize: 14,
    color: '#666',
  },
  totalAmount: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#333',
  },
  paidAmount: {
    fontSize: 14,
    color: '#10B981',
    fontWeight: '500',
  },
  outstandingAmount: {
    fontSize: 14,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    paddingHorizontal: 20,
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
    maxHeight: '70%',
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
});

export default InvoicesScreen; 