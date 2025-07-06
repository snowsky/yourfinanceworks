import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import apiService from '@/services/api';
import { Payment } from '@/types';

const PaymentsScreen: React.FC = () => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    loadPayments();
  }, []);

  const loadPayments = async (pageNum = 1) => {
    try {
      setIsLoading(true);
      const response = await apiService.getPayments(pageNum, 20);
      if (pageNum === 1) {
        setPayments(response.items);
      } else {
        setPayments(prev => [...prev, ...response.items]);
      }
      setHasMore(response.page < response.pages);
      setPage(response.page);
    } catch (error) {
      console.error('Failed to load payments:', error);
      Alert.alert('Error', 'Failed to load payments');
    } finally {
      setIsLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadPayments(1);
    setRefreshing(false);
  };

  const loadMore = () => {
    if (hasMore && !isLoading) {
      loadPayments(page + 1);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const renderPayment = ({ item }: { item: Payment }) => (
    <TouchableOpacity style={styles.paymentCard}>
      <View style={styles.paymentHeader}>
        <Text style={styles.paymentAmount}>{formatCurrency(item.amount)}</Text>
        <Text style={styles.paymentMethod}>{item.payment_method}</Text>
      </View>
      <Text style={styles.invoiceNumber}>
        Invoice: #{item.invoice.invoice_number}
      </Text>
      <Text style={styles.clientName}>{item.invoice.client.name}</Text>
      <View style={styles.paymentFooter}>
        <Text style={styles.paymentDate}>
          {new Date(item.payment_date).toLocaleDateString()}
        </Text>
        {item.reference_number && (
          <Text style={styles.referenceNumber}>
            Ref: {item.reference_number}
          </Text>
        )}
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={payments}
        renderItem={renderPayment}
        keyExtractor={(item) => item.id.toString()}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.1}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No payments found</Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  paymentCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    marginBottom: 8,
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
    alignItems: 'center',
    marginBottom: 8,
  },
  paymentAmount: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#34C759',
  },
  paymentMethod: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  invoiceNumber: {
    fontSize: 14,
    color: '#007AFF',
    marginBottom: 4,
  },
  clientName: {
    fontSize: 16,
    color: '#333',
    marginBottom: 8,
  },
  paymentFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  paymentDate: {
    fontSize: 12,
    color: '#999',
  },
  referenceNumber: {
    fontSize: 12,
    color: '#999',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
});

export default PaymentsScreen; 