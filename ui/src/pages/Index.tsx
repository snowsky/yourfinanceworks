import { API_BASE_URL } from '@/lib/api';
import { useState, useEffect } from "react";
import { BarChart, DollarSign, FileText, Users, TrendingDown } from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import { RecentInvoices } from "@/components/dashboard/RecentInvoices";
import { InvoiceChart } from "@/components/dashboard/InvoiceChart";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { ProfessionalDashboard } from "@/components/dashboard/ProfessionalDashboard";
import { AppLayout } from "@/components/layout/AppLayout";
import { dashboardApi } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from 'react-i18next';
import { DisplayMD, BodyLG } from "@/components/ui/typography";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { ProgressiveDisclosure } from "@/components/onboarding/ProgressiveDisclosure";
import { OnboardingWelcome, useOnboarding } from "@/components/onboarding";
import { CookieConsentBanner } from "@/components/cookie-consent/CookieConsentBanner";
import { useTracking, useBusinessTracking } from "@/hooks/useTracking";

const Dashboard = () => {
  const { t } = useTranslation();
  const { showWelcome, setShowWelcome, startTour } = useOnboarding();
  const tracking = useTracking();
  const businessTracking = useBusinessTracking();
  const [dashboardStats, setDashboardStats] = useState({
    totalIncome: {},
    pendingInvoices: {},
    totalExpenses: {},
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

  // Initialize with current tenant ID to avoid null state
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(() => getCurrentTenantId());

  // Listen for storage changes
  useEffect(() => {
    const handleStorageChange = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Dashboard: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
      }
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

  // Check for tour parameter and start tour
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tourParam = urlParams.get('tour');
    if (tourParam) {
      setTimeout(() => {
        startTour(tourParam);
      }, 500);
      // Clean up the URL parameter
      const url = new URL(window.location.href);
      url.searchParams.delete('tour');
      window.history.replaceState({}, '', url.toString());
    }
  }, [startTour]);

  useEffect(() => {
    let isMounted = true;
    
    const fetchData = async () => {
      console.log('🔄 Dashboard fetching data, currentTenantId:', currentTenantId);
      
      if (!isMounted) return;
      
      setLoading(true);
      
      try {
        // Fetch dashboard stats
        const stats = await dashboardApi.getStats();
        if (isMounted) {
          setDashboardStats(stats);
        }
        
        // Load user info
        const userData = localStorage.getItem('user');
        if (userData && isMounted) {
          try {
            const user = JSON.parse(userData);
            setUserName(user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email);
          } catch (error) {
            console.error('Error parsing user data:', error);
          }
        }

        // Fetch tenant name
        const token = localStorage.getItem('token');
        if (token && isMounted) {
          try {
            const response = await fetch(`${API_BASE_URL}/tenants/me`, {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
            });

            if (response.ok) {
              const tenant = await response.json();
              if (isMounted) {
                setTenantName(tenant.name);
              }
            }
          } catch (error) {
            console.error('Error fetching tenant name:', error);
          }
        }
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
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
    
    return () => {
      isMounted = false;
    };
  }, [currentTenantId, t]);

  // Check for professional mode (you can add a toggle later)
  const useProfessionalMode = true;

  if (useProfessionalMode) {
    return (
      <AppLayout>
        <OnboardingWelcome 
          open={showWelcome} 
          onClose={() => setShowWelcome(false)} 
        />
        <ProfessionalDashboard />
        <CookieConsentBanner 
          analyticsConfig={{
            googleAnalytics: {
              trackingId: 'GA_DEMO_ID',
              enabled: true
            }
          }}
          onConsentChange={(status) => {
            console.log('Cookie consent changed:', status);
          }}
        />
      </AppLayout>
    );
  }

  // Professional styling object
  const professionalCardStyle = {
    background: 'rgba(255, 255, 255, 0.95)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '16px',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.12)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    overflow: 'hidden',
    position: 'relative' as const
  };

  const professionalContainerStyle = {
    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.02), transparent)',
    borderRadius: '24px',
    padding: '8px'
  };

  return (
    <AppLayout>
      <OnboardingWelcome 
        open={showWelcome} 
        onClose={() => setShowWelcome(false)} 
      />
      <div className="h-full space-y-6 fade-in" style={professionalContainerStyle}>
        <div data-tour="dashboard-welcome" className="-mt-4">
          <div className="flex items-center gap-2">
            <DisplayMD>
              {userName ? t('dashboard.welcome', { name: userName }) : t('dashboard.title')}
            </DisplayMD>
            <HelpTooltip
              content={t('dashboard.help.overview_content')}
              title={t('dashboard.help.overview_title')}
            />
          </div>
        </div>
        
        <div 
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 slide-in" 
          data-tour="dashboard-stats"
          style={professionalContainerStyle}
        >
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
            title={t('dashboard.stats.total_expenses')}
            value={formatMultiCurrencyString(dashboardStats.totalExpenses)}
            icon={TrendingDown}
            description={t('dashboard.stats.expenses_description')}
            trend={{ value: 0, isPositive: false }}
            loading={loading}
            variant="info"
            onClick={() => console.log('Navigate to expenses')}
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
        
        <div 
          className="grid grid-cols-1 lg:grid-cols-3 gap-6 slide-in" 
          style={{ 
            animationDelay: '100ms',
            ...professionalContainerStyle
          }}
        >
          <div className="lg:col-span-2 space-y-6">
            <div 
              data-tour="dashboard-chart" 
              style={professionalCardStyle}
              className="hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
            >
              <InvoiceChart />
            </div>
            <div 
              data-tour="dashboard-quick-actions" 
              style={professionalCardStyle}
              className="hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
            >
              <QuickActions />
            </div>
          </div>
          <div className="lg:col-span-1" data-tour="dashboard-recent">
            <div 
              style={professionalCardStyle}
              className="hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
            >
              <RecentInvoices />
            </div>
          </div>
        </div>
        
        <ProgressiveDisclosure
          features={[
            {
              id: 'ai-assistant',
              title: t('dashboard.progressive_features.ai_assistant_title'),
              description: t('dashboard.progressive_features.ai_assistant_desc'),
              category: 'automation',
              difficulty: 'beginner',
              action: () => {
                const url = new URL('/settings', window.location.origin);
                url.searchParams.set('tab', 'ai-config');
                url.searchParams.set('highlight', 'ai_assistant');
                window.location.href = url.toString();
              }
            },
            {
              id: 'email-automation',
              title: t('dashboard.progressive_features.email_automation_title'),
              description: t('dashboard.progressive_features.email_automation_desc'),
              category: 'automation',
              difficulty: 'intermediate',
              action: () => window.location.href = '/settings'
            },
            {
              id: 'advanced-analytics',
              title: t('dashboard.progressive_features.advanced_analytics_title'),
              description: t('dashboard.progressive_features.advanced_analytics_desc'),
              category: 'analytics',
              difficulty: 'intermediate',
              action: () => window.location.href = '/analytics'
            },
            {
              id: 'api-integration',
              title: t('dashboard.progressive_features.api_integration_title'),
              description: t('dashboard.progressive_features.api_integration_desc'),
              category: 'integration',
              difficulty: 'advanced'
            }
          ]}
          className="mt-6"
        />
        
        <CookieConsentBanner 
          analyticsConfig={{
            googleAnalytics: {
              trackingId: 'GA_DEMO_ID',
              enabled: true
            }
          }}
          onConsentChange={(status) => {
            console.log('Cookie consent changed:', status);
          }}
        />
      </div>
    </AppLayout>
  );
};

export default Dashboard;
