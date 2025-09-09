import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  reportApi, 
  ReportTemplate, 
  ReportGenerateRequest,
  ReportFilters
} from '@/lib/api';
import { ExportFormatSelector } from './ExportFormatSelector';
import { ReportPreview } from './ReportPreview';
import { 
  FileText, 
  Calendar, 
  Filter, 
  Columns,
  Users,
  Eye,
  Download
} from 'lucide-react';

interface TemplateGenerateDialogProps {
  template: ReportTemplate;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const TemplateGenerateDialog: React.FC<TemplateGenerateDialogProps> = ({
  template,
  open,
  onOpenChange,
}) => {
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'excel' | 'json'>('pdf');
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: () => reportApi.previewReport({
      report_type: template.report_type,
      filters: template.filters,
      limit: 10,
    }),
    onSuccess: (data) => {
      setPreviewData(data);
      setPreviewError(null);
    },
    onError: (error: any) => {
      setPreviewError(error.message || 'Failed to generate preview');
      setPreviewData(null);
    },
  });

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: () => {
      const request: ReportGenerateRequest = {
        report_type: template.report_type,
        filters: template.filters,
        columns: template.columns,
        export_format: exportFormat,
        template_id: template.id,
      };
      return reportApi.generateReport(request);
    },
    onSuccess: (result) => {
      if (result.success) {
        if (result.download_url) {
          window.open(result.download_url, '_blank');
        } else if (result.report_id) {
          handleDownload(result.report_id);
        }
        toast.success('Report generated successfully!');
        onOpenChange(false);
      } else {
        toast.error(result.error_message || 'Failed to generate report');
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to generate report');
    },
  });

  const handleDownload = async (reportId: number) => {
    try {
      const response = await reportApi.downloadReport(reportId);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${template.name}-${reportId}.${exportFormat}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        throw new Error('Failed to download report');
      }
    } catch (error) {
      toast.error('Failed to download report');
    }
  };

  const handlePreview = () => {
    previewMutation.mutate();
  };

  const handleGenerate = () => {
    generateMutation.mutate();
  };

  const getReportTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      client: 'Client Report',
      invoice: 'Invoice Report',
      payment: 'Payment Report',
      expense: 'Expense Report',
      statement: 'Statement Report',
    };
    return labels[type] || type;
  };

  const getReportTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      client: 'bg-blue-100 text-blue-800',
      invoice: 'bg-green-100 text-green-800',
      payment: 'bg-purple-100 text-purple-800',
      expense: 'bg-orange-100 text-orange-800',
      statement: 'bg-gray-100 text-gray-800',
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  const formatFilterValue = (key: string, value: any): string => {
    if (Array.isArray(value)) {
      return value.length > 3 ? `${value.slice(0, 3).join(', ')} +${value.length - 3} more` : value.join(', ');
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (key.includes('date')) {
      return new Date(value).toLocaleDateString();
    }
    return String(value);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Generate Report: {template.name}
          </DialogTitle>
          <DialogDescription>
            Generate a report using this template with current data
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Template Overview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Template Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                <Badge className={getReportTypeColor(template.report_type)}>
                  {getReportTypeLabel(template.report_type)}
                </Badge>
                {template.is_shared && (
                  <Badge variant="outline">
                    <Users className="mr-1 h-3 w-3" />
                    Shared
                  </Badge>
                )}
              </div>

              {/* Filters Summary */}
              {Object.keys(template.filters).length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Filter className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Active Filters</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                    {Object.entries(template.filters).map(([key, value]) => (
                      <div key={key} className="flex justify-between">
                        <span className="text-muted-foreground">
                          {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:
                        </span>
                        <span className="font-medium">
                          {formatFilterValue(key, value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Columns Summary */}
              {template.columns && template.columns.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Columns className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      Custom Columns ({template.columns.length})
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {template.columns.slice(0, 6).map((column) => (
                      <Badge key={column} variant="outline" className="text-xs">
                        {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </Badge>
                    ))}
                    {template.columns.length > 6 && (
                      <Badge variant="outline" className="text-xs">
                        +{template.columns.length - 6} more
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Template Metadata */}
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
                <div className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Created {new Date(template.created_at).toLocaleDateString()}
                </div>
                {template.updated_at !== template.created_at && (
                  <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    Updated {new Date(template.updated_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Preview Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Preview Controls */}
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Preview</CardTitle>
                  <CardDescription>
                    Preview the report with current data
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    onClick={handlePreview}
                    disabled={previewMutation.isPending}
                    variant="outline"
                    className="w-full"
                  >
                    {previewMutation.isPending ? (
                      <>
                        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        Generating Preview...
                      </>
                    ) : (
                      <>
                        <Eye className="mr-2 h-4 w-4" />
                        Preview Report
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              {/* Export Format Selection */}
              <ExportFormatSelector
                selectedFormat={exportFormat}
                onFormatChange={setExportFormat}
                onExport={handleGenerate}
                loading={generateMutation.isPending}
                disabled={false}
              />
            </div>

            {/* Preview Results */}
            <div>
              <ReportPreview
                reportData={previewData}
                loading={previewMutation.isPending}
                error={previewError}
                onRefresh={handlePreview}
              />
            </div>
          </div>

          <Separator />

          {/* Action Buttons */}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleGenerate}
              disabled={generateMutation.isPending}
            >
              {generateMutation.isPending ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Generating...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Generate & Download
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};