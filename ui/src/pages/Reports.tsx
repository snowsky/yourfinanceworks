import React from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ReportGenerator } from '@/components/reports/ReportGenerator';

const Reports: React.FC = () => {
  return (
    <AppLayout>
      <div className="container mx-auto px-4 py-8">
        <ReportGenerator />
      </div>
    </AppLayout>
  );
};

export default Reports;