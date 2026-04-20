import React from 'react';
import { ReportGenerator } from '@/components/reports/ReportGenerator';
import { FeatureGate } from '@/components/FeatureGate';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { BarChart3, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const Reports: React.FC = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-8 fade-in dashboard-highlight-mode dashboard-shell">
        <div className="dashboard-highlight-block dashboard-highlight-block-primary dashboard-hero bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 md:p-7 backdrop-blur-sm">
          <div className="space-y-2">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
              {t('navigation.reports')} & {t('navigation.analytics')}
            </h1>
            <p className="text-muted-foreground text-sm md:text-base max-w-2xl">
              {t('dashboard.quick_actions.analytics_desc')}
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/25">
                <BarChart3 className="h-3 w-3 mr-1" />
                {t('navigation.analytics')}
              </Badge>
              <Badge variant="secondary" className="bg-blue-500/10 text-blue-700 border-blue-500/20">
                <FileText className="h-3 w-3 mr-1" />
                {t('navigation.reports')}
              </Badge>
            </div>
          </div>
        </div>

        <ProfessionalCard className="slide-in dashboard-highlight-block dashboard-highlight-block-primary p-5 md:p-6" variant="elevated">
          <FeatureGate
            feature="reporting"
            showUpgradePrompt={true}
            upgradeMessage={t('reports.upgrade_message')}
          >
            <ReportGenerator />
          </FeatureGate>
        </ProfessionalCard>
      </div>
    </>
  );
};

export default Reports;
