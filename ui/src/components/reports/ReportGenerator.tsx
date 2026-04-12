import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ReportTypeSelector } from './ReportTypeSelector';
import { reportApi } from '@/lib/api';
import { FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export const ReportGenerator: React.FC = () => {
  const { t } = useTranslation();
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // Fetch available report types
  const { data: reportTypesData, isLoading: reportTypesLoading } = useQuery({
    queryKey: ['reportTypes'],
    queryFn: reportApi.getReportTypes,
  });

  const reportTypes = reportTypesData?.report_types || [];

  return (
    <div className="space-y-8">
      {/* Report Type Selection */}
      <Card className="slide-in">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('reports.report_type_selection')}
          </CardTitle>
          <CardDescription>
            {t('reports.choose_report_type')}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <p className="mb-4 text-sm text-muted-foreground">
            Select a report card below to open its preview page.
          </p>
          <ReportTypeSelector
            reportTypes={reportTypes}
            selectedType={selectedType}
            onTypeSelect={setSelectedType}
            loading={reportTypesLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
};
