import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Cpu as CpuIcon, Plus, Edit, Trash2, Loader2, ShieldCheck, Shield, Zap, RotateCcw, Wand } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import {
    ProfessionalTable,
    ProfessionalTableHeader,
    ProfessionalTableBody,
    ProfessionalTableRow,
    ProfessionalTableCell,
    ProfessionalTableHead,
    StatusBadge,
} from "@/components/ui/professional-table";
import { aiConfigApi, settingsApi, AIConfig, AIConfigCreate, AIProviderInfo } from "@/lib/api";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useFeatures } from "@/contexts/FeatureContext";
import { FeatureGate } from "@/components/FeatureGate";

interface AIConfigTabProps {
    isAdmin: boolean;
}

export const AIConfigTab: React.FC<AIConfigTabProps> = ({
    isAdmin,
}) => {
    return (
        <FeatureGate
            feature="ai_chat"
            fallback={
                <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
                    <ProfessionalCardContent className="p-12 text-center">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                            <Zap className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-foreground mb-3">Business License Required</h3>
                        <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                            AI configuration allows you to set up custom AI providers and models for invoice processing, expense analysis, and intelligent automation.
                            Upgrade to a business license to access advanced AI features and customize your AI workflows.
                        </p>
                        <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                            <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                                <Shield className="h-4 w-4 text-primary" />
                                With Business License, you get:
                            </h4>
                            <ul className="text-left space-y-3 text-sm text-foreground/80">
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Configure multiple AI providers (OpenAI, Anthropic, etc.)</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Custom AI model selection and fine-tuning options</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Advanced AI assistant with chat functionality</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>AI-powered invoice and expense processing automation</span>
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
                                onClick={() => window.open('https://docs.example.com/ai-configuration', '_blank')}
                                size="lg"
                            >
                                Learn More
                            </ProfessionalButton>
                        </div>
                    </ProfessionalCardContent>
                </ProfessionalCard>
            }
        >
            <AIConfigContent isAdmin={isAdmin} />
        </FeatureGate>
    );
};

