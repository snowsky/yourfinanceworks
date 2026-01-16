import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { FeatureGate } from '@/components/FeatureGate';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalTextarea } from '@/components/ui/professional-textarea';
import {
  ProfessionalTable,
  ProfessionalTableHeader,
  ProfessionalTableBody,
  ProfessionalTableRow,
  ProfessionalTableCell,
  ProfessionalTableHead,
  StatusBadge,
} from '@/components/ui/professional-table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { MetricCard } from '@/components/ui/professional-card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
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
  Plus, Edit, Trash2, RefreshCw, Save, RotateCcw, Eye, Play,
  GitBranch, Activity, CheckCircle2, XCircle, Clock, Zap, Calendar, Code, Terminal, Shield
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Types
interface PromptTemplate {
  id: number;
  name: string;
  description: string;
  category: string;
  template_content: string;
  template_variables: string[];
  default_values: Record<string, any>;
  provider_overrides: Record<string, string>;
  version: number;
  is_active: boolean;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
}

interface PromptVersion extends PromptTemplate {
  is_current: boolean;
}

interface PromptUsageStats {
  total_usage: number;
  successful_usage: number;
  success_rate: number;
  avg_processing_time_ms: number;
  total_tokens: number;
  provider_stats: Record<string, any>;
  days_analyzed: number;
}

const PromptManagement = () => {
  return (
    <FeatureGate
      feature="prompt_management"
      fallback={
        <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
          <ProfessionalCardContent className="p-12 text-center">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
              <Terminal className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">Business License Required</h3>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
              Prompt management allows you to customize AI behavior and create specialized templates for different document types.
              Upgrade to a business license to access advanced prompt customization and template management.
            </p>
            <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
              <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                With Business License, you get:
              </h4>
              <ul className="text-left space-y-3 text-sm text-foreground/80">
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Create custom AI prompts for specialized workflows</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Version control and prompt history tracking</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Test and optimize prompts with real-time preview</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Advanced template variables and conditional logic</span>
                </li>
              </ul>
            </div>
            <div className="flex justify-center gap-4">
              <ProfessionalButton
                variant="gradient"
                onClick={() => window.location.href = '/settings?tab=license'}
                size="lg"
              >
                Activate Business License
              </ProfessionalButton>
              <ProfessionalButton
                variant="outline"
                onClick={() => window.open('https://docs.example.com/prompt-management', '_blank')}
                size="lg"
              >
                Learn More
              </ProfessionalButton>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      }
    >
      <PromptManagementContent />
    </FeatureGate>
  );
};

