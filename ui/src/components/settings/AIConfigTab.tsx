import React from "react";
import { useTranslation } from "react-i18next";
import { Cpu, Plus, Edit, Trash2, Loader2, ShieldCheck } from "lucide-react";
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
import { AIConfig, AIConfigCreate, AIProviderInfo } from "@/lib/api";

interface AIConfigTabProps {
    aiAssistantEnabled: boolean;
    aiConfigs: AIConfig[];
    loadingAiConfigs: boolean;
    showAIConfigDialog: boolean;
    editingAIConfig: AIConfig | null;
    supportedProviders: Record<string, AIProviderInfo>;
    newAIConfig: AIConfigCreate;
    testingNewConfig: boolean;
    testResult: { success: boolean; message: string } | null;
    isFeatureEnabled: (feature: string) => boolean;
    onAIAssistantToggle: (checked: boolean) => void;
    onOpenCreateDialog: () => void;
    onOpenEditDialog: (config: AIConfig) => void;
    onDeleteAIConfig: (id: number) => void;
    onCloseDialog: () => void;
    onAIConfigChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onAIConfigToggleChange: (field: string, checked: boolean) => void;
    onTestConfig: () => void;
    onCreateConfig: () => void;
    onUpdateConfig: () => void;
}

export const AIConfigTab: React.FC<AIConfigTabProps> = ({
    aiAssistantEnabled,
    aiConfigs,
    loadingAiConfigs,
    showAIConfigDialog,
    editingAIConfig,
    supportedProviders,
    newAIConfig,
    testingNewConfig,
    testResult,
    isFeatureEnabled,
    onAIAssistantToggle,
    onOpenCreateDialog,
    onOpenEditDialog,
    onDeleteAIConfig,
    onCloseDialog,
    onAIConfigChange,
    onAIConfigToggleChange,
    onTestConfig,
    onCreateConfig,
    onUpdateConfig,
}) => {
    const { t } = useTranslation();
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = React.useState(false);
    const [configToDelete, setConfigToDelete] = React.useState<number | null>(null);

    const handleDeleteClick = (id: number) => {
        setConfigToDelete(id);
        setIsDeleteDialogOpen(true);
    };

    const confirmDelete = () => {
        if (configToDelete !== null) {
            onDeleteAIConfig(configToDelete);
            setIsDeleteDialogOpen(false);
            setConfigToDelete(null);
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
                        <Cpu className="w-5 h-5 text-primary" />
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
                                {!isFeatureEnabled('ai_chat') && (
                                    <div className="flex items-center gap-2 mt-2 text-xs font-medium text-amber-600 dark:text-amber-400">
                                        <ShieldCheck className="w-3.5 h-3.5" />
                                        {t('settings.ai_config.ai_assistant_license_required', 'AI Assistant requires a valid license. Please upgrade your plan.')}
                                    </div>
                                )}
                            </div>
                            <Switch
                                id="ai_assistant"
                                checked={aiAssistantEnabled}
                                onCheckedChange={onAIAssistantToggle}
                                disabled={!isFeatureEnabled('ai_chat') && !aiAssistantEnabled}
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
                            <ProfessionalButton onClick={onOpenCreateDialog} leftIcon={<Plus className="h-4 w-4" />}>
                                {t('settings.ai_config.add_provider')}
                            </ProfessionalButton>
                        </div>

                        {loadingAiConfigs ? (
                            <div className="flex justify-center py-12">
                                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                            </div>
                        ) : aiConfigs.length === 0 ? (
                            <div className="text-center py-12 bg-muted/10 rounded-xl border-2 border-dashed border-border">
                                <Cpu className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-20" />
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
                                        {aiConfigs.map((config) => (
                                            <ProfessionalTableRow key={config.id} interactive>
                                                <ProfessionalTableCell className="font-medium">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                                                            <Cpu className="w-4 h-4 text-primary" />
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
                                                            onClick={() => onOpenEditDialog(config)}
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
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* AI Provider Config Dialog */}
            <Dialog open={showAIConfigDialog} onOpenChange={onCloseDialog}>
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
                                    onValueChange={(value) => onAIConfigToggleChange('provider_name', value as any)}
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
                                    onChange={onAIConfigChange}
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
                                onChange={onAIConfigChange}
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
                                onChange={onAIConfigChange}
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
                                    onCheckedChange={(checked) => onAIConfigToggleChange('is_active', checked)}
                                />
                                <Label htmlFor="is_active">{t('settings.ai_config.active')}</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="is_default"
                                    checked={newAIConfig.is_default}
                                    onCheckedChange={(checked) => onAIConfigToggleChange('is_default', checked)}
                                />
                                <Label htmlFor="is_default">{t('settings.ai_config.default_provider')}</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="tested"
                                    checked={newAIConfig.tested || false}
                                    onCheckedChange={(checked) => onAIConfigToggleChange('tested', checked)}
                                />
                                <Label htmlFor="tested">{t('settings.ai_config.mark_as_tested')}</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                                <Switch
                                    id="ocr_enabled"
                                    checked={newAIConfig.ocr_enabled || false}
                                    onCheckedChange={(checked) => onAIConfigToggleChange('ocr_enabled', checked)}
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
                        <Button variant="outline" onClick={onCloseDialog}>
                            {t('settings.ai_config.cancel')}
                        </Button>
                        <Button
                            variant="outline"
                            onClick={onTestConfig}
                            disabled={testingNewConfig || !newAIConfig.model_name || (providerRequiresApiKey(newAIConfig.provider_name) && !newAIConfig.api_key)}
                        >
                            {testingNewConfig ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t('common.loading')}
                                </>
                            ) : (
                                t('settings.ai_config.test')
                            )}
                        </Button>
                        <Button
                            onClick={editingAIConfig ? onUpdateConfig : onCreateConfig}
                        >
                            {editingAIConfig ? t('settings.update') : t('settings.ai_config.create')}
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
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {t('common.delete')}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
};
