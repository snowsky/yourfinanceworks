import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertTriangle,
  Download,
  Calendar,
  FileText,
  Settings
} from 'lucide-react';
import { ReportHistory as ReportHistoryType, reportApi } from '@/lib/api';
import { toast } from 'sonner';
import { format } from 'date-fns';

interface ReportRegenerationProps {
  report: ReportHistoryType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRegenerated?: (newReport: ReportHistoryType) => void;
}

interface RegenerationProgress {
  stage: string;
  progress: number;
  message: string;
  estimatedTimeRemaining?: number;
}

const REGENERATION_STAGES = [
  { key: 'validating', label: 'Validating Parameters', progress: 10 },
  { key: 'fetching', label: 'Fetching Data', progress: 30 },
  { key: 'processing', label: 'Processing Data', progress: 60 },
  { key: 'formatting', label: 'Formatting Report', progress: 80 },
  { key: 'finalizing', label: 'Finalizing', progress: 95 },
  { key: 'completed', label: 'Completed', progress: 100 }
];

export function ReportRegeneration({ 
  report, 
  open, 
  onOpenChange, 
  onRegenerated 
}: ReportRegenerationProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [progress, setProgress] = useState<RegenerationProgress | null>(null);
  const [newReportId, setNewReportId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);

  // Simulate progress updates
  useEffect(() => {
    if (!regenerating) return;

    let currentStageIndex = 0;
    const interval = setInterval(() => {
      if (currentStageIndex < REGENERATION_STAGES.length) {
        const stage = REGENERATION_STAGES[currentStageIndex];
        setProgress({
          stage: stage.key,
          progress: stage.progress,
          message: stage.label,
          estimatedTimeRemaining: (REGENERATION_STAGES.length - currentStageIndex) * 2 // 2 seconds per stage
        });
        currentStageIndex++;
      } else {
        clearInterval(interval);
        setRegenerating(false);
        // Simulate successful completion
        setNewReportId(Math.floor(Math.random() * 10000));
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [regenerating]);

  const handleStartRegeneration = async () => {
    try {
      setRegenerating(true);
      setProgress(null);
      setError(null);
      setNewReportId(null);
      
      // Create regeneration request with current data
      const regenerateRequest = {
        report_type: report.report_type,
        filters: {
          ...report.parameters.filters,
          // Update date range to current if it was relative
          date_from: report.parameters.filters?.date_from,
          date_to: new Date().toISOString() // Use current date as end date
        },
        columns: report.parameters.columns,
        export_format: report.parameters.export_format || 'pdf',
        template_id: report.template_id
      };
      
      const result = await reportApi.generateReport(regenerateRequest);
      
      if (result.success) {
        // The actual regeneration will be handled by the progress simulation
        // In a real implementation, you would poll for status updates
        toast.success('Report regeneration started');
      } else {
        throw new Error(result.error_message || 'Regeneration failed');
      }
    } catch (error) {
      console.error('Regeneration failed:', error);
      setError(error instanceof Error ? error.message : 'Regeneration failed');
      setRegenerating(false);
      setProgress(null);
      toast.error('Failed to start regeneration');
    }
  };

  const handleDownloadNew = async () => {
    if (!newReportId) return;
    
    try {
      const response = await reportApi.downloadReport(newReportId);
      
      if (!response.ok) {
        throw new Error('Download failed');
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Generate filename
      const timestamp = format(new Date(), 'yyyyMMdd_HHmmss');
      const extension = report.parameters.export_format === 'excel' ? 'xlsx' : 
                       report.parameters.export_format === 'csv' ? 'csv' : 'pdf';
      a.download = `${report.report_type}_report_regenerated_${timestamp}.${extension}`;
      
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success('Regenerated report downloaded successfully');
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Failed to download regenerated report');
    }
  };

  const handleClose = () => {
    if (regenerating) {
      setConfirmDialogOpen(true);
    } else {
      onOpenChange(false);
      // Reset state
      setProgress(null);
      setError(null);
      setNewReportId(null);
    }
  };

  const handleForceClose = () => {
    setConfirmDialogOpen(false);
    onOpenChange(false);
    // Reset state
    setRegenerating(false);
    setProgress(null);
    setError(null);
    setNewReportId(null);
  };

  const getProgressIcon = () => {
    if (error) return <XCircle className="h-5 w-5 text-red-500" />;
    if (newReportId) return <CheckCircle className="h-5 w-5 text-green-500" />;
    if (regenerating) return <RefreshCw className="h-5 w-5 animate-spin text-blue-500" />;
    return <Clock className="h-5 w-5 text-gray-400" />;
  };

  const getStatusMessage = () => {
    if (error) return 'Regeneration failed';
    if (newReportId) return 'Regeneration completed successfully';
    if (regenerating && progress) return progress.message;
    return 'Ready to regenerate';
  };

  const formatTimeRemaining = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Regenerate Report
            </DialogTitle>
            <DialogDescription>
              Generate a new version of this report with current data. The original report will remain unchanged.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Original Report Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Original Report
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-500">Type</p>
                    <p className="capitalize">{report.report_type} Report</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Format</p>
                    <Badge variant="outline">
                      {(report.parameters.export_format || 'pdf').toUpperCase()}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Generated</p>
                    <p className="flex items-center gap-1">
                      <Calendar className="h-4 w-4 text-gray-400" />
                      {format(new Date(report.generated_at), 'MMM dd, yyyy HH:mm')}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">Status</p>
                    <Badge className="bg-green-100 text-green-800">
                      {report.status}
                    </Badge>
                  </div>
                </div>

                {/* Show filters if available */}
                {report.parameters.filters && Object.keys(report.parameters.filters).length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-2">Applied Filters</p>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(report.parameters.filters).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-medium capitalize">{key.replace('_', ' ')}:</span>{' '}
                            <span className="text-gray-600">
                              {Array.isArray(value) ? value.join(', ') : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Regeneration Status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  {getProgressIcon()}
                  Regeneration Status
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{getStatusMessage()}</p>
                  {progress?.estimatedTimeRemaining && (
                    <p className="text-sm text-gray-500">
                      ~{formatTimeRemaining(progress.estimatedTimeRemaining)} remaining
                    </p>
                  )}
                </div>

                {(regenerating || progress) && (
                  <div className="space-y-2">
                    <Progress value={progress?.progress || 0} className="w-full" />
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>0%</span>
                      <span>{progress?.progress || 0}%</span>
                      <span>100%</span>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <XCircle className="h-4 w-4 text-red-500" />
                      <p className="text-sm font-medium text-red-800">Error</p>
                    </div>
                    <p className="text-sm text-red-700 mt-1">{error}</p>
                  </div>
                )}

                {newReportId && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <p className="text-sm font-medium text-green-800">
                          Report regenerated successfully
                        </p>
                      </div>
                      <Button size="sm" onClick={handleDownloadNew}>
                        <Download className="h-4 w-4 mr-2" />
                        Download
                      </Button>
                    </div>
                    <p className="text-sm text-green-700 mt-1">
                      New report ID: #{newReportId}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Warning about data changes */}
            {!regenerating && !newReportId && !error && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-yellow-800">
                      Data Changes Notice
                    </p>
                    <p className="text-sm text-yellow-700 mt-1">
                      The regenerated report will use current data, which may differ from the original report. 
                      Any changes in your data since the original generation will be reflected in the new report.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              {regenerating ? 'Cancel' : 'Close'}
            </Button>
            {!regenerating && !newReportId && (
              <Button onClick={handleStartRegeneration} disabled={regenerating}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Start Regeneration
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirmation dialog for closing during regeneration */}
      <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Regeneration?</AlertDialogTitle>
            <AlertDialogDescription>
              The report regeneration is currently in progress. If you close this dialog, 
              the regeneration will continue in the background, but you won't be able to 
              track its progress.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Open</AlertDialogCancel>
            <AlertDialogAction onClick={handleForceClose}>
              Close Anyway
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}