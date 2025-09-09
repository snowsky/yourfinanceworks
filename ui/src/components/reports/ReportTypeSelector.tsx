import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileText, Users, CreditCard, Receipt, Building } from 'lucide-react';
import { ReportType } from '@/lib/api';

interface ReportTypeSelectorProps {
  reportTypes: ReportType[];
  selectedType: string | null;
  onTypeSelect: (type: string) => void;
  loading?: boolean;
}

const getReportIcon = (type: string) => {
  switch (type) {
    case 'client':
      return <Users className="h-6 w-6" />;
    case 'invoice':
      return <FileText className="h-6 w-6" />;
    case 'payment':
      return <CreditCard className="h-6 w-6" />;
    case 'expense':
      return <Receipt className="h-6 w-6" />;
    case 'statement':
      return <Building className="h-6 w-6" />;
    default:
      return <FileText className="h-6 w-6" />;
  }
};

export const ReportTypeSelector: React.FC<ReportTypeSelectorProps> = ({
  reportTypes,
  selectedType,
  onTypeSelect,
  loading = false,
}) => {
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Select Report Type</CardTitle>
          <CardDescription>Choose the type of report you want to generate</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="h-24 bg-gray-200 rounded-lg"></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Report Type</CardTitle>
        <CardDescription>Choose the type of report you want to generate</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reportTypes.map((reportType) => (
            <Button
              key={reportType.type}
              variant={selectedType === reportType.type ? "default" : "outline"}
              className="h-auto p-4 flex flex-col items-center space-y-2"
              onClick={() => onTypeSelect(reportType.type)}
            >
              {getReportIcon(reportType.type)}
              <div className="text-center">
                <div className="font-medium">{reportType.name}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {reportType.description}
                </div>
              </div>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};