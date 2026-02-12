import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { apiRequest, investmentApi } from '@/lib/api';
import { toast } from 'sonner';
import { Loader2, Eye, Download, FileText, AlertCircle } from 'lucide-react';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface FileAttachment {
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

interface FileAttachmentDetailProps {
  attachment: FileAttachment | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const FileAttachmentDetail: React.FC<FileAttachmentDetailProps> = ({
  attachment,
  open,
  onOpenChange,
}) => {
  const { t } = useTranslation();
  const [previewLoaded, setPreviewLoaded] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewObjectUrl, setPreviewObjectUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Clean up object URL when dialog closes
  useEffect(() => {
    if (!open && previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl);
      setPreviewObjectUrl(null);
      setPreviewUrl(null);
      setPreviewText(null);
      setPreviewType(null);
      setPreviewLoaded(false);
    }
  }, [open, previewObjectUrl]);

  if (!attachment) return null;

  const handleLoadPreview = async () => {
    if (previewLoaded) return;

    try {
      setPreviewLoading(true);
      const { blob, contentType } = await investmentApi.downloadHoldingsFileBlob(parseInt(attachment.id));

      let type = contentType || blob.type;

      // Fallback to filename extension if type is generic or missing
      if (!type || type === 'application/octet-stream') {
        const filename = attachment.original_filename.toLowerCase();
        if (filename.endsWith('.pdf')) {
          type = 'application/pdf';
        } else if (filename.endsWith('.png')) {
           type = 'image/png';
        } else if (filename.endsWith('.jpg') || filename.endsWith('.jpeg')) {
           type = 'image/jpeg';
        } else if (filename.endsWith('.csv')) {
           type = 'text/csv';
        } else if (filename.endsWith('.txt')) {
           type = 'text/plain';
        }
      }

      setPreviewType(type);

      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);

      if (type?.includes('text/csv') || type?.includes('text/plain')) {
        const text = await blob.text();
        setPreviewText(text);
        setPreviewUrl(null);
        setPreviewObjectUrl(null);
      } else {
        const objectUrl = URL.createObjectURL(blob);
        setPreviewObjectUrl(objectUrl);
        setPreviewUrl(objectUrl);
        setPreviewText(null);
      }
      setPreviewLoaded(true);
    } catch (e: any) {
      toast.error(e?.message || t('Failed to preview file'));
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-7xl w-[95vw] h-[90vh] flex flex-col p-0 gap-0 rounded-2xl overflow-hidden bg-background">
        <DialogHeader className="p-6 border-b shrink-0">
          <DialogTitle className="text-xl flex items-center justify-between">
            <span>{t('Extraction Results')}</span>
            <span className="text-sm font-normal text-muted-foreground ml-4 truncate flex-1 text-right mr-8">
              {attachment.original_filename}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 min-h-0 divide-y lg:divide-y-0 lg:divide-x">
          {/* Left Column: Extraction Details */}
          <div className="overflow-y-auto p-6 space-y-6 bg-muted/10">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-card border shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">
                  {t('Status')}
                </p>
                <Badge variant={
                    attachment.status === 'completed' ? 'default' :
                    attachment.status === 'failed' ? 'destructive' :
                    'secondary'
                  } className="capitalize">
                  {attachment.status}
                </Badge>
              </div>
              <div className="p-4 rounded-xl bg-card border shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">
                  {t('File Size')}
                </p>
                <p className="text-lg font-semibold text-foreground">
                  {(attachment.file_size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>

            {(attachment.status === 'completed' || attachment.status === 'partial') && (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1 rounded-full bg-emerald-100">
                       <FileText className="w-4 h-4" />
                    </div>
                    <span className="font-semibold">{t('Extraction Success')}</span>
                  </div>
                  <p className="text-2xl font-bold">
                    {attachment.extracted_holdings_count} <span className="text-sm font-normal text-emerald-600">{t('holdings created')}</span>
                  </p>
                </div>

                {attachment.failed_holdings_count > 0 && (
                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
                     <div className="flex items-center gap-2 mb-2">
                        <div className="p-1 rounded-full bg-amber-100">
                           <AlertCircle className="w-4 h-4" />
                        </div>
                        <span className="font-semibold">{t('Validation Issues')}</span>
                     </div>
                    <p className="text-2xl font-bold">
                      {attachment.failed_holdings_count} <span className="text-sm font-normal text-amber-600">{t('holdings failed')}</span>
                    </p>
                  </div>
                )}
              </div>
            )}

            {attachment.status === 'pending' && attachment.extraction_error && (
              <div className="p-4 rounded-xl bg-blue-50 border border-blue-200">
                <p className="text-sm font-medium text-blue-700 mb-2">{t('Information')}:</p>
                <p className="text-sm text-blue-600 font-mono bg-blue-100/50 p-2 rounded">{attachment.extraction_error}</p>
              </div>
            )}

            {attachment.status === 'failed' && attachment.extraction_error && (
              <div className="p-4 rounded-xl bg-red-50 border border-red-200">
                <p className="text-sm font-medium text-red-700 mb-2">{t('Error Details')}:</p>
                <p className="text-sm text-red-600 font-mono bg-red-100/50 p-2 rounded">{attachment.extraction_error}</p>
              </div>
            )}

            {attachment.extracted_data && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  {t('Raw Extracted Data')}
                </p>
                <div className="rounded-xl border bg-card overflow-hidden text-xs">
                  <pre className="p-4 overflow-x-auto max-h-[400px]">
                    {JSON.stringify(attachment.extracted_data, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: File Preview */}
          <div className="flex flex-col min-h-0 bg-background lg:bg-muted/5 relative">
             <div className="p-4 border-b flex items-center justify-between bg-background lg:bg-transparent sticky top-0 z-10 backdrop-blur-sm">
                <h3 className="font-semibold flex items-center gap-2">
                   <Eye className="w-4 h-4 text-muted-foreground" />
                   {t('File Preview')}
                </h3>
                 <div className="flex gap-2">
                    {previewLoaded && (
                        <ProfessionalButton
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (previewUrl) {
                              const link = document.createElement('a');
                              link.href = previewUrl;
                              link.setAttribute('download', attachment.original_filename);
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                            }
                          }}
                        >
                          <Download className="w-4 h-4 mr-2" />
                          {t('Download')}
                        </ProfessionalButton>
                    )}
                     {!previewLoaded && (
                        <ProfessionalButton
                        variant="default"
                        size="sm"
                        onClick={handleLoadPreview}
                        disabled={previewLoading}
                      >
                        {previewLoading ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <Eye className="w-4 h-4 mr-2" />
                        )}
                        {t('Load Preview')}
                      </ProfessionalButton>
                     )}
                 </div>
             </div>

             <div className="flex-1 overflow-auto p-4 flex items-center justify-center min-h-[400px]">
                {!previewLoaded ? (
                    <div className="text-center p-8">
                       <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                          <FileText className="w-8 h-8 text-muted-foreground/50" />
                       </div>
                       <p className="text-muted-foreground">{t('Click "Load Preview" above to view the file')}</p>
                    </div>
                ) : (
                    <div className="w-full h-full bg-white rounded-lg border shadow-sm overflow-hidden flex flex-col">
                        {previewType?.includes('pdf') ? (
                          <iframe
                            src={previewUrl || ''}
                            className="w-full h-full bg-white"
                            title="Preview"
                          />
                        ) : previewType?.startsWith('image/') ? (
                          <div className="flex-1 overflow-auto flex items-center justify-center p-4">
                            <img
                              src={previewUrl || ''}
                              alt="Preview"
                              className="max-w-full max-h-full object-contain"
                            />
                          </div>
                        ) : previewText ? (
                          <pre className="p-6 whitespace-pre-wrap font-mono text-xs w-full h-full overflow-auto text-foreground">
                            {previewText}
                          </pre>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8">
                              <FileText className="w-16 h-16 mb-4 opacity-20" />
                              <p>{t('Preview not available for this file type')}</p>
                              <ProfessionalButton
                                variant="link"
                                onClick={() => {
                                   if (previewUrl) {
                                      const link = document.createElement('a');
                                      link.href = previewUrl;
                                      link.setAttribute('download', attachment.original_filename);
                                      document.body.appendChild(link);
                                      link.click();
                                      document.body.removeChild(link);
                                    }
                                }}
                                className="mt-2"
                              >
                                {t('Download to view')}
                              </ProfessionalButton>
                            </div>
                        )}
                    </div>
                )}
             </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default FileAttachmentDetail;
