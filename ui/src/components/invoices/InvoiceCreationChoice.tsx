import React, { useState, useEffect } from "react";
import { Upload, FileText, Loader2, AlertCircle, Package } from "lucide-react";
import { CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { apiRequest } from "@/lib/api";

import { FeatureGate } from "@/components/FeatureGate";

interface InvoiceCreationChoiceProps {
  onManualCreate: (attachment?: File) => void;
  onPdfImport: (pdfData: any, pdfFile: File) => void;
  onInventoryCreate?: () => void;
}

export function InvoiceCreationChoice({ onManualCreate, onPdfImport, onInventoryCreate }: InvoiceCreationChoiceProps) {
  const { t } = useTranslation();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [llmStatus, setLlmStatus] = useState<{ configured: boolean; config_source: string; message: string } | null>(null);
  const [manualAttachment, setManualAttachment] = useState<File | null>(null);


  const checkLlmConfiguration = async () => {
    try {
      const response = await apiRequest<{ configured: boolean; config_source: string; message: string }>('/invoices/ai-status');
      return response;
    } catch (error) {
      console.error('Failed to check LLM configuration:', error);
      return { configured: false, config_source: 'none', message: 'Failed to check configuration' };
    }
  };

  // Check AI status on component mount and log to console
  useEffect(() => {
    const checkInitialStatus = async () => {
      const status = await checkLlmConfiguration();
      console.log('AI Status:', status);
      setLlmStatus(status);
    };
    checkInitialStatus();
  }, []);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>, isManual = false) => {
    const file = event.target.files?.[0];
    if (file && file.type === 'application/pdf') {
      if (isManual) {
        setManualAttachment(file);
      } else {
        setSelectedFile(file);
      }
    } else {
      toast.error(t('invoices.please_select_pdf_file'));
    }
  };

  const processPdfImport = async () => {
    if (!selectedFile) return;

    setProcessing(true);

    // Add processing notification
    const addNotification = (window as any).addAINotification;
    const notificationId = addNotification?.('processing', t('invoices.processing_invoice_pdf'), t('invoices.analyzing_with_ai', { fileName: selectedFile.name }));

    try {
      // Check LLM configuration status
      const status = await checkLlmConfiguration();
      console.log('PDF Processing - AI Status:', status);
      setLlmStatus(status);

      // Upload PDF and get task_id
      const formData = new FormData();
      formData.append('pdf_file', selectedFile);

      const uploadResponse = await apiRequest<any>('/invoices/process-pdf', {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.success || !uploadResponse.task_id) {
        throw new Error(uploadResponse.message || 'Failed to queue PDF for processing');
      }

      const taskId = uploadResponse.task_id;
      console.log('PDF queued for processing, task_id:', taskId);

      // Poll for processing status
      const maxAttempts = 60; // 3 minutes with 3-second intervals
      let attempts = 0;

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3 seconds

        try {
          const statusResponse = await apiRequest<any>(`/invoices/process-status/${taskId}`);
          console.log('Processing status:', statusResponse.status);

          if (statusResponse.status === 'completed') {
            // Success! Extract the data
            addNotification?.('success', t('invoices.invoice_pdf_processed'), t('invoices.successfully_extracted_data', { fileName: selectedFile.name }));
            toast.success(t('invoices.pdf_processed_successfully'));

            const payload = statusResponse.data?.invoice_data || statusResponse.data;
            onPdfImport(payload, selectedFile);
            return;
          } else if (statusResponse.status === 'failed') {
            throw new Error(statusResponse.error || 'Processing failed');
          }

          // Still processing, continue polling
          attempts++;
        } catch (pollError) {
          console.error('Error polling status:', pollError);
          attempts++;
        }
      }

      // Timeout
      throw new Error('Processing timeout - please try again');

    } catch (error) {
      console.error('PDF processing error:', error);
      // Update notification to error
      addNotification?.('error', t('invoices.pdf_processing_failed'), t('invoices.failed_to_process_file', { fileName: selectedFile.name, error: error instanceof Error ? error.message : 'Unknown error' }));
      toast.error(t('invoices.failed_to_process_pdf_proceeding_manual'));
      onManualCreate(selectedFile);
    } finally {
      setProcessing(false);
    }
  };

  const handleManualCreate = () => {
    onManualCreate(manualAttachment || undefined);
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in-up">
      <div className="text-center space-y-3">
        <h2 className="text-3xl font-bold tracking-tight text-gradient-primary">
          {t('invoices.create_new_invoice')}
        </h2>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
          {t('invoices.choose_creation_method')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {/* PDF Import Option */}
        <FeatureGate feature="ai_invoice">
          <div
            className="professional-card group cursor-pointer relative overflow-hidden h-full interactive-lift"
            onClick={() => !processing && document.getElementById('pdf-upload')?.click()}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <CardContent className="p-8 space-y-6 relative z-10 flex flex-col h-full">
              <div className="mx-auto w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg shadow-blue-500/30 flex items-center justify-center transform group-hover:scale-110 transition-transform duration-300">
                <Upload className="w-10 h-10 text-white" />
              </div>

              <div className="text-center space-y-2 flex-grow">
                <h3 className="text-xl font-bold text-foreground group-hover:text-blue-600 transition-colors">
                  {t('invoices.import_from_pdf')}
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {t('invoices.upload_pdf_to_extract_invoice_details')}
                </p>
              </div>

              <div className="space-y-4 mt-auto">
                <div className="hidden">
                  <Input
                    id="pdf-upload"
                    type="file"
                    accept=".pdf"
                    onChange={(e) => handleFileSelect(e)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>

                {selectedFile ? (
                  <div className="text-sm text-primary bg-primary/10 border border-primary/30 p-3 rounded-lg flex items-center justify-center gap-2">
                    <FileText className="w-4 h-4" />
                    <span className="truncate max-w-[200px]">{selectedFile.name}</span>
                  </div>
                ) : (
                  <div className="h-[46px] flex items-center justify-center text-sm text-muted-foreground/60 border border-dashed border-border rounded-lg bg-muted/20">
                    Drag & drop or click to upload
                  </div>
                )}

                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    processPdfImport();
                  }}
                  disabled={!selectedFile || processing}
                  className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white shadow-lg shadow-blue-500/20"
                >
                  {processing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {processing ? t('invoices.processing_pdf') : t('invoices.import_from_pdf')}
                </Button>
              </div>
            </CardContent>
          </div>
        </FeatureGate>

        {/* Manual Creation Option */}
        <div
          className="professional-card group cursor-pointer relative overflow-hidden h-full interactive-lift"
          onClick={() => handleManualCreate()}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

          <CardContent className="p-8 space-y-6 relative z-10 flex flex-col h-full">
            <div className="mx-auto w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-lg shadow-emerald-500/30 flex items-center justify-center transform group-hover:scale-110 transition-transform duration-300">
              <FileText className="w-10 h-10 text-white" />
            </div>

            <div className="text-center space-y-2 flex-grow">
              <h3 className="text-xl font-bold text-foreground group-hover:text-emerald-600 transition-colors">
                {t('invoices.create_manually')}
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('invoices.quick_create_guided_create_manual_description')}
              </p>
            </div>

            <div className="space-y-4 mt-auto">
              <div onClick={(e) => e.stopPropagation()}>
                <Label htmlFor="manual-attachment" className="sr-only">{t('invoices.optional_attachment')}</Label>
                <div className="relative">
                  <Input
                    id="manual-attachment"
                    type="file"
                    accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                    onChange={(e) => handleFileSelect(e, true)}
                    className="cursor-pointer opacity-0 absolute inset-0 w-full h-full z-20"
                  />
                  <div className="h-10 w-full border border-input rounded-md bg-background flex items-center px-3 text-sm text-muted-foreground">
                    {manualAttachment ? (
                      <span className="text-success flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        {manualAttachment.name}
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <Upload className="w-4 h-4" />
                        {t('invoices.optional_attachment')}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <Button
                onClick={(e) => {
                  e.stopPropagation();
                  handleManualCreate();
                }}
                className="w-full bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-700 hover:to-emerald-800 text-white shadow-lg shadow-emerald-500/20"
              >
                {t('invoices.create_manually')}
              </Button>
            </div>
          </CardContent>
        </div>

        {/* Inventory Integration Option */}
        {onInventoryCreate && (
          <div
            className="professional-card group cursor-pointer relative overflow-hidden h-full interactive-lift"
            onClick={onInventoryCreate}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <CardContent className="p-8 space-y-6 relative z-10 flex flex-col h-full">
              <div className="mx-auto w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500 to-purple-600 shadow-lg shadow-purple-500/30 flex items-center justify-center transform group-hover:scale-110 transition-transform duration-300">
                <Package className="w-10 h-10 text-white" />
              </div>

              <div className="text-center space-y-2 flex-grow">
                <h3 className="text-xl font-bold text-foreground group-hover:text-purple-600 transition-colors">
                  {t('invoices.create_with_inventory')}
                </h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {t('invoices.inventory_catalog_description')}
                </p>
              </div>

              <div className="space-y-4 mt-auto">
                <div className="bg-purple-50/50 border border-purple-100/50 rounded-xl p-4 backdrop-blur-sm">
                  <ul className="text-xs text-purple-700 space-y-2">
                    <li className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                      {t('invoices.select_from_inventory_catalog')}
                    </li>
                    <li className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                      {t('invoices.automatic_stock_validation')}
                    </li>
                    <li className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                      {t('invoices.real_time_pricing_updates')}
                    </li>
                  </ul>
                </div>

                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    onInventoryCreate();
                  }}
                  className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white shadow-lg shadow-purple-500/20"
                >
                  <Package className="w-4 h-4 mr-2" />
                  {t('invoices.create_with_inventory')}
                </Button>
              </div>
            </CardContent>
          </div>
        )}
      </div>
    </div>
  );
}