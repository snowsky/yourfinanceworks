import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ReportFilters } from '@/components/reports/ReportFilters';
import { ReportPreview } from '@/components/reports/ReportPreview';
import { ExportFormatSelector } from '@/components/reports/ExportFormatSelector';
import {
    reportApi,
    ReportFilters as ReportFiltersType,
    ReportGenerateRequest,
    ReportPreviewRequest,
    ReportData
} from '@/lib/api';
import { Eye, FileDown, RefreshCw, ArrowLeft } from 'lucide-react';
import { ensureAuthenticated } from '@/utils/auth';
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";

const ReportDetail: React.FC = () => {
    const { reportType } = useParams<{ reportType: string }>();
    const navigate = useNavigate();

    const [filters, setFilters] = useState<ReportFiltersType>({});
    const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'excel' | 'json'>('pdf');
    const [previewData, setPreviewData] = useState<ReportData | null>(null);
    const [previewError, setPreviewError] = useState<string | null>(null);

    // Fetch available report types to get the config
    const { data: reportTypesData } = useQuery({
        queryKey: ['reportTypes'],
        queryFn: reportApi.getReportTypes,
    });

    const reportTypes = reportTypesData?.report_types || [];
    const selectedTypeConfig = reportTypes.find(type => type.type === reportType);

    // Preview mutation
    const previewMutation = useMutation({
        mutationFn: (request: ReportPreviewRequest) => reportApi.previewReport(request),
        onSuccess: (data) => {
            setPreviewData(data);
            setPreviewError(null);
        },
        onError: (error: any) => {
            console.error('Preview error:', error);

            if (error.message && (error.message.includes('401') || error.message.includes('Authentication failed'))) {
                setPreviewError('Session expired. Please log in again.');
                toast.error('Session expired. Please log in again.');
                return;
            }

            setPreviewError(error.message || 'Failed to generate preview');
            setPreviewData(null);
        },
    });

    // Export mutation
    const exportMutation = useMutation({
        mutationFn: (request: ReportGenerateRequest) => reportApi.generateReport(request),
        onSuccess: (result) => {
            if (result.success) {
                if (result.report_id) {
                    console.log('Report generated with ID:', result.report_id);
                    handleDownload(result.report_id);
                } else if (result.download_url) {
                    console.log('Report generated with direct URL:', result.download_url);
                    window.open(result.download_url, '_blank');
                }
                toast.success('Report generated successfully!');
            } else {
                toast.error(result.error_message || 'Failed to generate report');
            }
        },
        onError: (error: any) => {
            console.error('Export error:', error);

            if (error.message && error.message.includes('401')) {
                toast.error('Session expired. Please log in again.');
                return;
            }

            if (error.message && error.message.includes('Authentication failed')) {
                toast.error('Authentication failed. Please log in again.');
                return;
            }

            toast.error(error.message || 'Failed to generate report. Please try again.');
        },
    });

    // Handle download
    const handleDownload = async (reportId: number) => {
        try {
            console.log('Attempting to download report:', reportId);

            const response = await reportApi.downloadReport(reportId);

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report-${reportId}.${exportFormat}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            toast.success('Report downloaded successfully!');
        } catch (error: any) {
            console.error('Download error:', error);

            if (error.message && error.message.includes('Authentication failed')) {
                return;
            }

            toast.error(error.message || 'Failed to download report. Please try again.');
        }
    };

    // Generate preview
    const handlePreview = () => {
        if (!reportType) {
            toast.error('Invalid report type');
            return;
        }

        if (!ensureAuthenticated()) {
            toast.error('Session expired. Please log in again.');
            return;
        }

        const request: ReportPreviewRequest = {
            report_type: reportType as any,
            filters,
            limit: 10,
        };

        previewMutation.mutate(request);
    };

    // Generate and export report
    const handleExport = () => {
        if (!reportType) {
            toast.error('Invalid report type');
            return;
        }

        if (!ensureAuthenticated()) {
            toast.error('Session expired. Please log in again.');
            return;
        }

        const request: ReportGenerateRequest = {
            report_type: reportType as any,
            filters,
            export_format: exportFormat,
        };

        exportMutation.mutate(request);
    };

    // Auto-preview when filters change (debounced)
    useEffect(() => {
        if (!reportType) return;

        const timeoutId = setTimeout(() => {
            if (Object.keys(filters).length > 0) {
                handlePreview();
            }
        }, 1000);

        return () => clearTimeout(timeoutId);
    }, [filters, reportType]);

    if (!selectedTypeConfig) {
        return (
            <>
                <div className="flex items-center justify-center h-full">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
            </>
        );
    }

    return (
        <>
            <div className="h-full space-y-6 fade-in">
                <PageHeader
                    title={selectedTypeConfig.name}
                    description={selectedTypeConfig.description}
                    backButton={{
                        onClick: () => navigate('/reports'),
                        label: 'Back to Reports'
                    }}
                />

                <ContentSection className="slide-in">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Quick Actions</CardTitle>
                            <CardDescription>Common report generation shortcuts</CardDescription>
                        </CardHeader>
                        <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
                                className="h-auto py-3 px-4 flex flex-col items-start gap-1"
                            >
                                <span className="font-medium">This Month</span>
                                <span className="text-xs text-muted-foreground">Current month data</span>
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
                                className="h-auto py-3 px-4 flex flex-col items-start gap-1"
                            >
                                <span className="font-medium">Last Month</span>
                                <span className="text-xs text-muted-foreground">Previous month data</span>
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
                                className="h-auto py-3 px-4 flex flex-col items-start gap-1"
                            >
                                <span className="font-medium">Year to Date</span>
                                <span className="text-xs text-muted-foreground">Current year data</span>
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    setFilters({});
                                }}
                                className="h-auto py-3 px-4 flex flex-col items-start gap-1"
                            >
                                <span className="font-medium">Clear Filters</span>
                                <span className="text-xs text-muted-foreground">Reset all filters</span>
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Filters and Preview Layout */}
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                    {/* Left Column - Filters */}
                    <div className="xl:col-span-1 space-y-6">
                        <ReportFilters
                            reportType={reportType!}
                            reportTypeConfig={selectedTypeConfig}
                            filters={filters}
                            onFiltersChange={setFilters}
                        />

                        {/* Preview Button */}
                        <Card className="slide-in">
                            <CardContent className="pt-6">
                                <Button
                                    onClick={handlePreview}
                                    disabled={previewMutation.isPending}
                                    variant="outline"
                                    className="w-full"
                                    size="lg"
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
                    <div className="xl:col-span-2 space-y-6">
                        <ReportPreview
                            reportData={previewData}
                            loading={previewMutation.isPending}
                            error={previewError}
                            onRefresh={handlePreview}
                        />
                    </div>
                </div>

                {/* Export Section */}
                <Card className="slide-in">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileDown className="h-5 w-5" />
                            Export Options
                        </CardTitle>
                        <CardDescription>
                            Choose your preferred export format and download your report
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-6">
                        <ExportFormatSelector
                            selectedFormat={exportFormat}
                            onFormatChange={setExportFormat}
                            onExport={handleExport}
                            loading={exportMutation.isPending}
                            disabled={!previewData}
                        />
                    </CardContent>
                </Card>
                </ContentSection>
            </div>
        </>
    );
};

export default ReportDetail;
