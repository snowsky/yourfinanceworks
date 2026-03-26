import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useTranslation } from "react-i18next";
import { Cpu as CpuIcon, Plus, Edit, Trash2, Loader2, ShieldCheck, Shield, Zap, RotateCcw, Wand, X, PieChart, FileText, Receipt, Landmark, CheckCircle, Clock, AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
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
    const [showReviewProgress, setShowReviewProgress] = useState(false);
    const [reviewProgress, setReviewProgress] = useState<any>(null);
    const [isLoadingProgress, setIsLoadingProgress] = useState(false);
    const [showReviewConfirmation, setShowReviewConfirmation] = useState(false);
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
        mutationFn: (data: Partial<AIConfigCreate> & { _existingConfigId?: number }) => {
            const { _existingConfigId, ...configData } = data;
            if (_existingConfigId && !configData.api_key) {
                // Editing an existing config without a new API key — use the stored key via ID
                return aiConfigApi.testAIConfig(_existingConfigId);
            }
            return aiConfigApi.testAIConfigWithOverrides({
                provider_name: configData.provider_name!,
                provider_url: configData.provider_url,
                api_key: configData.api_key,
                model_name: configData.model_name!,
            });
        },
        onSuccess: (result) => {
            setTestResult({
                success: result.success,
                message: result.message || (result.success ? "Connection successful" : "Connection failed")
            });
            if (result.success) {
                setNewAIConfig(prev => ({ ...prev, tested: true }));
            }
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
        setNewAIConfig(prev => ({ ...prev, [name]: value, tested: false }));
    };

    const handleAIConfigToggleChange = (field: string, value: any) => {
        setNewAIConfig(prev => ({ ...prev, [field]: value, tested: field === "is_active" || field === "ocr_enabled" || field === "is_default" ? prev.tested : false }));
    };

    const handleTestConfig = () => {
        testConfigMutation.mutate({
            ...newAIConfig,
            _existingConfigId: editingAIConfig?.id,
        });
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

    const handleOpenReviewProgress = async () => {
        console.log("Opening review progress modal");
        setShowReviewProgress(true);
        await fetchReviewProgress();
    };

    const confirmTriggerFullReview = async () => {
        console.log("User confirmed full review trigger");
        setShowReviewConfirmation(false);
        setIsTriggeringReview(true);

        try {
            console.log("About to call triggerFullReview API...");
            const result = await aiConfigApi.triggerFullReview();
            console.log("API Response received:", result);

            toast.success("Full system review triggered successfully!");

            // Fetch initial progress
            await fetchReviewProgress();

            // Start polling for updates
            startProgressPolling();

        } catch (error: any) {
            console.error("Error in confirmTriggerFullReview:", error);
            toast.error(error?.message || "Failed to trigger full system review");
        } finally {
            console.log("Setting isTriggeringReview to false");
            setIsTriggeringReview(false);
        }
    };

    const fetchReviewProgress = async () => {
        try {
            console.log("Fetching review progress...");
            setIsLoadingProgress(true);
            const progress = await aiConfigApi.getReviewProgress();
            console.log("Review progress:", progress);
            setReviewProgress(progress);
        } catch (error) {
            console.error('Failed to fetch review progress:', error);
            toast.error("Failed to fetch review progress");
        } finally {
            setIsLoadingProgress(false);
        }
    };

    const handleCancelFullReview = async () => {
        try {
            setIsTriggeringReview(true);
            const result = await aiConfigApi.cancelFullReview();
            toast.success(result.message);
            setShowReviewProgress(false);
            setReviewProgress(null);
            await fetchReviewProgress();
        } catch (error: any) {
            console.error("Error cancelling full review:", error);
            toast.error(error?.message || "Failed to cancel full system review");
        } finally {
            setIsTriggeringReview(false);
        }
    };

    const startProgressPolling = () => {
        console.log("Starting progress polling...");
        const pollInterval = setInterval(async () => {
            try {
                const progress = await aiConfigApi.getReviewProgress();
                console.log("Polled progress:", progress);
                setReviewProgress(progress);

                // Stop polling if all items are completed
                if (progress.overall_progress_percent === 100) {
                    clearInterval(pollInterval);
                    toast.success("Full system review completed!");
                    // Clear progress after a short delay so user sees completion
                    setTimeout(() => setReviewProgress(null), 2000);
                }
            } catch (error) {
                console.error('Error polling review progress:', error);
            }
        }, 2000); // Poll every 2 seconds

        // Auto-stop polling after 30 minutes
        setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);
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
                                    {t('settings.ai_config.review_worker_settings')}
                                </h3>
                                <p className="text-sm text-muted-foreground">{t('settings.ai_config.review_worker_description')}</p>
                            </div>
                        </div>

                        <div className="p-6 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-100 dark:border-yellow-900/30 rounded-xl">
                            <div className="flex items-start gap-3">
                                <Zap className="w-5 h-5 text-yellow-600 mt-0.5" />
                                <div className="space-y-1">
                                    <h4 className="font-semibold text-yellow-800 dark:text-yellow-400">{t('settings.ai_config.ai_usage_notice')}</h4>
                                    <p className="text-sm text-yellow-700 dark:text-yellow-500/80">
                                        {t('settings.ai_config.ai_usage_notice_description')}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center justify-between p-6 bg-muted/20 rounded-xl border border-border/50">
                            <div className="space-y-1">
                                <Label htmlFor="review_worker" className="text-base font-semibold">{t('settings.ai_config.enable_review_worker')}</Label>
                                <p className="text-sm text-muted-foreground">{t('settings.ai_config.enable_review_worker_description')}</p>
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
                                    <Label htmlFor="use_custom_reviewer">{t('settings.ai_config.use_custom_reviewer_ai_configuration')}</Label>
                                </div>

                                {reviewerConfig.use_custom_config && (
                                    <div className="flex items-center space-x-2">
                                        <Switch
                                            id="use_for_extraction"
                                            checked={reviewerConfig.use_for_extraction}
                                            onCheckedChange={(checked) => setReviewerConfig((prev: any) => ({ ...prev, use_for_extraction: checked }))}
                                        />
                                        <Label htmlFor="use_for_extraction" className="flex items-center gap-1.5">
                                            {t('settings.ai_config.use_reviewer_model_for_extraction_pass')}
                                            <Badge variant="outline" className="text-[10px] h-4 px-1.5 font-normal">Pass 1</Badge>
                                        </Label>
                                    </div>
                                )}

                                {!reviewerConfig.use_custom_config ? (
                                    <div className="p-4 bg-muted/30 rounded-lg border border-border/50 text-sm text-muted-foreground italic">
                                        The reviewer will use the system default AI provider and model.
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-muted/30 rounded-xl border border-border/50">
                                        <div className="space-y-2">
                                            <Label>{t('settings.ai_config.reviewer_provider')}</Label>
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
                                            <Label>{t('settings.ai_config.reviewer_model_name')}</Label>
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
                                            <Label>{t('settings.ai_config.reviewer_api_key_optional_override')}</Label>
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
                                onClick={handleOpenReviewProgress}
                                disabled={isTriggeringReview}
                                leftIcon={<RotateCcw className="h-4 w-4" />}
                            >
                                {t('settings.ai_config.view_review_progress')}
                            </ProfessionalButton>
                            <ProfessionalButton
                                onClick={() => saveReviewerSettingsMutation.mutate()}
                                disabled={saveReviewerSettingsMutation.isPending}
                                loading={saveReviewerSettingsMutation.isPending}
                            >
                                {t('settings.ai_config.save_reviewer_settings')}
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
                            disabled={testConfigMutation.isPending || !newAIConfig.model_name || (providerRequiresApiKey(newAIConfig.provider_name) && !newAIConfig.api_key && !editingAIConfig)}
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

            {/* Review Progress Modal */}
            <Dialog open={showReviewProgress} onOpenChange={setShowReviewProgress}>
                <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden border-none shadow-2xl bg-background/95 backdrop-blur-xl">
                    <DialogHeader className="p-6 pb-4 border-b bg-muted/10">
                        <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                                <RotateCcw className={cn("h-5 w-5 text-primary", isLoadingProgress && "animate-spin")} />
                            </div>
                            <div>
                                <DialogTitle className="text-xl font-bold tracking-tight">Full System Review Progress</DialogTitle>
                                <DialogDescription className="text-muted-foreground mt-1">
                                    AI is re-analyzing all documents in the background to detect discrepancies.
                                </DialogDescription>
                            </div>
                        </div>
                    </DialogHeader>

                    {isLoadingProgress && !reviewProgress ? (
                        <div className="flex flex-col items-center justify-center py-24 space-y-4">
                            <Loader2 className="h-12 w-12 animate-spin text-primary/50" />
                            <p className="text-muted-foreground font-medium">Connecting to review worker...</p>
                        </div>
                    ) : reviewProgress ? (
                        <div className="p-6 space-y-8 bg-muted/5 flex-1 overflow-y-auto">

                            {/* Hero Progress Section */}
                            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/90 to-blue-600 p-8 text-primary-foreground shadow-lg">
                                <div className="absolute top-0 right-0 -mt-10 -mr-10 h-64 w-64 rounded-full bg-white/10 blur-3xl opacity-50 pointer-events-none"></div>
                                <div className="absolute bottom-0 left-0 -mb-10 -ml-10 h-64 w-64 rounded-full bg-black/10 blur-3xl opacity-50 pointer-events-none"></div>

                                <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-8">
                                    <div className="flex-1 space-y-4 w-full">
                                        <div className="flex items-center justify-between">
                                            <div className="space-y-1">
                                                <h3 className="text-2xl font-bold">Overall Completion</h3>
                                                <p className="text-primary-foreground/80 font-medium">
                                                    {reviewProgress.overall_progress_percent === 100 
                                                        ? "All reviews completed successfully" 
                                                        : "Processing documents across all categories..."}
                                                </p>
                                            </div>
                                            <div className="text-4xl font-black tabular-nums tracking-tight">
                                                {Math.round(reviewProgress.overall_progress_percent)}%
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <div className="h-4 w-full overflow-hidden rounded-full bg-black/20 backdrop-blur-sm">
                                                <div 
                                                    className="h-full bg-white shadow-[0_0_10px_rgba(255,255,255,0.5)] transition-all duration-1000 ease-out"
                                                    style={{ width: `${reviewProgress.overall_progress_percent}%` }}
                                                />
                                            </div>
                                            <div className="flex justify-between text-xs font-medium text-primary-foreground/70 uppercase tracking-widest">
                                                <span>Start</span>
                                                <span>{reviewProgress.overall_progress_percent === 100 ? "Completed" : "In Progress"}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Quick Summary Circle if space permits or layout desires */}
                                    <div className="hidden md:flex flex-col items-center justify-center bg-white/10 rounded-xl p-4 backdrop-blur-md border border-white/20 min-w-[140px]">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-primary-foreground/70 mb-1">Total Items</div>
                                        <div className="text-3xl font-bold">
                                            {reviewProgress.invoices.total + reviewProgress.expenses.total + reviewProgress.statements.total}
                                        </div>
                                        <div className="text-xs text-primary-foreground/60 mt-1">Documents</div>
                                    </div>
                                </div>
                            </div>

                            {/* Detailed Stats Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                {/* Invoices Card */}
                                <div className="group rounded-xl border bg-card p-5 shadow-sm transition-all hover:shadow-md hover:border-blue-200 dark:hover:border-blue-800">
                                    <div className="mb-4 flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                                            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                                                <FileText className="h-5 w-5" />
                                            </div>
                                            <span className="font-bold">Invoices</span>
                                        </div>
                                        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/10 dark:text-blue-400 dark:border-blue-800/30">
                                            {reviewProgress.invoices.progress_percent}%
                                        </Badge>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="flex items-end justify-between">
                                            <div className="text-3xl font-bold tabular-nums text-foreground">
                                                {reviewProgress.invoices.completed}
                                                <span className="text-lg text-muted-foreground font-normal ml-1">/ {reviewProgress.invoices.total}</span>
                                            </div>
                                        </div>

                                        <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                            <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${reviewProgress.invoices.progress_percent}%` }} />
                                        </div>

                                        <div className="grid grid-cols-2 gap-2 pt-2">
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                                                <span>Reviewed: <span className="font-semibold text-foreground">{reviewProgress.invoices.stats.reviewed}</span></span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <Clock className="h-3.5 w-3.5 text-amber-500" />
                                                <span>Pending: <span className="font-semibold text-foreground">{reviewProgress.invoices.stats.pending}</span></span>
                                            </div>
                                            {(reviewProgress.invoices.stats.failed > 0) && (
                                                 <div className="col-span-2 flex items-center gap-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/10 p-2 rounded border border-red-100 dark:border-red-900/30">
                                                    <AlertTriangle className="h-3.5 w-3.5" />
                                                    <span>Failed: <span className="font-semibold">{reviewProgress.invoices.stats.failed}</span></span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Expenses Card */}
                                <div className="group rounded-xl border bg-card p-5 shadow-sm transition-all hover:shadow-md hover:border-green-200 dark:hover:border-green-800">
                                    <div className="mb-4 flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                                            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                                                <Receipt className="h-5 w-5" />
                                            </div>
                                            <span className="font-bold">Expenses</span>
                                        </div>
                                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 dark:bg-green-900/10 dark:text-green-400 dark:border-green-800/30">
                                            {reviewProgress.expenses.progress_percent}%
                                        </Badge>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="flex items-end justify-between">
                                            <div className="text-3xl font-bold tabular-nums text-foreground">
                                                {reviewProgress.expenses.completed}
                                                <span className="text-lg text-muted-foreground font-normal ml-1">/ {reviewProgress.expenses.total}</span>
                                            </div>
                                        </div>

                                        <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                            <div className="h-full bg-green-500 rounded-full transition-all duration-500" style={{ width: `${reviewProgress.expenses.progress_percent}%` }} />
                                        </div>

                                        <div className="grid grid-cols-2 gap-2 pt-2">
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                                                <span>Reviewed: <span className="font-semibold text-foreground">{reviewProgress.expenses.stats.reviewed}</span></span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <Clock className="h-3.5 w-3.5 text-amber-500" />
                                                <span>Pending: <span className="font-semibold text-foreground">{reviewProgress.expenses.stats.pending}</span></span>
                                            </div>
                                            {(reviewProgress.expenses.stats.failed > 0) && (
                                                 <div className="col-span-2 flex items-center gap-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/10 p-2 rounded border border-red-100 dark:border-red-900/30">
                                                    <AlertTriangle className="h-3.5 w-3.5" />
                                                    <span>Failed: <span className="font-semibold">{reviewProgress.expenses.stats.failed}</span></span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Bank Statements Card */}
                                <div className="group rounded-xl border bg-card p-5 shadow-sm transition-all hover:shadow-md hover:border-purple-200 dark:hover:border-purple-800">
                                    <div className="mb-4 flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-purple-600 dark:text-purple-400">
                                            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                                                <Landmark className="h-5 w-5" />
                                            </div>
                                            <span className="font-bold">Statements</span>
                                        </div>
                                        <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/10 dark:text-purple-400 dark:border-purple-800/30">
                                            {reviewProgress.statements.progress_percent}%
                                        </Badge>
                                    </div>

                                    <div className="space-y-4">
                                        <div className="flex items-end justify-between">
                                            <div className="text-3xl font-bold tabular-nums text-foreground">
                                                {reviewProgress.statements.completed}
                                                <span className="text-lg text-muted-foreground font-normal ml-1">/ {reviewProgress.statements.total}</span>
                                            </div>
                                        </div>

                                        <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                            <div className="h-full bg-purple-500 rounded-full transition-all duration-500" style={{ width: `${reviewProgress.statements.progress_percent}%` }} />
                                        </div>

                                        <div className="grid grid-cols-2 gap-2 pt-2">
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                                                <span>Reviewed: <span className="font-semibold text-foreground">{reviewProgress.statements.stats.reviewed}</span></span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                                                <Clock className="h-3.5 w-3.5 text-amber-500" />
                                                <span>Pending: <span className="font-semibold text-foreground">{reviewProgress.statements.stats.pending}</span></span>
                                            </div>
                                            {(reviewProgress.statements.stats.failed > 0) && (
                                                 <div className="col-span-2 flex items-center gap-2 text-xs text-red-600 bg-red-50 dark:bg-red-900/10 p-2 rounded border border-red-100 dark:border-red-900/30">
                                                    <AlertTriangle className="h-3.5 w-3.5" />
                                                    <span>Failed: <span className="font-semibold">{reviewProgress.statements.stats.failed}</span></span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-start gap-3 p-4 bg-muted/50 rounded-lg border border-border/50 text-sm text-muted-foreground">
                                <RotateCcw className="h-4 w-4 mt-0.5 animate-spin-slow" />
                                <div className="space-y-1">
                                    <p className="font-medium text-foreground">Live Updates Active</p>
                                    <p>The system is automatically polling for updates every 2 seconds. You can close this modal and the review process will continue uninterrupted in the background.</p>
                                </div>
                            </div>
                        </div>
                    ) : null}

                    <div className="p-6 pt-4 border-t bg-muted/5">
                        <DialogFooter className="flex-col sm:flex-row gap-3 sm:justify-between items-center w-full">
                            <div className="flex gap-2 w-full sm:w-auto">
                                <Button 
                                    variant="ghost" 
                                    onClick={() => setShowReviewProgress(false)}
                                    className="flex-1 sm:flex-none"
                                >
                                    Close Monitor
                                </Button>
                                <Button 
                                    variant="outline"
                                    onClick={fetchReviewProgress} 
                                    disabled={isLoadingProgress}
                                    className="flex-1 sm:flex-none"
                                >
                                    {isLoadingProgress ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-2 h-4 w-4" />}
                                    Refresh Status
                                </Button>
                            </div>

                            <div className="flex gap-2 w-full sm:w-auto justify-end">
                                {reviewProgress && reviewProgress.overall_progress_percent > 0 && reviewProgress.overall_progress_percent < 100 && (
                                    <Button
                                        onClick={handleCancelFullReview}
                                        disabled={isTriggeringReview}
                                        variant="destructive"
                                        className="flex-1 sm:flex-none border-destructive/20 hover:bg-destructive/90"
                                    >
                                        <X className="mr-2 h-4 w-4" />
                                        Stop Review
                                    </Button>
                                )}

                                <Button
                                    onClick={() => setShowReviewConfirmation(true)}
                                    disabled={isTriggeringReview || (reviewProgress && (reviewProgress.invoices.stats.pending > 0 || reviewProgress.expenses.stats.pending > 0 || reviewProgress.statements.stats.pending > 0))}
                                    className="flex-1 sm:flex-none bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20"
                                >
                                    {isTriggeringReview ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
                                    Trigger New Review
                                </Button>
                            </div>
                        </DialogFooter>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Full Review Confirmation Dialog */}
            <AlertDialog open={showReviewConfirmation} onOpenChange={setShowReviewConfirmation}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Trigger Full System Review?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will reset the review status for ALL invoices, expenses, and bank statements to "not_started". The review worker will re-process everything from scratch.
                            <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800/50">
                                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-400">⚠️ This action cannot be undone and may take a long time depending on your data volume.</p>
                            </div>
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmTriggerFullReview} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                            Trigger Review
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
};
