import { useState, useEffect, useRef } from 'react';
import { InvoiceForm } from './InvoiceForm';
import { Invoice, clientApi, approvalApi } from '@/lib/api';
import { Loader2, AlertCircle, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface InvoiceFormWithApprovalProps {
  invoice?: Invoice;
  isEdit?: boolean;
  onInvoiceUpdate?: (updatedInvoice: Invoice) => void;
  initialData?: any;
  attachment?: File | null;
  prefillNewClient?: { name?: string; email?: string; address?: string; phone?: string } | null;
  openNewClientOnInit?: boolean;
  existingApproval?: { approver_id: number };
}

export function InvoiceFormWithApproval({
  invoice,
  isEdit = false,
  onInvoiceUpdate,
  initialData,
  attachment,
  prefillNewClient,
  openNewClientOnInit,
  existingApproval
}: InvoiceFormWithApprovalProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasClients, setHasClients] = useState(true);
  const [loadingClients, setLoadingClients] = useState(true);
  const [submitForApproval, setSubmitForApproval] = useState(false);
  const [selectedApproverId, setSelectedApproverId] = useState<string>('');
  const [availableApprovers, setAvailableApprovers] = useState<Array<{ id: number; name: string; email: string }>>([]);
  const [approvalsNotLicensed, setApprovalsNotLicensed] = useState(false);
  const submitButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const checkClients = async () => {
      try {
        const clients = await clientApi.getClients();
        setHasClients(Array.isArray(clients) && clients.length > 0);
      } catch (error) {
        console.error('Failed to fetch clients:', error);
        setHasClients(false);
      } finally {
        setLoadingClients(false);
      }
    };
    checkClients();
  }, []);

  useEffect(() => {
    const fetchApprovers = async () => {
      try {
        const response = await approvalApi.getApprovers();
        setAvailableApprovers(response);
        setApprovalsNotLicensed(false);
        
        // Pre-populate approval state if existingApproval is provided
        if (existingApproval && existingApproval.approver_id) {
          setSubmitForApproval(true);
          setSelectedApproverId(existingApproval.approver_id.toString());
          console.log('🔍 Pre-populated approval state:', {
            submitForApproval: true,
            selectedApproverId: existingApproval.approver_id
          });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        // Check if it's a license error (402 Payment Required)
        if (errorMessage.includes('not included in your current license') || errorMessage.includes('requires a valid license')) {
          setApprovalsNotLicensed(true);
          setAvailableApprovers([]);
        } else {
          console.error('Failed to fetch approvers:', error);
          setAvailableApprovers([]);
        }
      }
    };
    fetchApprovers();
  }, [existingApproval]);

  const checkClientsAgain = async () => {
    try {
      const clients = await clientApi.getClients();
      setHasClients(Array.isArray(clients) && clients.length > 0);
    } catch (error) {
      console.error('Failed to fetch clients:', error);
    }
  };

  const handleInvoiceUpdate = async (updatedInvoice: Invoice) => {
    // Call the original callback if provided
    if (onInvoiceUpdate) {
      onInvoiceUpdate(updatedInvoice);
    }
  };

  const handleFormSubmit = async () => {
    if (submitButtonRef.current) {
      submitButtonRef.current.click();
    }
  };

  const handleCancel = () => {
    navigate('/invoices');
  };

  return (
    <>
      <div>
        <InvoiceForm
          invoice={invoice}
          isEdit={isEdit}
          onInvoiceUpdate={handleInvoiceUpdate}
          initialData={initialData}
          attachment={attachment}
          prefillNewClient={prefillNewClient}
          openNewClientOnInit={openNewClientOnInit}
          renderButtons={false}
          onFormCancel={handleCancel}
          onClientCreated={checkClientsAgain}
          submitForApproval={submitForApproval && !approvalsNotLicensed}
          approverIdForApproval={selectedApproverId ? parseInt(selectedApproverId) : undefined}
          submitButtonRef={submitButtonRef}
          onSubmitStateChange={setIsSubmitting}
        />
      </div>

      {/* Approval Workflow Section */}
      {!loadingClients && hasClients && (
        <div className="w-full px-6 py-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('invoices.approval_workflow', 'Approval Workflow')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="submit-for-approval"
                  checked={submitForApproval}
                  onCheckedChange={(checked) => setSubmitForApproval(checked as boolean)}
                />
                <label
                  htmlFor="submit-for-approval"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {isEdit
                    ? t('invoices.submit_this_invoice_for_approval', 'Submit this invoice for approval')
                    : t('invoices.submit_this_invoice_for_approval_after_creation', 'Submit this invoice for approval after creation')}
                </label>
              </div>
              {submitForApproval && (
                <div className="mt-3 space-y-3">
                  {approvalsNotLicensed ? (
                    <Alert className="border-amber-200 bg-amber-50">
                      <AlertCircle className="h-4 w-4 text-amber-600" />
                      <AlertDescription className="text-amber-800">
                        {t('common.feature_not_licensed', {
                          defaultValue: 'Approval workflows require a commercial license. Please upgrade your license to use this feature.'
                        })}
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <>
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-700">
                          {t('invoices.this_invoice_will_be_submitted_for_approval', 'This invoice will be submitted for approval')}
                        </p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="approver-select" className="flex items-center gap-2 text-sm font-medium">
                          <Users className="h-4 w-4" />
                          {t('invoices.select_approver', 'Select Approver')} *
                        </Label>
                        <Select value={selectedApproverId} onValueChange={setSelectedApproverId}>
                          <SelectTrigger>
                            <SelectValue placeholder={t('invoices.choose_an_approver', 'Choose an approver')} />
                          </SelectTrigger>
                          <SelectContent>
                            {availableApprovers.map((approver) => (
                              <SelectItem key={approver.id} value={approver.id.toString()}>
                                {approver.name} ({approver.email})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Form Actions */}
      <div className="w-full px-6 py-6">
        <div className="flex justify-end gap-4">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={isSubmitting}
          >
            {t('invoices.cancel')}
          </Button>
          <Button
            type="button"
            onClick={handleFormSubmit}
            disabled={isSubmitting || (submitForApproval && !approvalsNotLicensed && !selectedApproverId)}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEdit ? t('invoices.update_invoice') : t('invoices.create_invoice')}
          </Button>
        </div>
      </div>


    </>
  );
}
