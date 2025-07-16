import { API_BASE_URL } from '@/lib/api';
import { useState, useEffect } from "react";
import { BarChart, DollarSign, FileText, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { RecentInvoices } from "@/components/dashboard/RecentInvoices";
import { InvoiceChart } from "@/components/dashboard/InvoiceChart";
import { AppLayout } from "@/components/layout/AppLayout";
import { dashboardApi } from "@/lib/api";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { useTranslation } from 'react-i18next';

const Dashboard = () => {
  const { t } = useTranslation();
  const [dashboardStats, setDashboardStats] = useState({
    totalIncome: {},
    pendingInvoices: {},
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
    trends: {
      income: { value: 0, isPositive: true },
      pending: { value: 0, isPositive: true },
      clients: { value: 0, isPositive: true },
      overdue: { value: 0, isPositive: false }
    }
  });
  const [loading, setLoading] = useState(true);
  const [tenantName, setTenantName] = useState('');
  const [userName, setUserName] = useState('');

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

  useEffect(() => {
    const fetchDashboardStats = async () => {
      setLoading(true);
      try {
        const stats = await dashboardApi.getStats();
        setDashboardStats(stats);
      } catch (error) {
        console.error("Failed to fetch dashboard stats:", error);
        toast.error(t('dashboard.errors.load_failed'));
      } finally {
        setLoading(false);
      }
    };
    
    const loadUserInfo = () => {
      const userData = localStorage.getItem('user');
      if (userData) {
        try {
          const user = JSON.parse(userData);
          setUserName(user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email);
          console.log('Dashboard userData:', user);
          console.log('Dashboard userName:', user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email);
        } catch (error) {
          console.error('Error parsing user data:', error);
        }
      }
    };

    const fetchTenantName = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const response = await fetch(`${API_BASE_URL}/tenants/me`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const tenant = await response.json();
          setTenantName(tenant.name);
        }
      } catch (error) {
        console.error('Error fetching tenant name:', error);
      }
    };
    
    fetchDashboardStats();
    loadUserInfo();
    fetchTenantName();
  }, []);

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">
            {userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}
          </h1>
          <p className="text-muted-foreground">
            {tenantName ? t('dashboard.tenant_overview', { tenant: tenantName }) : t('dashboard.overview')}
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 slide-in">
          <StatCard
            title={t('dashboard.stats.total_income')}
            value={formatMultiCurrencyString(dashboardStats.totalIncome)}
            icon={DollarSign}
            description={t('dashboard.stats.revenue_description')}
            trend={dashboardStats.trends.income}
            loading={loading}
          />
          <StatCard
            title={t('dashboard.stats.pending_amount')}
            value={formatMultiCurrencyString(dashboardStats.pendingInvoices)}
            icon={FileText}
            description={t('dashboard.stats.pending_description')}
            trend={dashboardStats.trends.pending}
            loading={loading}
          />
          <StatCard
            title={t('dashboard.stats.total_clients')}
            value={dashboardStats.totalClients.toString()}
            icon={Users}
            description={t('dashboard.stats.clients_description')}
            trend={dashboardStats.trends.clients}
            loading={loading}
          />
          <StatCard
            title={t('dashboard.stats.overdue_invoices')}
            value={dashboardStats.invoicesOverdue.toString()}
            icon={FileText}
            description={t('dashboard.stats.overdue_description')}
            trend={dashboardStats.trends.overdue}
            loading={loading}
          />
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 slide-in" style={{ animationDelay: '100ms' }}>
          <InvoiceChart />
          <RecentInvoices />
        </div>
      </div>
    </AppLayout>
  );
};

export default Dashboard;
