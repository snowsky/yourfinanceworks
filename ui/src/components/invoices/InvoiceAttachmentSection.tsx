import React from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton, ButtonGroup } from "@/components/ui/professional-button";
import { Paperclip, Download, CloudUpload, AlertCircle, FileText, Eye, Trash, Plus } from "lucide-react";
import { InvoiceAttachmentMeta } from "@/lib/api";

interface InvoiceAttachmentSectionProps {
  isEdit: boolean;
  invoiceAttachments: File[];
  existingAttachments: InvoiceAttachmentMeta[];
  attachmentPreview: {
    open: boolean;
    url: string | null;
    contentType: string | null;
    filename: string | null;
  };
  attachmentPreviewLoading: {
    id: number | string | null;
    loading: boolean;
  };
  onAddFiles: (files: FileList | null) => void;
  onRemoveNewFile: (index: number) => void;
  onPreviewExisting: (id: number) => Promise<void>;
  onPreviewNew: (index: number) => Promise<void>;
  onDownload: (id: number) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onClosePreview: () => void;
}

export function InvoiceAttachmentSection({
  isEdit,
  invoiceAttachments,
  existingAttachments,
  attachmentPreview,
  attachmentPreviewLoading,
  onAddFiles,
  onRemoveNewFile,
  onPreviewExisting,
  onPreviewNew,
  onDownload,
  onDelete,
  onClosePreview,
}: InvoiceAttachmentSectionProps) {
  const { t } = useTranslation();

  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-amber-100 dark:bg-amber-900/30 rounded-xl">
            <Paperclip className="h-6 w-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.attachments', 'Attachments')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('invoices.attachment_section_description', 'Upload and manage files related to this invoice.')}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-8">
        <div
          className="relative group border-2 border-dashed border-border/50 rounded-3xl p-10 text-center hover:bg-muted/10 hover:border-primary/30 transition-all duration-300"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            onAddFiles(e.dataTransfer.files);
          }}
        >
          <Input
            id="attachment"
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
            onChange={(e) => onAddFiles(e.target.files)}
            className="hidden"
          />
          <Label
            htmlFor="attachment"
            className="cursor-pointer flex flex-col items-center gap-4"
          >
            <div className="p-5 bg-primary/5 rounded-full group-hover:scale-110 transition-transform duration-300">
              <CloudUpload className="h-10 w-10 text-primary/60" />
            </div>
            <div>
              <p className="text-lg font-bold text-foreground mb-1">
                {t('invoices.click_or_drag_to_upload', 'Click or drag to upload')}
              </p>
              <p className="text-sm text-muted-foreground">
                {t('invoices.supported_formats_limit', 'PDF, DOC, DOCX, JPG, PNG (Max 10MB)')}
              </p>
            </div>
          </Label>
        </div>

        {/* Selected Files (New) */}
        {invoiceAttachments.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider px-2">
              {t('invoices.new_attachments', 'New Attachments')}
            </h3>
            {invoiceAttachments.map((file, index) => (
              <div key={`new-${index}`} className="p-4 rounded-2xl bg-primary/5 border border-primary/20 animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-primary/10 rounded-xl">
                    <FileText className="h-6 w-6 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-foreground truncate">{file.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                        {t('invoices.ready_to_upload', 'Ready to upload')}
                      </span>
                      <span className="text-xs text-muted-foreground italic">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <ProfessionalButton
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => onPreviewNew(index)}
                      loading={attachmentPreviewLoading.id === `new-${index}` && attachmentPreviewLoading.loading}
                      className="text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-xl"
                    >
                      <Eye className="h-4 w-4" />
                    </ProfessionalButton>
                    <ProfessionalButton
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => onRemoveNewFile(index)}
                      className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl"
                    >
                      <Trash className="h-4 w-4" />
                    </ProfessionalButton>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Existing Attachments */}
        {existingAttachments.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider px-2">
              {t('invoices.existing_attachments', 'Existing Attachments')}
            </h3>
            <div className="grid grid-cols-1 gap-4">
              {existingAttachments.map((att) => (
                <div key={att.id} className="p-6 rounded-3xl bg-secondary/30 border border-border/50 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
                  <div className="flex flex-col md:flex-row items-center gap-6">
                    <div className="p-4 bg-emerald-100 dark:bg-emerald-900/30 rounded-2xl">
                      <FileText className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
                    </div>

                    <div className="flex-1 text-center md:text-left min-w-0">
                      <h4 className="text-lg font-bold text-foreground truncate">
                        {att.filename}
                      </h4>
                      <div className="flex items-center justify-center md:justify-start gap-4 mt-1 italic text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />
                          {t('invoices.attachment_uploaded')}
                        </span>
                        <span>
                          {(att.file_size / 1024 / 1024).toFixed(2)} MB
                        </span>
                      </div>
                    </div>

                    <ButtonGroup size="sm">
                      <ProfessionalButton
                        type="button"
                        variant="outline"
                        onClick={() => onPreviewExisting(att.id)}
                        loading={attachmentPreviewLoading.id === att.id && attachmentPreviewLoading.loading}
                        leftIcon={<Eye className="w-4 h-4" />}
                      >
                        {t('common.preview', 'Preview')}
                      </ProfessionalButton>

                      <ProfessionalButton
                        type="button"
                        variant="outline"
                        onClick={() => onDownload(att.id)}
                        leftIcon={<Download className="w-4 h-4" />}
                      >
                        {t('invoices.download')}
                      </ProfessionalButton>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <ProfessionalButton
                            type="button"
                            variant="ghost"
                            className="text-destructive hover:bg-destructive/10"
                            leftIcon={<Trash className="h-4 w-4" />}
                          >
                            {t('common.delete')}
                          </ProfessionalButton>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="rounded-3xl">
                          <AlertDialogHeader>
                            <AlertDialogTitle className="text-2xl font-black">
                              {t('invoices.delete_attachment_confirm_title', 'Delete Attachment?')}
                            </AlertDialogTitle>
                            <AlertDialogDescription className="text-base">
                              {t('invoices.delete_attachment_confirm_desc', 'This will permanently remove the attachment. This action cannot be undone.')}
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter className="mt-4 gap-3">
                            <AlertDialogCancel className="rounded-xl">{t('common.cancel')}</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(att.id)}
                              className="bg-destructive hover:bg-destructive/90 rounded-xl px-6"
                            >
                              {t('common.delete')}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </ButtonGroup>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Attachment Preview Modal */}
      <Dialog open={attachmentPreview.open} onOpenChange={(open) => {
        if (!open) onClosePreview();
      }}>
        <DialogContent className="max-w-4xl rounded-3xl overflow-hidden border-0 shadow-2xl p-0">
          <DialogHeader className="p-6 bg-muted/30 border-b border-border/50">
            <DialogTitle className="flex items-center gap-3 text-xl font-black">
              <div className="p-2 bg-primary/10 rounded-lg">
                <FileText className="h-5 w-5 text-primary" />
              </div>
              {attachmentPreview.filename || t('invoices.preview')}
            </DialogTitle>
          </DialogHeader>

          <div className="bg-background/50 backdrop-blur-xl p-4 min-h-[50vh] flex items-center justify-center">
            {attachmentPreview.url && (attachmentPreview.contentType || '').startsWith('image/') && (
              <img
                src={attachmentPreview.url}
                alt={attachmentPreview.filename || 'attachment'}
                className="max-w-full max-h-[70vh] rounded-xl shadow-lg border border-border/50 object-contain"
              />
            )}
            {attachmentPreview.url && attachmentPreview.contentType === 'application/pdf' && (
              <iframe
                src={attachmentPreview.url}
                className="w-full h-[70vh] rounded-xl border border-border/50 shadow-inner"
                title="PDF Preview"
              />
            )}
            {attachmentPreview.url && attachmentPreview.contentType && !((attachmentPreview.contentType || '').startsWith('image/') || attachmentPreview.contentType === 'application/pdf') && (
              <div className="text-center p-8 bg-muted/20 rounded-2xl border border-dashed border-border/50">
                <AlertCircle className="h-12 w-12 text-muted-foreground/40 mx-auto mb-4" />
                <h3 className="text-lg font-bold text-foreground mb-1">{t('invoices.preview_not_available')}</h3>
                <p className="text-sm text-muted-foreground">
                  {t('invoices.preview_not_supported_desc', 'This file type cannot be previewed. Please download it to view.')}
                </p>
              </div>
            )}
          </div>

          {attachmentPreview.url && (
            <div className="p-6 bg-muted/30 border-t border-border/50 flex justify-end">
              <ProfessionalButton
                variant="gradient"
                onClick={() => {
                  const a = document.createElement('a');
                  a.href = attachmentPreview.url!;
                  a.download = attachmentPreview.filename || 'attachment';
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                }}
                leftIcon={<Download className="h-4 w-4" />}
              >
                {t('invoices.download')}
              </ProfessionalButton>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </ProfessionalCard>
  );
}
