import { useState, useEffect, useRef } from 'react';
import { InvoiceForm } from './InvoiceForm';
import { Invoice, clientApi, approvalApi } from '@/lib/api';
import { Loader2, AlertCircle, Users, CheckCircle, XCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ApprovalHistoryEntry } from '@/types';

interface InvoiceFormWithApprovalProps {
  invoice?: Invoice;
  isEdit?: boolean;
  onInvoiceUpdate?: (updatedInvoice: Invoice) => void;
  initialData?: any;
  attachment?: File | null;
  prefillNewClient?: { name?: string; email?: string; address?: string; phone?: string } | null;
  openNewClientOnInit?: boolean;
  existingApproval?: { approver_id: number };
  canEditPayment?: boolean;
}

export function InvoiceFormWithApproval({
  invoice,
  isEdit = false,
  onInvoiceUpdate,
  initialData,
  attachment,
  prefillNewClient,
  openNewClientOnInit,
  existingApproval,
  canEditPayment = false
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
  const [approvalHistory, setApprovalHistory] = useState<ApprovalHistoryEntry | null>(null);
  const [loadingApprovalHistory, setLoadingApprovalHistory] = useState(false);
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

  // Fetch approval history if invoice exists and has been processed
  useEffect(() => {
    const fetchApprovalHistory = async () => {
      if (!invoice?.id || !isEdit) return;

      // Only fetch if invoice status indicates it has been through approval workflow
      if (!['approved', 'rejected', 'pending_approval'].includes(invoice.status)) return;

      try {
        setLoadingApprovalHistory(true);
        const historyResponse = await approvalApi.getInvoiceApprovalHistory(invoice.id);
        console.log('Invoice approval history response:', historyResponse);

        if (invoice.status === 'pending_approval') {
          // Get pending approval
          const pendingApproval = historyResponse.approval_history
            .filter((a: any) => a.status === 'pending')
            .sort((a: any, b: any) => new Date(b.submitted_at || b.timestamp).getTime() - new Date(a.submitted_at || a.timestamp).getTime())[0];

          if (pendingApproval) {
            console.log('Found pending approval:', pendingApproval);
            setApprovalHistory(pendingApproval);
          }
        } else {
          // Get most recent completed approval (approved or rejected)
          const completedApproval = historyResponse.approval_history
            ?.filter((a: any) => a.status === 'approved' || a.status === 'rejected')
            .sort((a: any, b: any) => new Date(b.decided_at || b.timestamp).getTime() - new Date(a.decided_at || a.timestamp).getTime())[0];

          if (completedApproval) {
            console.log('Found completed approval:', completedApproval);
            setApprovalHistory(completedApproval);
          }
        }
      } catch (error) {
        console.error('Error fetching approval history:', error);
        setApprovalHistory(null);
      } finally {
        setLoadingApprovalHistory(false);
      }
    };

    fetchApprovalHistory();
  }, [invoice?.id, invoice?.status, isEdit]);

  const checkClientsAgain = async () => {
    try {
      setLoadingClients(true);
      const clients = await clientApi.getClients();
      setHasClients(Array.isArray(clients) && clients.length > 0);
    } catch (error) {
      console.error('Failed to fetch clients:', error);
    } finally {
      setLoadingClients(false);
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
          canEditPayment={canEditPayment}
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
              {loadingApprovalHistory ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading approval status...</span>
                </div>
              ) : invoice?.status === 'approved' && approvalHistory ? (
                // Show approval information for approved invoices
                <div className="space-y-3">
                  <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800/50 rounded-lg">
                    <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-green-800 dark:text-green-200">
                        {t('invoices.invoice_approved', 'This invoice was approved')}
                      </p>
                      <p className="text-sm text-green-700 dark:text-green-300">
                        {t('invoices.approved_by', 'Approved by')}: {' '}
                        {approvalHistory.approved_by_username ||
                         approvalHistory.approver?.name ||
                         approvalHistory.approver?.email ||
                         'Unknown'}
                      </p>
                      {approvalHistory.decided_at && (
                        <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                          {new Date(approvalHistory.decided_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  {approvalHistory.notes && (
                    <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800/50 rounded-lg">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
                        {t('invoices.approval_notes', 'Approval Notes')}:
                      </p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">{approvalHistory.notes}</p>
                    </div>
                  )}
                </div>
              ) : invoice?.status === 'rejected' && approvalHistory ? (
                // Show rejection information for rejected invoices
                <div className="space-y-3">
                  <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800/50 rounded-lg">
                    <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-red-800 dark:text-red-200">
                        {t('invoices.invoice_rejected', 'This invoice was rejected')}
                      </p>
                      <p className="text-sm text-red-700 dark:text-red-300">
                        {t('invoices.rejected_by', 'Rejected by')}: {' '}
                        {approvalHistory.rejected_by_username ||
                         approvalHistory.approver?.name ||
                         approvalHistory.approver?.email ||
                         'Unknown'}
                      </p>
                      {approvalHistory.decided_at && (
                        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                          {new Date(approvalHistory.decided_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  {approvalHistory.rejection_reason && (
                    <div className="p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800/50 rounded-lg">
                      <p className="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
                        {t('invoices.rejection_reason', 'Rejection Reason')}:
                      </p>
                      <p className="text-sm text-red-700 dark:text-red-300">{approvalHistory.rejection_reason}</p>
                    </div>
                  )}
                  {approvalHistory.notes && (
                    <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800/50 rounded-lg">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
                        {t('invoices.rejection_notes', 'Additional Notes')}:
                      </p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">{approvalHistory.notes}</p>
                    </div>
                  )}
                </div>
              ) : invoice?.status === 'pending_approval' && approvalHistory ? (
                // Show pending approval information
                <div className="space-y-3">
                  <div className="flex items-center gap-2 p-3 bg-yellow-50 dark:bg-yellow-950/50 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
                    <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                        {t('invoices.invoice_pending_approval', 'This invoice is pending approval')}
                      </p>
                      <p className="text-sm text-yellow-700 dark:text-yellow-300">
                        {t('invoices.waiting_for_approval_from', 'Waiting for approval from')}: {' '}
                        {approvalHistory.approver?.name || approvalHistory.approver?.email || 'Unknown'}
                      </p>
                      {approvalHistory.submitted_at && (
                        <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
                          {t('invoices.submitted_at', 'Submitted at')}: {new Date(approvalHistory.submitted_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  {approvalHistory.notes && (
                    <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800/50 rounded-lg">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
                        {t('invoices.submission_notes', 'Submission Notes')}:
                      </p>
                      <p className="text-sm text-gray-700 dark:text-gray-300">{approvalHistory.notes}</p>
                    </div>
                  )}
                </div>
              ) : (
                // Show approval submission form for new/draft invoices
                <>
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
                          <div className="p-3 bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800/50 rounded-lg">
                            <p className="text-sm text-blue-700 dark:text-blue-200">
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
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Form Actions */}
      {!isEdit && (
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
              {t('invoices.create_invoice')}
            </Button>
          </div>
        </div>
      )}


    </>
  );
}