const AIConfigContent: React.FC<AIConfigTabProps> = ({
    isAdmin,
}) => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();
    const { isFeatureEnabled } = useFeatures();

    const [aiAssistantEnabled, setAiAssistantEnabled] = useState(false);
    const [showAIConfigDialog, setShowAIConfigDialog] = useState(false);
    const [editingAIConfig, setEditingAIConfig] = useState<AIConfig | null>(null);
    const [newAIConfig, setNewAIConfig] = useState<AIConfigCreate>({
        provider_name: "openai",
        provider_url: "",
        api_key: "",
        model_name: "gpt-4",
        is_active: true,
        is_default: false,
        ocr_enabled: false,
    });
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
    const [configToDelete, setConfigToDelete] = useState<number | null>(null);
    const [reviewWorkerEnabled, setReviewWorkerEnabled] = useState(false);
    const [isTriggeringReview, setIsTriggeringReview] = useState(false);
    const [reviewerConfig, setReviewerConfig] = useState<any>({
        use_custom_config: false,
        config: {
            provider_name: '',
            model_name: '',
            api_key: '',
        }
    });

    const { data: configs = [], isLoading: isLoadingConfigs } = useQuery({
        queryKey: ['aiConfigs'],
        queryFn: () => aiConfigApi.getAIConfigs(),
        enabled: isAdmin,
    });

    const { data: providersData } = useQuery({
        queryKey: ['aiProviders'],
        queryFn: () => aiConfigApi.getSupportedProviders(),
        enabled: isAdmin,
    });

    const { data: generalSettings } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.getSettings(),
        enabled: isAdmin,
    });

    useEffect(() => {
        if (generalSettings) {
            setAiAssistantEnabled(generalSettings.enable_ai_assistant ?? false);
        }
    }, [generalSettings]);

    useEffect(() => {
        const fetchReviewerSettings = async () => {
            try {
                const workerSetting = await settingsApi.getSetting('review_worker_enabled');
                setReviewWorkerEnabled(!!workerSetting?.value);

                const configSetting = await settingsApi.getSetting('reviewer_ai_config');
                if (configSetting?.value) {
                    setReviewerConfig(configSetting.value);
                }
            } catch (error) {
                console.error('Error fetching reviewer settings:', error);
            }
        };
        if (isAdmin) {
            fetchReviewerSettings();
        }
    }, [isAdmin]);

    const supportedProviders = providersData?.providers || {};

    const toggleAssistantMutation = useMutation({
        mutationFn: (checked: boolean) => settingsApi.updateSettings({ enable_ai_assistant: checked }),
        onSuccess: (data, checked) => {
            setAiAssistantEnabled(checked);
            toast.success(checked ? t('settings.ai_config.ai_assistant_enabled') : t('settings.ai_assistant_disabled'));
            queryClient.invalidateQueries({ queryKey: ['settings'] });
        },
        onError: () => {
            toast.error(t('settings.ai_config.failed_to_update_settings'));
        }
    });

    const createConfigMutation = useMutation({
        mutationFn: (data: AIConfigCreate) => aiConfigApi.createAIConfig(data),
        onSuccess: () => {
            toast.success(t('settings.ai_config.ai_config_created'));
            queryClient.invalidateQueries({ queryKey: ['aiConfigs'] });
            handleCloseDialog();
        },
        onError: () => {
            toast.error(t('settings.ai_config.failed_to_create_ai_config'));
        }
    });

    const updateConfigMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: AIConfigCreate }) => aiConfigApi.updateAIConfig(id, data),
        onSuccess: () => {
            toast.success(t('settings.ai_config.ai_config_updated'));
            queryClient.invalidateQueries({ queryKey: ['aiConfigs'] });
            handleCloseDialog();
        },
        onError: () => {
            toast.error(t('settings.ai_config.failed_to_update_ai_config'));
        }
    });

    const deleteConfigMutation = useMutation({
        mutationFn: (id: number) => aiConfigApi.deleteAIConfig(id),
        onSuccess: () => {
            toast.success(t('settings.ai_config.ai_config_deleted'));
            queryClient.invalidateQueries({ queryKey: ['aiConfigs'] });
        },
        onError: () => {
            toast.error(t('settings.ai_config.failed_to_delete_ai_config'));
        }
    });

    const saveReviewerSettingsMutation = useMutation({
        mutationFn: async () => {
            await settingsApi.updateSetting('review_worker_enabled', reviewWorkerEnabled);
            await settingsApi.updateSetting('reviewer_ai_config', reviewerConfig);
        },
        onSuccess: () => {
            toast.success("Reviewer settings updated successfully");
        },
        onError: () => {
            toast.error("Failed to update reviewer settings");
        }
    });

    const testConfigMutation = useMutation({
        mutationFn: (data: Partial<AIConfigCreate>) => aiConfigApi.testAIConfigWithOverrides({
            provider_name: data.provider_name!,
            provider_url: data.provider_url,
            api_key: data.api_key,
            model_name: data.model_name!,
        }),
        onSuccess: (result) => {
            setTestResult({
                success: result.success,
                message: result.message || (result.success ? "Connection successful" : "Connection failed")
            });
        },
        onError: (error) => {
            setTestResult({
                success: false,
                message: error instanceof Error ? error.message : "Unknown error during testing"
            });
        }
    });

    const handleAIAssistantToggle = (checked: boolean) => {
        if (!isAdmin) return;
        toggleAssistantMutation.mutate(checked);
    };

    const handleOpenCreateDialog = () => {
        setEditingAIConfig(null);
        setNewAIConfig({
            provider_name: "openai",
            provider_url: "",
            api_key: "",
            model_name: "gpt-4",
            is_active: true,
            is_default: false,
            ocr_enabled: false,
        });
        setTestResult(null);
        setShowAIConfigDialog(true);
    };

    const handleOpenEditDialog = (config: AIConfig) => {
        setEditingAIConfig(config);
        setNewAIConfig({
            provider_name: config.provider_name,
            provider_url: config.provider_url,
            api_key: "", // Don't show existing API key for security
            model_name: config.model_name,
            is_active: config.is_active,
            is_default: config.is_default,
            ocr_enabled: config.ocr_enabled,
        });
        setTestResult(null);
        setShowAIConfigDialog(true);
    };

    const handleCloseDialog = () => {
        setShowAIConfigDialog(false);
        setEditingAIConfig(null);
        setTestResult(null);
    };

    const handleAIConfigChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setNewAIConfig(prev => ({ ...prev, [name]: value }));
    };

    const handleAIConfigToggleChange = (field: string, value: any) => {
        setNewAIConfig(prev => ({ ...prev, [field]: value }));
    };

    const handleTestConfig = () => {
        testConfigMutation.mutate(newAIConfig);
    };

    const handleSaveConfig = () => {
        if (editingAIConfig) {
            updateConfigMutation.mutate({ id: editingAIConfig.id, data: newAIConfig });
        } else {
            createConfigMutation.mutate(newAIConfig);
        }
    };

    const handleDeleteClick = (id: number) => {
        setConfigToDelete(id);
        setIsDeleteDialogOpen(true);
    };

    const confirmDelete = () => {
        if (configToDelete !== null) {
            deleteConfigMutation.mutate(configToDelete, {
                onSettled: () => {
                    setIsDeleteDialogOpen(false);
                    setConfigToDelete(null);
                }
            });
        }
    };

    const handleTriggerFullReview = async () => {
        if (!window.confirm("This will reset the review status for ALL invoices, expenses, and bank statements. The review worker will re-process everything. Are you sure?")) {
            return;
        }

        setIsTriggeringReview(true);
        try {
            const result = await aiConfigApi.triggerFullReview();
            toast.success(result.message);
        } catch (error: any) {
            toast.error(error?.message || "Failed to trigger full system review");
        } finally {
            setIsTriggeringReview(false);
        }
    };

    const providerRequiresApiKey = (providerName: string): boolean => {
        const provider = supportedProviders[providerName];
        return provider ? provider.requires_api_key : true;
    };

    return (
        <>
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="flex items-center gap-2">
                        <CpuIcon className="w-5 h-5 text-primary" />
                        {t('settings.ai_config.ai_configuration')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-8">
                    {/* AI Assistant Toggle */}
                    <div className="p-6 bg-muted/20 rounded-xl border border-border/50">
                        <div className="flex items-center justify-between gap-4">
                            <div className="space-y-1">
                                <Label htmlFor="ai_assistant" className="text-base font-semibold">{t('settings.ai_config.ai_assistant')}</Label>
                                <p className="text-sm text-muted-foreground">{t('settings.ai_config.ai_assistant_description')}</p>
                            </div>
                            <Switch
                                id="ai_assistant"
                                checked={aiAssistantEnabled}
                                onCheckedChange={handleAIAssistantToggle}
                                disabled={(!isFeatureEnabled('ai_chat') && !aiAssistantEnabled) || toggleAssistantMutation.isPending}
                            />
                        </div>
                    </div>

                    {/* AI Provider Configurations */}
                    <div className="space-y-6">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div>
                                <h3 className="text-lg font-semibold flex items-center gap-2">
                                    {t('settings.ai_config.ai_provider_configurations')}
                                </h3>
                                <p className="text-sm text-muted-foreground">{t('settings.ai_config.ai_provider_configurations_description')}</p>
                            </div>
                            <ProfessionalButton onClick={handleOpenCreateDialog} leftIcon={<Plus className="h-4 w-4" />}>
                                {t('settings.ai_config.add_provider')}
                            </ProfessionalButton>
                        </div>

                        {isLoadingConfigs ? (
                            <div className="flex justify-center py-12">
                                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                            </div>
                        ) : configs.length === 0 ? (
                            <div className="text-center py-12 bg-muted/10 rounded-xl border-2 border-dashed border-border">
                                <CpuIcon className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
                                <p className="text-muted-foreground font-medium">{t('settings.ai_config.no_ai_configurations')}</p>
                                <p className="text-sm text-muted-foreground mt-2">
                                    {t('settings.ai_config.add_ai_providers_hint')}
                                </p>
                            </div>
                        ) : (
                            <div className="rounded-xl border border-border/50 overflow-hidden">
                                <ProfessionalTable>
                                    <ProfessionalTableHeader>
                                        <ProfessionalTableRow>
                                            <ProfessionalTableHead>{t('settings.ai_config.provider')}</ProfessionalTableHead>
                                            <ProfessionalTableHead>{t('settings.ai_config.model')}</ProfessionalTableHead>
                                            <ProfessionalTableHead>{t('settings.status')}</ProfessionalTableHead>
                                            <ProfessionalTableHead className="text-right">{t('common.actions')}</ProfessionalTableHead>
                                        </ProfessionalTableRow>
                                    </ProfessionalTableHeader>
                                    <ProfessionalTableBody>
                                        {configs.map((config: AIConfig) => (
                                            <ProfessionalTableRow key={config.id} interactive>
                                                <ProfessionalTableCell className="font-medium">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                                                            <CpuIcon className="w-4 h-4 text-primary" />
                                                        </div>
                                                        <div className="flex flex-col">
                                                            <span>{config.provider_name}</span>
                                                            {config.is_default && (
                                                                <Badge variant="secondary" className="w-fit text-[10px] h-4 px-1.5 mt-1">Default</Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                </ProfessionalTableCell>
                                                <ProfessionalTableCell>
                                                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{config.model_name}</code>
                                                </ProfessionalTableCell>
                                                <ProfessionalTableCell>
                                                    <StatusBadge status={config.is_active ? "success" : "neutral"}>
                                                        {config.is_active ? t('common.active') : t('common.inactive')}
                                                    </StatusBadge>
                                                </ProfessionalTableCell>
                                                <ProfessionalTableCell className="text-right">
                                                    <div className="flex justify-end gap-2">
                                                        <ProfessionalButton
                                                            variant="ghost"
                                                            size="icon-sm"
                                                            onClick={() => handleOpenEditDialog(config)}
                                                        >
                                                            <Edit className="h-4 w-4" />
                                                        </ProfessionalButton>
                                                        <ProfessionalButton
                                                            variant="ghost"
                                                            size="icon-sm"
                                                            className="text-destructive hover:bg-destructive/10"
                                                            onClick={() => handleDeleteClick(config.id)}
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </ProfessionalButton>
                                                    </div>
                                                </ProfessionalTableCell>
                                            </ProfessionalTableRow>
                                        ))}
                                    </ProfessionalTableBody>
                                </ProfessionalTable>
                            </div>
                        )}
                    </div>

                    {/* Reviewer Settings Section */}
                    <div className="space-y-6 pt-8 border-t">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div>
                                <h3 className="text-lg font-semibold flex items-center gap-2">
                                    <ShieldCheck className="w-5 h-5 text-primary" />
                                    Review Worker Settings
                                </h3>
                                <p className="text-sm text-muted-foreground">Automatically review processed documents for potential inaccuracies.</p>
                            </div>
                        </div>

                        <div className="p-6 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-100 dark:border-yellow-900/30 rounded-xl">
                            <div className="flex items-start gap-3">
                                <Zap className="w-5 h-5 text-yellow-600 mt-0.5" />
                                <div className="space-y-1">
                                    <h4 className="font-semibold text-yellow-800 dark:text-yellow-400">AI Usage Notice</h4>
                                    <p className="text-sm text-yellow-700 dark:text-yellow-500/80">
                                        Enabling the Review Worker will perform a secondary AI analysis on every document, which will double your AI costs for processing.
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center justify-between p-6 bg-muted/20 rounded-xl border border-border/50">
                            <div className="space-y-1">
                                <Label htmlFor="review_worker" className="text-base font-semibold">Enable Review Worker</Label>
                                <p className="text-sm text-muted-foreground">Background AI agent will verify extraction results.</p>
                            </div>
                            <Switch
                                id="review_worker"
                                checked={reviewWorkerEnabled}
                                onCheckedChange={setReviewWorkerEnabled}
                            />
                        </div>

                        {reviewWorkerEnabled && (
                            <div className="space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                                <div className="flex items-center space-x-2">
                                    <Switch
                                        id="use_custom_reviewer"
                                        checked={reviewerConfig.use_custom_config}
                                        onCheckedChange={(checked) => setReviewerConfig((prev: any) => ({ ...prev, use_custom_config: checked }))}
                                    />
                                    <Label htmlFor="use_custom_reviewer">Use Custom Reviewer AI Configuration</Label>
                                </div>

                                {!reviewerConfig.use_custom_config ? (
                                    <div className="p-4 bg-muted/30 rounded-lg border border-border/50 text-sm text-muted-foreground italic">
                                        The reviewer will use the system default AI provider and model.
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-muted/30 rounded-xl border border-border/50">
                                        <div className="space-y-2">
                                            <Label>Reviewer Provider</Label>
                                            <Select
                                                value={reviewerConfig.config.provider_name}
                                                onValueChange={(value) => setReviewerConfig((prev: any) => ({
                                                    ...prev,
                                                    config: { ...prev.config, provider_name: value }
                                                }))}
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select provider" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {(Object.values(supportedProviders) as AIProviderInfo[]).map((p) => (
                                                        <SelectItem key={p.name} value={p.name}>
                                                            {p.display_name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Model Name</Label>
                                            <Input
                                                value={reviewerConfig.config.model_name}
                                                onChange={(e) => setReviewerConfig((prev: any) => ({
                                                    ...prev,
                                                    config: { ...prev.config, model_name: e.target.value }
                                                }))}
                                                placeholder="e.g. gpt-4"
                                            />
                                        </div>
                                        <div className="space-y-2 md:col-span-2">
                                            <Label>API Key (Optional override)</Label>
                                            <Input
                                                type="password"
                                                value={reviewerConfig.config.api_key}
                                                onChange={(e) => setReviewerConfig((prev: any) => ({
                                                    ...prev,
                                                    config: { ...prev.config, api_key: e.target.value }
                                                }))}
                                                placeholder="Leave blank to use provider key"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="flex justify-end gap-3">
                            <ProfessionalButton
                                variant="outline"
                                onClick={handleTriggerFullReview}
                                disabled={isTriggeringReview}
                                loading={isTriggeringReview}
                                leftIcon={<RotateCcw className="h-4 w-4" />}
                            >
                                Trigger Full System Review
                            </ProfessionalButton>
                            <ProfessionalButton
                                onClick={() => saveReviewerSettingsMutation.mutate()}
                                disabled={saveReviewerSettingsMutation.isPending}
                                loading={saveReviewerSettingsMutation.isPending}
                            >
                                Save Reviewer Settings
                            </ProfessionalButton>
                        </div>
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* AI Provider Config Dialog */}
            <Dialog open={showAIConfigDialog} onOpenChange={handleCloseDialog}>
                <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>
                            {editingAIConfig ? t('settings.ai_config.edit_ai_configuration') : t('settings.ai_config.add_ai_configuration')}
                        </DialogTitle>
                    </DialogHeader>

                    <div className="space-y-6 py-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <Label htmlFor="provider_name">{t('settings.ai_config.provider')}</Label>
                                <Select
                                    value={newAIConfig.provider_name}
                                    onValueChange={(value) => handleAIConfigToggleChange('provider_name', value as any)}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {(Object.values(supportedProviders) as AIProviderInfo[]).map((p) => (
                                            <SelectItem key={p.name} value={p.name}>
                                                {p.display_name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="model_name">{t('settings.ai_config.model')}</Label>
                                <Input
                                    id="model_name"
                                    name="model_name"
                                    value={newAIConfig.model_name}
                                    onChange={handleAIConfigChange}
                                    placeholder={
                                        newAIConfig.provider_name === "openai" ? t('settings.ai_config.openai_model_example') :
                                            newAIConfig.provider_name === "openrouter" ? "openai/gpt-4, anthropic/claude-3-sonnet" :
                                                newAIConfig.provider_name === "ollama" ? t('settings.ai_config.ollama_model_example') :
                                                    newAIConfig.provider_name === "anthropic" ? t('settings.ai_config.anthropic_model_example') :
                                                        newAIConfig.provider_name === "google" ? t('settings.ai_config.google_model_example') :
                                                            t('settings.ai_config.model_name_example')
                                    }
                                />
                                <p className="text-sm text-muted-foreground">
                                    {newAIConfig.provider_name === "openai" && t('settings.ai_config.openai_model_hint')}
                                    {newAIConfig.provider_name === "openrouter" && "Access 100+ models via OpenRouter. Use format: provider/model (e.g., openai/gpt-4, anthropic/claude-3-sonnet)"}
                                    {newAIConfig.provider_name === "ollama" && t('settings.ai_config.ollama_model_hint')}
                                    {newAIConfig.provider_name === "anthropic" && t('settings.ai_config.anthropic_model_hint')}
                                    {newAIConfig.provider_name === "google" && t('settings.ai_config.google_model_hint')}
                                    {newAIConfig.provider_name === "custom" && t('settings.ai_config.custom_model_hint')}
                                </p>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="provider_url">{t('settings.ai_config.provider_url_optional')}</Label>
                            <Input
                                id="provider_url"
                                name="provider_url"
                                value={newAIConfig.provider_url || ""}
                                onChange={handleAIConfigChange}
                                placeholder={t('settings.ai_config.provider_url_placeholder')}
                            />
                            <p className="text-sm text-muted-foreground">
                                {t('settings.ai_config.leave_empty_for_default_endpoints')}
                            </p>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="api_key">
                                {t('settings.ai_config.api_key')}
                                {!providerRequiresApiKey(newAIConfig.provider_name) && (
                                    <span className="text-sm text-muted-foreground ml-1">(Optional)</span>
                                )}
                            </Label>
                            <Input
                                id="api_key"
                                name="api_key"
                                type="password"
                                value={newAIConfig.api_key || ""}
                                onChange={handleAIConfigChange}
                                placeholder={
                                    providerRequiresApiKey(newAIConfig.provider_name)
                                        ? t('settings.ai_config.enter_api_key')
                                        : "Optional - leave empty for local providers"
                                }
                            />
                        </div>

                        <div className="flex flex-wrap items-center gap-6">
                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="is_active"
                                    checked={newAIConfig.is_active}
                                    onCheckedChange={(checked) => handleAIConfigToggleChange('is_active', checked)}
                                />
                                <Label htmlFor="is_active">{t('settings.ai_config.active')}</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="is_default"
                                    checked={newAIConfig.is_default}
                                    onCheckedChange={(checked) => handleAIConfigToggleChange('is_default', checked)}
                                />
                                <Label htmlFor="is_default">{t('settings.ai_config.default_provider')}</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="ocr_enabled"
                                    checked={newAIConfig.ocr_enabled || false}
                                    onCheckedChange={(checked) => handleAIConfigToggleChange('ocr_enabled', checked)}
                                />
                                <Label htmlFor="ocr_enabled">OCR Enabled</Label>
                            </div>
                        </div>

                        {/* Test Result Display */}
                        {testResult && (
                            <div className={`p-3 rounded-lg border ${testResult.success
                                ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-900/20 dark:border-green-800/50 dark:text-green-400'
                                : 'bg-red-50 border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800/50 dark:text-red-400'
                                }`}>
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${testResult.success ? 'bg-green-500' : 'bg-red-500'}`}></div>
                                    <span className="font-medium">
                                        {testResult.success ? 'Test Successful' : 'Test Failed'}
                                    </span>
                                </div>
                                <p className="text-sm mt-1">{testResult.message}</p>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0">
                        <Button variant="outline" onClick={handleCloseDialog}>
                            {t('settings.ai_config.cancel')}
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleTestConfig}
                            disabled={testConfigMutation.isPending || !newAIConfig.model_name || (providerRequiresApiKey(newAIConfig.provider_name) && !newAIConfig.api_key)}
                        >
                            {testConfigMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t('common.loading')}
                                </>
                            ) : (
                                t('settings.ai_config.test')
                            )}
                        </Button>
                        <Button
                            onClick={handleSaveConfig}
                            disabled={createConfigMutation.isPending || updateConfigMutation.isPending}
                        >
                            {createConfigMutation.isPending || updateConfigMutation.isPending ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                editingAIConfig ? t('settings.update') : t('settings.ai_config.create')
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation */}
            <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{t('settings.ai_config.delete_ai_configuration')}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {t('settings.ai_config.confirm_delete_ai_config')}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmDelete}
                            disabled={deleteConfigMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteConfigMutation.isPending ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                t('common.delete')
                            )}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
};
