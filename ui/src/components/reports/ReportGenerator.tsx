import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ReportTypeSelector } from './ReportTypeSelector';
import { ReportFilters } from './ReportFilters';
import { ReportPreview } from './ReportPreview';
import { ExportFormatSelector } from './ExportFormatSelector';
import { 
  reportApi, 
  ReportFilters as ReportFiltersType, 
  ReportGenerateRequest,
  ReportPreviewRequest,
  ReportData,
  ReportType
} from '@/lib/api';
import { Eye, FileDown, RefreshCw } from 'lucide-react';

export const ReportGenerator: React.FC = () => {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [filters, setFilters] = useState<ReportFiltersType>({});
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'excel' | 'json'>('pdf');
  const [previewData, setPreviewData] = useState<ReportData | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Fetch available report types
  const { data: reportTypesData, isLoading: reportTypesLoading } = useQuery({
    queryKey: ['reportTypes'],
    queryFn: reportApi.getReportTypes,
  });

  const reportTypes = reportTypesData?.report_types || [];
  const selectedTypeConfig = reportTypes.find(type => type.type === selectedType);

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: (request: ReportPreviewRequest) => reportApi.previewReport(request),
    onSuccess: (data) => {
      setPreviewData(data);
      setPreviewError(null);
    },
    onError: (error: any) => {
      setPreviewError(error.message || 'Failed to generate preview');
      setPreviewData(null);
    },
  });

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: (request: ReportGenerateRequest) => reportApi.generateReport(request),
    onSuccess: (result) => {
      if (result.success) {
        if (result.download_url) {
          // Direct download
          window.open(result.download_url, '_blank');
        } else if (result.file_path) {
          // Use report ID to download
          if (result.report_id) {
            handleDownload(result.report_id);
          }
        }
        toast.success('Report generated successfully!');
      } else {
        toast.error(result.error_message || 'Failed to generate report');
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to generate report');
    },
  });

  // Handle download
  const handleDownload = async (reportId: number) => {
    try {
      const response = await reportApi.downloadReport(reportId);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report-${reportId}.${exportFormat}`;
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

  // Generate preview
  const handlePreview = () => {
    if (!selectedType) {
      toast.error('Please select a report type');
      return;
    }

    const request: ReportPreviewRequest = {
      report_type: selectedType as any,
      filters,
      limit: 10,
    };

    previewMutation.mutate(request);
  };

  // Generate and export report
  const handleExport = () => {
    if (!selectedType) {
      toast.error('Please select a report type');
      return;
    }

    const request: ReportGenerateRequest = {
      report_type: selectedType as any,
      filters,
      export_format: exportFormat,
    };

    exportMutation.mutate(request);
  };

  // Auto-preview when filters change (debounced)
  useEffect(() => {
    if (!selectedType) return;

    const timeoutId = setTimeout(() => {
      if (Object.keys(filters).length > 0) {
        handlePreview();
      }
    }, 1000);

    return () => clearTimeout(timeoutId);
  }, [filters, selectedType]);

  // Reset preview when type changes
  useEffect(() => {
    setPreviewData(null);
    setPreviewError(null);
    setFilters({});
  }, [selectedType]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Report Generator</h1>
        <p className="text-muted-foreground">
          Generate comprehensive reports for your business data
        </p>
      </div>

      {/* Report Type Selection */}
      <ReportTypeSelector
        reportTypes={reportTypes}
        selectedType={selectedType}
        onTypeSelect={setSelectedType}
        loading={reportTypesLoading}
      />

      {selectedType && selectedTypeConfig && (
        <>
          <Separator />
          
          {/* Filters and Preview Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column - Filters */}
            <div className="space-y-6">
              <ReportFilters
                reportType={selectedType}
                reportTypeConfig={selectedTypeConfig}
                filters={filters}
                onFiltersChange={setFilters}
              />

              {/* Preview Button */}
              <Card>
                <CardContent className="pt-6">
                  <Button
                    onClick={handlePreview}
                    disabled={previewMutation.isPending}
                    variant="outline"
                    className="w-full"
                  >
                    {previewMutation.isPending ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
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
            </div>

            {/* Right Column - Preview */}
            <div className="space-y-6">
              <ReportPreview
                reportData={previewData}
                loading={previewMutation.isPending}
                error={previewError}
                onRefresh={handlePreview}
              />
            </div>
          </div>

          <Separator />

          {/* Export Section */}
          <ExportFormatSelector
            selectedFormat={exportFormat}
            onFormatChange={setExportFormat}
            onExport={handleExport}
            loading={exportMutation.isPending}
            disabled={!previewData}
          />

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Common report generation shortcuts</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const today = new Date();
                    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
                    setFilters({
                      ...filters,
                      date_from: firstDayOfMonth.toISOString().split('T')[0],
                      date_to: today.toISOString().split('T')[0],
                    });
                  }}
                >
                  This Month
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const today = new Date();
                    const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                    const lastDayOfLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
                    setFilters({
                      ...filters,
                      date_from: lastMonth.toISOString().split('T')[0],
                      date_to: lastDayOfLastMonth.toISOString().split('T')[0],
                    });
                  }}
                >
                  Last Month
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const today = new Date();
                    const firstDayOfYear = new Date(today.getFullYear(), 0, 1);
                    setFilters({
                      ...filters,
                      date_from: firstDayOfYear.toISOString().split('T')[0],
                      date_to: today.toISOString().split('T')[0],
                    });
                  }}
                >
                  Year to Date
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setFilters({});
                  }}
                >
                  Clear Filters
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};