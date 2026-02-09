import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { FileUpload, FileData } from '@/components/ui/file-upload';
import { apiRequest } from '@/lib/api';
import { toast } from 'sonner';
import { Upload, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface FileUploadDialogProps {
  portfolioId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploadSuccess?: () => void;
}

const FileUploadDialog: React.FC<FileUploadDialogProps> = ({
  portfolioId,
  open,
  onOpenChange,
  onUploadSuccess,
}) => {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
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
      onOpenChange(false);
      onUploadSuccess?.();
    },
    onError: (error: any) => {
      const errorMessage = error?.message || t('Failed to upload files');
      toast.error(errorMessage);
    },
  });

  const handleFilesSelected = (files: FileData[]) => {
    if (files.length + selectedFiles.length > 12) {
      toast.error(t('Maximum 12 files per upload'));
      return;
    }
    setSelectedFiles([...selectedFiles, ...files]);
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(selectedFiles.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    if (selectedFiles.length === 0) {
      toast.error(t('Please select at least one file'));
      return;
    }
    uploadFilesMutation.mutate(selectedFiles);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] rounded-3xl p-0 overflow-hidden border-border/40 shadow-2xl">
        <DialogHeader className="p-8 bg-primary/5 border-b border-primary/10">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-primary text-white shadow-lg">
              <Upload className="w-6 h-6" />
            </div>
            <div>
              <DialogTitle className="text-2xl font-bold tracking-tight">
                {t('Upload Holdings Files')}
              </DialogTitle>
              <DialogDescription className="text-muted-foreground pt-1">
                {t('Upload PDF or CSV files containing your investment holdings data.')}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="p-8 space-y-6">
          <Alert className="border-amber-200 bg-amber-50">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              {t('Files will be processed in the background. You can track the status in the file attachments list.')}
            </AlertDescription>
          </Alert>

          <div className="space-y-4">
            <FileUpload
              onFilesSelected={handleFilesSelected}
              maxFiles={12}
              allowedTypes={['application/pdf', 'text/csv']}
              title={t('Select Holdings Files')}
              maxFileSize={20}
              selectedFiles={selectedFiles}
              onRemoveFile={handleRemoveFile}
              uploading={uploadFilesMutation.isPending}
              enableCompression={false}
              enableBulkOperations={true}
            />
          </div>

          {selectedFiles.length > 0 && (
            <div className="p-4 rounded-xl bg-muted/50 border border-border/50">
              <p className="text-sm font-medium text-foreground">
                {t('Ready to upload')}: {selectedFiles.length} {selectedFiles.length === 1 ? t('file') : t('files')}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {t('Total size')}: {(selectedFiles.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="p-8 border-t border-border/30 gap-3 sm:gap-0">
          <ProfessionalButton
            type="button"
            variant="outline"
            className="rounded-xl px-8 h-12 flex-1"
            onClick={() => {
              setSelectedFiles([]);
              onOpenChange(false);
            }}
            disabled={uploadFilesMutation.isPending}
          >
            {t('Cancel')}
          </ProfessionalButton>
          <ProfessionalButton
            type="button"
            variant="gradient"
            className="rounded-xl px-10 h-12 flex-1 shadow-lg shadow-primary/20"
            loading={uploadFilesMutation.isPending}
            onClick={handleSubmit}
            disabled={selectedFiles.length === 0}
          >
            {t('Upload Files')}
          </ProfessionalButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default FileUploadDialog;
