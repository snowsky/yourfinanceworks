import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { 
  Plus, 
  MoreVertical, 
  Edit, 
  Trash2, 
  Share2, 
  Copy, 
  FileText,
  Users,
  Lock
} from 'lucide-react';
import { reportApi, ReportTemplate } from '@/lib/api';
import { TemplateForm } from './TemplateForm';
import { TemplateGenerateDialog } from './TemplateGenerateDialog';

export const TemplateManager: React.FC = () => {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null);
  const [deletingTemplate, setDeletingTemplate] = useState<ReportTemplate | null>(null);
  const [generatingTemplate, setGeneratingTemplate] = useState<ReportTemplate | null>(null);
  
  const queryClient = useQueryClient();

  // Fetch templates
  const { data: templatesData, isLoading } = useQuery({
    queryKey: ['reportTemplates'],
    queryFn: reportApi.getTemplates,
  });

  const templates = templatesData?.templates || [];

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: reportApi.deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reportTemplates'] });
      toast.success('Template deleted successfully');
      setDeletingTemplate(null);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete template');
    },
  });

  // Duplicate mutation
  const duplicateMutation = useMutation({
    mutationFn: async (template: ReportTemplate) => {
      const duplicateData = {
        name: `${template.name} (Copy)`,
        report_type: template.report_type,
        filters: template.filters,
        columns: template.columns,
        formatting: template.formatting,
        is_shared: false, // Duplicates are private by default
      };
      return reportApi.createTemplate(duplicateData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reportTemplates'] });
      toast.success('Template duplicated successfully');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to duplicate template');
    },
  });

  const handleDelete = (template: ReportTemplate) => {
    setDeletingTemplate(template);
  };

  const confirmDelete = () => {
    if (deletingTemplate) {
      deleteMutation.mutate(deletingTemplate.id);
    }
  };

  const handleDuplicate = (template: ReportTemplate) => {
    duplicateMutation.mutate(template);
  };

  const handleEdit = (template: ReportTemplate) => {
    setEditingTemplate(template);
  };

  const handleGenerate = (template: ReportTemplate) => {
    setGeneratingTemplate(template);
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

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Report Templates</h1>
            <p className="text-muted-foreground">Manage your report templates</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="h-3 bg-gray-200 rounded"></div>
                  <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Report Templates</h1>
          <p className="text-muted-foreground">
            Create and manage reusable report templates
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Template
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Report Template</DialogTitle>
              <DialogDescription>
                Create a new report template with custom filters and formatting
              </DialogDescription>
            </DialogHeader>
            <TemplateForm
              onSuccess={() => {
                setIsCreateDialogOpen(false);
                queryClient.invalidateQueries({ queryKey: ['reportTemplates'] });
              }}
              onCancel={() => setIsCreateDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      {/* Templates Grid */}
      {templates.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No templates yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first report template to get started with automated reporting
            </p>
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Template
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <Card key={template.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg truncate">{template.name}</CardTitle>
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
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleGenerate(template)}>
                        <FileText className="mr-2 h-4 w-4" />
                        Generate Report
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleEdit(template)}>
                        <Edit className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleDuplicate(template)}>
                        <Copy className="mr-2 h-4 w-4" />
                        Duplicate
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        onClick={() => handleDelete(template)}
                        className="text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  {/* Filter Summary */}
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Filters:</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(template.filters).length === 0 ? (
                        <Badge variant="outline" className="text-xs">No filters</Badge>
                      ) : (
                        Object.keys(template.filters).slice(0, 3).map((key) => (
                          <Badge key={key} variant="outline" className="text-xs">
                            {key.replace('_', ' ')}
                          </Badge>
                        ))
                      )}
                      {Object.keys(template.filters).length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{Object.keys(template.filters).length - 3} more
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Columns Summary */}
                  {template.columns && template.columns.length > 0 && (
                    <div>
                      <p className="text-sm text-muted-foreground mb-1">
                        Columns: {template.columns.length} selected
                      </p>
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="text-xs text-muted-foreground">
                    Created {new Date(template.created_at).toLocaleDateString()}
                  </div>
                </div>

                <Separator className="my-4" />

                {/* Actions */}
                <div className="flex gap-2">
                  <Button 
                    size="sm" 
                    onClick={() => handleGenerate(template)}
                    className="flex-1"
                  >
                    Generate
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => handleEdit(template)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Dialog */}
      {editingTemplate && (
        <Dialog open={!!editingTemplate} onOpenChange={() => setEditingTemplate(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Template</DialogTitle>
              <DialogDescription>
                Modify the template settings and filters
              </DialogDescription>
            </DialogHeader>
            <TemplateForm
              template={editingTemplate}
              onSuccess={() => {
                setEditingTemplate(null);
                queryClient.invalidateQueries({ queryKey: ['reportTemplates'] });
              }}
              onCancel={() => setEditingTemplate(null)}
            />
          </DialogContent>
        </Dialog>
      )}

      {/* Generate Dialog */}
      {generatingTemplate && (
        <TemplateGenerateDialog
          template={generatingTemplate}
          open={!!generatingTemplate}
          onOpenChange={() => setGeneratingTemplate(null)}
        />
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={!!deletingTemplate} onOpenChange={() => setDeletingTemplate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Template</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingTemplate?.name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};