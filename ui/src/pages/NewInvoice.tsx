import React, { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { InvoiceForm } from "@/components/invoices/InvoiceForm";
import { InvoiceCreationChoice } from "@/components/invoices/InvoiceCreationChoice";
import { InventoryInvoiceForm } from "@/components/inventory/InventoryInvoiceForm";
import { useTranslation } from "react-i18next";
import { useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";

const NewInvoice = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [showInventoryForm, setShowInventoryForm] = useState(false);
  const [initialData, setInitialData] = useState<any>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [prefillNewClient, setPrefillNewClient] = useState<{ name?: string; email?: string; address?: string; phone?: string } | null>(null);
  const [openNewClientOnInit, setOpenNewClientOnInit] = useState(false);

  // Handle bank statement pre-population
  useEffect(() => {
    const fromBankStatement = searchParams.get('from_bank_statement');
    if (fromBankStatement === 'true') {
      const date = searchParams.get('date');
      const dueDate = searchParams.get('due_date');
      const amount = searchParams.get('amount');
      const paidAmount = searchParams.get('paid_amount');
      const status = searchParams.get('status');
      const description = searchParams.get('description');
      const notes = searchParams.get('notes');

      // Normalize YYYY-MM-DD from query as UTC midnight to avoid off-by-one
      const parseDateOnly = (s: string | null) => {
        if (!s) return new Date();
        const m = s.match(/^\d{4}-(\d{2})-(\d{2})$/);
        if (m) {
          const [y, mth, d] = s.split('-').map(n => parseInt(n, 10));
          return new Date(Date.UTC(y, mth - 1, d));
        }
        return new Date(s);
      };
      const parsedDate = parseDateOnly(date);
      const parsedDueDate = parseDateOnly(dueDate);
      console.log('Bank statement dates:', { date, dueDate, parsedDate, parsedDueDate });
      
      setInitialData({
        date: parsedDate,
        dueDate: parsedDueDate,
        status: status || 'paid',
        paidAmount: paidAmount ? parseFloat(paidAmount) : 0,
        notes: notes || '',
        items: [{
          description: description || '',
          quantity: 1,
          price: amount ? parseFloat(amount) : 0,
        }],
        client: '' // Initialize client field
      });
      setShowForm(true);
      toast.success('Invoice pre-populated from bank statement');
    }
  }, [searchParams]);

  const handleManualCreate = (attachmentFile?: File) => {
    setAttachment(attachmentFile || null);
    setShowForm(true);
  };

  const handleInventoryCreate = () => {
    navigate('/invoices/new-inventory');
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
        // Prefill and open create client modal in the form
        const suggested = pdfData.suggested_client || {};
        setPrefillNewClient({
          name: suggested.name || '',
          email: suggested.email || '',
          address: suggested.address || '',
          phone: ''
        });
        setOpenNewClientOnInit(true);
        toast.success('Suggested client detected. Opening create client dialog...');
      }

      // Prepare initial data from PDF extraction
      const invoiceData = pdfData.invoice_data || pdfData;
      const formattedItems = invoiceData?.items?.map((item: any) => ({
        description: item.description || '',
        quantity: item.quantity || 1,
        price: item.price || 0,
      })) || [{ description: '', quantity: 1, price: 0 }];

      setInitialData({
        client: clientId?.toString() || '',
        items: formattedItems,
        notes: `Imported from PDF: ${pdfFile.name}`,
        date: invoiceData?.date ? new Date(invoiceData.date) : new Date(),
      });
      
      setAttachment(pdfFile);
      setShowForm(true);
      
    } catch (error) {
      console.error('Error processing PDF import:', error);
      toast.error('Failed to process PDF import');
    }
  };

  if (showForm) {
    const fromBankStatement = searchParams.get('from_bank_statement') === 'true';
    return (
      <AppLayout>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
            <p className="text-muted-foreground">
              {fromBankStatement ? 'Create invoice from bank statement transaction' : 'Choose between Quick Create for fast entry or Guided Create for step-by-step assistance'}
            </p>
          </div>
          
          <div className="slide-in">
            <InvoiceForm 
              initialData={initialData}
              attachment={attachment}
              prefillNewClient={prefillNewClient}
              openNewClientOnInit={openNewClientOnInit}
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
            onInventoryCreate={handleInventoryCreate}
          />
        </div>
      </div>
    </AppLayout>
  );
};

export default NewInvoice;
