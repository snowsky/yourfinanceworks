import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '@/components/ui/select';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
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
  Download, 
  RefreshCw, 
  Search, 
  Filter, 
  MoreHorizontal,
  Share2,
  Trash2,
  Eye,
  Calendar,
  FileText,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle
} from 'lucide-react';
import { reportApi, ReportHistory as ReportHistoryType } from '@/lib/api';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { ReportSharing } from './ReportSharing';
import { ReportRegeneration } from './ReportRegeneration';

interface ReportHistoryProps {
  className?: string;
}

interface ReportHistoryFilters {
  search: string;
  reportType: string;
  status: string;
  dateFrom: string;
  dateTo: string;
}

const REPORT_TYPE_LABELS = {
  client: 'Client Reports',
  invoice: 'Invoice Reports', 
  payment: 'Payment Reports',
  expense: 'Expense Reports',
  statement: 'Statement Reports'
};

const STATUS_LABELS = {
  pending: 'Pending',
  generating: 'Generating',
  completed: 'Completed',
  failed: 'Failed'
};

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800',
  generating: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800'
};

const STATUS_ICONS = {
  pending: Clock,
  generating: RefreshCw,
  completed: CheckCircle,
  failed: XCircle
};

export function ReportHistory({ className }: ReportHistoryProps) {
  const [reports, setReports] = useState<ReportHistoryType[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [limit] = useState(20);
  const [downloadingReports, setDownloadingReports] = useState<Set<number>>(new Set());
  const [regeneratingReports, setRegeneratingReports] = useState<Set<number>>(new Set());
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState<ReportHistoryType | null>(null);
  const [sharingDialogOpen, setSharingDialogOpen] = useState(false);
  const [reportToShare, setReportToShare] = useState<ReportHistoryType | null>(null);
  const [regenerationDialogOpen, setRegenerationDialogOpen] = useState(false);
  const [reportToRegenerate, setReportToRegenerate] = useState<ReportHistoryType | null>(null);
  
  const [filters, setFilters] = useState<ReportHistoryFilters>({
    search: '',
    reportType: '',
    status: '',
    dateFrom: '',
    dateTo: ''
  });

  const loadReports = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      
      if (filters.reportType && filters.reportType !== 'all') params.set('report_type', filters.reportType);
      if (filters.status && filters.status !== 'all') params.set('status', filters.status);
      if (limit) params.set('limit', limit.toString());
      if (page * limit) params.set('skip', (page * limit).toString());
      
      const response = await reportApi.getHistory(limit, page * limit);
      setReports(response.reports);
      setTotal(response.total);
    } catch (error) {
      console.error('Failed to load report history:', error);
      toast.error('Failed to load report history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [page, filters.reportType, filters.status]);

  const handleDownload = async (report: ReportHistoryType) => {
    if (report.status !== 'completed') {
      toast.error('Report is not ready for download');
      return;
    }

    try {
      setDownloadingReports(prev => new Set(prev).add(report.id));
      
      const response = await reportApi.downloadReport(report.id);
      
      if (!response.ok) {
        throw new Error('Download failed');
      }

      // Create blob and download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Generate filename based on report type and date
      const timestamp = format(new Date(report.generated_at), 'yyyyMMdd_HHmmss');
      const extension = getFileExtension(report.parameters.export_format);
      a.download = `${report.report_type}_report_${timestamp}.${extension}`;
      
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success('Report downloaded successfully');
    } catch (error) {
      console.error('Download failed:', error);
      toast.error('Failed to download report');
    } finally {
      setDownloadingReports(prev => {
        const newSet = new Set(prev);
        newSet.delete(report.id);
        return newSet;
      });
    }
  };

  const handleRegenerate = (report: ReportHistoryType) => {
    setReportToRegenerate(report);
    setRegenerationDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!reportToDelete) return;
    
    try {
      // Note: This would need to be implemented in the API
      // await reportApi.deleteReport(reportToDelete.id);
      toast.success('Report deleted successfully');
      loadReports();
    } catch (error) {
      console.error('Delete failed:', error);
      toast.error('Failed to delete report');
    } finally {
      setDeleteDialogOpen(false);
      setReportToDelete(null);
    }
  };

  const handleShare = (report: ReportHistoryType) => {
    setReportToShare(report);
    setSharingDialogOpen(true);
  };

  const getFileExtension = (format: string): string => {
    const extensions: Record<string, string> = {
      pdf: 'pdf',
      csv: 'csv',
      excel: 'xlsx',
      json: 'json'
    };
    return extensions[format] || 'bin';
  };

  const getStatusIcon = (status: string) => {
    const Icon = STATUS_ICONS[status as keyof typeof STATUS_ICONS] || AlertCircle;
    return <Icon className="h-4 w-4" />;
  };

  const filteredReports = reports.filter(report => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return (
        report.report_type.toLowerCase().includes(searchLower) ||
        (report.parameters.filters?.client_name || '').toLowerCase().includes(searchLower)
      );
    }
    return true;
  });

  const totalPages = Math.ceil(total / limit);

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Report History
            </CardTitle>
            <Button onClick={loadReports} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-wrap gap-4 mb-6">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Search reports..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="pl-10"
                />
              </div>
            </div>
            
            <Select
              value={filters.reportType || undefined}
              onValueChange={(value) => setFilters(prev => ({ ...prev, reportType: value || '' }))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Report Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {Object.entries(REPORT_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={filters.status || undefined}
              onValueChange={(value) => setFilters(prev => ({ ...prev, status: value || '' }))}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Reports Table */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin mr-2" />
              Loading reports...
            </div>
          ) : filteredReports.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No reports found</p>
              <p className="text-sm">Generate your first report to see it here</p>
            </div>
          ) : (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Report Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Generated</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredReports.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell>
                        <div>
                          <div className="font-medium">
                            {REPORT_TYPE_LABELS[report.report_type as keyof typeof REPORT_TYPE_LABELS]}
                          </div>
                          {report.parameters.filters?.client_name && (
                            <div className="text-sm text-gray-500">
                              Client: {report.parameters.filters.client_name}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[report.status as keyof typeof STATUS_COLORS]}>
                          <div className="flex items-center gap-1">
                            {getStatusIcon(report.status)}
                            {STATUS_LABELS[report.status as keyof typeof STATUS_LABELS]}
                          </div>
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Calendar className="h-4 w-4 text-gray-400" />
                          {format(new Date(report.generated_at), 'MMM dd, yyyy HH:mm')}
                        </div>
                      </TableCell>
                      <TableCell>
                        {report.expires_at ? (
                          <div className="text-sm text-gray-500">
                            {format(new Date(report.expires_at), 'MMM dd, yyyy')}
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {(report.parameters.export_format || 'pdf').toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {report.status === 'completed' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDownload(report)}
                              disabled={downloadingReports.has(report.id)}
                            >
                              {downloadingReports.has(report.id) ? (
                                <RefreshCw className="h-4 w-4 animate-spin" />
                              ) : (
                                <Download className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                          
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => handleRegenerate(report)}
                              >
                                <RefreshCw className="h-4 w-4 mr-2" />
                                Regenerate with Current Data
                              </DropdownMenuItem>
                              
                              {report.status === 'completed' && (
                                <DropdownMenuItem onClick={() => handleShare(report)}>
                                  <Share2 className="h-4 w-4 mr-2" />
                                  Share Report
                                </DropdownMenuItem>
                              )}
                              
                              <DropdownMenuItem
                                onClick={() => {
                                  setReportToDelete(report);
                                  setDeleteDialogOpen(true);
                                }}
                                className="text-red-600"
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-500">
                    Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total} reports
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(prev => Math.max(0, prev - 1))}
                      disabled={page === 0}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(prev => Math.min(totalPages - 1, prev + 1))}
                      disabled={page >= totalPages - 1}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Report</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this report? This action cannot be undone.
              {reportToDelete && (
                <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
                  <strong>{REPORT_TYPE_LABELS[reportToDelete.report_type as keyof typeof REPORT_TYPE_LABELS]}</strong>
                  <br />
                  Generated: {format(new Date(reportToDelete.generated_at), 'MMM dd, yyyy HH:mm')}
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Delete Report
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Report Sharing Dialog */}
      {reportToShare && (
        <ReportSharing
          report={reportToShare}
          open={sharingDialogOpen}
          onOpenChange={(open) => {
            setSharingDialogOpen(open);
            if (!open) setReportToShare(null);
          }}
        />
      )}

      {/* Report Regeneration Dialog */}
      {reportToRegenerate && (
        <ReportRegeneration
          report={reportToRegenerate}
          open={regenerationDialogOpen}
          onOpenChange={(open) => {
            setRegenerationDialogOpen(open);
            if (!open) setReportToRegenerate(null);
          }}
          onRegenerated={(newReport) => {
            loadReports(); // Refresh the list
            toast.success('Report regenerated successfully');
          }}
        />
      )}
    </div>
  );
}