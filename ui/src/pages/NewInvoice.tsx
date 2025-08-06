import React, { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { InvoiceForm } from "@/components/invoices/InvoiceForm";
import { InvoiceCreationChoice } from "@/components/invoices/InvoiceCreationChoice";
import { useTranslation } from "react-i18next";
import { clientApi } from "@/lib/api";
import { toast } from "sonner";

const NewInvoice = () => {
  const { t } = useTranslation();
  const [showForm, setShowForm] = useState(false);
  const [initialData, setInitialData] = useState<any>(null);
  const [attachment, setAttachment] = useState<File | null>(null);

  const handleManualCreate = (attachmentFile?: File) => {
    setAttachment(attachmentFile || null);
    setShowForm(true);
  };

  const handlePdfImport = async (pdfData: any, pdfFile: File) => {
    try {
      let clientId = null;
      
      // Check if client exists or create new one
      if (pdfData.client_exists && pdfData.existing_client) {
        // Use existing client
        clientId = pdfData.existing_client.id;
        toast.success(`Using existing client: ${pdfData.existing_client.name}`);
      } else if (!pdfData.client_exists && pdfData.suggested_client) {
        // Create new client
        const newClient = await clientApi.createClient({
          name: pdfData.suggested_client.name,
          email: pdfData.suggested_client.email || '',
          phone: '',
          address: pdfData.suggested_client.address || '',
          preferred_currency: 'USD',
          balance: 0,
          paid_amount: 0,
        });
        clientId = newClient.id;
        toast.success(`Created new client: ${newClient.name}`);
      }

      // Prepare initial data from PDF extraction
      const invoiceData = pdfData.invoice_data;
      const formattedItems = invoiceData.items?.map((item: any) => ({
        description: item.description || '',
        quantity: item.quantity || 1,
        price: item.price || 0,
      })) || [{ description: '', quantity: 1, price: 0 }];

      setInitialData({
        client: clientId?.toString() || '',
        items: formattedItems,
        notes: `Imported from PDF: ${pdfFile.name}`,
        date: invoiceData.date ? new Date(invoiceData.date) : new Date(),
      });
      
      setAttachment(pdfFile);
      setShowForm(true);
      
    } catch (error) {
      console.error('Error processing PDF import:', error);
      toast.error('Failed to process PDF import');
    }
  };

  if (showForm) {
    return (
      <AppLayout>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
            <p className="text-muted-foreground">{t("invoices.description")}</p>
          </div>
          
          <div className="slide-in">
            <InvoiceForm 
              initialData={initialData}
              attachment={attachment}
            />
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
          <p className="text-muted-foreground">Import invoice from PDF file</p>
        </div>
        
        <div className="slide-in">
          <InvoiceCreationChoice
            onManualCreate={handleManualCreate}
            onPdfImport={handlePdfImport}
          />
        </div>
      </div>
    </AppLayout>
  );
};

export default NewInvoice;
