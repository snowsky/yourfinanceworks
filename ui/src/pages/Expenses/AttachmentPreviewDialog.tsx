import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { expenseApi, type ExpenseAttachmentMeta } from '@/lib/api';
import type { PreviewState, AttachmentPreviewState } from './types';

interface AttachmentPreviewDialogProps {
  attachmentPreviewOpen: AttachmentPreviewState;
  setAttachmentPreviewOpen: (state: AttachmentPreviewState) => void;
  attachments: Record<number, ExpenseAttachmentMeta[]>;
  preview: PreviewState;
  setPreview: (state: PreviewState) => void;
  previewLoading: { expenseId: number; attachmentId: number } | null;
  setPreviewLoading: (state: { expenseId: number; attachmentId: number } | null) => void;
}

export function AttachmentPreviewDialog({
  attachmentPreviewOpen,
  setAttachmentPreviewOpen,
  attachments,
  preview,
  setPreview,
  previewLoading,
  setPreviewLoading,
}: AttachmentPreviewDialogProps) {
  const { t } = useTranslation();

  return (
    <>
      {/* Attachment Preview Dialog */}
      <Dialog open={!!attachmentPreviewOpen.expenseId} onOpenChange={(o) => !o && setAttachmentPreviewOpen({ expenseId: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('expenses.attachments')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {(attachments[attachmentPreviewOpen.expenseId || -1] || []).length === 0 ? (
              <div className="text-sm text-muted-foreground">{t('expenses.no_attachments')}</div>
            ) : (
              <ul className="space-y-2">
                {(attachments[attachmentPreviewOpen.expenseId || -1] || []).map((att) => (
                  <li key={att.id} className="flex items-center justify-between gap-3 border rounded p-2">
                    <div className="truncate text-sm">
                      {att.filename}
                      {att.file_size ? <span className="ml-2 text-xs text-muted-foreground">({Math.round(att.file_size / 1024)} KB)</span> : null}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          if (!attachmentPreviewOpen.expenseId) return;
                          setPreviewLoading({ expenseId: attachmentPreviewOpen.expenseId, attachmentId: att.id });
                          try {
                            const { blob, contentType } = await expenseApi.downloadAttachmentBlob(attachmentPreviewOpen.expenseId, att.id);
                            const url = URL.createObjectURL(blob);
                            setPreview({ open: true, url, contentType: contentType || att.content_type || null, filename: att.filename || null });
                          } finally {
                            setPreviewLoading(null);
                          }
                        }}
                        disabled={previewLoading?.expenseId === attachmentPreviewOpen.expenseId && previewLoading?.attachmentId === att.id}
                      >
                        {previewLoading?.expenseId === attachmentPreviewOpen.expenseId && previewLoading?.attachmentId === att.id ? (
                          <>
                            <div className="w-4 h-4 mr-1 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            Loading...
                          </>
                        ) : (
                          t('expenses.preview')
                        )}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* File inline preview dialog */}
      <Dialog open={preview.open} onOpenChange={(o) => {
        if (!o && preview.url) URL.revokeObjectURL(preview.url);
        setPreview({ open: o, url: o ? preview.url : null, contentType: o ? preview.contentType : null, filename: o ? preview.filename : null });
      }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{preview.filename || t('expenses.preview', { defaultValue: 'Preview' })}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto">
            {preview.url && (preview.contentType || '').startsWith('image/') && (
              <img src={preview.url} alt={preview.filename || 'attachment'} className="max-w-full h-auto" />
            )}
            {preview.url && preview.contentType === 'application/pdf' && (
              <iframe src={preview.url} className="w-full h-[70vh]" title={t('expenses.pdf_preview', { defaultValue: 'PDF Preview' })} />
            )}
            {preview.url && preview.contentType && !((preview.contentType || '').startsWith('image/') || preview.contentType === 'application/pdf') && (
              <div className="text-sm text-muted-foreground">{t('expenses.cannot_preview', { defaultValue: 'This file type cannot be previewed. Please download instead.' })}</div>
            )}
          </div>
          <div className="flex gap-2">
            {preview.url && (
              <Button variant="outline" onClick={() => {
                if (!preview.url) return;
                const a = document.createElement('a');
                a.href = preview.url;
                a.download = preview.filename || 'attachment';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
              }}>{t('expenses.download')}</Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