const PromptManagementContent = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [testVariables, setTestVariables] = useState('{}');
  const [testResult, setTestResult] = useState<string>('');
  const [showVersions, setShowVersions] = useState(false);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    description: string;
    onConfirm: () => void;
  }>({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {},
  });

  // Queries
  const { data: prompts = [], isLoading: loadingPrompts, refetch: refetchPrompts } = useQuery<PromptTemplate[]>({
    queryKey: ['prompts'],
    queryFn: () => api.get('/prompts/'),
    staleTime: 0, // Always consider data stale to ensure fresh fetches
    gcTime: 0, // Don't cache the data
  });

  const { data: defaultPrompts = [] } = useQuery<PromptTemplate[]>({
    queryKey: ['default-prompts'],
    queryFn: () => api.get('/prompts/defaults/list'),
  });

  const { data: usageStats = null } = useQuery<PromptUsageStats>({
    queryKey: ['prompt-usage-stats'],
    queryFn: () => api.get('/prompts/usage-stats?days=30'),
  });

  // Mutations
  const saveMutation = useMutation({
    mutationFn: (prompt: PromptTemplate) =>
      prompt.id ? api.put(`/prompts/${prompt.name}`, prompt) : api.post('/prompts/', prompt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      refetchPrompts(); // Force immediate refetch
      toast.success(t('settings.promptManagement.messages.promptSavedSuccessfully'));
      setIsEditing(false);
      setSelectedPrompt(null);
      setSelectedVersion(null);
    },
    onError: (error) => {
      toast.error(t('settings.promptManagement.messages.failedToSavePrompt'));
      console.error('Error saving prompt:', error);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (promptName: string) => api.delete(`/prompts/${promptName}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      refetchPrompts(); // Force immediate refetch
      toast.success(t('settings.promptManagement.messages.promptDeletedSuccessfully'));
      setSelectedVersion(null);
    },
    onError: (error) => {
      toast.error(t('settings.promptManagement.messages.failedToDeletePrompt'));
      console.error('Error deleting prompt:', error);
    }
  });

  const resetMutation = useMutation({
    mutationFn: (promptName: string) => api.post(`/prompts/${promptName}/reset`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      refetchPrompts(); // Force immediate refetch
      toast.success(t('settings.promptManagement.messages.promptResetSuccessfully'));
      setSelectedVersion(null);
    },
    onError: (error) => {
      toast.error(t('settings.promptManagement.messages.failedToResetPrompt'));
      console.error('Error resetting prompt:', error);
    }
  });

  const restoreVersionMutation = useMutation({
    mutationFn: ({ promptName, version }: { promptName: string, version: number }) =>
      api.post(`/prompts/${promptName}/versions/${version}/restore`),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      refetchPrompts(); // Force immediate refetch
      toast.success(t('settings.promptManagement.messages.versionRestoredSuccessfully', { version: variables.version }));
      setSelectedVersion(variables.version);
      loadPromptVersions(variables.promptName);
    },
    onError: (error) => {
      toast.error(t('settings.promptManagement.messages.failedToRestoreVersion'));
      console.error('Error restoring version:', error);
    }
  });

  const testMutation = useMutation({
    mutationFn: (params: { promptName: string, variables: string }) =>
      api.post<{ result: string }>(`/prompts/${params.promptName}/test`, { variables: params.variables }),
    onSuccess: (data) => {
      setTestResult(data.result);
      toast.success(t('settings.promptManagement.messages.promptTestedSuccessfully'));
    },
    onError: (error) => {
      toast.error(t('settings.promptManagement.messages.failedToTestPrompt'));
      console.error('Error testing prompt:', error);
    }
  });

  // Helper function to format category names
  const formatCategoryName = (category: string) => {
    return t(`settings.promptManagement.categories.${category}`);
  };

  const loadPromptVersions = async (promptName: string) => {
    try {
      const response = await api.get<PromptTemplate[]>(`/prompts/${promptName}/versions`);
      // The highest version number is the current active one
      const currentVersion = Math.max(...response.map(v => v.version), 0);
      const versionsWithCurrent = response.map(v => ({
        ...v,
        is_current: v.version === currentVersion
      }));
      setPromptVersions(versionsWithCurrent);
    } catch (error) {
      console.error('Error loading prompt versions:', error);
    }
  };

  const handleResetPrompt = (promptName: string) => {
    setConfirmModal({
      open: true,
      title: t('settings.promptManagement.messages.confirmResetPromptTitle', { defaultValue: 'Reset Prompt' }),
      description: t('settings.promptManagement.messages.confirmResetPrompt'),
      onConfirm: () => resetMutation.mutate(promptName),
    });
  };

  const handleRestoreVersion = (promptName: string, version: number) => {
    setConfirmModal({
      open: true,
      title: t('settings.promptManagement.messages.confirmRestoreVersionTitle', { defaultValue: 'Restore Version' }),
      description: t('settings.promptManagement.messages.confirmRestoreVersion', { version }),
      onConfirm: () => restoreVersionMutation.mutate({ promptName, version }),
    });
  };

  const handleSavePrompt = (prompt: PromptTemplate) => {
    saveMutation.mutate(prompt);
  };

  const handleDeletePrompt = (promptName: string) => {
    setConfirmModal({
      open: true,
      title: t('settings.promptManagement.messages.confirmDeletePromptTitle', { defaultValue: 'Delete Prompt' }),
      description: t('settings.promptManagement.messages.confirmDeletePrompt'),
      onConfirm: () => deleteMutation.mutate(promptName),
    });
  };

  const handleTestPrompt = (prompt: PromptTemplate) => {
    testMutation.mutate({ promptName: prompt.name, variables: testVariables });
  };

  const handleEditPrompt = async (promptName: string) => {
    try {
      const latestPrompt = await api.get<PromptTemplate>(`/prompts/${promptName}`);
      setSelectedPrompt(latestPrompt);
      setSelectedVersion(latestPrompt.version);
      setIsEditing(true);
      loadPromptVersions(promptName);
    } catch (error) {
      console.error('Error loading prompt:', error);
      toast.error(t('settings.promptManagement.messages.failedToLoadPrompt'));
    }
  };

  const handleViewPrompt = async (prompt: PromptTemplate) => {
    try {
      // For default prompts, they might be customized, so try to get the latest
      const latestPrompt = await api.get<PromptTemplate>(`/prompts/${prompt.name}`).catch(() => prompt);
      setSelectedPrompt(latestPrompt);
      setSelectedVersion(latestPrompt.version);
      setIsEditing(true);
      loadPromptVersions(prompt.name);
    } catch (error) {
      setSelectedPrompt(prompt);
      setSelectedVersion(prompt.version);
      setIsEditing(true);
    }
  };

  // Refetch prompts when editor closes to ensure we have the latest data
  useEffect(() => {
    if (!isEditing && selectedPrompt === null) {
      refetchPrompts();
    }
  }, [isEditing, selectedPrompt, refetchPrompts]);

  // Ensure selectedVersion is synced with selectedPrompt if it's missing
  useEffect(() => {
    if (isEditing && selectedPrompt && (selectedVersion === null || selectedVersion === 0)) {
      setSelectedVersion(selectedPrompt.version);
    }
  }, [isEditing, selectedPrompt?.id, selectedPrompt?.version, selectedVersion]);

  const loading = loadingPrompts || saveMutation.isPending || resetMutation.isPending || restoreVersionMutation.isPending;
  const isTesting = testMutation.isPending;

  const renderPromptEditor = () => {
    if (!selectedPrompt) return null;

    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <div className="flex items-center justify-between">
            <ProfessionalCardTitle>
              {isEditing ? t('settings.promptManagement.editPrompt') : t('settings.promptManagement.createNewPrompt')}
            </ProfessionalCardTitle>
            {isEditing && selectedPrompt.version && promptVersions.length > 0 && (
              <div className="flex items-center gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">{t('settings.promptManagement.selectVersion')}</Label>
                  <Select
                    key={`${selectedPrompt.name}-${selectedPrompt.version}-${selectedVersion}`}
                    value={selectedVersion?.toString()}
                    onValueChange={(value) => {
                      const version = parseInt(value);
                      setSelectedVersion(version);
                      const versionData = promptVersions.find(v => v.version === version);
                      if (versionData) {
                        // Keep the editing state but update content with selected version
                        setSelectedPrompt({ ...versionData });
                      }
                    }}
                  >
                    <SelectTrigger className="h-9 w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {promptVersions.map((v) => (
                        <SelectItem key={v.id} value={v.version.toString()}>
                          v{v.version} {v.is_current ? '(current)' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ProfessionalInput
              label={t('settings.promptManagement.promptName')}
              value={selectedPrompt.name}
              onChange={(e) => setSelectedPrompt({ ...selectedPrompt, name: e.target.value })}
              placeholder="e.g., invoice_data_extraction"
            />

            <div className="space-y-2">
              <Label>{t('settings.promptManagement.category')}</Label>
              <Select
                value={selectedPrompt.category}
                onValueChange={(value) => setSelectedPrompt({ ...selectedPrompt, category: value })}
              >
                <SelectTrigger className="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="invoice_processing">{t('settings.promptManagement.categories.invoice_processing')}</SelectItem>
                  <SelectItem value="statement_processing">{t('settings.promptManagement.categories.statement_processing')}</SelectItem>
                  <SelectItem value="email_classification">{t('settings.promptManagement.categories.email_classification')}</SelectItem>
                  <SelectItem value="ocr_conversion">{t('settings.promptManagement.categories.ocr_conversion')}</SelectItem>
                  <SelectItem value="expense_processing">{t('settings.promptManagement.categories.expense_processing')}</SelectItem>
                  <SelectItem value="fraud_detection">{t('settings.promptManagement.categories.fraud_detection')}</SelectItem>
                  <SelectItem value="general">{t('settings.promptManagement.categories.general')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <ProfessionalTextarea
            label={t('settings.promptManagement.promptDescription')}
            value={selectedPrompt.description}
            onChange={(e) => setSelectedPrompt({ ...selectedPrompt, description: e.target.value })}
            placeholder="Describe what this prompt does..."
            rows={3}
          />

          <ProfessionalTextarea
            label={t('settings.promptManagement.templateContent')}
            value={selectedPrompt.template_content}
            onChange={(e) => setSelectedPrompt({ ...selectedPrompt, template_content: e.target.value })}
            className="font-mono text-sm"
            rows={12}
            placeholder="Enter your prompt template using Jinja2 syntax: {{variable_name}}"
          />

          <ProfessionalInput
            label={t('settings.promptManagement.templateVariables')}
            value={selectedPrompt.template_variables?.join(', ') || ''}
            onChange={(e) => setSelectedPrompt({
              ...selectedPrompt,
              template_variables: e.target.value.split(',').map(v => v.trim()).filter(v => v)
            })}
            placeholder="e.g., file_path, text, raw_content"
          />

          <div className="flex justify-end gap-3 pt-4">
            <ProfessionalButton
              variant="outline"
              onClick={() => {
                setIsEditing(false);
                setSelectedPrompt(null);
                setSelectedVersion(null);
              }}
            >
              {t('settings.promptManagement.cancel')}
            </ProfessionalButton>
            {isEditing && selectedVersion && selectedVersion !== prompts.find(p => p.name === selectedPrompt.name)?.version && (
              <>
                <ProfessionalButton
                  onClick={() => {
                    // Apply this version as the current version
                    handleRestoreVersion(selectedPrompt.name, selectedVersion);
                  }}
                  disabled={loading}
                  loading={loading}
                  variant="outline"
                  className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                >
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  {t('settings.promptManagement.applyVersion')}
                </ProfessionalButton>
              </>
            )}
            <ProfessionalButton
              onClick={() => handleSavePrompt(selectedPrompt)}
              disabled={loading}
              loading={loading}
              variant="gradient"
            >
              <Save className="h-4 w-4 mr-2" />
              {t('settings.promptManagement.saveNewVersion')}
            </ProfessionalButton>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  };

  const renderPromptList = () => (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <div className="flex justify-between items-center">
          <ProfessionalCardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5 text-primary" />
            {t('settings.promptManagement.promptTemplates')}
          </ProfessionalCardTitle>
          <ProfessionalButton
            onClick={() => {
              setSelectedPrompt({
                id: 0,
                name: '',
                description: '',
                category: 'general',
                template_content: '',
                template_variables: [],
                default_values: {},
                provider_overrides: {},
                version: 1,
                is_active: true,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                created_by: null,
                updated_by: null
              });
              setIsEditing(true);
            }}
            variant="gradient"
            size="sm"
          >
            <Plus className="h-4 w-4 mr-2" />
            {t('settings.promptManagement.createNewPrompt')}
          </ProfessionalButton>
        </div>
      </ProfessionalCardHeader>

      <ProfessionalCardContent className="space-y-8">
        {/* Default Prompts Section */}
        {defaultPrompts.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary/50" />
              {t('settings.promptManagement.defaultPrompts')}
            </h3>
            <ProfessionalTable>
              <ProfessionalTableHeader>
                <ProfessionalTableRow>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.name')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.category')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.description')}</ProfessionalTableHead>
                  <ProfessionalTableHead className="text-right">{t('settings.promptManagement.tableHeaders.actions')}</ProfessionalTableHead>
                </ProfessionalTableRow>
              </ProfessionalTableHeader>
              <ProfessionalTableBody>
                {defaultPrompts.map((prompt) => {
                  const isCustomized = prompts.some(p => p.name === prompt.name && p.created_by !== null);
                  return (
                    <ProfessionalTableRow key={prompt.id}>
                      <ProfessionalTableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {prompt.name}
                          {isCustomized && (
                            <Badge variant="secondary" className="text-[10px] h-5">
                              {t('settings.promptManagement.customized')}
                            </Badge>
                          )}
                        </div>
                      </ProfessionalTableCell>
                      <ProfessionalTableCell>
                        <Badge variant="outline" className="font-normal text-muted-foreground">
                          {formatCategoryName(prompt.category)}
                        </Badge>
                      </ProfessionalTableCell>
                      <ProfessionalTableCell className="text-muted-foreground truncate max-w-[300px]">
                        {prompt.description || '-'}
                      </ProfessionalTableCell>
                      <ProfessionalTableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <ProfessionalButton
                            variant="ghost"
                            size="icon"
                            onClick={() => handleViewPrompt(prompt)}
                            title={t('settings.promptManagement.view')}
                          >
                            <Eye className="h-4 w-4 text-muted-foreground" />
                          </ProfessionalButton>
                          {isCustomized && (
                            <ProfessionalButton
                              variant="ghost"
                              size="icon"
                              onClick={() => handleResetPrompt(prompt.name)}
                              title={t('settings.promptManagement.reset')}
                              className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </ProfessionalButton>
                          )}
                        </div>
                      </ProfessionalTableCell>
                    </ProfessionalTableRow>
                  );
                })}
              </ProfessionalTableBody>
            </ProfessionalTable>
          </div>
        )}

        {/* Custom Prompts Section */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary/50" />
            {t('settings.promptManagement.customPrompts')}
          </h3>
          {loading ? (
            <div className="flex items-center justify-center p-8 text-muted-foreground">
              <RefreshCw className="h-6 w-6 animate-spin mr-2" />
              {t('settings.promptManagement.loadingPrompts')}
            </div>
          ) : (
            <ProfessionalTable>
              <ProfessionalTableHeader>
                <ProfessionalTableRow>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.name')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.category')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.version')}</ProfessionalTableHead>
                  <ProfessionalTableHead>{t('settings.promptManagement.tableHeaders.active')}</ProfessionalTableHead>
                  <ProfessionalTableHead className="text-right">{t('settings.promptManagement.tableHeaders.actions')}</ProfessionalTableHead>
                </ProfessionalTableRow>
              </ProfessionalTableHeader>
              <ProfessionalTableBody>
                {prompts.filter(p => p.created_by !== null).map((prompt) => (
                  <ProfessionalTableRow key={prompt.id}>
                    <ProfessionalTableCell className="font-medium">
                      {prompt.name}
                    </ProfessionalTableCell>
                    <ProfessionalTableCell>
                      <Badge variant="outline" className="font-normal text-muted-foreground">
                        {formatCategoryName(prompt.category)}
                      </Badge>
                    </ProfessionalTableCell>
                    <ProfessionalTableCell>
                      <Badge variant="secondary" className="font-mono text-xs">v{prompt.version}</Badge>
                    </ProfessionalTableCell>
                    <ProfessionalTableCell>
                      <StatusBadge status={prompt.is_active ? 'success' : 'neutral'}>
                        {prompt.is_active ? t('common.active') : t('common.inactive')}
                      </StatusBadge>
                    </ProfessionalTableCell>
                    <ProfessionalTableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <ProfessionalButton
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEditPrompt(prompt.name)}
                          title={t('settings.promptManagement.editAction')}
                        >
                          <Edit className="h-4 w-4 text-muted-foreground" />
                        </ProfessionalButton>
                        <ProfessionalButton
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            loadPromptVersions(prompt.name);
                            setShowVersions(true);
                          }}
                          title={t('settings.promptManagement.versions')}
                        >
                          <GitBranch className="h-4 w-4 text-muted-foreground" />
                        </ProfessionalButton>
                        <ProfessionalButton
                          variant="ghost"
                          size="icon"
                          onClick={() => handleTestPrompt(prompt)}
                          title={t('settings.promptManagement.testPrompt')}
                          className="text-green-600 hover:text-green-700 hover:bg-green-50"
                        >
                          <Play className="h-4 w-4" />
                        </ProfessionalButton>
                        <ProfessionalButton
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeletePrompt(prompt.name)}
                          title={t('settings.promptManagement.delete')}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </ProfessionalButton>
                      </div>
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                ))}
                {prompts.filter(p => p.created_by !== null).length === 0 && (
                  <ProfessionalTableRow>
                    <ProfessionalTableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      {t('settings.promptManagement.noCustomPrompts')}
                    </ProfessionalTableCell>
                  </ProfessionalTableRow>
                )}
              </ProfessionalTableBody>
            </ProfessionalTable>
          )}
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );

  const renderTestInterface = () => {
    if (!selectedPrompt || !isEditing) return null;

    return (
      <ProfessionalCard variant="elevated" className="mt-6 border-indigo-200 shadow-indigo-50">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <Play className="h-5 w-5 text-indigo-500" />
            {t('settings.promptManagement.testPrompt')}
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-4">
          <ProfessionalTextarea
            label={t('settings.promptManagement.testVariables')}
            value={JSON.stringify(testVariables, null, 2)}
            onChange={(e) => {
              try {
                setTestVariables(JSON.parse(e.target.value));
              } catch {
                // Invalid JSON, ignore
              }
            }}
            className="font-mono text-sm"
            rows={6}
            placeholder='{"file_path": "/path/to/file.pdf", "text": "sample text"}'
            helperText="Enter variables as a valid JSON object"
          />

          <div className="flex gap-4">
            <ProfessionalButton
              onClick={() => handleTestPrompt(selectedPrompt)}
              disabled={isTesting}
              loading={isTesting}
              variant="gradient"
            >
              <Play className="h-4 w-4 mr-2" />
              {t('settings.promptManagement.testPrompt')}
            </ProfessionalButton>
          </div>

          {testResult && (
            <div className="mt-6">
              <h4 className="font-semibold mb-2 flex items-center gap-2">
                <Activity className="h-4 w-4 text-green-600" />
                {t('settings.promptManagement.testResult')}
              </h4>
              <div className="bg-muted p-4 rounded-xl border border-border/50 overflow-x-auto">
                <pre className="text-sm font-mono text-foreground">
                  {testResult}
                </pre>
              </div>
            </div>
          )}
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  };

  const renderUsageStats = () => (
    <ProfessionalCard variant="default" className="mt-6">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          {t('settings.promptManagement.usageStatistics')}
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>

      <ProfessionalCardContent>
        {usageStats ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricCard
              title={t('settings.promptManagement.totalUsage')}
              value={usageStats.total_usage}
              icon={Zap}
              variant="default"
            />
            <MetricCard
              title={t('settings.promptManagement.successfulUsage')}
              value={usageStats.successful_usage}
              icon={CheckCircle2}
              variant="success"
            />
            <MetricCard
              title={t('settings.promptManagement.successRate')}
              value={`${(usageStats.success_rate * 100).toFixed(1)}%`}
              icon={Activity}
              variant="warning"
            />
            <MetricCard
              title={t('settings.promptManagement.avgProcessingTime')}
              value={`${usageStats.avg_processing_time_ms.toFixed(0)} ms`}
              icon={Clock}
              variant="default"
            />
            <MetricCard
              title={t('settings.promptManagement.totalTokens')}
              value={usageStats.total_tokens.toLocaleString()}
              icon={Code}
              variant="default"
            />
            <MetricCard
              title={t('settings.promptManagement.daysAnalyzed')}
              value={usageStats.days_analyzed}
              icon={Calendar}
              variant="default"
            />
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            {t('settings.promptManagement.noUsageStatistics')}
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );

  const renderVersionModal = () => {
    return (
      <Dialog open={showVersions} onOpenChange={setShowVersions}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-primary" />
              {t('settings.promptManagement.versionHistory')}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {promptVersions.length > 0 ? (
              <div className="space-y-4">
                {promptVersions.map((version) => (
                  <div key={version.id} className={cn(
                    "border rounded-xl p-5 transition-all",
                    version.is_current
                      ? "border-primary/30 bg-primary/5 shadow-sm"
                      : "border-border/50 bg-card hover:border-primary/20"
                  )}>
                    <div className="flex flex-col md:flex-row justify-between md:items-start gap-4 mb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge variant={version.is_current ? "default" : "outline"}>
                            v{version.version}
                          </Badge>
                          {version.is_current && <span className="text-xs font-medium text-primary">({t('settings.promptManagement.current')})</span>}
                        </div>
                        <div className="mt-3 text-sm text-muted-foreground space-y-1">
                          <p className="flex items-center gap-2">
                            <Calendar className="h-3.5 w-3.5" />
                            Created: {new Date(version.created_at).toLocaleString()}
                          </p>
                          {version.updated_at && (
                            <p className="flex items-center gap-2">
                              <Clock className="h-3.5 w-3.5" />
                              Updated: {new Date(version.updated_at).toLocaleString()}
                            </p>
                          )}
                          {version.is_active && (
                            <p className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Active
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        {!version.is_current && (
                          <ProfessionalButton
                            size="sm"
                            variant="outline"
                            onClick={() => handleRestoreVersion(version.name, version.version)}
                            className="border-purple-200 text-purple-700 hover:bg-purple-50 hover:text-purple-800"
                          >
                            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                            {t('settings.promptManagement.restore')}
                          </ProfessionalButton>
                        )}
                        <ProfessionalButton
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setSelectedPrompt(version);
                            setIsEditing(true);
                            setShowVersions(false);
                          }}
                        >
                          <Eye className="h-3.5 w-3.5 mr-1.5" />
                          {t('settings.promptManagement.view')}
                        </ProfessionalButton>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-semibold text-foreground">{t('settings.promptManagement.category')}:</span>
                          <span className="ml-2 text-muted-foreground">{version.category}</span>
                        </div>
                        <div>
                          <span className="font-semibold text-foreground">{t('settings.promptManagement.promptDescription')}:</span>
                          <span className="ml-2 text-muted-foreground">{version.description || '-'}</span>
                        </div>
                      </div>

                      <div className="bg-muted p-3 rounded-lg border border-border/50 font-mono text-xs overflow-x-auto max-h-32">
                        {version.template_content}
                      </div>

                      {version.template_variables && version.template_variables.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {version.template_variables.map((v, i) => (
                            <Badge key={i} variant="secondary" className="text-[10px] font-mono">
                              {v}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border/50">
                {t('settings.promptManagement.noVersionsAvailable')}
              </div>
            )}
          </div>
          <DialogFooter>
            <ProfessionalButton variant="outline" onClick={() => setShowVersions(false)}>
              {t('common.close')}
            </ProfessionalButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight">{t('settings.promptManagement.title')}</h2>
        <p className="text-muted-foreground">
          {t('settings.promptManagement.pageDescription')}
        </p>
      </div>

      {isEditing ? (
        <div className="space-y-6">
          {renderPromptEditor()}
          {renderTestInterface()}
        </div>
      ) : (
        <div className="space-y-6">
          {renderPromptList()}
          {renderUsageStats()}
        </div>
      )}

      {renderVersionModal()}

      <AlertDialog open={confirmModal.open} onOpenChange={(open) => setConfirmModal({ ...confirmModal, open })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmModal.title}</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmModal.description}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                confirmModal.onConfirm();
                setConfirmModal({ ...confirmModal, open: false });
              }}
              className={confirmModal.title.toLowerCase().includes('delete') ? 'bg-destructive text-white hover:bg-destructive/90' : 'bg-primary text-primary-foreground hover:bg-primary/90'}
            >
              {t('common.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PromptManagement;
