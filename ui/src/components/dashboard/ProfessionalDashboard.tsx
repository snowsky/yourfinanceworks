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
  RefreshCw,
  Gamepad2
} from 'lucide-react';

import { ContentSection } from '@/components/ui/professional-layout';
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
  totalExpenses: Record<string, number>;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
  paymentTrends: {
    onTimePaymentRate: number;
    averagePaymentTime: number;
    overdueRate: number;
  };
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
    totalExpenses: {},
    totalClients: 0,
    invoicesPaid: 0,
    invoicesPending: 0,
    invoicesOverdue: 0,
    paymentTrends: {
      onTimePaymentRate: 0,
      averagePaymentTime: 0,
      overdueRate: 0
    },
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
        return `${symbol}${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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
      title: t('dashboard.stats.total_expenses'),
      value: formatMultiCurrencyString(dashboardStats.totalExpenses),
      change: {
        value: 0, // We can add expense trends later if needed
        type: 'increase' as const
      },
      icon: TrendingUp,
      description: t('dashboard.stats.expenses_description'),
      variant: 'default' as const
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
    <div className="h-full space-y-8 fade-in dashboard-highlight-mode dashboard-shell" data-tour="dashboard-welcome">
      {/* Dashboard Header with Professional Styling */}
      <div className="dashboard-highlight-block dashboard-highlight-block-primary dashboard-hero bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 md:p-7 backdrop-blur-sm" data-tour="dashboard-header">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-2 flex-1">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">{userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}</h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl">{t('dashboard.overview')}</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <HelpCenter />
            <ProfessionalButton
              variant="gradient"
              className="group h-9"
              onClick={() => {
                // Scroll to Quick Actions section
                const quickActionsElement = document.querySelector('[data-tour="dashboard-quick-actions"]');
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
              {t('dashboard.actions.quick_actions_button')}
              <ArrowRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
            </ProfessionalButton>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <ContentSection
        title={t('dashboard.sections.key_metrics')}
        description={t('dashboard.sections.key_metrics_desc')}
        data-tour="dashboard-stats"
        className="dashboard-highlight-block dashboard-highlight-block-primary dashboard-section rounded-2xl p-5 md:p-6"
        headerClassName="dashboard-section-header"
        titleClassName="dashboard-section-title"
        descriptionClassName="dashboard-section-description"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
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
              className="dashboard-highlight-item"
            />
          ))}
        </div>
      </ContentSection>



      {/* Charts and Recent Activity Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 xl:gap-8">
        {/* Left Column - Charts */}
        <div className="lg:col-span-2 flex flex-col">
          {/* Chart Section */}
          <ContentSection
            title={t('dashboard.sections.revenue_trends')}
            description={t('dashboard.sections.revenue_trends_desc')}
            variant="card"
            data-tour="dashboard-revenue-chart"
            className="flex-1 flex flex-col dashboard-highlight-block dashboard-highlight-block-primary dashboard-section"
            headerClassName="dashboard-section-header"
            titleClassName="dashboard-section-title"
            descriptionClassName="dashboard-section-description"
          >
            <div className="flex-1 min-h-0">
              <InvoiceChart />
            </div>
          </ContentSection>
        </div>

        {/* Right Column - Recent Activity */}
        <div className="lg:col-span-1 flex flex-col">
          {/* Recent Invoices */}
          <ContentSection
            title={t('dashboard.sections.recent_activity')}
            description={t('dashboard.sections.recent_activity_desc')}
            variant="card"
            data-tour="dashboard-recent"
            className="flex-1 flex flex-col dashboard-highlight-block dashboard-highlight-block-primary dashboard-section"
            headerClassName="dashboard-section-header"
            titleClassName="dashboard-section-title"
            descriptionClassName="dashboard-section-description"
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
                  {t('dashboard.actions.view_all')}
                  <ArrowRight className="h-3 w-3" />
                </ProfessionalButton>
              </div>
            }
          >
            <div className="flex-1 min-h-0">
              <RecentActivity refreshKey={refreshKey} />
            </div>
          </ContentSection>
        </div>
      </div>

      {/* Full Width Quick Actions */}
      <ContentSection
        title={t('dashboard.quick_actions.title')}
        description={t('dashboard.quick_actions.subtitle')}
        className="scroll-mt-8 dashboard-highlight-block dashboard-highlight-block-primary dashboard-section"
        data-tour="dashboard-quick-actions"
        variant="card"
        headerClassName="dashboard-section-header"
        titleClassName="dashboard-section-title"
        descriptionClassName="dashboard-section-description"
      >
        <QuickActions />
      </ContentSection>

      {/* Business Insights Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Payment Trends */}
        <ProfessionalCard
          variant="elevated"
          className="p-6 dashboard-highlight-block dashboard-highlight-block-success"
          data-tour="dashboard-payment-trends"
        >
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-primary/10 rounded-xl">
                <TrendingUp className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-bold">{t('dashboard.sections.payment_trends')}</h3>
                <p className="text-sm text-muted-foreground">{t('dashboard.sections.payment_trends_desc')}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.on_time_payments')}</span>
                </div>
                <span className="text-lg font-bold text-green-600">{dashboardStats.paymentTrends.onTimePaymentRate}%</span>
              </div>

              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.average_payment_time')}</span>
                </div>
                <span className="text-lg font-bold text-yellow-600">{dashboardStats.paymentTrends.averagePaymentTime} days</span>
              </div>

              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.overdue_rate')}</span>
                </div>
                <span className="text-lg font-bold text-red-600">{dashboardStats.paymentTrends.overdueRate}%</span>
              </div>
            </div>
          </div>
        </ProfessionalCard>

        {/* Business Health */}
        <ProfessionalCard
          variant="elevated"
          className="p-6 dashboard-highlight-block dashboard-highlight-block-success"
          data-tour="dashboard-business-health"
        >
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-500/10 rounded-xl">
                <Users className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold">{t('dashboard.sections.business_health')}</h3>
                <p className="text-sm text-muted-foreground">{t('dashboard.sections.business_health_desc')}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.monthly_growth')}</span>
                </div>
                <span className={`text-lg font-bold ${dashboardStats.trends.income.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                  {dashboardStats.trends.income.isPositive ? '+' : ''}{dashboardStats.trends.income.value}%
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-purple-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.active_clients')}</span>
                </div>
                <span className="text-lg font-bold">{dashboardStats.totalClients}</span>
              </div>

              <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-indigo-600" />
                  <span className="text-sm font-medium">{t('dashboard.metrics.revenue_trend')}</span>
                </div>
                <span className="text-lg font-bold text-green-600">
                  {dashboardStats.trends.income.isPositive ? '↗' : '↘'} {dashboardStats.trends.income.value}%
                </span>
              </div>

              {/* Gamification Link */}
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <Gamepad2 className="h-4 w-4 text-purple-600" />
                  <div>
                    <span className="text-sm font-medium">{t('dashboard.metrics.gamification_score')}</span>
                    <p className="text-xs text-muted-foreground">{t('dashboard.metrics.gamification_desc')}</p>
                  </div>
                </div>
                <ProfessionalButton
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/settings?tab=gamification')}
                  className="text-purple-600 hover:bg-purple-100 h-8 px-3"
                >
                  {t('dashboard.actions.view_score')}
                  <ArrowRight className="h-3 w-3 ml-1" />
                </ProfessionalButton>
              </div>
            </div>
          </div>
        </ProfessionalCard>
      </div>
    </div>
  );
}
