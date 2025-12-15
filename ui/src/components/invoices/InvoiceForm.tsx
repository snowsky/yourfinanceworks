import React, { useState } from "react";
import { Loader2, FileText, Mail } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PDFDownloadLink } from '@react-pdf/renderer';
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

// Custom hooks
import { useInvoiceForm } from "@/hooks/useInvoiceForm";
import { useClientManagement } from "@/hooks/useClientManagement";
import { useAttachmentManagement } from "@/hooks/useAttachmentManagement";

// Sub-components
import { InvoiceClientSection } from "./InvoiceClientSection";
import { InvoiceItemsSection } from "./InvoiceItemsSection";
import { InvoiceDiscountSection } from "./InvoiceDiscountSection";
import { InvoiceAttachmentSection } from "./InvoiceAttachmentSection";

// UI Components
import { Form } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { invoiceApi, paymentApi, Invoice } from "@/lib/api";
import { InvoicePDF } from "./InvoicePDF";
import { TemplateSelector } from "./TemplateSelector";
import { apiRequest } from "@/lib/api";
import { InvoiceHistoryDetailsModal } from "./InvoiceHistoryDetailsModal";
import { getErrorMessage } from '@/lib/api';

interface InvoiceFormProps {
  invoice?: Invoice;
  isEdit?: boolean;
  onInvoiceUpdate?: (updatedInvoice: Invoice) => void;
  initialData?: any;
  attachment?: File | null;
  prefillNewClient?: { name?: string; email?: string; address?: string; phone?: string } | null;
  openNewClientOnInit?: boolean;
  renderButtons?: boolean;
  onFormSubmit?: () => Promise<void>;
  onFormCancel?: () => void;
  onClientCreated?: () => void;
  submitForApproval?: boolean;
  approverIdForApproval?: number;
  submitButtonRef?: React.RefObject<HTMLButtonElement | null>;
  onSubmitStateChange?: (isSubmitting: boolean) => void;
}

