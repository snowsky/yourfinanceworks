import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { loadPluginTranslations, arePluginTranslationsLoaded } from '@/i18n';
import { useLocaleFormatter } from '@/i18n/formatters';
import {
  ArrowLeft, Wallet, TrendingUp, Activity, Target,
  Edit, BarChart3, PieChart, History, Trash2, Upload
} from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ShareButton } from '@/components/sharing/ShareButton';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { investmentApi, InvestmentPortfolio } from '@/lib/api';
import HoldingsList from '@/components/investments/HoldingsList';
import TransactionsList from '@/components/investments/TransactionsList';
import EditPortfolioDialog from '@/components/investments/EditPortfolioDialog';

import PortfolioAnalytics from '@/components/investments/PortfolioAnalytics';
import FileAttachmentsList from '@/components/investments/FileAttachmentsList';
import FileUploadArea from '@/components/investments/FileUploadArea';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const PortfolioDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const portfolioId = parseInt(id || '0', 10);
  const { t, ready } = useTranslation('investments');
  const formatter = useLocaleFormatter();

  const [showEditPortfolio, setShowEditPortfolio] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [translationsReady, setTranslationsReady] = useState(false);

  // Ensure plugin translations are loaded
  React.useEffect(() => {
    const loadTranslations = async () => {
      if (!arePluginTranslationsLoaded('investments')) {
        try {
          await loadPluginTranslations('investments');
          console.log('Investment translations loaded on portfolio detail page');
          setTranslationsReady(true);
        } catch (error) {
          console.warn('Failed to load investment translations:', error);
          setTranslationsReady(true); // Still mark as ready to avoid infinite loading
        }
      } else {
        setTranslationsReady(true);
      }
    };

    loadTranslations();
  }, []);

  const { data: portfolio, isLoading: portfolioLoading } = useQuery<InvestmentPortfolio>({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => investmentApi.get(portfolioId),
    enabled: !!portfolioId
  });

  const { data: performance, isLoading: performanceLoading } = useQuery({
    queryKey: ['portfolio', portfolioId, 'performance'],
    queryFn: () => investmentApi.getPerformance(portfolioId),
    enabled: !!portfolioId
  });

  const deleteMutation = useMutation({
    mutationFn: () => investmentApi.delete(portfolioId),
    onSuccess: () => {
      toast.success(t('Portfolio deleted successfully'));
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      navigate('/investments');
    },
    onError: (error: any) => {
      const message = error instanceof Error ? error.message : t('Failed to delete portfolio');
      toast.error(message);
    }
  });

  const isLoading = portfolioLoading || performanceLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">{t('Loading portfolio details...')}</p>
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-6">
        <div className="p-4 rounded-full bg-destructive/10 text-destructive">
          <Wallet className="w-12 h-12" />
        </div>
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold">{t('Portfolio Not Found')}</h2>
          <p className="text-muted-foreground max-w-md">{t('The portfolio you are looking for does not exist or you do not have permission to view it.')}</p>
        </div>
        <ProfessionalButton asChild variant="outline">
          <Link to="/investments">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('Back to Dashboard')}
          </Link>
        </ProfessionalButton>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return formatter.formatCurrency(amount, portfolio.currency || 'USD');
  };

  const formatPercentage = (percentage: number) => {
    return formatter.formatPercent(percentage / 100, 2);
  };

  const getPortfolioTypeColor = (type: string) => {
    switch (type) {
      case 'taxable': return 'bg-blue-100/50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200/50';
      case 'retirement': return 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200/50';
      case 'business': return 'bg-amber-100/50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200/50';
      default: return 'bg-slate-100/50 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200/50';
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <div className="flex items-center gap-4 mb-2">
        <ProfessionalButton asChild variant="ghost" size="sm" className="rounded-full h-10 w-10 p-0 hover:bg-primary/10 hover:text-primary transition-all">
          <Link to="/investments">
            <ArrowLeft className="w-5 h-5" />
          </Link>
        </ProfessionalButton>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-medium">Investments</span>
          <span className="text-muted-foreground/30 px-1">/</span>
          <span className="text-foreground font-semibold text-sm px-2 py-0.5 rounded-md bg-muted">{portfolio.name}</span>
        </div>
      </div>

      <PageHeader
        title={portfolio.name}
        description={translationsReady ? t('portfolio.taxable_portfolio_description') : 'Manage holdings and track performance for your taxable portfolio'}
        actions={
          <div className="flex gap-2">
            <ShareButton recordType="portfolio" recordId={portfolio.id} />
            <ProfessionalButton
              variant="outline"
              size="sm"
              className="rounded-xl border-border/50 text-destructive hover:bg-destructive/5 hover:text-destructive hover:border-destructive/30 transition-all"
              onClick={() => setShowDeleteConfirm(true)}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              {t('Delete')}
            </ProfessionalButton>
          </div>
        }
      >
        <div className="flex items-center gap-3 mt-4">
          <Badge variant="outline" className={cn("px-3 py-1 rounded-full border shadow-sm font-semibold uppercase tracking-wider text-[10px]", getPortfolioTypeColor(portfolio.portfolio_type))}>
            {portfolio.portfolio_type}
          </Badge>
          <span className="text-muted-foreground text-sm font-medium">
            Currency: <span className="text-foreground font-bold">{portfolio.currency}</span>
          </span>
        </div>
      </PageHeader>

      <ContentSection>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title={t('portfolio.total_market_value_detail')}
            value={formatCurrency(performance?.total_value || portfolio.total_value || 0)}
            icon={Wallet}
            description={t('portfolio.total_market_value_detail_description')}
          />
          <MetricCard
            title={t('portfolio.total_return_detail')}
            value={formatPercentage(performance?.total_return_percentage || 0)}
            change={{
              value: performance?.total_gain_loss || 0,
              type: (performance?.total_gain_loss || 0) >= 0 ? 'increase' : 'decrease'
            }}
            icon={TrendingUp}
            variant={(performance?.total_return_percentage || 0) >= 0 ? 'success' : 'danger'}
            description={t('portfolio.total_return_detail_description')}
          />
          <MetricCard
            title={t('portfolio.unrealized_gain_detail')}
            value={formatCurrency(performance?.unrealized_gain_loss || 0)}
            icon={Activity}
            variant={(performance?.unrealized_gain_loss || 0) >= 0 ? 'success' : 'danger'}
            description={t('portfolio.unrealized_gain_detail_description')}
          />
          <MetricCard
            title={t('portfolio.asset_classes_detail')}
            value={portfolio.holdings_count || 0}
            icon={Target}
            description={t('portfolio.asset_classes_detail_description')}
          />
        </div>
      </ContentSection>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 items-start">
        <div className="xl:col-span-2 space-y-8">
          <Tabs defaultValue="holdings" className="w-full">
            <div className="flex items-center justify-between mb-4">
              <TabsList className="bg-muted/50 p-1 rounded-xl h-11 border border-border/50">
                <TabsTrigger value="holdings" className="rounded-lg px-6 font-semibold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <PieChart className="w-4 h-4 mr-2" />
                  {t('portfolio.holdings_tab')}
                </TabsTrigger>
                <TabsTrigger value="transactions" className="rounded-lg px-6 font-semibold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <History className="w-4 h-4 mr-2" />
                  {t('portfolio.transactions_tab')}
                </TabsTrigger>
                <TabsTrigger value="analytics" className="rounded-lg px-6 font-semibold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <BarChart3 className="w-4 h-4 mr-2" />
                  {t('portfolio.analytics_tab')}
                </TabsTrigger>
                <TabsTrigger value="imports" className="rounded-lg px-6 font-semibold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <Upload className="w-4 h-4 mr-2" />
                  {t('portfolio.imports_tab')}
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="holdings" className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <HoldingsList portfolioId={portfolio.id} />
            </TabsContent>

            <TabsContent value="transactions" className="mt-0 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <TransactionsList portfolioId={portfolio.id} />
            </TabsContent>


            <TabsContent value="analytics" className="mt-0 pt-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <PortfolioAnalytics portfolioId={portfolio.id} />
            </TabsContent>

            <TabsContent value="imports" className="mt-0 space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <FileUploadArea portfolioId={portfolio.id} />
              <FileAttachmentsList portfolioId={portfolio.id} />
            </TabsContent>
          </Tabs>
        </div>

        <div className="space-y-6">
          <ProfessionalCard title="Portfolio Details" variant="elevated" className="border-border/40 overflow-hidden">
            <div className="space-y-4 pt-4">
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('portfolio.created_at')}</span>
                <span className="font-medium text-sm">{formatter.formatDate(new Date(portfolio.created_at), 'medium')}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('portfolio.last_updated')}</span>
                <span className="font-medium text-sm">{formatter.formatDate(new Date(portfolio.updated_at), 'medium')}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('portfolio.status')}</span>
                <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 rounded-lg">{t('portfolio.status_active')}</Badge>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-muted-foreground text-sm">{t('portfolio.portfolio_id')}</span>
                <span className="font-mono text-xs text-muted-foreground">#{portfolio.id}</span>
              </div>
              <ProfessionalButton
                variant="outline"
                className="w-full mt-4 rounded-xl border-border/50 hover:bg-primary/5 hover:text-primary transition-all shadow-sm"
                onClick={() => setShowEditPortfolio(true)}
              >
                <Edit className="w-4 h-4 mr-2" />
                {t('Edit Portfolio Details')}
              </ProfessionalButton>
            </div>
          </ProfessionalCard>

          <ProfessionalCard title={t('portfolio.quick_actions')} className="border-border/40">
            <div className="grid grid-cols-1 gap-2 mt-2">
              <ProfessionalButton
                variant="minimal"
                className="justify-start h-12 px-4 rounded-xl hover:bg-primary/5 hover:text-primary transition-all group"
                onClick={() => navigate(`/investments/portfolio/${portfolioId}/performance`)}
              >
                <div className="p-2 rounded-lg bg-primary/5 group-hover:bg-primary/10 mr-3">
                  <BarChart3 className="w-4 h-4" />
                </div>
                {t('portfolio.generate_performance_report')}
              </ProfessionalButton>
              <ProfessionalButton
                variant="minimal"
                className="justify-start h-12 px-4 rounded-xl hover:bg-primary/5 hover:text-primary transition-all group"
                onClick={() => navigate(`/investments/portfolio/${portfolioId}/rebalance`)}
              >
                <div className="p-2 rounded-lg bg-primary/5 group-hover:bg-primary/10 mr-3">
                  <PieChart className="w-4 h-4" />
                </div>
                {t('portfolio.asset_rebalancing_tool')}
              </ProfessionalButton>
            </div>
          </ProfessionalCard>
        </div>
      </div>

      {/* Action Dialogs */}
      {portfolio && (
        <>
          <EditPortfolioDialog
            portfolio={portfolio}
            open={showEditPortfolio}
            onOpenChange={setShowEditPortfolio}
          />

          <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
            <AlertDialogContent className="rounded-3xl border-border/50 shadow-2xl">
              <AlertDialogHeader>
                <AlertDialogTitle className="text-2xl font-bold tracking-tight">{t('Delete Portfolio?')}</AlertDialogTitle>
                <AlertDialogDescription className="text-muted-foreground leading-relaxed">
                  {t('This will move "{{name}}" and all its transaction history to the Recycle Bin. You can restore it later if needed.', { name: portfolio.name })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter className="gap-2 pt-4">
                <AlertDialogCancel className="rounded-xl font-semibold border-border/50">{t('Cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  className="rounded-xl font-semibold bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? t('Deleting...') : t('Delete Portfolio')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </div>
  );
};

export default PortfolioDetail;