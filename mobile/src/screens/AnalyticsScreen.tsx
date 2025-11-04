import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import apiService, { DashboardStats } from '../services/api';
import { formatCurrency } from '../utils/currency';

interface AnalyticsScreenProps {
  onNavigateBack: () => void;
}

const AnalyticsScreen: React.FC<AnalyticsScreenProps> = ({
  onNavigateBack,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState<DashboardStats>({
    totalIncome: {},
    pendingInvoices: {},
    totalExpenses: {},
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
  });
  const [period, setPeriod] = useState<'7' | '30' | '90'>('30');

  useEffect(() => {
    fetchAnalytics();
  }, [period]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const dashboardStats = await apiService.getDashboardStats();
      setStats(dashboardStats);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      Alert.alert('Error', 'Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAnalytics();
    setRefreshing(false);
  };

  const MetricCard = ({ 
    title, 
    value, 
    icon, 
    color, 
    trend 
  }: {
    title: string;
    value: string;
    icon: string;
    color: string;
    trend?: { value: number; direction: 'up' | 'down' | 'neutral' };
  }) => (
    <View style={styles.metricCard}>
      <View style={styles.metricHeader}>
        <View style={[styles.metricIcon, { backgroundColor: color }]}>
          <Ionicons name={icon as any} size={24} color="#FFFFFF" />
        </View>
        {trend && (
          <View style={styles.trendContainer}>
            <Ionicons 
              name={
                trend.direction === 'up' 
                  ? 'trending-up' 
                  : trend.direction === 'down' 
                    ? 'trending-down' 
                    : 'remove'
              } 
              size={16} 
              color={
                trend.direction === 'up' 
                  ? '#10B981' 
                  : trend.direction === 'down' 
                    ? '#EF4444' 
                    : '#6B7280'
              } 
            />
            <Text 
              style={[
                styles.trendText,
                {
                  color: trend.direction === 'up' 
                    ? '#10B981' 
                    : trend.direction === 'down' 
                      ? '#EF4444' 
                      : '#6B7280'
                }
              ]}
            >
              {Math.abs(trend.value)}%
            </Text>
          </View>
        )}
      </View>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricTitle}>{title}</Text>
    </View>
  );

  const SummaryRow = ({ 
    label, 
    value, 
    color = '#374151' 
  }: {
    label: string;
    value: string;
    color?: string;
  }) => (
    <View style={styles.summaryRow}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={[styles.summaryValue, { color }]}>{value}</Text>
    </View>
  );

  const formatIncomeDisplay = (income: Record<string, number>) => {
    const entries = Object.entries(income);
    if (entries.length === 0) return '$0.00';
    if (entries.length === 1) {
      const [currency, amount] = entries[0];
      return formatCurrency(amount, currency);
    }
    return entries.map(([currency, amount]) => 
      formatCurrency(amount, currency)
    ).join(' + ');
  };

  const formatPendingDisplay = (pending: Record<string, number>) => {
    const entries = Object.entries(pending);
    if (entries.length === 0) return '$0.00';
    if (entries.length === 1) {
      const [currency, amount] = entries[0];
      return formatCurrency(amount, currency);
    }
    return entries.map(([currency, amount]) => 
      formatCurrency(amount, currency)
    ).join(' + ');
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <StatusBar style="dark" />
        
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={onNavigateBack}>
            <Ionicons name="arrow-back" size={24} color="#374151" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Analytics</Text>
          <View style={styles.placeholder} />
        </View>

        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3B82F6" />
          <Text style={styles.loadingText}>Loading analytics...</Text>
        </View>
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
        <Text style={styles.headerTitle}>Analytics</Text>
        <TouchableOpacity style={styles.refreshButton} onPress={onRefresh}>
          <Ionicons name="refresh" size={24} color="#3B82F6" />
        </TouchableOpacity>
      </View>

      {/* Period Selector */}
      <View style={styles.periodSelector}>
        {['7', '30', '90'].map((days) => (
          <TouchableOpacity
            key={days}
            style={[
              styles.periodButton,
              period === days && styles.periodButtonActive
            ]}
            onPress={() => setPeriod(days as any)}
          >
            <Text 
              style={[
                styles.periodButtonText,
                period === days && styles.periodButtonTextActive
              ]}
            >
              {days === '7' ? 'Last 7 days' : 
               days === '30' ? 'Last 30 days' : 
               'Last 90 days'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Key Metrics */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Key Metrics</Text>
          <View style={styles.metricsGrid}>
            <MetricCard
              title="Total Revenue"
              value={formatIncomeDisplay(stats.totalIncome)}
              icon="wallet-outline"
              color="#10B981"
              trend={
                stats.monthlyStats
                  ? {
                      value: Math.abs(stats.monthlyStats.percentageChange),
                      direction: stats.monthlyStats.percentageChange > 0 
                        ? 'up' 
                        : stats.monthlyStats.percentageChange < 0 
                          ? 'down' 
                          : 'neutral'
                    }
                  : undefined
              }
            />
            <MetricCard
              title="Pending Amount"
              value={formatPendingDisplay(stats.pendingInvoices)}
              icon="time-outline"
              color="#F59E0B"
            />
            <MetricCard
              title="Total Clients"
              value={stats.totalClients.toString()}
              icon="people-outline"
              color="#3B82F6"
            />
            <MetricCard
              title="Overdue Invoices"
              value={stats.invoicesOverdue.toString()}
              icon="alert-circle-outline"
              color="#EF4444"
            />
          </View>
        </View>

        {/* Invoice Summary */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>t('inventory.invoice_summary')</Text>
          <View style={styles.summaryCard}>
            <SummaryRow 
              label="Paid Invoices" 
              value={stats.invoicesPaid.toString()} 
              color="#10B981"
            />
            <SummaryRow 
              label="Pending Invoices" 
              value={stats.invoicesPending.toString()} 
              color="#F59E0B"
            />
            <SummaryRow 
              label="Overdue Invoices" 
              value={stats.invoicesOverdue.toString()} 
              color="#EF4444"
            />
            <View style={styles.summaryDivider} />
            <SummaryRow 
              label="Total Invoices" 
              value={(stats.invoicesPaid + stats.invoicesPending + stats.invoicesOverdue).toString()}
            />
          </View>
        </View>

        {/* Monthly Trend */}
        {stats.monthlyStats && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Monthly Trend</Text>
            <View style={styles.trendCard}>
              <View style={styles.trendRow}>
                <Text style={styles.trendLabel}>Current Month</Text>
                <Text style={styles.trendValue}>
                  {formatCurrency(stats.monthlyStats.currentMonth, 'USD')}
                </Text>
              </View>
              <View style={styles.trendRow}>
                <Text style={styles.trendLabel}>Previous Month</Text>
                <Text style={styles.trendValue}>
                  {formatCurrency(stats.monthlyStats.previousMonth, 'USD')}
                </Text>
              </View>
              <View style={styles.trendDivider} />
              <View style={styles.trendRow}>
                <Text style={styles.trendLabel}>Change</Text>
                <View style={styles.trendChangeContainer}>
                  <Ionicons 
                    name={
                      stats.monthlyStats.percentageChange > 0 
                        ? 'trending-up' 
                        : stats.monthlyStats.percentageChange < 0 
                          ? 'trending-down' 
                          : 'remove'
                    } 
                    size={16} 
                    color={
                      stats.monthlyStats.percentageChange > 0 
                        ? '#10B981' 
                        : stats.monthlyStats.percentageChange < 0 
                          ? '#EF4444' 
                          : '#6B7280'
                    } 
                  />
                  <Text 
                    style={[
                      styles.trendChangeText,
                      {
                        color: stats.monthlyStats.percentageChange > 0 
                          ? '#10B981' 
                          : stats.monthlyStats.percentageChange < 0 
                            ? '#EF4444' 
                            : '#6B7280'
                      }
                    ]}
                  >
                    {Math.abs(stats.monthlyStats.percentageChange).toFixed(1)}%
                  </Text>
                </View>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
    borderRadius: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
  },
  refreshButton: {
    padding: 8,
    borderRadius: 8,
  },
  placeholder: {
    width: 40,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6B7280',
  },
  periodSelector: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 8,
  },
  periodButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    alignItems: 'center',
  },
  periodButtonActive: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  periodButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#374151',
  },
  periodButtonTextActive: {
    color: '#FFFFFF',
  },
  scrollView: {
    flex: 1,
  },
  section: {
    paddingHorizontal: 20,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 16,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  metricCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    width: '47%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  metricHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  metricIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  trendContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  trendText: {
    fontSize: 12,
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 4,
  },
  metricTitle: {
    fontSize: 12,
    color: '#6B7280',
  },
  summaryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  summaryValue: {
    fontSize: 16,
    fontWeight: '600',
  },
  summaryDivider: {
    height: 1,
    backgroundColor: '#E5E7EB',
    marginVertical: 8,
  },
  trendCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  trendRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  trendLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  trendValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  trendDivider: {
    height: 1,
    backgroundColor: '#E5E7EB',
    marginVertical: 8,
  },
  trendChangeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  trendChangeText: {
    fontSize: 16,
    fontWeight: '600',
  },
});

export default AnalyticsScreen;
