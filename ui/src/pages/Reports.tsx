import React from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { ReportGenerator } from '@/components/reports/ReportGenerator';
import { BarChart3 } from 'lucide-react';

const Reports: React.FC = () => {
  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <BarChart3 className="h-8 w-8 text-primary" />
              Reports & Analytics
            </h1>
            <p className="text-muted-foreground">
              Generate comprehensive reports and analyze your business data
            </p>
          </div>
        </div>

        <div className="slide-in">
          <ReportGenerator />
        </div>
      </div>
    </AppLayout>
  );
};

export default Reports;