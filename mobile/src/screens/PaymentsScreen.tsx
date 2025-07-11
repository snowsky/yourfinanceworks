import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  TextInput,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import apiService from '../services/api';
import { Payment } from '../services/api';
import { formatCurrency } from '../utils/currency';

interface PaymentsScreenProps {
  onNavigateBack: () => void;
}

const PaymentsScreen: React.FC<PaymentsScreenProps> = ({ onNavigateBack }) => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [filteredPayments, setFilteredPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [methodFilter, setMethodFilter] = useState('all');
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const paymentMethods = [
    { value: 'all', label: 'All Methods' },
    { value: 'credit_card', label: 'Credit Card' },
    { value: 'bank_transfer', label: 'Bank Transfer' },
    { value: 'cash', label: 'Cash' },
    { value: 'system', label: 'System' },
    { value: 'check', label: 'Check' },
    { value: 'paypal', label: 'PayPal' },
  ];

  useEffect(() => {
    loadPayments();
  }, []);

  useEffect(() => {
    filterPayments();
  }, [payments, searchQuery, methodFilter]);

  const loadPayments = async (pageNum = 1) => {
    try {
      setLoading(true);
      const response = await apiService.getPayments();
      if (pageNum === 1) {
        setPayments(response);
      } else {
        setPayments(prev => [...prev, ...response]);
      }
      setHasMore(response.length === 20); // Assuming 20 items per page
      setPage(response.length > 0 ? pageNum : pageNum - 1);
    } catch (error) {
      console.error('Failed to load payments:', error);
      Alert.alert('Error', 'Failed to load payments');
    } finally {
      setLoading(false);
    }
  };

  const filterPayments = () => {
    let filtered = payments;

    // Apply search filter
    if (searchQuery.trim()) {
      filtered = filtered.filter(payment =>
        payment.invoice_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
        payment.client_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (payment.reference_number && payment.reference_number.toLowerCase().includes(searchQuery.toLowerCase()))
      );
    }

    // Apply method filter
    if (methodFilter !== 'all') {
      filtered = filtered.filter(payment => payment.payment_method === methodFilter);
    }

    setFilteredPayments(filtered);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadPayments(1);
    setRefreshing(false);
  };

  const loadMore = () => {
    if (hasMore && !loading) {
      loadPayments(page + 1);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#10B981';
      case 'pending':
        return '#F59E0B';
      case 'failed':
        return '#EF4444';
      default:
        return '#6B7280';
    }
  };

  const getMethodIcon = (method: string) => {
    switch (method) {
      case 'credit_card':
        return 'card-outline';
      case 'bank_transfer':
        return 'business-outline';
      case 'cash':
        return 'cash-outline';
      case 'system':
        return 'settings-outline';
      case 'check':
        return 'document-text-outline';
      case 'paypal':
        return 'logo-paypal';
      default:
        return 'card-outline';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const renderPayment = ({ item }: { item: Payment }) => (
    <TouchableOpacity style={styles.paymentCard}>
      <View style={styles.paymentHeader}>
        <View style={styles.paymentInfo}>
          <Text style={styles.paymentAmount}>
            {formatCurrency(item.amount, item.currency || 'USD')}
          </Text>
          <View style={styles.paymentMeta}>
            <Text style={styles.invoiceNumber}>#{item.invoice_number}</Text>
            <Text style={styles.clientName}>{item.client_name}</Text>
          </View>
        </View>
        <View style={styles.paymentStatus}>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
            <Text style={styles.statusText}>{item.status}</Text>
          </View>
        </View>
      </View>

      <View style={styles.paymentDetails}>
        <View style={styles.detailRow}>
          <View style={styles.detailItem}>
            <Ionicons name={getMethodIcon(item.payment_method) as any} size={16} color="#6B7280" />
            <Text style={styles.detailText}>{item.payment_method.replace('_', ' ')}</Text>
          </View>
          <Text style={styles.paymentDate}>{formatDate(item.payment_date)}</Text>
        </View>

        {item.reference_number && (
          <View style={styles.detailRow}>
            <Text style={styles.referenceLabel}>Reference:</Text>
            <Text style={styles.referenceNumber}>{item.reference_number}</Text>
          </View>
        )}

        {item.notes && (
          <View style={styles.notesContainer}>
            <Text style={styles.notesLabel}>Notes:</Text>
            <Text style={styles.notesText}>{item.notes}</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  const renderFilterModal = () => (
    <Modal
      visible={showFilterModal}
      animationType="slide"
      transparent={true}
      onRequestClose={() => setShowFilterModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Filter Payments</Text>
            <TouchableOpacity onPress={() => setShowFilterModal(false)}>
              <Ionicons name="close" size={24} color="#6B7280" />
            </TouchableOpacity>
          </View>

          <View style={styles.filterSection}>
            <Text style={styles.filterLabel}>Payment Method</Text>
            {paymentMethods.map((method) => (
              <TouchableOpacity
                key={method.value}
                style={[
                  styles.filterOption,
                  methodFilter === method.value && styles.filterOptionActive
                ]}
                onPress={() => {
                  setMethodFilter(method.value);
                  setShowFilterModal(false);
                }}
              >
                <Text style={[
                  styles.filterOptionText,
                  methodFilter === method.value && styles.filterOptionTextActive
                ]}>
                  {method.label}
                </Text>
                {methodFilter === method.value && (
                  <Ionicons name="checkmark" size={20} color="#3B82F6" />
                )}
              </TouchableOpacity>
            ))}
          </View>

          <TouchableOpacity
            style={styles.clearFilterButton}
            onPress={() => {
              setMethodFilter('all');
              setShowFilterModal(false);
            }}
          >
            <Text style={styles.clearFilterText}>Clear Filters</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  const renderEmptyState = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="card-outline" size={64} color="#9CA3AF" />
      <Text style={styles.emptyTitle}>No Payments Found</Text>
      <Text style={styles.emptySubtitle}>
        {searchQuery || methodFilter !== 'all' 
          ? 'Try adjusting your search or filters'
          : 'Payments will appear here once they are recorded'
        }
      </Text>
    </View>
  );

  const renderHeader = () => (
    <View style={styles.header}>
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#6B7280" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search payments..."
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholderTextColor="#9CA3AF"
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => setSearchQuery('')}>
            <Ionicons name="close-circle" size={20} color="#6B7280" />
          </TouchableOpacity>
        )}
      </View>

      <TouchableOpacity
        style={[styles.filterButton, methodFilter !== 'all' && styles.filterButtonActive]}
        onPress={() => setShowFilterModal(true)}
      >
        <Ionicons name="filter" size={20} color={methodFilter !== 'all' ? '#FFFFFF' : '#6B7280'} />
        <Text style={[styles.filterButtonText, methodFilter !== 'all' && styles.filterButtonTextActive]}>
          Filter
        </Text>
        {methodFilter !== 'all' && (
          <View style={styles.filterBadge}>
            <Text style={styles.filterBadgeText}>1</Text>
          </View>
        )}
      </TouchableOpacity>
    </View>
  );

  if (loading && payments.length === 0) {
    return (
      <View style={styles.loadingContainer}>
        <StatusBar style="dark" />
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>Loading payments...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      
      <View style={styles.navigationHeader}>
        <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
          <Ionicons name="arrow-back" size={24} color="#374151" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Payments</Text>
        <View style={styles.headerSpacer} />
      </View>

      {renderHeader()}

      <FlatList
        data={filteredPayments}
        renderItem={renderPayment}
        keyExtractor={(item) => item.id.toString()}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.1}
        ListEmptyComponent={renderEmptyState()}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContainer}
      />

      {renderFilterModal()}
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
  navigationHeader: {
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
  headerSpacer: {
    width: 40,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    gap: 12,
  },
  searchContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: '#111827',
    paddingVertical: 12,
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
    gap: 4,
  },
  filterButtonActive: {
    backgroundColor: '#3B82F6',
  },
  filterButtonText: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
  filterButtonTextActive: {
    color: '#FFFFFF',
  },
  filterBadge: {
    backgroundColor: '#EF4444',
    borderRadius: 10,
    width: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 4,
  },
  filterBadgeText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  listContainer: {
    paddingBottom: 20,
  },
  paymentCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    margin: 16,
    marginBottom: 8,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  paymentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  paymentInfo: {
    flex: 1,
  },
  paymentAmount: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#10B981',
    marginBottom: 4,
  },
  paymentMeta: {
    gap: 2,
  },
  invoiceNumber: {
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  clientName: {
    fontSize: 14,
    color: '#6B7280',
  },
  paymentStatus: {
    alignItems: 'flex-end',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    textTransform: 'capitalize',
  },
  paymentDetails: {
    gap: 8,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  detailText: {
    fontSize: 14,
    color: '#6B7280',
    textTransform: 'capitalize',
  },
  paymentDate: {
    fontSize: 14,
    color: '#6B7280',
  },
  referenceLabel: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
  },
  referenceNumber: {
    fontSize: 14,
    color: '#374151',
    fontWeight: '500',
  },
  notesContainer: {
    marginTop: 4,
  },
  notesLabel: {
    fontSize: 14,
    color: '#6B7280',
    fontWeight: '500',
    marginBottom: 2,
  },
  notesText: {
    fontSize: 14,
    color: '#374151',
    fontStyle: 'italic',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
  },
  filterSection: {
    marginBottom: 20,
  },
  filterLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 12,
  },
  filterOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 4,
  },
  filterOptionActive: {
    backgroundColor: '#EFF6FF',
  },
  filterOptionText: {
    fontSize: 16,
    color: '#374151',
  },
  filterOptionTextActive: {
    color: '#3B82F6',
    fontWeight: '600',
  },
  clearFilterButton: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  clearFilterText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
});

export default PaymentsScreen; 