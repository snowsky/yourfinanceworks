import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
    Database, Download, Upload, Loader2, RefreshCw, Cloud, ShieldCheck, CheckCircle2, AlertCircle, Share2
} from "lucide-react";
import { toast } from "sonner";
import { settingsApi, syncApi, getErrorMessage, SyncStatus } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
    ProfessionalCard
} from "@/components/ui/professional-card";
import { useMutation } from "@tanstack/react-query";

interface DataManagementTabProps {
    isAdmin: boolean;
}

export const DataManagementTab: React.FC<DataManagementTabProps> = ({ isAdmin }) => {
    const { t } = useTranslation();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [remoteUrl, setRemoteUrl] = useState<string>(localStorage.getItem('sync_remote_url') || '');
    const [remoteApiKey, setRemoteApiKey] = useState<string>(localStorage.getItem('sync_api_key') || '');
    const [includeAttachments, setIncludeAttachments] = useState<boolean>(true);
    const [status, setStatus] = useState<SyncStatus | null>(null);
    const [isCheckingStatus, setIsCheckingStatus] = useState(false);

    const exportMutation = useMutation({
        mutationFn: () => settingsApi.exportData(),
        onSuccess: () => {
            toast.success(t('settings.data_management.data_exported_successfully'));
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, t));
        }
    });

    const checkStatusMutation = useMutation({
        mutationFn: () => syncApi.getStatus(remoteUrl, remoteApiKey),
        onSuccess: (data) => {
            setStatus(data);
            if (data.suggest_skip_attachments) {
                setIncludeAttachments(false);
            }
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, t));
        }
    });

    const pushMutation = useMutation({
        mutationFn: () => syncApi.push(remoteUrl, remoteApiKey, includeAttachments),
        onSuccess: (result) => {
            toast.success(t('settings.data_management.data_pushed_successfully'));
            checkStatusMutation.mutate();
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, t));
        }
    });

    const handleCheckStatus = () => {
        if (!remoteUrl || !remoteApiKey) return;
        localStorage.setItem('sync_remote_url', remoteUrl);
        localStorage.setItem('sync_api_key', remoteApiKey);
        checkStatusMutation.mutate();
    };

    const importMutation = useMutation({
        mutationFn: (file: File) => settingsApi.importData(file),
        onSuccess: (result) => {
            toast.success(t('settings.data_management.data_imported_successfully', { imported_counts: JSON.stringify(result.imported_counts) }));
            setSelectedFile(null);
            const fileInput = document.getElementById('import-file') as HTMLInputElement;
            if (fileInput) fileInput.value = '';
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, t));
        }
    });

    const handleExportData = () => {
        if (!isAdmin) return;
        exportMutation.mutate();
    };

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            if (!file.name.endsWith('.sqlite')) {
                toast.error(t('settings.data_management.please_select_sqlite_file'));
                return;
            }
            setSelectedFile(file);
        }
    };

    const handleImportData = () => {
        if (!isAdmin) return;
        if (!selectedFile) {
            toast.error(t('settings.data_management.please_select_file_to_import'));
            return;
        }
        importMutation.mutate(selectedFile);
    };

    return (
        <div className="space-y-6">
            {/* Data Overview Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        {t('settings.data_management.title')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.data_management.description')}
                    </p>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="text-2xl font-bold text-blue-600">📊</div>
                            <h3 className="font-medium text-blue-900 mt-2">{t('settings.data_management.complete_backup')}</h3>
                            <p className="text-sm text-blue-700 mt-1">{t('settings.data_management.complete_backup_description')}</p>
                        </div>
                        <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                            <div className="text-2xl font-bold text-green-600">🔄</div>
                            <h3 className="font-medium text-green-900 mt-2">{t('settings.data_management.easy_restore')}</h3>
                            <p className="text-sm text-green-700 mt-1">{t('settings.data_management.easy_restore_description')}</p>
                        </div>
                        <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
                            <div className="text-2xl font-bold text-purple-600">🔒</div>
                            <h3 className="font-medium text-purple-900 mt-2">{t('settings.data_management.data_control')}</h3>
                            <p className="text-sm text-purple-700 mt-1">{t('settings.data_management.data_control_description')}</p>
                        </div>
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Synchronization Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <RefreshCw className={`h-5 w-5 ${checkStatusMutation.isPending ? 'animate-spin' : ''}`} />
                            {t('settings.data_management.cloud_synchronization')}
                        </div>
                        {status && (
                            <div className="flex items-center gap-2 text-sm font-normal">
                                <span className={`flex items-center gap-1 ${status.is_in_sync ? 'text-green-600' : 'text-amber-600'}`}>
                                    {status.is_in_sync ? (
                                        <CheckCircle2 className="h-4 w-4" />
                                    ) : (
                                        <AlertCircle className="h-4 w-4" />
                                    )}
                                    {status.is_in_sync ? t('settings.data_management.synced') : t('settings.data_management.out_of_sync')}
                                </span>
                                <div className={`w-3 h-3 rounded-full ${status.is_in_sync ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]'} animate-pulse`}></div>
                            </div>
                        )}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.data_management.sync_description')}
                    </p>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="remote-url">{t('settings.data_management.remote_instance_url')}</Label>
                            <Input
                                id="remote-url"
                                placeholder="https://app.yourcloud.com"
                                value={remoteUrl}
                                onChange={(e) => setRemoteUrl(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="remote-api-key">{t('settings.data_management.remote_api_key')}</Label>
                            <Input
                                id="remote-api-key"
                                type="password"
                                placeholder="sk-..."
                                value={remoteApiKey}
                                onChange={(e) => setRemoteApiKey(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <Button 
                            variant="secondary" 
                            size="sm"
                            onClick={handleCheckStatus}
                            disabled={checkStatusMutation.isPending || !remoteUrl || !remoteApiKey}
                        >
                            {checkStatusMutation.isPending ? t('settings.data_management.checking') : t('settings.data_management.test_connection_and_check_sync')}
                        </Button>

                        {status?.suggest_skip_attachments && (
                            <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full border border-blue-100">
                                <Cloud className="h-3 w-3" />
                                {t('settings.data_management.shared_cloud_storage_detected')}
                            </div>
                        )}
                    </div>

                    <div className="space-y-6 pt-2">
                        <div className="flex items-center gap-2 font-medium">
                            <Label className="flex items-center gap-2 cursor-pointer">
                                <input 
                                    type="checkbox" 
                                    checked={includeAttachments} 
                                    onChange={(e) => setIncludeAttachments(e.target.checked)}
                                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                                {t('settings.data_management.sync_attachment_files')}
                            </Label>
                            {status?.suggest_skip_attachments && (
                                <span className="text-[10px] text-muted-foreground bg-gray-100 px-1.5 py-0.5 rounded">
                                    {t('settings.data_management.recommended_off')}
                                </span>
                            )}
                        </div>

                        <div className="flex flex-col gap-2">
                            <Button
                                onClick={() => pushMutation.mutate()}
                                disabled={pushMutation.isPending || !status}
                                className="w-full"
                            >
                                {pushMutation.isPending ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <Upload className="mr-2 h-4 w-4" />
                                )}
                                {t('settings.data_management.push_to_remote')}
                            </Button>
                            <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground px-1">
                                <span className="font-semibold">{t('settings.data_management.source')}:</span>
                                <span>{t('settings.data_management.local_instance')}</span>
                                <span className="mx-1">→</span>
                                <span className="font-semibold">{t('settings.data_management.destination')}:</span>
                                <span>{t('settings.data_management.remote_instance')}</span>
                            </div>
                        </div>

                        {status && (
                            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs space-y-1">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">{t('settings.data_management.local_fingerprint')}:</span>
                                    <code className="bg-gray-200 px-1 rounded">{status.local_fingerprint.substring(0, 12)}...</code>
                                </div>
                                {status.remote_fingerprint && (
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">{t('settings.data_management.remote_fingerprint')}:</span>
                                        <code className="bg-gray-200 px-1 rounded">{status.remote_fingerprint.substring(0, 12)}...</code>
                                    </div>
                                )}
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">{t('settings.data_management.last_check')}:</span>
                                    <span>{new Date(status.timestamp).toLocaleString()}</span>
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Import Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Upload className="h-5 w-5" />
                        {t('settings.data_management.import_data')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.data_management.import_data_description')}
                    </p>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                        <div className="flex items-start gap-3">
                            <div className="text-amber-600 text-lg">⚠️</div>
                            <div>
                                <h4 className="font-medium text-amber-900 mb-1">{t('settings.data_management.important_warning')}</h4>
                                <p className="text-sm text-amber-800">
                                    {t('settings.data_management.importing_data_warning_strong')}
                                    {t('settings.data_management.importing_data_warning_cannot_be_undone')}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <Label htmlFor="import-file" className="text-base font-medium">{t('settings.data_management.select_backup_file')}</Label>
                                <p className="text-sm text-muted-foreground mb-3">
                                    {t('settings.data_management.choose_sqlite_file')}
                                </p>
                                <Input
                                    id="import-file"
                                    type="file"
                                    accept=".sqlite"
                                    onChange={handleFileSelect}
                                    disabled={importMutation.isPending}
                                    className="cursor-pointer"
                                />
                                {selectedFile && (
                                    <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                                        <div className="flex items-center gap-2 text-sm">
                                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                            <span className="font-medium">{t('settings.data_management.file_selected')}:</span>
                                        </div>
                                        <p className="text-sm text-green-700 mt-1">
                                            {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} {t('settings.data_management.mb')})
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <h4 className="font-medium mb-3">{t('settings.data_management.import_process')}</h4>
                                <div className="space-y-2 text-sm text-muted-foreground">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.data_management.file_validation_and_structure_check')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.data_management.current_data_backup_and_removal')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.data_management.import_new_data_with_id_mapping')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.data_management.data_integrity_verification')}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="border-t pt-4">
                        <div className="flex flex-col sm:flex-row gap-3">
                            <Button
                                onClick={handleExportData}
                                disabled={exportMutation.isPending || importMutation.isPending}
                                variant="outline"
                                size="lg"
                            >
                                {exportMutation.isPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        {t('settings.data_management.creating_backup')}
                                    </>
                                ) : (
                                    <>
                                        <Download className="mr-2 h-4 w-4" />
                                        {t('settings.data_management.backup_current_data_first')}
                                    </>
                                )}
                            </Button>

                            <Button
                                onClick={handleImportData}
                                disabled={importMutation.isPending || !selectedFile}
                                variant="destructive"
                                size="lg"
                            >
                                {importMutation.isPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        {t('settings.data_management.importing_data')}
                                    </>
                                ) : (
                                    <>
                                        <Upload className="mr-2 h-4 w-4" />
                                        {t('settings.data_management.import_and_replace_data')}
                                    </>
                                )}
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            {t('settings.data_management.recommended_backup_hint')}
                        </p>
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Best Practices Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-lg">💡</span>
                        {t('settings.data_management.best_practices_and_tips')}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h4 className="font-medium mb-3 text-green-700">{t('settings.data_management.recommended_practices')}</h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.create_regular_backups')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.always_backup_before_importing')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.store_backup_files_in_multiple_safe_locations')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.test_imports_in_a_separate_environment_first')}</span>
                                </li>
                            </ul>
                        </div>

                        <div>
                            <h4 className="font-medium mb-3 text-blue-700">{t('settings.data_management.technical_information')}</h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.sqlite_files_can_be_opened_with_db_browser')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.data_can_be_used_programmatically_in_custom_applications')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.import_validates_file_structure_before_processing')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.data_management.new_invoice_numbers_are_generated_to_avoid_conflicts')}</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </CardContent>
            </ProfessionalCard>
        </div>
    );
};
