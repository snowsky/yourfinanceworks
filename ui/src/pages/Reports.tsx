import React from 'react';
import { ReportGenerator } from '@/components/reports/ReportGenerator';
import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import { useTranslation } from 'react-i18next';

const Reports: React.FC = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('navigation.reports') + ' & ' + t('navigation.analytics')}
          description={t('dashboard.quick_actions.analytics_desc')}
        />

        <ContentSection className="slide-in">
          <FeatureGate
            feature="reporting"
            showUpgradePrompt={true}
            upgradeMessage={t('reports.upgrade_message')}
          >
            <ReportGenerator />
          </FeatureGate>
        </ContentSection>
      </div>
    </>
  );
};

export default Reports;
