import React, { useState } from "react";
import { Upload, FileText, Loader2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { apiRequest } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface InvoiceCreationChoiceProps {
  onManualCreate: (attachment?: File) => void;
  onPdfImport: (pdfData: any, pdfFile: File) => void;
}

export function InvoiceCreationChoice({ onManualCreate, onPdfImport }: InvoiceCreationChoiceProps) {
  const { t } = useTranslation();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [manualAttachment, setManualAttachment] = useState<File | null>(null);

  const checkLlmConfiguration = async () => {
    try {
      const response = await apiRequest<{ configured: boolean }>('/invoices/ai-status');
      return response.configured;
    } catch (error) {
      console.error('Failed to check LLM configuration:', error);
      return false;
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>, isManual = false) => {
    const file = event.target.files?.[0];
    if (file && file.type === 'application/pdf') {
      if (isManual) {
        setManualAttachment(file);
      } else {
        setSelectedFile(file);
      }
    } else {
      toast.error('Please select a PDF file');
    }
  };

  const processPdfImport = async () => {
    if (!selectedFile) return;

    setProcessing(true);
    try {
      // Check if LLM is configured
      const isConfigured = await checkLlmConfiguration();
      setLlmConfigured(isConfigured);

      if (!isConfigured) {
        // If LLM not configured, proceed with manual creation but attach PDF
        toast.info('LLM not configured. Proceeding with manual invoice creation with PDF attached.');
        onManualCreate(selectedFile);
        return;
        // toast.info('No stored AI config. Trying env-based model on the server...');
      }

      // Process PDF with LLM
      const formData = new FormData();
      formData.append('pdf_file', selectedFile);

      const response = await apiRequest<any>('/invoices/process-pdf', {
        method: 'POST',
        body: formData,
      });

      if (response.success) {
        toast.success('PDF processed successfully!');
        const payload = (response?.data?.invoice_data) ?? response?.data ?? response;
        onPdfImport(payload, selectedFile);
      } else {
        throw new Error(response.message || 'Failed to process PDF');
      }
    } catch (error) {
      console.error('PDF processing error:', error);
      toast.error('Failed to process PDF. Proceeding with manual creation.');
      onManualCreate(selectedFile);
    } finally {
      setProcessing(false);
    }
  };

  const handleManualCreate = () => {
    onManualCreate(manualAttachment || undefined);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold">{t('invoices.create_new_invoice')}</h2>
        <p className="text-muted-foreground">{t('invoices.choose_creation_method')}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PDF Import Option */}
        <Card className="cursor-pointer hover:shadow-lg transition-shadow">
          <CardHeader className="text-center">
            <div className="mx-auto w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
              <Upload className="w-8 h-8 text-blue-600" />
            </div>
            <CardTitle className="text-xl">{t('invoices.import_from_pdf')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground text-center">
              {t('invoices.upload_pdf_to_extract_invoice_details')}
            </p>
            
            <div className="space-y-3">
              <div>
                <Label htmlFor="pdf-upload">{t('invoices.select_pdf_file')}</Label>
                <Input
                  id="pdf-upload"
                  type="file"
                  accept=".pdf"
                  onChange={(e) => handleFileSelect(e)}
                  className="cursor-pointer"
                />
              </div>

              {selectedFile && (
                <div className="text-sm text-green-600 bg-green-50 p-2 rounded">
                  {t('invoices.selected_file')}: {selectedFile.name}
                </div>
              )}

              {llmConfigured === false && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {t('invoices.llm_not_configured_will_proceed_manually')}
                  </AlertDescription>
                </Alert>
              )}

              <Button
                onClick={processPdfImport}
                disabled={!selectedFile || processing}
                className="w-full"
              >
                {processing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {processing ? t('invoices.processing_pdf') : t('invoices.import_from_pdf')}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Manual Creation Option */}
        <Card className="cursor-pointer hover:shadow-lg transition-shadow">
          <CardHeader className="text-center">
            <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <FileText className="w-8 h-8 text-green-600" />
            </div>
            <CardTitle className="text-xl">{t('invoices.create_manually')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground text-center">
              {t('invoices.enter_invoice_details_manually')}
            </p>

            <div className="space-y-3">
              <div>
                <Label htmlFor="manual-attachment">{t('invoices.optional_attachment')}</Label>
                <Input
                  id="manual-attachment"
                  type="file"
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                  onChange={(e) => handleFileSelect(e, true)}
                  className="cursor-pointer"
                />
              </div>

              {manualAttachment && (
                <div className="text-sm text-green-600 bg-green-50 p-2 rounded">
                  {t('invoices.attachment_selected')}: {manualAttachment.name}
                </div>
              )}

              <Button
                onClick={handleManualCreate}
                className="w-full"
                variant="outline"
              >
                {t('invoices.create_manually')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}