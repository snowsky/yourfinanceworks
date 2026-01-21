import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Invoice, invoiceApi, API_BASE_URL, InvoiceAttachmentMeta } from "@/lib/api";

interface UseAttachmentManagementProps {
  invoice?: Invoice;
  attachment?: File | null;
  isEdit?: boolean;
}

export function useAttachmentManagement({ invoice, attachment, isEdit }: UseAttachmentManagementProps) {
  const { t } = useTranslation();

  // Attachment state
  const [invoiceAttachments, setInvoiceAttachments] = useState<File[]>([]);
  const [existingAttachments, setExistingAttachments] = useState<InvoiceAttachmentMeta[]>([]);
  const [attachmentPreview, setAttachmentPreview] = useState<{
    open: boolean;
    url: string | null;
    contentType: string | null;
    filename: string | null;
  }>({ open: false, url: null, contentType: null, filename: null });
  const [attachmentPreviewLoading, setAttachmentPreviewLoading] = useState<{
    id: number | string | null;
    loading: boolean;
  }>({ id: null, loading: false });

  const [isUploading, setIsUploading] = useState(false);

  // Initialize from invoice
  useEffect(() => {
    if (invoice?.attachments) {
      setExistingAttachments(invoice.attachments);
    } else {
      setExistingAttachments([]);
    }
  }, [invoice]);

  // Handle attachment prop (for new invoices with initial attachment)
  useEffect(() => {
    if (attachment && !isEdit && invoiceAttachments.length === 0) {
      setInvoiceAttachments([attachment]);
    }
  }, [attachment, isEdit, invoiceAttachments.length]);

  // Preview existing attachment
  const previewExistingAttachment = useCallback(async (attachmentId: number) => {
    if (!invoice?.id) return;

    setAttachmentPreviewLoading({ id: attachmentId, loading: true });
    try {
      const blob = await invoiceApi.previewAttachmentBlob(invoice.id, attachmentId);
      const url = window.URL.createObjectURL(blob);
      const att = existingAttachments.find(a => a.id === attachmentId);
      const filename = att?.filename || 'attachment';
      setAttachmentPreview({ open: true, url, contentType: blob.type || null, filename });
    } catch (e) {
      console.error('Preview failed:', e);
      toast.error(t('invoices.preview_failed', { defaultValue: 'Preview failed' }));
    } finally {
      setAttachmentPreviewLoading({ id: null, loading: false });
    }
  }, [invoice?.id, existingAttachments, t]);

  // Preview new attachment
  const previewNewAttachment = useCallback(async (index: number) => {
    const file = invoiceAttachments[index];
    if (!file) return;

    setAttachmentPreviewLoading({ id: `new-${index}`, loading: true });
    try {
      const url = window.URL.createObjectURL(file);
      setAttachmentPreview({
        open: true,
        url,
        contentType: file.type || null,
        filename: file.name
      });
    } catch (e) {
      console.error('Preview failed:', e);
      toast.error(t('invoices.preview_failed', { defaultValue: 'Preview failed' }));
    } finally {
      setAttachmentPreviewLoading({ id: null, loading: false });
    }
  }, [invoiceAttachments, t]);

  // Download attachment
  const downloadAttachment = useCallback(async (attachmentId: number) => {
    if (!invoice?.id) return;
    invoiceApi.downloadAttachment(invoice.id, attachmentId);
  }, [invoice?.id]);

  // Delete existing attachment
  const deleteAttachment = useCallback(async (attachmentId: number, onUpdate?: (updatedInvoice: Invoice) => void) => {
    if (!invoice?.id) return;

    try {
      await invoiceApi.deleteAttachment(invoice.id, attachmentId);
      setExistingAttachments(prev => prev.filter(a => a.id !== attachmentId));

      if (onUpdate) {
        const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
        onUpdate(updatedInvoice);
      }

      toast.success(t('invoices.attachment_deleted', { defaultValue: 'Attachment deleted successfully' }));
    } catch (error) {
      console.error('Failed to delete attachment:', error);
      toast.error(t('invoices.delete_attachment_failed', { defaultValue: 'Failed to delete attachment' }));
    }
  }, [invoice?.id, t]);

  // Upload all attachments
  const uploadAttachments = useCallback(async (invoiceId: number) => {
    if (invoiceAttachments.length === 0) return [];

    setIsUploading(true);
    console.log("✅ STARTING ATTACHMENTS UPLOAD for invoice:", invoiceId);
    const results = [];
    for (const file of invoiceAttachments) {
      try {
        const result = await invoiceApi.uploadAttachment(invoiceId, file);
        results.push(result);
      } catch (error) {
        console.error(`❌ ATTACHMENT UPLOAD FAILED for ${file.name}:`, error);
        toast.error(`Failed to upload ${file.name}`);
      }
    }

    setInvoiceAttachments([]);
    setIsUploading(false);
    if (results.length > 0) {
      toast.success(t('invoices.attachments_uploaded', { count: results.length, defaultValue: 'Attachments uploaded successfully' }));
    }
    return results;
  }, [invoiceAttachments, t]);

  // Add file(s)
  const addFiles = useCallback((files: FileList | File[] | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setInvoiceAttachments(prev => [...prev, ...newFiles]);
  }, []);

  // Remove new file
  const removeNewFile = useCallback((index: number) => {
    setInvoiceAttachments(prev => prev.filter((_, i) => i !== index));
  }, []);

  // Close preview
  const closePreview = useCallback(() => {
    if (attachmentPreview.url) {
      URL.revokeObjectURL(attachmentPreview.url);
    }
    setAttachmentPreview({ open: false, url: null, contentType: null, filename: null });
  }, [attachmentPreview.url]);

  return {
    invoiceAttachments,
    existingAttachments,
    attachmentPreview,
    attachmentPreviewLoading,
    isUploading,
    previewExistingAttachment,
    previewNewAttachment,
    downloadAttachment,
    deleteAttachment,
    uploadAttachments,
    addFiles,
    removeNewFile,
    closePreview,
  };
}
