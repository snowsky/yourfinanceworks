import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ReportTypeSelector } from './ReportTypeSelector';
import { reportApi } from '@/lib/api';
import { FileText } from 'lucide-react';

export const ReportGenerator: React.FC = () => {
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
            Report Type Selection
          </CardTitle>
          <CardDescription>
            Choose the type of report you want to generate
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
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