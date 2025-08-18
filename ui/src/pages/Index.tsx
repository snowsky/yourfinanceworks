import { API_BASE_URL } from '@/lib/api';
import { useState, useEffect } from "react";
import { BarChart, DollarSign, FileText, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { RecentInvoices } from "@/components/dashboard/RecentInvoices";
import { InvoiceChart } from "@/components/dashboard/InvoiceChart";
import { AppLayout } from "@/components/layout/AppLayout";
import { dashboardApi } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from 'react-i18next';
import { DisplayMD, BodyLG } from "@/components/ui/typography";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { ProgressiveDisclosure } from "@/components/onboarding/ProgressiveDisclosure";

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
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  // Get current tenant ID to trigger refetch when organization switches
  const getCurrentTenantId = () => {
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        return selectedTenantId;
      }
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user?.tenant_id?.toString();
      }
    } catch (e) {
      console.error('Error getting tenant ID:', e);
    }
    return null;
  };
  
  // Update tenant ID when it changes
  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Dashboard: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
      }
    };
    
    updateTenantId();
    
    // Listen for storage changes
    const handleStorageChange = () => {
      updateTenantId();
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [currentTenantId]);

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
  }, [currentTenantId]); // Add tenant ID as dependency

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div data-tour="dashboard-welcome">
          <div className="flex items-center gap-2">
            <DisplayMD>
              {userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}
            </DisplayMD>
            <HelpTooltip 
              content="This dashboard provides an overview of your business finances, including income, pending invoices, and client metrics."
              title="Dashboard Overview"
            />
          </div>
          <BodyLG className="text-muted-foreground mt-2">
            {tenantName ? t('dashboard.tenant_overview', { tenant: tenantName }) : t('dashboard.overview')}
          </BodyLG>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 slide-in" data-tour="dashboard-stats">
          <StatCard
            title={t('dashboard.stats.total_income')}
            value={formatMultiCurrencyString(dashboardStats.totalIncome)}
            icon={DollarSign}
            description={t('dashboard.stats.revenue_description')}
            trend={dashboardStats.trends.income}
            loading={loading}
            variant="success"
            onClick={() => console.log('Navigate to income details')}
          />
          <StatCard
            title={t('dashboard.stats.pending_amount')}
            value={formatMultiCurrencyString(dashboardStats.pendingInvoices)}
            icon={FileText}
            description={t('dashboard.stats.pending_description')}
            trend={dashboardStats.trends.pending}
            loading={loading}
            variant="warning"
            onClick={() => console.log('Navigate to pending invoices')}
          />
          <StatCard
            title={t('dashboard.stats.total_clients')}
            value={dashboardStats.totalClients.toString()}
            icon={Users}
            description={t('dashboard.stats.clients_description')}
            trend={dashboardStats.trends.clients}
            loading={loading}
            variant="default"
            onClick={() => console.log('Navigate to clients')}
          />
          <StatCard
            title={t('dashboard.stats.overdue_invoices')}
            value={dashboardStats.invoicesOverdue.toString()}
            icon={FileText}
            description={t('dashboard.stats.overdue_description')}
            trend={dashboardStats.trends.overdue}
            loading={loading}
            variant="destructive"
            onClick={() => console.log('Navigate to overdue invoices')}
          />
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 slide-in" style={{ animationDelay: '100ms' }}>
          <div className="lg:col-span-3" data-tour="dashboard-chart">
            <InvoiceChart />
          </div>
          <div className="lg:col-span-2" data-tour="dashboard-recent">
            <RecentInvoices />
          </div>
        </div>
        
        <ProgressiveDisclosure
          features={[
            {
              id: 'ai-assistant',
              title: 'AI Business Assistant',
              description: 'Get intelligent insights about your business data and automate routine tasks.',
              category: 'automation',
              difficulty: 'beginner',
              action: () => {
                const aiButton = document.querySelector('[data-ai-assistant-trigger]') as HTMLElement;
                if (aiButton) aiButton.click();
              }
            },
            {
              id: 'email-automation',
              title: 'Automated Email Reminders',
              description: 'Set up automatic payment reminders for overdue invoices.',
              category: 'automation',
              difficulty: 'intermediate',
              action: () => window.location.href = '/settings'
            },
            {
              id: 'advanced-analytics',
              title: 'Advanced Analytics Dashboard',
              description: 'Deep dive into your business metrics with advanced charts and forecasting.',
              category: 'analytics',
              difficulty: 'intermediate',
              action: () => window.location.href = '/analytics'
            },
            {
              id: 'api-integration',
              title: 'API Integration',
              description: 'Connect with external accounting software and payment processors.',
              category: 'integration',
              difficulty: 'advanced'
            }
          ]}
          className="mt-6"
        />
      </div>
    </AppLayout>
  );
};

export default Dashboard;
