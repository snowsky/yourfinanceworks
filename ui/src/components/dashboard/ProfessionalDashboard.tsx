import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { 
  DollarSign, 
  Users, 
  TrendingUp, 
  Clock,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  Zap,
  RefreshCw
} from 'lucide-react';

import { ContentSection, GridLayout } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { QuickActions } from './QuickActions';
import { InvoiceChart } from './InvoiceChart';
import { RecentActivity } from './RecentActivity';
import { HelpCenter } from '@/components/onboarding/HelpCenter';
import { dashboardApi } from '@/lib/api';
import { getCurrentUser } from '@/utils/auth';
import { toast } from 'sonner';

interface DashboardStats {
  totalIncome: Record<string, number>;
  pendingInvoices: Record<string, number>;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
  trends: {
    income: { value: number; isPositive: boolean };
    pending: { value: number; isPositive: boolean };
    clients: { value: number; isPositive: boolean };
    overdue: { value: number; isPositive: boolean };
  };
}

export function ProfessionalDashboard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
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
  const [userName, setUserName] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  // Function to refresh dashboard data
  const refreshDashboard = () => {
    setRefreshKey(prev => prev + 1);
    // Also refresh the main dashboard stats
    const fetchData = async () => {
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
    fetchData();
  };

  // Format multiple currencies as string
  const formatMultiCurrencyString = (currencyAmounts: Record<string, number>) => {
    if (Object.keys(currencyAmounts).length === 0) {
      return "$0.00";
    }
    
    return Object.entries(currencyAmounts)
      .map(([currency, amount]) => {
        const symbols: { [key: string]: string } = {
          'USD': '$', 'EUR': '€', 'GBP': '£', 'CAD': 'C$', 'AUD': 'A$',
          'JPY': '¥', 'CHF': 'CHF', 'CNY': '¥', 'INR': '₹', 'BRL': 'R$'
        };
        
        const symbol = symbols[currency.toUpperCase()] || currency;
        return `${symbol}${amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
      })
      .join(' / ');
  };

  useEffect(() => {
    let isMounted = true;
    
    const fetchData = async () => {
      if (!isMounted) return;
      
      setLoading(true);
      
      try {
        const stats = await dashboardApi.getStats();
        if (isMounted) {
          setDashboardStats(stats);
        }
        
        // Load user info once
        const user = getCurrentUser();
        if (user && isMounted) {
          setUserName(user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email);
        }
      } catch (error) {
        console.error("Failed to fetch dashboard stats:", error);
        if (isMounted) {
          toast.error(t('dashboard.errors.load_failed'));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    // Listen for dashboard refresh events
    // Other components can trigger refresh by calling: window.dispatchEvent(new CustomEvent('dashboard-refresh'))
    // Or by importing and calling: refreshDashboard() from '@/utils/dashboard'
    const handleRefresh = () => {
      if (isMounted) {
        refreshDashboard();
      }
    };

    window.addEventListener('dashboard-refresh', handleRefresh);

    // Auto-refresh dashboard data every 5 minutes
    const refreshInterval = setInterval(() => {
      if (isMounted) {
        setRefreshKey(prev => prev + 1);
      }
    }, 5 * 60 * 1000); // 5 minutes
    
    return () => {
      isMounted = false;
      window.removeEventListener('dashboard-refresh', handleRefresh);
      clearInterval(refreshInterval);
    };
  }, []); // No dependencies to prevent refresh loops

  const metrics = [
    {
      title: t('dashboard.stats.total_income'),
      value: formatMultiCurrencyString(dashboardStats.totalIncome),
      change: {
        value: dashboardStats.trends.income.value,
        type: dashboardStats.trends.income.isPositive ? 'increase' as const : 'decrease' as const
      },
      icon: DollarSign,
      description: t('dashboard.stats.revenue_description'),
      variant: 'success' as const
    },
    {
      title: t('dashboard.stats.pending_amount'),
      value: formatMultiCurrencyString(dashboardStats.pendingInvoices),
      change: {
        value: dashboardStats.trends.pending.value,
        type: dashboardStats.trends.pending.isPositive ? 'increase' as const : 'decrease' as const
      },
      icon: Clock,
      description: t('dashboard.stats.pending_description'),
      variant: 'warning' as const
    },
    {
      title: t('dashboard.stats.total_clients'),
      value: dashboardStats.totalClients.toString(),
      change: {
        value: dashboardStats.trends.clients.value,
        type: dashboardStats.trends.clients.isPositive ? 'increase' as const : 'decrease' as const
      },
      icon: Users,
      description: t('dashboard.stats.clients_description'),
      variant: 'default' as const
    },
    {
      title: t('dashboard.stats.overdue_invoices'),
      value: dashboardStats.invoicesOverdue.toString(),
      change: {
        value: dashboardStats.trends.overdue.value,
        type: dashboardStats.trends.overdue.isPositive ? 'increase' as const : 'decrease' as const
      },
      icon: AlertCircle,
      description: t('dashboard.stats.overdue_description'),
      variant: 'danger' as const
    }
  ];



  return (
    <div className="h-full space-y-6 fade-in">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}</h1>
            <p className="text-muted-foreground">{t('dashboard.overview')}</p>
          </div>
          <div className="flex items-center gap-3">
            <HelpCenter />
            <ProfessionalButton
              variant="gradient"
              size="sm"
              className="group"
              onClick={() => {
                // Scroll to Quick Actions section
                const quickActionsElement = document.querySelector('[data-section="quick-actions"]');
                if (quickActionsElement) {
                  quickActionsElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  // Add a subtle highlight effect
                  quickActionsElement.classList.add('ring-2', 'ring-blue-500/50', 'ring-offset-2');
                  setTimeout(() => {
                    quickActionsElement.classList.remove('ring-2', 'ring-blue-500/50', 'ring-offset-2');
                  }, 2000);
                }
              }}
            >
              <Zap className="h-4 w-4" />
              Quick Actions
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </ProfessionalButton>
          </div>
        </div>

        {/* Metrics Grid */}
        <ContentSection title="Key Metrics" description="Overview of your business performance">
          <GridLayout cols={4} gap="lg" responsive>
            {metrics.map((metric, index) => (
              <MetricCard
                key={index}
                title={metric.title}
                value={metric.value}
                change={metric.change}
                icon={metric.icon}
                description={metric.description}
                variant={metric.variant}
                loading={loading}
              />
            ))}
          </GridLayout>
        </ContentSection>



        {/* Charts and Recent Activity Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Charts */}
          <div className="lg:col-span-2">
            {/* Chart Section */}
            <ContentSection 
              title="Revenue Trends" 
              description="Monthly revenue and invoice performance"
              variant="card"
            >
              <InvoiceChart />
            </ContentSection>
          </div>

          {/* Right Column - Recent Activity */}
          <div className="lg:col-span-1">
            {/* Recent Invoices */}
            <ContentSection 
              title="Recent Activity" 
              description="Latest invoices and transactions"
              variant="card"
              actions={
                <div className="flex items-center gap-2">
                  <ProfessionalButton 
                    variant="ghost" 
                    size="sm"
                    onClick={() => setRefreshKey(prev => prev + 1)}
                    className="p-2"
                  >
                    <RefreshCw className="h-3 w-3" />
                  </ProfessionalButton>
                  <ProfessionalButton 
                    variant="ghost" 
                    size="sm"
                    onClick={() => navigate('/activity')}
                  >
                    View All
                    <ArrowRight className="h-3 w-3" />
                  </ProfessionalButton>
                </div>
              }
            >
              <RecentActivity refreshKey={refreshKey} />
            </ContentSection>


          </div>
        </div>

        {/* Full Width Quick Actions */}
        <ContentSection 
          title="Quick Actions" 
          description="Common tasks and shortcuts"
          className="scroll-mt-8"
          data-section="quick-actions"
          variant="card"
        >
          <QuickActions />
        </ContentSection>

        {/* Business Insights Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Payment Trends */}
          <ProfessionalCard variant="elevated" className="p-6">
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-blue-100 rounded-xl">
                  <TrendingUp className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-lg font-bold">Payment Trends</h3>
                  <p className="text-sm text-muted-foreground">Monthly payment analysis</p>
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium">On-time Payments</span>
                  </div>
                  <span className="text-lg font-bold text-green-600">87%</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-yellow-600" />
                    <span className="text-sm font-medium">Average Payment Time</span>
                  </div>
                  <span className="text-lg font-bold text-yellow-600">12 days</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <span className="text-sm font-medium">Overdue Rate</span>
                  </div>
                  <span className="text-lg font-bold text-red-600">8%</span>
                </div>
              </div>
            </div>
          </ProfessionalCard>

          {/* Business Health */}
          <ProfessionalCard variant="elevated" className="p-6">
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-green-100 rounded-xl">
                  <Users className="h-6 w-6 text-green-600" />
                </div>
                <div>
                  <h3 className="text-lg font-bold">Business Health</h3>
                  <p className="text-sm text-muted-foreground">Key performance indicators</p>
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium">Monthly Growth</span>
                  </div>
                  <span className="text-lg font-bold text-green-600">+15%</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-purple-600" />
                    <span className="text-sm font-medium">Active Clients</span>
                  </div>
                  <span className="text-lg font-bold">{dashboardStats.totalClients}</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-indigo-600" />
                    <span className="text-sm font-medium">Revenue Trend</span>
                  </div>
                  <span className="text-lg font-bold text-green-600">
                    {dashboardStats.trends.income.isPositive ? '↗' : '↘'} {dashboardStats.trends.income.value}%
                  </span>
                </div>
              </div>
            </div>
          </ProfessionalCard>
        </div>
      </div>
  );
}