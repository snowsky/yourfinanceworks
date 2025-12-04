import React from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ReportGenerator } from '@/components/reports/ReportGenerator';
import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";

const Reports: React.FC = () => {
  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title="Reports & Analytics"
          description="Generate comprehensive reports and analyze your business data"
        />

        <ContentSection className="slide-in">
          <FeatureGate
            feature="reporting"
            showUpgradePrompt={true}
            upgradeMessage="Advanced Reporting requires a commercial license. Upgrade to access comprehensive reports and analytics."
          >
            <ReportGenerator />
          </FeatureGate>
        </ContentSection>
      </div>
    </AppLayout>
  );
};

export default Reports;