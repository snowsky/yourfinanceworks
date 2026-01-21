import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
    Database, Download, Upload, Loader2
} from "lucide-react";
import { toast } from "sonner";
import { settingsApi, getErrorMessage } from "@/lib/api";
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

    const exportMutation = useMutation({
        mutationFn: () => settingsApi.exportData(),
        onSuccess: () => {
            toast.success(t('settings.data_exported_successfully'));
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, t));
        }
    });

    const importMutation = useMutation({
        mutationFn: (file: File) => settingsApi.importData(file),
        onSuccess: (result) => {
            toast.success(t('settings.data_imported_successfully', { imported_counts: JSON.stringify(result.imported_counts) }));
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
                toast.error(t('settings.please_select_sqlite_file'));
                return;
            }
            setSelectedFile(file);
        }
    };

    const handleImportData = () => {
        if (!isAdmin) return;
        if (!selectedFile) {
            toast.error(t('settings.please_select_file_to_import'));
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
                        {t('settings.data_management')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.data_management_description')}
                    </p>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="text-2xl font-bold text-blue-600">📊</div>
                            <h3 className="font-medium text-blue-900 mt-2">{t('settings.complete_backup')}</h3>
                            <p className="text-sm text-blue-700 mt-1">{t('settings.complete_backup_description')}</p>
                        </div>
                        <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                            <div className="text-2xl font-bold text-green-600">🔄</div>
                            <h3 className="font-medium text-green-900 mt-2">{t('settings.easy_restore')}</h3>
                            <p className="text-sm text-green-700 mt-1">{t('settings.easy_restore_description')}</p>
                        </div>
                        <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
                            <div className="text-2xl font-bold text-purple-600">🔒</div>
                            <h3 className="font-medium text-purple-900 mt-2">{t('settings.data_control')}</h3>
                            <p className="text-sm text-purple-700 mt-1">{t('settings.data_control_description')}</p>
                        </div>
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Export Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Download className="h-5 w-5" />
                        {t('settings.export_data')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.export_data_description')}
                    </p>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <h4 className="font-medium mb-3">{t('settings.what_will_be_exported')}</h4>
                                <div className="space-y-2">
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.client_information')}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                        <span>{t('settings.complete_invoice_history')}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                                        <span>{t('settings.payment_records')}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                                        <span>{t('settings.client_notes')}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
                                        <span>{t('settings.company_settings')}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                                        <span>Expenses & Receipts</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                                        <span>Statements & Transactions</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>
                                        <span>Audit Logs & Activity History</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm">
                                        <div className="w-2 h-2 bg-pink-500 rounded-full"></div>
                                        <span>AI Chat History</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <h4 className="font-medium mb-3">{t('settings.export_details')}</h4>
                                <div className="space-y-2 text-sm text-muted-foreground">
                                    <p><strong>{t('settings.format')}:</strong> {t('settings.sqlite_database')}</p>
                                    <p><strong>{t('settings.compatibility')}:</strong> {t('settings.works_with_database_tools')}</p>
                                    <p><strong>{t('settings.security')}:</strong> {t('settings.no_sensitive_authentication_data')}</p>
                                    <p><strong>{t('settings.size')}:</strong> {t('settings.size_description')}</p>
                                    <p><strong>Note:</strong> Attachment files (receipts, bank statements, invoice attachments) are not included in the export. Only database records are exported.</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="border-t pt-4">
                        <Button
                            onClick={handleExportData}
                            disabled={exportMutation.isPending}
                            size="lg"
                            className="w-full sm:w-auto"
                        >
                            {exportMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t('settings.creating_export')}
                                </>
                            ) : (
                                <>
                                    <Download className="mr-2 h-4 w-4" />
                                    {t('settings.download_complete_backup')}
                                </>
                            )}
                        </Button>
                        <p className="text-xs text-muted-foreground mt-2">
                            {t('settings.export_includes_all_data')}
                        </p>
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Import Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Upload className="h-5 w-5" />
                        {t('settings.import_data')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                        {t('settings.import_data_description')}
                    </p>
                </CardHeader>
                <CardContent className="space-y-6">
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                        <div className="flex items-start gap-3">
                            <div className="text-amber-600 text-lg">⚠️</div>
                            <div>
                                <h4 className="font-medium text-amber-900 mb-1">{t('settings.important_warning')}</h4>
                                <p className="text-sm text-amber-800">
                                    {t('settings.importing_data_warning_strong')}
                                    {t('settings.importing_data_warning_cannot_be_undone')}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div>
                                <Label htmlFor="import-file" className="text-base font-medium">{t('settings.select_backup_file')}</Label>
                                <p className="text-sm text-muted-foreground mb-3">
                                    {t('settings.choose_sqlite_file')}
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
                                            <span className="font-medium">{t('settings.file_selected')}:</span>
                                        </div>
                                        <p className="text-sm text-green-700 mt-1">
                                            {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} {t('settings.mb')})
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <h4 className="font-medium mb-3">{t('settings.import_process')}</h4>
                                <div className="space-y-2 text-sm text-muted-foreground">
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.file_validation_and_structure_check')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.current_data_backup_and_removal')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.import_new_data_with_id_mapping')}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                                        <span>{t('settings.data_integrity_verification')}</span>
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
                                        {t('settings.creating_backup')}
                                    </>
                                ) : (
                                    <>
                                        <Download className="mr-2 h-4 w-4" />
                                        {t('settings.backup_current_data_first')}
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
                                        {t('settings.importing_data')}
                                    </>
                                ) : (
                                    <>
                                        <Upload className="mr-2 h-4 w-4" />
                                        {t('settings.import_and_replace_data')}
                                    </>
                                )}
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            {t('settings.recommended_backup_hint')}
                        </p>
                    </div>
                </CardContent>
            </ProfessionalCard>

            {/* Best Practices Section */}
            <ProfessionalCard>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <span className="text-lg">💡</span>
                        {t('settings.best_practices_and_tips')}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h4 className="font-medium mb-3 text-green-700">{t('settings.recommended_practices')}</h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.create_regular_backups')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.always_backup_before_importing')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.store_backup_files_in_multiple_safe_locations')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-green-500 mt-0.5">•</span>
                                    <span>{t('settings.test_imports_in_a_separate_environment_first')}</span>
                                </li>
                            </ul>
                        </div>

                        <div>
                            <h4 className="font-medium mb-3 text-blue-700">{t('settings.technical_information')}</h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.sqlite_files_can_be_opened_with_db_browser')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.data_can_be_used_programmatically_in_custom_applications')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.import_validates_file_structure_before_processing')}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>{t('settings.new_invoice_numbers_are_generated_to_avoid_conflicts')}</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </CardContent>
            </ProfessionalCard>
        </div>
    );
};
