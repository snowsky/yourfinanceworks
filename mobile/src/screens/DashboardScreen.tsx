import React, { useState, useEffect } from 'react';
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

interface DashboardStats {
  totalIncome: number;
  pendingInvoices: number;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
}

interface DashboardScreenProps {
  onNavigateToInvoices: () => void;
  onNavigateToClients: () => void;
  onNavigateToPayments: () => void;
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
  onNavigateToSettings,
  onSignOut,
  user,
}) => {
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
    totalIncome: 0,
    pendingInvoices: 0,
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [userName, setUserName] = useState('');
  const [tenantName, setTenantName] = useState('');

  const fetchDashboardStats = async () => {
    try {
      // Simulate API call - replace with actual API
      await new Promise(resolve => setTimeout(resolve, 1000));
      setDashboardStats({
        totalIncome: 15420.50,
        pendingInvoices: 8230.00,
        totalClients: 24,
        invoicesPaid: 18,
        invoicesPending: 6,
        invoicesOverdue: 2,
      });
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
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
    await fetchDashboardStats();
    setRefreshing(false);
  };

  useEffect(() => {
    const initializeDashboard = async () => {
      setLoading(true);
      await fetchDashboardStats();
      loadUserInfo();
      setLoading(false);
    };

    initializeDashboard();
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

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>Loading dashboard...</Text>
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
            <View>
              <Text style={styles.welcomeText}>
                {userName ? `Welcome back, ${userName}!` : 'Dashboard'}
              </Text>
              <Text style={styles.subtitle}>
                {tenantName ? `${tenantName} - Overview of your invoicing activity` : 'Overview of your invoicing activity'}
              </Text>
            </View>
            <TouchableOpacity style={styles.signOutButton} onPress={onSignOut}>
              <Ionicons name="log-out-outline" size={20} color="#EF4444" />
              <Text style={styles.signOutText}>Sign Out</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.statsGrid}>
          <StatCard
            title="Total Income"
            value={`$${dashboardStats.totalIncome.toFixed(2)}`}
            icon="cash-outline"
            description="Revenue from paid invoices"
            color="#10B981"
          />
          <StatCard
            title="Pending Amount"
            value={`$${dashboardStats.pendingInvoices.toFixed(2)}`}
            icon="document-text-outline"
            description="Awaiting payment"
            color="#F59E0B"
          />
          <StatCard
            title="Total Clients"
            value={dashboardStats.totalClients.toString()}
            icon="people-outline"
            description="Active client accounts"
            color="#3B82F6"
          />
          <StatCard
            title="Overdue Invoices"
            value={dashboardStats.invoicesOverdue.toString()}
            icon="alert-circle-outline"
            description="Invoices past due date"
            color="#EF4444"
          />
        </View>

        <View style={styles.quickActionsSection}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.quickActionsGrid}>
            <QuickAction
              title="Invoices"
              icon="document-text-outline"
              onPress={onNavigateToInvoices}
              color="#3B82F6"
            />
            <QuickAction
              title="Clients"
              icon="people-outline"
              onPress={onNavigateToClients}
              color="#10B981"
            />
            <QuickAction
              title="Payments"
              icon="card-outline"
              onPress={onNavigateToPayments}
              color="#F59E0B"
            />
            <QuickAction
              title="Settings"
              icon="settings-outline"
              onPress={onNavigateToSettings}
              color="#6B7280"
            />
          </View>
        </View>

        <View style={styles.recentSection}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Recent Activity</Text>
            <TouchableOpacity onPress={onNavigateToInvoices}>
              <Text style={styles.viewAllText}>View all</Text>
            </TouchableOpacity>
          </View>
          
          <View style={styles.recentItem}>
            <View style={styles.recentIcon}>
              <Ionicons name="document-text-outline" size={20} color="#3B82F6" />
            </View>
            <View style={styles.recentContent}>
              <Text style={styles.recentTitle}>Invoice #INV-001</Text>
              <Text style={styles.recentSubtitle}>Client: ABC Company</Text>
              <Text style={styles.recentAmount}>$1,250.00</Text>
            </View>
            <View style={styles.recentStatus}>
              <Text style={[styles.statusText, { color: '#10B981' }]}>Paid</Text>
            </View>
          </View>

          <View style={styles.recentItem}>
            <View style={styles.recentIcon}>
              <Ionicons name="document-text-outline" size={20} color="#F59E0B" />
            </View>
            <View style={styles.recentContent}>
              <Text style={styles.recentTitle}>Invoice #INV-002</Text>
              <Text style={styles.recentSubtitle}>Client: XYZ Corp</Text>
              <Text style={styles.recentAmount}>$850.00</Text>
            </View>
            <View style={styles.recentStatus}>
              <Text style={[styles.statusText, { color: '#F59E0B' }]}>Pending</Text>
            </View>
          </View>
        </View>
      </ScrollView>
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
  scrollView: {
    flex: 1,
  },
  header: {
    padding: 20,
    paddingTop: 40,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEE2E2',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  signOutText: {
    marginLeft: 4,
    fontSize: 14,
    fontWeight: '600',
    color: '#EF4444',
  },
  welcomeText: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
  },
  statsGrid: {
    paddingHorizontal: 20,
    marginBottom: 24,
  },
  statCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  statTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  statDescription: {
    fontSize: 14,
    color: '#666',
  },
  quickActionsSection: {
    paddingHorizontal: 20,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  quickAction: {
    width: '48%',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  quickActionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  quickActionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    textAlign: 'center',
  },
  recentSection: {
    paddingHorizontal: 20,
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  viewAllText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600',
  },
  recentItem: {
    flexDirection: 'row',
    alignItems: 'center',
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
  recentIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#f3f4f6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  recentContent: {
    flex: 1,
  },
  recentTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  recentSubtitle: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  recentAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  recentStatus: {
    marginLeft: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
});

export default DashboardScreen; 