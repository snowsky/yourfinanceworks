import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { FileUpload, FileData } from '@/components/ui/file-upload';
import { apiRequest } from '@/lib/api';
import { toast } from 'sonner';
import { Upload, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface FileUploadAreaProps {
  portfolioId: number;
  onUploadSuccess?: () => void;
}

const FileUploadArea: React.FC<FileUploadAreaProps> = ({
  portfolioId,
  onUploadSuccess,
}) => {
  const queryClient = useQueryClient();
  const { t } = useTranslation('investments');
  const [selectedFiles, setSelectedFiles] = useState<FileData[]>([]);

  const uploadFilesMutation = useMutation({
    mutationFn: async (files: FileData[]) => {
      const formData = new FormData();
      files.forEach((fileData) => {
        formData.append('files', fileData.file);
      });

      try {
        const response = await apiRequest<any>(
          `/investments/portfolios/${portfolioId}/holdings-files`,
          {
            method: 'POST',
            body: formData,
            headers: {}, // Let browser set content-type for FormData
          }
        );
        return response;
      } catch (error) {
        throw error;
      }
    },
    onSuccess: (data) => {
      const uploadedCount = Array.isArray(data) ? data.length : 1;
      toast.success(
        t('{{count}} file(s) uploaded successfully. Processing will begin shortly.', {
          count: uploadedCount,
        })
      );
      queryClient.invalidateQueries({ queryKey: ['file-attachments', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] });
      setSelectedFiles([]);
      onUploadSuccess?.();
    },
    onError: (error: any) => {
      const errorMessage = error?.message || t('file_upload.failed_to_upload_files');
      toast.error(errorMessage);
    },
  });

  const handleFilesSelected = (files: FileData[]) => {
    if (files.length + selectedFiles.length > 12) {
      toast.error(t('file_upload.maximum_files_per_upload'));
      return;
    }
    setSelectedFiles([...selectedFiles, ...files]);
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(selectedFiles.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    if (selectedFiles.length === 0) {
      toast.error(t('file_upload.please_select_at_least_one_file'));
      return;
    }
    uploadFilesMutation.mutate(selectedFiles);
  };

  return (
    <ProfessionalCard variant="elevated" className="border-border/40 shadow-xl overflow-hidden">
      <div className="bg-primary/5 p-6 border-b border-primary/10">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-primary text-white shadow-lg">
            <Upload className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-lg">{t('file_upload.import_portfolio_data')}</h3>

            <p className="text-sm text-muted-foreground">{t('file_upload.upload_description')}</p>

            <p className="text-xs text-muted-foreground mt-2">{t('file_upload.processing_note')}</p>

          </div>
        </div>
      </div>

      <div className="p-8 space-y-6">
        <Alert className="border-amber-200 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            {t('file_upload.processing_note')}
          </AlertDescription>
        </Alert>

        <div className="space-y-4">
          <FileUpload
            onFilesSelected={handleFilesSelected}
            maxFiles={12}
            allowedTypes={['application/pdf', 'text/csv']}
            title={t('file_upload.select_portfolio_files')}
            maxFileSize={20}
            selectedFiles={selectedFiles}
            onRemoveFile={handleRemoveFile}
            uploading={uploadFilesMutation.isPending}
            enableCompression={false}
            enableBulkOperations={true}
            customText={{
              dragAndDrop: t('file_upload.drag_and_drop_description'),
              supports: t('file_upload.supports_info')
            }}
          />
        </div>

        {selectedFiles.length > 0 && (
          <div className="p-4 rounded-xl bg-muted/50 border border-border/50">
            <p className="text-sm font-medium text-foreground">
              {t('file_upload.ready_to_upload')}: {selectedFiles.length} {selectedFiles.length === 1 ? t('file_upload.file') : t('file_upload.files')}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t('file_upload.total_size')}: {(selectedFiles.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        )}

        <div className="flex gap-3 pt-4 border-t border-border/30">
          <ProfessionalButton
            type="button"
            variant="outline"
            className="rounded-xl px-8 h-12 flex-1"
            onClick={() => setSelectedFiles([])}
            disabled={uploadFilesMutation.isPending || selectedFiles.length === 0}
          >
            {t('file_upload.clear')}
          </ProfessionalButton>
          <ProfessionalButton
            type="button"
            variant="gradient"
            className="rounded-xl px-10 h-12 flex-1 shadow-lg shadow-primary/20"
            loading={uploadFilesMutation.isPending}
            onClick={handleSubmit}
            disabled={selectedFiles.length === 0}
          >
            {t('file_upload.upload_files')}
          </ProfessionalButton>
        </div>
      </div>
    </ProfessionalCard>
  );
};

export default FileUploadArea;
