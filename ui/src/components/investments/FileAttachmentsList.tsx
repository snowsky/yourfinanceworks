import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { apiRequest, investmentApi } from '@/lib/api';
import { toast } from 'sonner';
import {
  FileText,
  Download,
  Trash2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Eye,
  RefreshCw,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import FileAttachmentDetail from './FileAttachmentDetail';

interface FileAttachment {
  id: string;
  original_filename: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'partial';
  extraction_error?: string;
  extracted_holdings_count: number;
  failed_holdings_count: number;
  extracted_transactions_count: number;
  failed_transactions_count: number;
  created_at: string;
  processed_at?: string;
  extracted_data?: any;
}

interface FileAttachmentsListProps {
  portfolioId: number;
  onRefresh?: () => void;
}

const FileAttachmentsList: React.FC<FileAttachmentsListProps> = ({
  portfolioId,
  onRefresh,
}) => {
  const queryClient = useQueryClient();
  const { t } = useTranslation('investments');
  const [selectedAttachment, setSelectedAttachment] = useState<FileAttachment | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  // Fetch file attachments with smart polling
  // Poll more frequently while processing, less frequently when idle
  const queryResult = useQuery({
    queryKey: ['file-attachments', portfolioId],
    queryFn: async () => {
      const response = await apiRequest<FileAttachment[]>(
        `/investments/portfolios/${portfolioId}/holdings-files`
      );
      return response || [];
    },
    refetchInterval: 3000, // Poll every 3 seconds
    refetchIntervalInBackground: true,
  });

  const { data: attachments = [], isLoading, refetch } = queryResult;

  // Delete attachment mutation
  const deleteAttachmentMutation = useMutation({
    mutationFn: async (attachmentId: string) => {
      await apiRequest(`/investments/holdings-files/${attachmentId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      toast.success(t('File deleted successfully'));
      queryClient.invalidateQueries({ queryKey: ['file-attachments', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || t('Failed to delete file');
      toast.error(errorMessage);
    },
  });

  // Download attachment mutation
  const downloadAttachmentMutation = useMutation({
    mutationFn: async (attachmentId: string) => {
      try {
        const token = localStorage.getItem('token');
        const selectedTenantId = localStorage.getItem('selected_tenant_id');
        const userStr = localStorage.getItem('user');
        let tenantId = selectedTenantId;
        if (!tenantId && userStr) {
          const user = JSON.parse(userStr);
          tenantId = user?.tenant_id?.toString();
        }

        const response = await fetch(
          `/api/v1/investments/holdings-files/${attachmentId}/download`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              ...(tenantId && { 'X-Tenant-ID': tenantId }),
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Download failed: ${response.statusText}`);
        }

        return response;
      } catch (error) {
        throw error;
      }
    },
    onSuccess: (response, attachmentId) => {
      const attachment = attachments.find((a) => a.id === attachmentId);
      if (attachment && response.ok) {
        response.blob().then((blob) => {
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', attachment.original_filename);
          document.body.appendChild(link);
          link.click();
          link.parentNode?.removeChild(link);
          window.URL.revokeObjectURL(url);
          toast.success(t('File downloaded successfully'));
        });
      }
    },
    onError: (error: any) => {
      const errorMessage = error?.message || t('Failed to download file');
      toast.error(errorMessage);
    },
  });

  // Reprocess attachment mutation
  const reprocessAttachmentMutation = useMutation({
    mutationFn: async (attachmentId: string) => {
      await apiRequest(`/investments/holdings-files/${attachmentId}/reprocess`, {
        method: 'POST',
      });
    },
    onSuccess: () => {
      toast.success(t('Reprocessing started'));
      queryClient.invalidateQueries({ queryKey: ['file-attachments', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || t('Failed to start reprocessing');
      toast.error(errorMessage);
    },
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-5 h-5 text-amber-500" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'partial':
        return <AlertCircle className="w-5 h-5 text-amber-500" />;
      default:
        return <FileText className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{t('Pending')}</Badge>;
      case 'processing':
        return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{t('Processing')}</Badge>;
      case 'completed':
        return <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">{t('Completed')}</Badge>;
      case 'failed':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">{t('Failed')}</Badge>;
      case 'partial':
        return <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{t('Partial')}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  if (isLoading) {
    return (
      <ProfessionalCard className="border-border/40">
        <div className="p-8 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
          <span className="ml-3 text-muted-foreground">{t('Loading files...')}</span>
        </div>
      </ProfessionalCard>
    );
  }

  if (attachments.length === 0) {
    return (
      <ProfessionalCard className="border-border/40 bg-muted/20">
        <div className="p-8 text-center">
          <FileText className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
          <p className="text-muted-foreground font-medium">{t('No files uploaded yet')}</p>
          <p className="text-sm text-muted-foreground/70 mt-1">
            {t('Upload holdings files to get started')}
          </p>
        </div>
      </ProfessionalCard>
    );
  }

  return (
    <>
      <ProfessionalCard variant="elevated" className="border-border/40 shadow-xl overflow-hidden">
        <div className="bg-primary/5 p-6 border-b border-primary/10">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-primary text-white shadow-lg">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-lg">{t('file_upload.uploaded_files')}</h3>
              <p className="text-sm text-muted-foreground">
                {t('file_upload.track_status_description')}
              </p>
            </div>
          </div>
        </div>

        <div className="divide-y divide-border/30">
          {attachments.map((attachment) => (
            <div
              key={attachment.id}
              className="p-6 hover:bg-muted/30 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className="mt-1">{getStatusIcon(attachment.status)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <p className="font-medium truncate">{attachment.original_filename}</p>
                      {getStatusBadge(attachment.status)}
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                      <div>
                        <span className="font-medium">{t('file_upload.size')}:</span> {formatFileSize(attachment.file_size)}
                      </div>
                      <div>
                        <span className="font-medium">{t('file_upload.uploaded')}:</span>{' '}
                        {format(parseISO(attachment.created_at), 'MMM d, yyyy HH:mm')}
                      </div>
                    </div>

                    {attachment.status === 'completed' && (
                      <div className="mt-3 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                        <p className="text-sm text-emerald-700">
                          {attachment.extracted_transactions_count > 0 ? (
                            t('file_upload.x_holdings_y_transactions_created', {
                              holdings: attachment.extracted_holdings_count,
                              transactions: attachment.extracted_transactions_count
                            })
                          ) : (
                            t('file_upload.x_holdings_created', {
                              count: attachment.extracted_holdings_count
                            })
                          )}
                        </p>
                      </div>
                    )}

                    {attachment.status === 'partial' && (
                      <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                        <p className="text-sm text-amber-700">
                          {(attachment.failed_holdings_count > 0 || attachment.failed_transactions_count > 0) ? (
                            t('file_upload.x_holdings_y_transactions_z_failed', {
                              holdings: attachment.extracted_holdings_count,
                              transactions: attachment.extracted_transactions_count,
                              failed: attachment.failed_holdings_count + attachment.failed_transactions_count
                            })
                          ) : (
                            t('file_upload.x_holdings_y_transactions_created', {
                              holdings: attachment.extracted_holdings_count,
                              transactions: attachment.extracted_transactions_count
                            })
                          )}
                        </p>
                      </div>
                    )}

                    {attachment.status === 'pending' && attachment.extraction_error && (
                      <div className="mt-3 p-3 rounded-lg bg-blue-50 border border-blue-200">
                        <p className="text-sm text-blue-700">
                          <span className="font-medium">{t('Info')}:</span> {attachment.extraction_error}
                        </p>
                      </div>
                    )}

                    {attachment.status === 'failed' && attachment.extraction_error && (
                      <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200">
                        <p className="text-sm text-red-700">
                          <span className="font-medium">{t('Error')}:</span> {attachment.extraction_error}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex gap-2 flex-shrink-0">
                  {attachment.status === 'completed' || attachment.status === 'partial' || attachment.status === 'failed' ? (
                    <ProfessionalButton
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSelectedAttachment(attachment);
                        setShowDetails(true);
                      }}
                      className="rounded-lg"
                    >
                      <Eye className="w-4 h-4" />
                    </ProfessionalButton>
                  ) : null}
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={() => downloadAttachmentMutation.mutate(attachment.id)}
                    disabled={downloadAttachmentMutation.isPending}
                    className="rounded-lg"
                  >
                    <Download className="w-4 h-4" />
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={() => reprocessAttachmentMutation.mutate(attachment.id)}
                    disabled={
                      reprocessAttachmentMutation.isPending ||
                      attachment.status === 'processing' ||
                      (attachment.status === 'pending' && !attachment.extraction_error)
                    }
                    className="rounded-lg text-blue-500 hover:text-blue-600 hover:bg-blue-50"
                    title={t('Reprocess file')}
                  >
                    <RefreshCw className={`w-4 h-4 ${reprocessAttachmentMutation.isPending && reprocessAttachmentMutation.variables === attachment.id ? 'animate-spin' : ''}`} />
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteAttachmentMutation.mutate(attachment.id)}
                    disabled={deleteAttachmentMutation.isPending}
                    className="rounded-lg text-red-500 hover:text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="w-4 h-4" />
                  </ProfessionalButton>
                </div>
              </div>
            </div>
          ))}
        </div>
      </ProfessionalCard>

      {/* Details Dialog */}
      {selectedAttachment && (
        <FileAttachmentDetail
          attachment={selectedAttachment}
          open={showDetails}
          onOpenChange={setShowDetails}
        />
      )}
    </>
  );
};

export default FileAttachmentsList;
