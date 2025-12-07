import React from "react";
import { FileText, Eye, Trash } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface InvoiceAttachmentSectionProps {
  isEdit: boolean;
  invoiceAttachment: File | null;
  attachmentInfo: { has_attachment: boolean; filename?: string } | null;
  attachmentPreview: {
    open: boolean;
    url: string | null;
    contentType: string | null;
    filename: string | null;
  };
  attachmentPreviewLoading: {
    type: 'existing' | 'new';
    loading: boolean;
  };
  onFileSelect: (file: File | null) => void;
  onPreviewExisting: () => Promise<void>;
  onPreviewNew: () => Promise<void>;
  onDownload: () => Promise<void>;
  onDelete: (onUpdate?: (updatedInvoice: any) => void) => Promise<void>;
  onClosePreview: () => void;
}

export function InvoiceAttachmentSection({
  isEdit,
  invoiceAttachment,
  attachmentInfo,
  attachmentPreview,
  attachmentPreviewLoading,
  onFileSelect,
  onPreviewExisting,
  onPreviewNew,
  onDownload,
  onDelete,
  onClosePreview,
}: InvoiceAttachmentSectionProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="attachment" className="text-base font-medium">
          {t('invoices.attachment')}
        </Label>
        <div className="mt-2">
          <Input
            id="attachment"
            type="file"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            onChange={(e) => {
              const file = e.target.files?.[0];
              onFileSelect(file || null);
            }}
            className="cursor-pointer"
          />
          <p className="text-sm text-muted-foreground mt-1">
            {t('invoices.supported_formats')}: PDF, DOC, DOCX, JPG, PNG
          </p>
        </div>

        {/* Show selected attachment for new invoices */}
        {invoiceAttachment && (
          <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-blue-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-900">{invoiceAttachment.name}</p>
                <p className="text-xs text-blue-700">
                  {(invoiceAttachment.size / 1024 / 1024).toFixed(2)} MB • Ready to upload
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onFileSelect(null)}
                className="text-blue-600 hover:text-blue-800"
              >
                <Trash className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {isEdit && (
        attachmentInfo?.has_attachment ||
        attachmentInfo?.filename ||
        attachmentPreview.filename
      ) && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-4 bg-white rounded-lg border border-green-200 shadow-sm">
              <FileText className="h-5 w-5 text-green-600" />
              <div className="flex-1">
                <div className="text-sm text-gray-700 font-medium mb-1">
                  {attachmentInfo?.filename || attachmentPreview.filename}
                </div>
                <div className="text-xs text-gray-500">
                  {t('invoices.attachment_uploaded')}
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={onPreviewExisting}
                  disabled={attachmentPreviewLoading.type === 'existing' && attachmentPreviewLoading.loading}
                >
                  <Eye className="w-4 h-4 mr-2" />
                  {attachmentPreviewLoading.type === 'existing' && attachmentPreviewLoading.loading ? 'Loading...' : 'Preview'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="default"
                  onClick={onDownload}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {t('invoices.download')}
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      className="bg-red-600 hover:bg-red-700 text-white"
                    >
                      <Trash className="h-4 w-4 mr-1" />
                      {t('invoices.delete_attachment', { defaultValue: 'Delete' })}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        {t('invoices.confirm_delete_attachment_title', { defaultValue: 'Delete Attachment' })}
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('invoices.confirm_delete_attachment_description', {
                          defaultValue: 'Are you sure you want to delete this attachment? This action cannot be undone.',
                          filename: attachmentInfo?.filename || attachmentPreview.filename || 'this attachment'
                        })}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>
                        {t('common.cancel', { defaultValue: 'Cancel' })}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => onDelete()}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        {t('common.delete', { defaultValue: 'Delete' })}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </div>
        )}

      {/* Show uploaded attachment for new invoices */}
      {(() => {
        return null;
      })()}

      {/* Attachment Preview Modal */}
      <Dialog open={attachmentPreview.open} onOpenChange={(open) => {
        if (!open) onClosePreview();
      }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{attachmentPreview.filename || t('invoices.preview', { defaultValue: 'Preview' })}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto">
            {attachmentPreview.url && (attachmentPreview.contentType || '').startsWith('image/') && (
              <img src={attachmentPreview.url} alt={attachmentPreview.filename || 'attachment'} className="max-w-full h-auto" />
            )}
            {attachmentPreview.url && attachmentPreview.contentType === 'application/pdf' && (
              <iframe src={attachmentPreview.url} className="w-full h-[70vh]" title="PDF Preview" />
            )}
            {attachmentPreview.url && attachmentPreview.contentType && !((attachmentPreview.contentType || '').startsWith('image/') || attachmentPreview.contentType === 'application/pdf') && (
              <div className="text-sm text-muted-foreground">{t('invoices.preview_not_supported', { defaultValue: 'This file type cannot be previewed. Please download instead.' })}</div>
            )}
          </div>
          <div className="flex gap-2">
            {attachmentPreview.url && (
              <Button variant="outline" onClick={() => {
                const a = document.createElement('a');
                a.href = attachmentPreview.url!;
                a.download = attachmentPreview.filename || 'attachment';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
              }}>{t('invoices.download')}</Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
