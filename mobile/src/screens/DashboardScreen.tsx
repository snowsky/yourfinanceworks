import React, { useState, useEffect } from 'react';
import { logger } from '../utils/logger';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import apiService, { DashboardStats, Invoice } from '../services/api';
import { formatCurrency, getCurrencySymbol } from '../utils/currency';
import { formatDate } from '../utils/date';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';

interface DashboardScreenProps {
  onNavigateToInvoices: () => void;
  onNavigateToClients: () => void;
  onNavigateToPayments: () => void;
  onNavigateToExpenses: () => void;
  onNavigateToStatements: () => void;
  onNavigateToAnalytics: () => void;
  onNavigateToSettings: () => void;
  onSignOut: () => void;
  user?: {
    first_name: string;
    last_name: string;
    email: string;
  };
}

const DashboardScreen: React.FC<DashboardScreenProps> = ({
  onNavigateToInvoices,
  onNavigateToClients,
  onNavigateToPayments,
  onNavigateToExpenses,
  onNavigateToStatements,
  onNavigateToAnalytics,
  onNavigateToSettings,
  onSignOut,
  user,
}) => {
  const { t } = useTranslation();
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
    totalIncome: {},
    pendingInvoices: {},
    totalExpenses: {},
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
  });
  const [recentInvoices, setRecentInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [userName, setUserName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [primaryCurrency, setPrimaryCurrency] = useState('USD');

  // Helper function to format multiple currencies as string
  const formatMultiCurrencyString = (currencyAmounts: Record<string, number>) => {
    if (Object.keys(currencyAmounts).length === 0) {
      return "$0.00";
    }
    
    return Object.entries(currencyAmounts)
      .map(([currency, amount]) => {
        // Use fallback symbols for common currencies
        const symbols: { [key: string]: string } = {
          'USD': '$',
          'EUR': '€',
          'GBP': '£',
          'CAD': 'C$',
          'AUD': 'A$',
          'JPY': '¥',
          'CHF': 'CHF',
          'CNY': '¥',
          'INR': '₹',
          'BRL': 'R$',
          'BTC': '₿',
          'ETH': 'Ξ',
          'XRP': 'XRP',
          'SOL': '◎'
        };
        
        const symbol = symbols[currency.toUpperCase()] || currency;
        return `${symbol}${amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
      })
      .join(' / ');
  };

  const fetchDashboardData = async () => {
    try {
      const [stats, invoicesList] = await Promise.all([
        apiService.getDashboardStats(),
        apiService.getInvoices()
      ]);
      
      // Fetch detailed invoice data for recent invoices
      const recentInvoiceIds = invoicesList.slice(0, 5);
      const detailedInvoices = await Promise.all(
        recentInvoiceIds.map(inv => apiService.getInvoice(inv.id))
      );
      
      logger.debug('Fetched detailed invoices', detailedInvoices.map(inv => ({
        id: inv.id,
        items: JSON.stringify(inv.items),
        currency: inv.currency,
        amount: inv.amount
      })));
      
      setDashboardStats(stats);
      setRecentInvoices(detailedInvoices);
      
      // Determine primary currency from invoices
      if (invoicesList.length > 0) {
        const currencyCounts = invoicesList.reduce((acc, invoice) => {
          const currency = invoice.currency || 'USD';
          acc[currency] = (acc[currency] || 0) + 1;
          return acc;
        }, {} as Record<string, number>);
        
        const mostCommonCurrency = Object.entries(currencyCounts)
          .sort(([,a], [,b]) => b - a)[0]?.[0] || 'USD';
        setPrimaryCurrency(mostCommonCurrency);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      // Keep existing data on error
    }
  };

  const loadUserInfo = () => {
    if (user) {
      setUserName(`${user.first_name} ${user.last_name}`);
      setTenantName(`${user.first_name}'s Organization`);
    } else {
      setUserName('User');
      setTenantName('Organization');
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const [stats, invoicesList] = await Promise.all([
        apiService.getDashboardStats(),
        apiService.getInvoices()
      ]);
      
      // Fetch detailed invoice data for recent invoices
      const recentInvoiceIds = invoicesList.slice(0, 5);
      const detailedInvoices = await Promise.all(
        recentInvoiceIds.map(inv => apiService.getInvoice(inv.id))
      );
      
      setDashboardStats(stats);
      setRecentInvoices(detailedInvoices);
      
      if (invoicesList.length > 0) {
        const currencyCounts = invoicesList.reduce((acc, invoice) => {
          const currency = invoice.currency || 'USD';
          acc[currency] = (acc[currency] || 0) + 1;
          return acc;
        }, {} as Record<string, number>);
        
        const mostCommonCurrency = Object.entries(currencyCounts)
          .sort(([,a], [,b]) => b - a)[0]?.[0] || 'USD';
        setPrimaryCurrency(mostCommonCurrency);
      }
    } catch (error) {
      console.error('Failed to refresh dashboard data:', error);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const initializeDashboard = async () => {
      setLoading(true);
      await fetchDashboardData();
      loadUserInfo();
      setLoading(false);
    };

    initializeDashboard();
    
    // Set up interval to refresh data every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const StatCard = ({ title, value, icon, description, color }: {
    title: string;
    value: string;
    icon: string;
    description: string;
    color: string;
  }) => (
    <View style={[styles.statCard, { borderLeftColor: color }]}>
      <View style={styles.statHeader}>
        <View style={[styles.iconContainer, { backgroundColor: color + '20' }]}>
          <Ionicons name={icon as any} size={24} color={color} />
        </View>
        <Text style={styles.statValue}>{value}</Text>
      </View>
      <Text style={styles.statTitle}>{title}</Text>
      <Text style={styles.statDescription}>{description}</Text>
    </View>
  );

  const QuickAction = ({ title, icon, onPress, color }: {
    title: string;
    icon: string;
    onPress: () => void;
    color: string;
  }) => (
    <TouchableOpacity style={styles.quickAction} onPress={onPress}>
      <View style={[styles.quickActionIcon, { backgroundColor: color + '20' }]}>
        <Ionicons name={icon as any} size={24} color={color} />
      </View>
      <Text style={styles.quickActionText}>{title}</Text>
    </TouchableOpacity>
  );

  const RecentInvoiceItem = ({ invoice }: { invoice: Invoice }) => (
    <TouchableOpacity style={styles.recentInvoiceItem}>
      <View style={styles.invoiceHeader}>
        <Text style={styles.invoiceNumber}>#{invoice.number}</Text>
        <View style={[styles.statusBadge, { 
          backgroundColor: invoice.status === 'paid' ? '#10B981' + '20' :
                         invoice.status === 'pending' ? '#F59E0B' + '20' :
                         invoice.status === 'overdue' ? '#EF4444' + '20' :
                         '#6B7280' + '20'
        }]}>
          <Text style={[styles.statusText, { 
            color: invoice.status === 'paid' ? '#10B981' :
                   invoice.status === 'pending' ? '#F59E0B' :
                   invoice.status === 'overdue' ? '#EF4444' :
                   '#6B7280'
          }]}>
            {invoice.status.replace('_', ' ').toUpperCase()}
          </Text>
        </View>
      </View>
      <Text style={styles.clientName}>{invoice.client_name}</Text>
      <View style={styles.invoiceFooter}>
        <Text style={styles.invoiceAmount}>
          {formatCurrency(invoice.amount, invoice.currency || primaryCurrency)}
        </Text>
        <Text style={styles.invoiceDate}>
          {formatDate(invoice.due_date)}
        </Text>
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>{t('common.loading')}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <ScrollView
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <View style={styles.header}>
          <View style={styles.headerTop}>
            <View style={styles.textContainer}>
              <Text style={styles.welcomeText}>
                {userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}
              </Text>
              <Text style={styles.subtitle} numberOfLines={2}>
                {tenantName ? `${tenantName} - Overview of your invoicing activity` : 'Overview of your invoicing activity'}
              </Text>
            </View>
            <TouchableOpacity style={styles.signOutButton} onPress={onSignOut}>
              <Ionicons name="log-out-outline" size={20} color="#EF4444" />
              <Text style={styles.signOutText}>{t('auth.logout')}</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.statsGrid}>
          <StatCard
            title={t('dashboard.stats.total_income')}
            value={formatMultiCurrencyString(dashboardStats.totalIncome)}
            icon="cash-outline"
            description={t('dashboard.stats.revenue_from_paid')}
            color="#10B981"
          />
          <StatCard
            title={t('dashboard.stats.total_expenses')}
            value={formatMultiCurrencyString(dashboardStats.totalExpenses)}
            icon="wallet-outline"
            description={t('dashboard.stats.total_business_expenses')}
            color="#8B5CF6"
          />
          <StatCard
            title={t('dashboard.stats.pending_amount')}
            value={formatMultiCurrencyString(dashboardStats.pendingInvoices)}
            icon="document-text-outline"
            description={t('dashboard.stats.awaiting_payment')}
            color="#F59E0B"
          />
          <StatCard
            title={t('dashboard.stats.total_clients')}
            value={dashboardStats.totalClients.toString()}
            icon="people-outline"
            description={t('dashboard.stats.active_clients')}
            color="#3B82F6"
          />
          <StatCard
            title={t('dashboard.stats.overdue_invoices')}
            value={dashboardStats.invoicesOverdue.toString()}
            icon="alert-circle-outline"
            description={t('dashboard.stats.past_due_invoices')}
            color="#EF4444"
          />
        </View>

        <View style={styles.quickActionsSection}>
          <Text style={styles.sectionTitle}>{t('dashboard.quick_actions')}</Text>
          <View style={styles.quickActionsGrid}>
            <QuickAction
              title={t('navigation.clients')}
              icon="people-outline"
              onPress={onNavigateToClients}
              color="#3B82F6"
            />
            <QuickAction
              title={t('navigation.invoices')}
              icon="document-text-outline"
              onPress={onNavigateToInvoices}
              color="#10B981"
            />
            <QuickAction
              title={t('navigation.payments')}
              icon="card-outline"
              onPress={onNavigateToPayments}
              color="#F59E0B"
            />
            <QuickAction
              title={t('expenses.title')}
              icon="wallet-outline"
              onPress={onNavigateToExpenses}
              color="#8B5CF6"
            />
            <QuickAction
              title={t('statements.title')}
              icon="document-text-outline"
              onPress={onNavigateToStatements}
              color="#06B6D4"
            />
            <QuickAction
              title="Analytics"
              icon="bar-chart-outline"
              onPress={onNavigateToAnalytics}
              color="#8B5CF6"
            />
            <QuickAction
              title={t('settings.title')}
              icon="settings-outline"
              onPress={onNavigateToSettings}
              color="#6B7280"
            />
          </View>
        </View>

        {recentInvoices.length > 0 && (
          <View style={styles.recentInvoicesSection}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>{t('dashboard.recent_invoices')}</Text>
              <TouchableOpacity onPress={onNavigateToInvoices}>
                <Text style={styles.viewAllText}>{t('common.view_all')}</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.recentInvoicesList}>
              {recentInvoices.map((invoice, index) => (
                <RecentInvoiceItem key={invoice.id || index} invoice={invoice} />
              ))}
            </View>
          </View>
        )}
        
        <View style={styles.languageRow}>
          <LanguageSwitcher />
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollView: {
    flex: 1,
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
  header: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingTop: 60,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    minHeight: 60, // Ensure minimum height for touch targets
  },
  textContainer: {
    flex: 1,
    marginRight: 16, // Add margin to ensure logout button doesn't get too close
  },
  languageRow: {
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 20,
  },
  welcomeText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    flexWrap: 'wrap',
    lineHeight: 18,
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#FEF2F2',
    minWidth: 60, // Ensure minimum width for touch target
    alignSelf: 'flex-start', // Don't stretch to fill space
  },
  signOutText: {
    marginLeft: 4,
    fontSize: 12,
    color: '#EF4444',
    fontWeight: '500',
  },
  statsGrid: {
    padding: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  statCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    width: '48%',
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
  },
  statTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 4,
  },
  statDescription: {
    fontSize: 12,
    color: '#6B7280',
  },
  quickActionsSection: {
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 16,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  quickAction: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    width: '31%',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  quickActionIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  quickActionText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#374151',
    textAlign: 'center',
  },
  recentInvoicesSection: {
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  viewAllText: {
    fontSize: 14,
    color: '#3B82F6',
    fontWeight: '500',
  },
  recentInvoicesList: {
    gap: 12,
  },
  recentInvoiceItem: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
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
  invoiceNumber: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '600',
  },
  clientName: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 8,
  },
  invoiceFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  invoiceAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#111827',
  },
  invoiceDate: {
    fontSize: 12,
    color: '#6B7280',
  },
});

export default DashboardScreen; 