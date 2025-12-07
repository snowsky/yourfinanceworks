import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Invoice, invoiceApi, API_BASE_URL } from "@/lib/api";

interface UseAttachmentManagementProps {
  invoice?: Invoice;
  attachment?: File | null;
  isEdit?: boolean;
}

export function useAttachmentManagement({ invoice, attachment, isEdit }: UseAttachmentManagementProps) {
  const { t } = useTranslation();

  // Attachment state
  const [invoiceAttachment, setInvoiceAttachment] = useState<File | null>(null);
  const [attachmentInfo, setAttachmentInfo] = useState<{ has_attachment: boolean, filename?: string } | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<{
    open: boolean;
    url: string | null;
    contentType: string | null;
    filename: string | null
  }>({ open: false, url: null, contentType: null, filename: null });
  const [attachmentPreviewLoading, setAttachmentPreviewLoading] = useState<{
    type: 'existing' | 'new';
    loading: boolean
  }>({ type: 'existing', loading: false });

  // Initialize attachment info when invoice changes
  useEffect(() => {
    if (invoice) {
      console.log("🔍 INITIALIZING attachmentInfo from invoice:", {
        has_attachment: invoice.has_attachment,
        attachment_filename: invoice.attachment_filename
      });
      setAttachmentInfo({
        has_attachment: invoice.has_attachment || !!invoice.attachment_filename,
        filename: invoice.attachment_filename
      });
    } else {
      setAttachmentInfo(null);
    }
  }, [invoice]);

  // Handle attachment prop changes
  useEffect(() => {
    if (attachment && !isEdit) {
      console.log("🔍 ATTACHMENT PROP CHANGED - Setting attachment:", {
        name: attachment.name,
        size: attachment.size,
        type: attachment.type
      });
      setInvoiceAttachment(attachment);
    }
  }, [attachment, isEdit]);

  // Preview existing attachment
  const previewExistingAttachment = useCallback(async () => {
    if (!invoice?.id) return;

    setAttachmentPreviewLoading({ type: 'existing', loading: true });
    try {
      const blob = await invoiceApi.previewAttachmentBlob(invoice.id);
      const url = window.URL.createObjectURL(blob);
      const filename = attachmentInfo?.filename || invoice.attachment_filename || 'attachment';
      setAttachmentPreview({ open: true, url, contentType: blob.type || null, filename });
    } catch (e) {
      console.error('Preview failed:', e);
      toast.error(t('invoices.preview_failed', { defaultValue: 'Preview failed' }));
    } finally {
      setAttachmentPreviewLoading({ type: 'existing', loading: false });
    }
  }, [invoice, attachmentInfo, t]);

  // Preview new attachment
  const previewNewAttachment = useCallback(async () => {
    if (!invoiceAttachment) return;

    setAttachmentPreviewLoading({ type: 'new', loading: true });
    try {
      const url = window.URL.createObjectURL(invoiceAttachment);
      setAttachmentPreview({
        open: true,
        url,
        contentType: invoiceAttachment.type || null,
        filename: invoiceAttachment.name
      });
    } catch (e) {
      console.error('Preview failed:', e);
      toast.error(t('invoices.preview_failed', { defaultValue: 'Preview failed' }));
    } finally {
      setAttachmentPreviewLoading({ type: 'new', loading: false });
    }
  }, [invoiceAttachment, t]);

  // Download attachment
  const downloadAttachment = useCallback(async () => {
    if (!invoice?.id) return;

    try {
      const token = localStorage.getItem('token');
      const tenantId = localStorage.getItem('selected_tenant_id') ||
        (() => {
          try {
            const user = JSON.parse(localStorage.getItem('user') || '{}');
            return user.tenant_id?.toString();
          } catch { return undefined; }
        })();

      const response = await fetch(`${API_BASE_URL}/invoices/${invoice.id}/download-attachment`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': tenantId || '1'
        }
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const downloadFilename = attachmentInfo?.filename || invoice?.attachment_filename || 'attachment';
      console.log("🔍 DOWNLOAD FILENAME:", downloadFilename);
      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Download failed:', error);
      toast.error(t('invoices.download_failed'));
    }
  }, [invoice, attachmentInfo, t]);

  // Delete attachment
  const deleteAttachment = useCallback(async (onUpdate?: (updatedInvoice: Invoice) => void) => {
    if (!invoice?.id) {
      toast.error(t('invoices.delete_failed_no_id', { defaultValue: 'Failed to delete attachment: Invoice ID not found' }));
      return;
    }

    try {
      await invoiceApi.updateInvoice(invoice.id, { attachment_filename: null });
      setAttachmentInfo(null);
      setInvoiceAttachment(null);

      if (onUpdate && invoice) {
        const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
        onUpdate(updatedInvoice);
      }

      toast.success(t('invoices.attachment_deleted', { defaultValue: 'Attachment deleted successfully' }));
    } catch (error) {
      console.error('Failed to delete attachment:', error);
      toast.error(t('invoices.delete_attachment_failed', { defaultValue: 'Failed to delete attachment' }));
    }
  }, [invoice, t]);

  // Upload attachment
  const uploadAttachment = useCallback(async (invoiceId: number) => {
    if (!invoiceAttachment) return null;

    console.log("✅ STARTING ATTACHMENT UPLOAD for invoice:", invoiceId);
    try {
      const uploadResult = await invoiceApi.uploadAttachment(invoiceId, invoiceAttachment);
      console.log("✅ UPLOAD API CALL COMPLETED - Upload result:", uploadResult);

      setAttachmentInfo({
        has_attachment: true,
        filename: uploadResult.filename
      });

      setInvoiceAttachment(null);
      toast.success("Invoice saved with attachment successfully!");

      return uploadResult;
    } catch (attachmentError) {
      console.error("❌ ATTACHMENT UPLOAD FAILED:", attachmentError);
      toast.error("Invoice saved successfully, but attachment upload failed");
      throw attachmentError;
    }
  }, [invoiceAttachment, t]);

  // Handle attachment file selection
  const handleFileSelect = useCallback((file: File | null) => {
    setInvoiceAttachment(file);
  }, []);

  // Close preview modal
  const closePreview = useCallback(() => {
    if (attachmentPreview.url) {
      URL.revokeObjectURL(attachmentPreview.url);
    }
    setAttachmentPreview({ open: false, url: null, contentType: null, filename: null });
  }, [attachmentPreview.url]);

  return {
    // State
    invoiceAttachment,
    attachmentInfo,
    attachmentPreview,
    attachmentPreviewLoading,

    // Actions
    previewExistingAttachment,
    previewNewAttachment,
    downloadAttachment,
    deleteAttachment,
    uploadAttachment,
    handleFileSelect,
    closePreview,

    // Setters
    setAttachmentInfo,
    setInvoiceAttachment,
  };
}
