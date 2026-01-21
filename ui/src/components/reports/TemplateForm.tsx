import React, { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  reportApi, 
  ReportTemplate, 
  ReportTemplateCreate, 
  ReportFilters,
  ReportType
} from '@/lib/api';
import { ReportTypeSelector } from './ReportTypeSelector';
import { ReportFilters as ReportFiltersComponent } from './ReportFilters';
import { Save, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface TemplateFormProps {
  template?: ReportTemplate;
  onSuccess: () => void;
  onCancel: () => void;
}

export const TemplateForm: React.FC<TemplateFormProps> = ({
  template,
  onSuccess,
  onCancel,
}) => {
  const { t } = useTranslation();
  const [name, setName] = useState(template?.name || '');
  const [reportType, setReportType] = useState<string | null>(template?.report_type || null);
  const [filters, setFilters] = useState<ReportFilters>(template?.filters || {});
  const [selectedColumns, setSelectedColumns] = useState<string[]>(template?.columns || []);
  const [isShared, setIsShared] = useState(template?.is_shared || false);
  const [activeTab, setActiveTab] = useState('basic');

  // Fetch available report types
  const { data: reportTypesData, isLoading: reportTypesLoading } = useQuery({
    queryKey: ['reportTypes'],
    queryFn: reportApi.getReportTypes,
  });

  const reportTypes = reportTypesData?.report_types || [];
  const selectedTypeConfig = reportTypes.find(type => type.type === reportType);

  // Create/Update mutation
  const saveMutation = useMutation({
    mutationFn: async (data: ReportTemplateCreate) => {
      if (template) {
        return reportApi.updateTemplate(template.id, data);
      } else {
        return reportApi.createTemplate(data);
      }
    },
    onSuccess: () => {
      toast.success(template ? 'Template updated successfully' : 'Template created successfully');
      onSuccess();
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to save template');
    },
  });

  const handleSave = () => {
    if (!name.trim()) {
      toast.error('Please enter a template name');
      return;
    }

    if (!reportType) {
      toast.error('Please select a report type');
      return;
    }

    const templateData: ReportTemplateCreate = {
      name: name.trim(),
      report_type: reportType as any,
      filters,
      columns: selectedColumns.length > 0 ? selectedColumns : undefined,
      is_shared: isShared,
    };

    saveMutation.mutate(templateData);
  };

  const handleColumnToggle = (column: string, checked: boolean) => {
    if (checked) {
      setSelectedColumns(prev => [...prev, column]);
    } else {
      setSelectedColumns(prev => prev.filter(col => col !== column));
    }
  };

  const handleSelectAllColumns = () => {
    if (selectedTypeConfig) {
      setSelectedColumns([...selectedTypeConfig.available_columns]);
    }
  };

  const handleSelectDefaultColumns = () => {
    if (selectedTypeConfig) {
      setSelectedColumns([...selectedTypeConfig.default_columns]);
    }
  };

  const handleClearColumns = () => {
    setSelectedColumns([]);
  };

  // Reset form when report type changes
  useEffect(() => {
    if (reportType && !template) {
      setFilters({});
      setSelectedColumns([]);
    }
  }, [reportType, template]);

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="basic">Basic Info</TabsTrigger>
          <TabsTrigger value="filters" disabled={!reportType}>Filters</TabsTrigger>
          <TabsTrigger value="columns" disabled={!reportType}>Columns</TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Template Information</CardTitle>
              <CardDescription>
                Basic template settings and {t('reports.report_type_selection').toLowerCase()}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Template Name</Label>
                <Input
                  id="name"
                  placeholder="Enter template name..."
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Report Type</Label>
                <ReportTypeSelector
                  reportTypes={reportTypes}
                  selectedType={reportType}
                  onTypeSelect={setReportType}
                  loading={reportTypesLoading}
                />
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="is_shared"
                  checked={isShared}
                  onCheckedChange={setIsShared}
                />
                <Label htmlFor="is_shared">Share with other users</Label>
              </div>
              {isShared && (
                <p className="text-sm text-muted-foreground">
                  Shared templates can be used by all users in your organization
                </p>
              )}
            </CardContent>
          </Card>

          {reportType && selectedTypeConfig && (
            <Card>
              <CardHeader>
                <CardTitle>Report Type Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <h4 className="font-medium">{selectedTypeConfig.name}</h4>
                  <p className="text-sm text-muted-foreground">
                    {selectedTypeConfig.description}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Badge variant="outline">
                      {selectedTypeConfig.available_filters.length} filters available
                    </Badge>
                    <Badge variant="outline">
                      {selectedTypeConfig.available_columns.length} columns available
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="filters" className="space-y-6">
          {reportType && selectedTypeConfig ? (
            <ReportFiltersComponent
              reportType={reportType}
              reportTypeConfig={selectedTypeConfig}
              filters={filters}
              onFiltersChange={setFilters}
            />
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">
                  Please select a report type first
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="columns" className="space-y-6">
          {reportType && selectedTypeConfig ? (
            <Card>
              <CardHeader>
                <CardTitle>Column Selection</CardTitle>
                <CardDescription>
                  Choose which columns to include in your report
                </CardDescription>
                <div className="flex gap-2 pt-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleSelectAllColumns}
                  >
                    Select All
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleSelectDefaultColumns}
                  >
                    Select Default
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={handleClearColumns}
                  >
                    Clear All
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {selectedTypeConfig.available_columns.map((column) => {
                    const isSelected = selectedColumns.includes(column);
                    const isDefault = selectedTypeConfig.default_columns.includes(column);
                    
                    return (
                      <div key={column} className="flex items-center space-x-2">
                        <Checkbox
                          id={column}
                          checked={isSelected}
                          onCheckedChange={(checked) => handleColumnToggle(column, !!checked)}
                        />
                        <Label 
                          htmlFor={column} 
                          className="text-sm font-normal cursor-pointer flex-1"
                        >
                          {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          {isDefault && (
                            <Badge variant="secondary" className="ml-2 text-xs">
                              Default
                            </Badge>
                          )}
                        </Label>
                      </div>
                    );
                  })}
                </div>

                {selectedColumns.length > 0 && (
                  <div className="mt-6">
                    <Label className="text-sm font-medium">Selected Columns ({selectedColumns.length})</Label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {selectedColumns.map((column) => (
                        <Badge key={column} variant="secondary">
                          {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="ml-1 h-4 w-4 p-0 hover:bg-transparent"
                            onClick={() => handleColumnToggle(column, false)}
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">
                  Please select a report type first
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Separator />

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button 
          onClick={handleSave} 
          disabled={saveMutation.isPending || !name.trim() || !reportType}
        >
          {saveMutation.isPending ? (
            <>
              <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              {template ? 'Update Template' : 'Create Template'}
            </>
          )}
        </Button>
      </div>
    </div>
  );
};