export function InvoiceForm({
  invoice,
  isEdit = false,
  onInvoiceUpdate,
  initialData,
  attachment,
  prefillNewClient,
  openNewClientOnInit,
  renderButtons = true,
  onFormSubmit,
  onFormCancel,
  onClientCreated,
  submitForApproval = false,
  approverIdForApproval,
  submitButtonRef,
  onSubmitStateChange
}: InvoiceFormProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Form state
  const [sendingEmail, setSendingEmail] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>(() => {
    return localStorage.getItem('invoice-template') || 'modern';
  });

  // Persist template selection
  React.useEffect(() => {
    localStorage.setItem('invoice-template', selectedTemplate);
  }, [selectedTemplate]);

  // Custom hooks
  const invoiceForm = useInvoiceForm({
    invoice,
    isEdit,
    initialData,
    prefillNewClient
  });

  const clientManagement = useClientManagement({
    clients: invoiceForm.clients,
    setClients: (clients) => invoiceForm.setClients(clients),
    tenantInfo: invoiceForm.tenantInfo
  });

  const attachmentManagement = useAttachmentManagement({
    invoice,
    attachment,
    isEdit
  });

  // Form submission
  const onSubmit = async (data: any) => {
    // Prevent double submission
    if (invoiceForm.submitting) {
      return;
    }

    invoiceForm.setSubmitting(true);
    onSubmitStateChange?.(true);

    // Validate after setting submitting state
    const isValid = await invoiceForm.form.trigger();
    if (!isValid) {
      toast.error("Please fix validation errors before submitting");
      invoiceForm.setSubmitting(false);
      onSubmitStateChange?.(false);
      return;
    }
    try {
      if (isEdit && invoice) {
        // Update existing invoice
        const updateData = {
          amount: invoiceForm.calculateTotal(),
          subtotal: invoiceForm.calculateSubtotal(),
          discount_type: data.discountType === "rule" && invoiceForm.appliedDiscountRule ?
            invoiceForm.appliedDiscountRule.discount_type : data.discountType,
          discount_value: data.discountType === "rule" && invoiceForm.appliedDiscountRule ?
            invoiceForm.appliedDiscountRule.discount_value : (data.discountValue || 0),
          currency: data.currency,
          due_date: data.dueDate ? data.dueDate.toISOString().split('T')[0] : '',
          notes: data.notes || "",
          status: data.status,
          client_id: Number(data.client),
          items: data.items.map((item: any) => ({
            description: item.description || '',
            quantity: Number(item.quantity) || 1,
            price: Number(item.price) || 0,
            amount: (Number(item.quantity) || 1) * (Number(item.price) || 0),
            id: item.id,
            inventory_item_id: item.inventory_item_id,
            unit_of_measure: item.unit_of_measure
          })),
          is_recurring: data.isRecurring,
          recurring_frequency: data.recurringFrequency,
          custom_fields: (data.customFields || []).reduce((acc: any, { key, value }: any) => {
            if (key?.trim()) acc[key.trim()] = value;
            return acc;
          }, {}),
          show_discount_in_pdf: data.showDiscountInPdf,
          payer: data.payer,
        };

        await invoiceApi.updateInvoice(invoice.id, updateData);

        // Handle attachment upload for updates
        if (attachmentManagement.invoiceAttachment) {
          try {
            await attachmentManagement.uploadAttachment(invoice.id);
            toast.success("Invoice updated with attachment successfully!");
          } catch {
            toast.success("Invoice updated successfully, but attachment upload failed");
          }
        } else {
          toast.success("Invoice updated successfully!");
        }

        if (onInvoiceUpdate) {
          const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
          onInvoiceUpdate(updatedInvoice);
        }

        navigate("/invoices");
      } else {
        // Create new invoice
        const invoiceData = {
          number: data.invoiceNumber || undefined,
          client_id: Number(data.client),
          date: data.date ? data.date.toISOString().split('T')[0] : '',
          due_date: data.dueDate ? data.dueDate.toISOString().split('T')[0] : '',
          amount: invoiceForm.calculateTotal(),
          subtotal: invoiceForm.calculateSubtotal(),
          discount_type: data.discountType === "rule" && invoiceForm.appliedDiscountRule ?
            invoiceForm.appliedDiscountRule.discount_type : data.discountType,
          discount_value: data.discountType === "rule" && invoiceForm.appliedDiscountRule ?
            invoiceForm.appliedDiscountRule.discount_value : (data.discountValue || 0),
          currency: data.currency,
          paid_amount: data.paidAmount || 0,
          status: data.status,
          notes: data.notes || "",
          items: data.items.map((item: any) => ({
            description: item.description || '',
            quantity: Number(item.quantity) || 1,
            price: Number(item.price) || 0,
            inventory_item_id: item.inventory_item_id,
            unit_of_measure: item.unit_of_measure
          })),
          is_recurring: data.isRecurring,
          recurring_frequency: data.recurringFrequency,
          custom_fields: (data.customFields || []).reduce((acc: any, { key, value }: any) => {
            if (key?.trim()) acc[key.trim()] = value;
            return acc;
          }, {}),
          show_discount_in_pdf: data.showDiscountInPdf,
          payer: data.payer,
        };

        const newInvoice = await invoiceApi.createInvoice(invoiceData);

        // Handle attachment upload
        if (attachmentManagement.invoiceAttachment) {
          try {
            await attachmentManagement.uploadAttachment(newInvoice.id);
            toast.success("Invoice created with attachment successfully!");
          } catch {
            toast.success("Invoice created successfully, but attachment upload failed");
          }
        } else {
          toast.success("Invoice created successfully!");
        }

        navigate("/invoices");
      }
    } catch (error) {
      console.error(`Failed to ${isEdit ? 'update' : 'create'} invoice:`, error);
      toast.error(`Failed to ${isEdit ? 'update' : 'save'} invoice`);
      invoiceForm.setSubmitting(false);
      onSubmitStateChange?.(false);
    }
  };

  // Email sending
  const sendInvoiceEmail = async () => {
    const invoiceId = invoice?.id;
    if (!invoiceId) {
      toast.error("Please save the invoice first before sending");
      return;
    }

    setSendingEmail(true);
    try {
      await apiRequest<any>('/email/send-invoice', {
        method: 'POST',
        body: JSON.stringify({
          invoice_id: invoiceId,
          include_pdf: true,
        }),
      });
      toast.success("Invoice sent successfully!");
    } catch (error) {
      console.error("Error sending invoice email:", error);
      toast.error("Failed to send invoice email");
    } finally {
      setSendingEmail(false);
    }
  };

  if (invoiceForm.loading) {
    return (
      <div className="w-full px-6 py-6">
        <div className="flex items-center justify-center h-[50vh]">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>Loading invoice data...</p>
        </div>
      </div>
    );
  }

  if (!invoiceForm.clients.length) {
    return (
      <>
        <div className="w-full px-6 py-6">
          <div className="flex flex-col items-center justify-center h-[50vh] space-y-4">
            <p className="text-lg">{t('invoices.no_clients_found')}</p>
            <Button onClick={() => clientManagement.setShowNewClientDialog(true)}>
              <FileText className="h-4 w-4 mr-2" />
              {t('invoices.add_new_client')}
            </Button>
          </div>
        </div>

        {/* Client Creation Dialog - rendered even when no clients exist */}
        <Dialog
          open={clientManagement.showNewClientDialog}
          onOpenChange={(open) => {
            clientManagement.setShowNewClientDialog(open);
            if (!open) {
              clientManagement.resetNewClientForm();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('invoices.add_new_client')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="name">{t('invoices.name')}</Label>
                <Input
                  id="name"
                  value={clientManagement.newClientForm.name}
                  onChange={(e) => clientManagement.setNewClientForm({ ...clientManagement.newClientForm, name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="email">{t('invoices.email')}</Label>
                <Input
                  id="email"
                  type="email"
                  value={clientManagement.newClientForm.email}
                  onChange={(e) => clientManagement.setNewClientForm({ ...clientManagement.newClientForm, email: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="phone">{t('invoices.phone')}</Label>
                <Input
                  id="phone"
                  value={clientManagement.newClientForm.phone || ''}
                  onChange={(e) => clientManagement.setNewClientForm({ ...clientManagement.newClientForm, phone: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="address">{t('invoices.address')}</Label>
                <Input
                  id="address"
                  value={clientManagement.newClientForm.address || ''}
                  onChange={(e) => clientManagement.setNewClientForm({ ...clientManagement.newClientForm, address: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="preferred_currency">{t('invoices.preferred_currency')}</Label>
                <CurrencySelector
                  value={clientManagement.newClientForm.preferred_currency || invoiceForm.tenantInfo?.default_currency || 'USD'}
                  onValueChange={(val) => clientManagement.setNewClientForm({ ...clientManagement.newClientForm, preferred_currency: val })}
                  placeholder={t('invoices.select_preferred_currency')}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => {
                clientManagement.setShowNewClientDialog(false);
                clientManagement.resetNewClientForm();
              }}>
                {t('invoices.cancel')}
              </Button>
              <Button onClick={clientManagement.handleCreateClient}>{t('invoices.add_client')}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  return (
    <div className="w-full px-6 py-6 space-y-6">
      {/* Global attachment indicator */}
      {attachmentManagement.invoiceAttachment && !isEdit && (
        <div className="mb-4 p-4 bg-gradient-to-r from-blue-50 to-green-50 border border-blue-200 rounded-lg shadow-sm">
          <div className="flex items-center gap-3">
            <FileText className="h-6 w-6 text-blue-600" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-gray-900">
                📄 PDF Uploaded Successfully
              </h4>
              <p className="text-sm text-gray-600">
                <span className="font-medium">{attachmentManagement.invoiceAttachment.name}</span>
              </p>
            </div>
          </div>
        </div>
      )}

      <Card className="pt-6">
        <CardContent>
          <Form {...invoiceForm.form}>
            <form onSubmit={invoiceForm.form.handleSubmit(onSubmit, (errors) => {
              console.error("Form validation errors:", errors);
              toast.error("Please fix validation errors before submitting");
              invoiceForm.setSubmitting(false);
            })} className="space-y-8">

              {/* Client Section */}
              <InvoiceClientSection
                form={invoiceForm.form}
                clients={invoiceForm.clients}
                isEdit={isEdit}
                isInvoicePaid={false}
                tenantInfo={invoiceForm.tenantInfo}
                showNewClientDialog={clientManagement.showNewClientDialog}
                setShowNewClientDialog={clientManagement.setShowNewClientDialog}
                newClientForm={clientManagement.newClientForm}
                setNewClientForm={clientManagement.setNewClientForm}
                resetNewClientForm={clientManagement.resetNewClientForm}
                handleCreateClient={clientManagement.handleCreateClient}
              />

              {/* Items Section */}
              <InvoiceItemsSection
                form={invoiceForm.form}
                isEdit={isEdit}
                isInvoicePaid={false}
                submitting={invoiceForm.submitting}
                itemKeyCounter={0}
                setItemKeyCounter={() => { }}
              />

              {/* Discount Section */}
              <InvoiceDiscountSection
                form={invoiceForm.form}
                isEdit={isEdit}
                isInvoicePaid={false}
                availableDiscountRules={invoiceForm.availableDiscountRules}
                appliedDiscountRule={invoiceForm.appliedDiscountRule}
                calculateSubtotal={invoiceForm.calculateSubtotal}
                calculateDiscount={invoiceForm.calculateDiscount}
                calculateTotal={invoiceForm.calculateTotal}
                applyDiscountRule={invoiceForm.applyDiscountRule}
              />

              {/* Attachment Section */}
              <InvoiceAttachmentSection
                isEdit={isEdit}
                invoiceAttachment={attachmentManagement.invoiceAttachment}
                attachmentInfo={attachmentManagement.attachmentInfo}
                attachmentPreview={attachmentManagement.attachmentPreview}
                attachmentPreviewLoading={attachmentManagement.attachmentPreviewLoading}
                onFileSelect={attachmentManagement.handleFileSelect}
                onPreviewExisting={attachmentManagement.previewExistingAttachment}
                onPreviewNew={attachmentManagement.previewNewAttachment}
                onDownload={attachmentManagement.downloadAttachment}
                onDelete={attachmentManagement.deleteAttachment}
                onClosePreview={attachmentManagement.closePreview}
              />

              {/* Form Actions */}
              {renderButtons && (
                <div className="flex justify-end gap-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onFormCancel ? onFormCancel() : navigate('/invoices')}
                  >
                    {t('invoices.cancel')}
                  </Button>
                  <Button
                    type="submit"
                    disabled={invoiceForm.submitting}
                  >
                    {invoiceForm.submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {isEdit ? t('invoices.update_invoice') : t('invoices.create_invoice')}
                  </Button>
                </div>
              )}

              {/* Hidden submit button for external triggering */}
              <button type="submit" style={{ display: 'none' }} ref={submitButtonRef} />
            </form>
          </Form>
        </CardContent>
      </Card>

      {/* Client Creation Dialog */}
      <Dialog
        open={clientManagement.showNewClientDialog}
        onOpenChange={(open) => {
          clientManagement.setShowNewClientDialog(open);
          if (!open) {
            clientManagement.resetNewClientForm();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('invoices.add_new_client')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <input
                className="w-full p-2 border rounded"
                value={clientManagement.newClientForm.name}
                onChange={(e) => clientManagement.setNewClientForm({
                  ...clientManagement.newClientForm,
                  name: e.target.value
                })}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Email</label>
              <input
                className="w-full p-2 border rounded"
                type="email"
                value={clientManagement.newClientForm.email}
                onChange={(e) => clientManagement.setNewClientForm({
                  ...clientManagement.newClientForm,
                  email: e.target.value
                })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              clientManagement.setShowNewClientDialog(false);
              clientManagement.resetNewClientForm();
            }}>
              {t('invoices.cancel')}
            </Button>
            <Button onClick={clientManagement.handleCreateClient}>
              {t('invoices.add_client')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Attachment Preview Modal */}
      <Dialog
        open={attachmentManagement.attachmentPreview.open}
        onOpenChange={(open) => {
          if (!open) attachmentManagement.closePreview();
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              {attachmentManagement.attachmentPreview.filename || t('invoices.preview')}
            </DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto">
            {attachmentManagement.attachmentPreview.url &&
              (attachmentManagement.attachmentPreview.contentType || '').startsWith('image/') && (
                <img
                  src={attachmentManagement.attachmentPreview.url}
                  alt={attachmentManagement.attachmentPreview.filename || 'attachment'}
                  className="max-w-full h-auto"
                />
              )}
            {attachmentManagement.attachmentPreview.url &&
              attachmentManagement.attachmentPreview.contentType === 'application/pdf' && (
                <iframe
                  src={attachmentManagement.attachmentPreview.url}
                  className="w-full h-[70vh]"
                  title="PDF Preview"
                />
              )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
