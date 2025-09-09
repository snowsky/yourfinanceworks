import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  reportApi, 
  ReportTemplate,
  ReportGenerateRequest,
  ReportPreviewRequest,
  ReportData
} from '@/lib/api';
import { ReportPreview } from './ReportPreview';
import { ExportFormatSelector } from './ExportFormatSelector';
import { TemplateSharing } from './TemplateSharing';
import { 
  FileText, 
  Template, 
  Eye, 
  Download,
  Filter,
  Columns,
  Users,
  RefreshCw,
  Settings
} from 'lucide-react';

export const TemplateBasedReportGenerator: React.FC = () => {
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'excel' | 'json'>('pdf');
  const [previewData, setPreviewData] = useState<ReportData | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('templates');

  // Fetch templates
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['reportTemplates'],
    queryFn: reportApi.getTemplates,
  });

  const templates = templatesData?.templates || [];
  const selectedTemplate = templates.find(t => t.id === selectedTemplateId);

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

  // Generate mutation
  const generateMutation = useMutation({
    mutationFn: (request: ReportGenerateRequest) => reportApi.generateReport(request),
    onSuccess: (result) => {
      if (result.success) {
        if (result.download_url) {
          window.open(result.download_url, '_blank');
        } else if (result.report_id) {
          handleDownload(result.report_id);
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

  const handleDownload = async (reportId: number) => {
    try {
      const response = await reportApi.downloadReport(reportId);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${selectedTemplate?.name || 'report'}-${reportId}.${exportFormat}`;
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
    if (!selectedTemplate) return;

    const request: ReportPreviewRequest = {
      report_type: selectedTemplate.report_type,
      filters: selectedTemplate.filters,
      limit: 10,
    };

    previewMutation.mutate(request);
  };

  const handleGenerate = () => {
    if (!selectedTemplate) return;

    const request: ReportGenerateRequest = {
      report_type: selectedTemplate.report_type,
      filters: selectedTemplate.filters,
      columns: selectedTemplate.columns,
      export_format: exportFormat,
      template_id: selectedTemplate.id,
    };

    generateMutation.mutate(request);
  };

  // Auto-preview when template changes
  useEffect(() => {
    if (selectedTemplate) {
      handlePreview();
    } else {
      setPreviewData(null);
      setPreviewError(null);
    }
  }, [selectedTemplateId]);

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
      return value.length > 2 ? `${value.slice(0, 2).join(', ')} +${value.length - 2} more` : value.join(', ');
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (key.includes('date')) {
      return new Date(value).toLocaleDateString();
    }
    return String(value);
  };

  // Group templates by type
  const templatesByType = templates.reduce((acc, template) => {
    if (!acc[template.report_type]) {
      acc[template.report_type] = [];
    }
    acc[template.report_type].push(template);
    return acc;
  }, {} as Record<string, ReportTemplate[]>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Template-Based Reports</h1>
        <p className="text-muted-foreground">
          Generate reports using your saved templates
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="templates">Select Template</TabsTrigger>
          <TabsTrigger value="preview" disabled={!selectedTemplate}>Preview & Generate</TabsTrigger>
        </TabsList>

        <TabsContent value="templates" className="space-y-6">
          {/* Template Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Template className="h-5 w-5" />
                Choose Template
              </CardTitle>
              <CardDescription>
                Select a template to generate a report with current data
              </CardDescription>
            </CardHeader>
            <CardContent>
              {templatesLoading ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">Loading templates...</span>
                </div>
              ) : templates.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No templates available</h3>
                  <p className="text-muted-foreground mb-4">
                    Create your first template to get started with template-based reporting
                  </p>
                  <Button onClick={() => window.location.href = '/reports/templates'}>
                    Manage Templates
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <Select 
                    value={selectedTemplateId?.toString() || ''} 
                    onValueChange={(value) => setSelectedTemplateId(parseInt(value))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a template..." />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(templatesByType).map(([type, typeTemplates]) => (
                        <div key={type}>
                          <div className="px-2 py-1.5 text-sm font-semibold text-muted-foreground">
                            {getReportTypeLabel(type)}
                          </div>
                          {typeTemplates.map((template) => (
                            <SelectItem key={template.id} value={template.id.toString()}>
                              <div className="flex items-center gap-2">
                                <span>{template.name}</span>
                                {template.is_shared && (
                                  <Users className="h-3 w-3 text-muted-foreground" />
                                )}
                              </div>
                            </SelectItem>
                          ))}
                        </div>
                      ))}
                    </SelectContent>
                  </Select>

                  {selectedTemplate && (
                    <Button 
                      onClick={() => setActiveTab('preview')}
                      className="w-full"
                    >
                      Continue with "{selectedTemplate.name}"
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Template Grid View */}
          {templates.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <Card 
                  key={template.id} 
                  className={`cursor-pointer transition-all hover:shadow-md ${
                    selectedTemplateId === template.id ? 'ring-2 ring-primary' : ''
                  }`}
                  onClick={() => setSelectedTemplateId(template.id)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-base truncate">{template.name}</CardTitle>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge 
                            variant="secondary" 
                            className={getReportTypeColor(template.report_type)}
                          >
                            {getReportTypeLabel(template.report_type)}
                          </Badge>
                          {template.is_shared && (
                            <Badge variant="outline" className="text-xs">
                              <Users className="mr-1 h-3 w-3" />
                              Shared
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="space-y-2">
                      <div className="text-xs text-muted-foreground">
                        {Object.keys(template.filters).length} filters • {' '}
                        {template.columns?.length || 'Default'} columns
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Created {new Date(template.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="preview" className="space-y-6">
          {selectedTemplate && (
            <>
              {/* Template Details */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5" />
                        {selectedTemplate.name}
                      </CardTitle>
                      <CardDescription>
                        {getReportTypeLabel(selectedTemplate.report_type)} • {' '}
                        Created {new Date(selectedTemplate.created_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={getReportTypeColor(selectedTemplate.report_type)}>
                        {getReportTypeLabel(selectedTemplate.report_type)}
                      </Badge>
                      {selectedTemplate.is_shared && (
                        <TemplateSharing 
                          template={selectedTemplate}
                          trigger={
                            <Button variant="outline" size="sm">
                              <Settings className="h-4 w-4" />
                            </Button>
                          }
                        />
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Filters */}
                  {Object.keys(selectedTemplate.filters).length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Active Filters</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        {Object.entries(selectedTemplate.filters).map(([key, value]) => (
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

                  {/* Columns */}
                  {selectedTemplate.columns && selectedTemplate.columns.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Columns className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">
                          Custom Columns ({selectedTemplate.columns.length})
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {selectedTemplate.columns.map((column) => (
                          <Badge key={column} variant="outline" className="text-xs">
                            {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Preview and Export */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Preview Controls */}
                <div className="space-y-6">
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
                            Refresh Preview
                          </>
                        )}
                      </Button>
                    </CardContent>
                  </Card>

                  <ExportFormatSelector
                    selectedFormat={exportFormat}
                    onFormatChange={setExportFormat}
                    onExport={handleGenerate}
                    loading={generateMutation.isPending}
                    disabled={!previewData}
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
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};