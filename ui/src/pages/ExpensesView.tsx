// @ts-nocheck - TypeScript configuration issue with React types
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload, Package, Eye, Pencil, AlertCircle, Trash2 } from 'lucide-react';
import { Calendar } from '@/components/ui/calendar';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, approvalApi, Expense, ExpenseAttachmentMeta, linkApi } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { ApprovalActionButtons } from '@/components/approvals/ApprovalActionButtons';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ShareButton } from '@/components/sharing/ShareButton';
import { ExpenseApproval } from '@/types';

export default function ExpensesView() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [form, setForm] = useState<Partial<Expense>>({});
  const [loading, setLoading] = useState(true);
  const [attachments, setAttachments] = useState<ExpenseAttachmentMeta[]>([]);
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);
  const [approval, setApproval] = useState<ExpenseApproval | null>(null);

  // Inventory consumption state (read-only)
  const [isInventoryConsumption, setIsInventoryConsumption] = useState(false);
  const [consumptionItems, setConsumptionItems] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        if (!id) return;
        const exp = await expenseApi.getExpense(Number(id));

        setForm(exp);

        // Initialize consumption state from existing expense data
        const isConsumption = !!(exp as any).is_inventory_consumption;
        const consumptionItemsData = (exp as any).consumption_items || [];
        setIsInventoryConsumption(isConsumption);
        setConsumptionItems(consumptionItemsData);

        const list = await expenseApi.listAttachments(Number(id));
        setAttachments(list);

        try {
          const invs = await linkApi.getInvoicesBasic();
          setInvoiceOptions(invs);
        } catch { }

        // Try to fetch approval data for this expense
        try {
          // First try to get pending approvals
          const pendingApprovals = await approvalApi.getPendingApprovals();
          const expenseApproval = pendingApprovals.approvals?.find((a: ExpenseApproval) => a.expense_id === Number(id));

          if (expenseApproval) {
            setApproval(expenseApproval);
          } else {
            // If not pending, try to get approval history to show completed approvals
            try {
              const historyResponse = await approvalApi.getExpenseApprovalHistory(Number(id));
              // Get the most recent approval (approved or rejected)
              const completedApproval = historyResponse.approval_history
                ?.filter((a: any) => a.status === 'approved' || a.status === 'rejected')
                .sort((a: any, b: any) => new Date(b.decided_at || b.timestamp).getTime() - new Date(a.decided_at || a.timestamp).getTime())[0];

              if (completedApproval) {
                setApproval(completedApproval as any);
              }
            } catch {
              // No approval history available
            }
          }
        } catch {
          setApproval(null);
        }
      } catch (e: any) {
        toast.error(e?.message || t('expenses.failed_to_load', { defaultValue: 'Failed to load expense' }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);


  // Calculate amount from consumption items
  useEffect(() => {
    if (isInventoryConsumption && consumptionItems.length > 0) {
      const total = consumptionItems.reduce((sum, item) => sum + (item.quantity * (item.unit_cost || 0)), 0);
      setForm(prev => ({ ...prev, amount: total }));
    }
  }, [consumptionItems, isInventoryConsumption]);

  const handleApprovalAction = async (approvalId: number, action: 'approve' | 'reject', data?: any) => {
    try {
      if (action === 'approve') {
        await approvalApi.approveExpense(approvalId, data?.notes || '');
        toast.success('Expense approved successfully');
      } else {
        await approvalApi.rejectExpense(approvalId, data?.rejection_reason || '', data?.notes || '');
        toast.success('Expense rejected successfully');
      }
      // Refresh the page to show updated status
      navigate(0);
    } catch (error: any) {
      toast.error(error?.message || `Failed to ${action} expense`);
      throw error;
    }
  };




  const [unsubmitLoading, setUnsubmitLoading] = useState(false);
  const handleUnsubmit = async () => {
    try {
      setUnsubmitLoading(true);
      await approvalApi.unsubmitExpenseApproval(Number(id));
      toast.success('Approval request unsubmitted successfully');
      // Refresh the page
      navigate(0);
    } catch (error: any) {
      toast.error(error?.message || 'Failed to unsubmit approval request');
    } finally {
      setUnsubmitLoading(false);
    }
  };

  if (loading) {
    return (
      <>
        <div className="p-6">{t('common.loading')}</div>
      </>
    );
  }

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('expenses.view_title', { defaultValue: 'View Expense' })}
          description={t('expenses.view_description', { defaultValue: 'Review expense details and take approval actions.' })}
          breadcrumbs={[
            { label: t('expenses.title', 'Expenses'), href: '/expenses' },
            { label: (form as any)?.description || `Expense #${id}`, href: '#' }
          ]}
          actions={
            <div className="flex gap-2">
              {form.id && <ShareButton recordType="expense" recordId={form.id as number} />}
              {approval && (
                <ApprovalActionButtons
                  approval={approval}
                  onAction={handleApprovalAction}
                />
              )}
              {form.status === 'pending_approval' && (
                <Button
                  onClick={handleUnsubmit}
                  variant="outline"
                  disabled={unsubmitLoading}
                  className="border-amber-200 text-amber-700 hover:bg-amber-50"
                >
                  <AlertCircle className="mr-2 h-4 w-4" />
                  {t('expenses.unsubmit', { defaultValue: 'Unsubmit' })}
                </Button>
              )}
              {(!approval || approval.status !== 'pending') && (
                <>
                  <Button
                    onClick={() => navigate(`/expenses/edit/${id}`)}
                    variant="outline"
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    {t('common.edit')}
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" className="flex items-center gap-2">
                        <Trash2 className="w-4 h-4" />
                        {t('common.delete', { defaultValue: 'Delete' })}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('expenses.delete_single_title', { defaultValue: 'Delete Expense' })}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t('expenses.delete_single_description', { defaultValue: 'Are you sure you want to delete this expense? This will move it to the recycle bin.' })}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel', { defaultValue: 'Cancel' })}</AlertDialogCancel>
                        <AlertDialogAction
                          className="bg-destructive text-white hover:bg-destructive/90"
                          onClick={async () => {
                            try {
                              await expenseApi.deleteExpense(Number(id));
                              toast.success(t('expenses.delete_success', { defaultValue: 'Expense deleted successfully' }));
                              navigate('/expenses');
                            } catch (e: any) {
                              toast.error(e?.message || t('expenses.delete_failed', { defaultValue: 'Failed to delete expense' }));
                            }
                          }}
                        >
                          {t('common.delete', { defaultValue: 'Delete' })}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}
            </div>
          }
        />

        {/* Show approval request message if exists */}
        {approval && approval.notes && (
          <Card className="slide-in border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/50">
            <CardHeader>
              <CardTitle className="text-blue-900 dark:text-blue-100">{t('expenses.approval_request_message', { defaultValue: 'Approval Request Message' })}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-blue-800 dark:text-blue-200">{approval.notes}</p>
            </CardContent>
          </Card>
        )}

        {/* Show approval/rejection information if expense has been processed */}
        {approval && approval.status === 'approved' && approval.approved_by_username && (
          <Card className="slide-in border-green-200 bg-green-50">
            <CardHeader>
              <CardTitle className="text-green-900">{t('expenses.approval_information', { defaultValue: 'Approval Information' })}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <span className="text-sm font-medium text-green-800">{t('expenses.approved_by', { defaultValue: 'Approved by' })}: </span>
                <span className="text-sm text-green-700">{approval.approved_by_username}</span>
              </div>
              {approval.decided_at && (
                <div>
                  <span className="text-sm font-medium text-green-800">{t('expenses.approved_at', { defaultValue: 'Approved at' })}: </span>
                  <span className="text-sm text-green-700">{new Date(approval.decided_at).toLocaleString()}</span>
                </div>
              )}
              {approval.notes && (
                <div>
                  <span className="text-sm font-medium text-green-800">{t('expenses.approval_notes', { defaultValue: 'Notes' })}: </span>
                  <span className="text-sm text-green-700">{approval.notes}</span>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {approval && approval.status === 'rejected' && approval.rejected_by_username && (
          <Card className="slide-in border-red-200 bg-red-50">
            <CardHeader>
              <CardTitle className="text-red-900">{t('expenses.rejection_information', { defaultValue: 'Rejection Information' })}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <span className="text-sm font-medium text-red-800">{t('expenses.rejected_by', { defaultValue: 'Rejected by' })}: </span>
                <span className="text-sm text-red-700">{approval.rejected_by_username}</span>
              </div>
              {approval.decided_at && (
                <div>
                  <span className="text-sm font-medium text-red-800">{t('expenses.rejected_at', { defaultValue: 'Rejected at' })}: </span>
                  <span className="text-sm text-red-700">{new Date(approval.decided_at).toLocaleString()}</span>
                </div>
              )}
              {approval.rejection_reason && (
                <div>
                  <span className="text-sm font-medium text-red-800">{t('expenses.rejection_reason', { defaultValue: 'Reason' })}: </span>
                  <span className="text-sm text-red-700">{approval.rejection_reason}</span>
                </div>
              )}
              {approval.notes && (
                <div>
                  <span className="text-sm font-medium text-red-800">{t('expenses.rejection_notes', { defaultValue: 'Notes' })}: </span>
                  <span className="text-sm text-red-700">{approval.notes}</span>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <ContentSection title={t('expenses.details')}>
          <ProfessionalCard>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{t('expenses.details')}</CardTitle>
                {attachments && attachments.length > 0 &&
                  form.status !== 'pending_approval' && form.status !== 'approved' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      try {
                        const addNotification = (window as any).addAINotification;
                        addNotification?.('processing', 'Reprocessing Expense', `Re-analyzing expense receipts with AI...`);

                        await expenseApi.reprocessExpense(Number(id));

                        addNotification?.('success', 'Expense Reprocessed', `Successfully reprocessed expense receipts.`);
                        toast.success(t('expenses.reprocessing_started'));
                        // Refresh the expense data
                        const exp = await expenseApi.getExpense(Number(id));
                        setForm(exp);
                      } catch (e: any) {
                        const addNotification = (window as any).addAINotification;
                        addNotification?.('error', 'Expense Reprocessing Failed', `Failed to reprocess expense: ${e?.message || 'Unknown error'}`);
                        toast.error(e?.message || t('expenses.failed_to_reprocess'));
                      }
                    }}
                  >
                    {t('expenses.process_again')}
                  </Button>
                )}
              </div>
              {(form as any)?.analysis_status && (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{t('expenses.analysis_status', { defaultValue: 'Analysis Status' })}:</span>
                    {form.analysis_status === 'done' ? (
                      <Badge variant="success" className="h-6">{t('expenses.status_done')}</Badge>
                    ) : form.analysis_status === 'processing' || form.analysis_status === 'queued' ? (
                      <Badge variant="secondary" className="h-6 bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-800 capitalize">
                        {form.analysis_status === 'processing' ? t('expenses.status_processing') : t('expenses.status_queued')}
                      </Badge>
                    ) : form.analysis_status === 'failed' ? (
                      <Badge variant="destructive" className="h-6">Failed</Badge>
                    ) : form.analysis_status === 'cancelled' ? (
                      <Badge variant="secondary" className="h-6">Cancelled</Badge>
                    ) : (form as any)?.imported_from_attachment ? (
                      <Badge variant="outline" className="h-6 border-blue-200 text-blue-700 bg-blue-50 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800">
                        Not Started
                      </Badge>
                    ) : null}
                  </div>
                  {(form as any)?.analysis_error && (form as any)?.analysis_status === 'failed' && (
                    <Alert className="border-red-200 bg-red-50">
                      <AlertCircle className="h-4 w-4 text-red-600" />
                      <AlertDescription className="text-red-800">
                        <details className="cursor-pointer">
                          <summary className="font-medium mb-1">{t('expenses.analysis_failed_click_details', { defaultValue: 'Analysis failed (click for details)' })}</summary>
                          <div className="mt-2 text-xs font-mono bg-red-100 p-2 rounded border border-red-200 overflow-x-auto">
                            {(form as any).analysis_error}
                          </div>
                        </details>
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              )}
            </CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm">{t('expenses.labels.amount')}</label>
                <Input
                  type="number"
                  value={Number(form.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4, useGrouping: false })}
                  disabled={true}
                  placeholder={isInventoryConsumption ? "Calculated from items" : ""}
                />
              </div>
              <div>
                <label className="text-sm">{t('expenses.link_to_invoice')}</label>
                <Select value={form.invoice_id ? String(form.invoice_id) : undefined} disabled={true}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('expenses.select_invoice')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t('expenses.none')}</SelectItem>
                    {invoiceOptions.map(inv => (
                      <SelectItem key={inv.id} value={String(inv.id)}>{inv.number} — {inv.client_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.currency')}</label>
                <CurrencySelector value={form.currency || 'USD'} disabled={true} onValueChange={() => { }} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.date')}</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start text-left font-normal" disabled={true}>
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {form.expense_date ? format(new Date(form.expense_date + 'T00:00:00'), 'PPP') : t('expenses.labels.pick_date')}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={form.expense_date ? new Date(form.expense_date + 'T00:00:00') : undefined}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.category')}</label>
                <Select value={(form.category as string) || 'General'} disabled={true}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('common.select_category')} />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.map(c => (<SelectItem key={c} value={c}>{t(`expenses.categories.${c}`)}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.vendor')}</label>
                <Input value={form.vendor || ''} disabled={true} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.payment_method')}</label>
                <Input value={form.payment_method || ''} disabled={true} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.reference_number')}</label>
                <Input value={form.reference_number || ''} disabled={true} />
              </div>
              {((form as any).created_by_username || (form as any).created_by_email) && (
                <div>
                  <label className="text-sm">{t('common.created_by')}</label>
                  <Input value={(form as any).created_by_username || (form as any).created_by_email || t('common.unknown')} disabled={true} />
                </div>
              )}
              <div className="sm:col-span-2">
                <label className="text-sm">{t('common.labels')}</label>
                <div className="flex flex-wrap items-center gap-2 mt-1">
                  {((form as any).labels || []).slice(0, 10).map((lab: string, idx: number) => {
                    return (
                      // @ts-expect-error - React key prop issue with Badge component
                      <Badge key={`lab-${idx}`} variant="secondary" className="text-xs">
                        {lab}
                      </Badge>
                    );
                  })}
                </div>
              </div>

              {/* Inventory Consumption Section - Only show if this is an inventory expense */}
              {isInventoryConsumption && (
                <div className="sm:col-span-2">
                  <div className="space-y-3 p-4 border rounded-lg bg-gray-50">
                    <div className="flex items-center gap-2">
                      <Package className="h-4 w-4" />
                      <span className="text-sm font-medium">{t('expenses.inventory_integration')}</span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="is-inventory-consumption"
                        checked={isInventoryConsumption}
                        disabled={true}
                      />
                      <label
                        htmlFor="is-inventory-consumption"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        {t('expenses.this_expense_is_for_consuming_inventory_items')}
                      </label>
                    </div>

                    <div className="space-y-4">
                      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                        <div className="flex items-center gap-2 text-orange-800 mb-3">
                          <Package className="h-4 w-4" />
                          <span className="text-sm font-medium">{t('expenses.inventory_consumption_details')}</span>
                        </div>
                        <p className="text-sm text-orange-700 mb-4">
                          {t('expenses.viewing_inventory_consumption', { defaultValue: 'This expense consumed the following inventory items:' })}
                        </p>

                        <InventoryConsumptionForm
                          onConsumptionItemsChange={setConsumptionItems}
                          currency={form.currency || 'USD'}
                          initialConsumptionItems={consumptionItems}
                        />
                      </div>

                      {consumptionItems.length > 0 && (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-green-800">
                            <Package className="h-4 w-4" />
                            <span className="text-sm font-medium">
                              {t('expenses.consumed_items_count', { count: consumptionItems.length, defaultValue: `${consumptionItems.length} item(s) consumed` })}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.notes')}</label>
                <Input value={form.notes || ''} disabled={true} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.max_attachments')}</label>
                {(form as any)?.analysis_status === 'done' && (
                  <div className="text-xs text-muted-foreground mt-1">{t('expenses.attachments_cannot_delete', { defaultValue: 'Attachments cannot be deleted after analysis is completed.' })}</div>
                )}
                <div className="mt-3">
                  <div className="text-sm font-medium mb-2">{t('expenses.existing_attachments', { defaultValue: 'Existing attachments' })}</div>
                  {attachments.length === 0 ? (
                    <div className="text-sm text-muted-foreground">{t('expenses.none')}</div>
                  ) : (
                    <ul className="space-y-3">
                      {attachments.map(att => (
                        <li key={att.id} className="flex flex-col gap-2 border rounded-lg p-3 bg-card hover:shadow-sm transition-shadow">
                          <div className="flex items-center justify-between gap-3">
                            <div className="truncate text-sm font-medium flex items-center gap-2">
                              {att.filename}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2"
                              onClick={async () => {
                                try {
                                  const { blob, contentType } = await expenseApi.downloadAttachmentBlob(Number(id), att.id);
                                  const url = URL.createObjectURL(blob);
                                  setPreview({ open: true, url, contentType: contentType || att.content_type || null, filename: att.filename || null });
                                } catch (e) {
                                  toast.error('Failed to download attachment');
                                }
                              }}
                            >
                              <Eye className="w-4 h-4 mr-2" />
                              {t('common.view')}
                            </Button>
                          </div>

                          <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-2 mt-1">
                            <div className="flex items-center gap-3">
                              <div className="flex items-center gap-1">
                                <span className="font-semibold uppercase text-[10px] text-muted-foreground/70 tracking-wider">Status:</span>
                                <Badge
                                  variant={
                                    att.analysis_status === 'done' ? 'default' :
                                      att.analysis_status === 'failed' ? 'destructive' :
                                        'outline'
                                  }
                                  className="h-4 text-[9px] px-1 font-bold tracking-tight"
                                >
                                  {att.analysis_status || 'not_started'}
                                </Badge>
                              </div>
                              {att.extracted_amount !== undefined && att.extracted_amount !== null && (
                                <div className="flex items-center gap-1">
                                  <span className="font-semibold uppercase text-[10px] text-muted-foreground/70 tracking-wider">Amount:</span>
                                  <span className="font-bold text-foreground">
                                    {new Intl.NumberFormat(undefined, { style: 'currency', currency: form.currency || 'USD' }).format(att.extracted_amount)}
                                  </span>
                                </div>
                              )}
                            </div>
                            {att.file_size && (
                              <span>{(att.file_size / 1024).toFixed(1)} KB</span>
                            )}
                          </div>

                          {att.analysis_error && att.analysis_status === 'failed' && (
                            <div className="text-[10px] text-destructive bg-destructive/5 p-1.5 rounded border border-destructive/10 mt-1 max-h-12 overflow-y-auto font-mono leading-tight">
                              {att.analysis_error}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </CardContent>
          </ProfessionalCard>
        </ContentSection>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back', { defaultValue: 'Back' })}</Button>
          <Button
            variant="default"
            onClick={() => navigate(`/expenses/edit/${id}`)}
            className="flex items-center gap-2"
          >
            <Pencil className="w-4 h-4" />
            {t('common.edit', { defaultValue: 'Edit' })}
          </Button>
        </div>

        {/* File inline preview dialog */}
        <Dialog open={preview.open} onOpenChange={(o) => {
          if (!o && preview.url) URL.revokeObjectURL(preview.url);
          setPreview(prev => ({ open: o, url: o ? prev.url : null, contentType: o ? prev.contentType : null, filename: o ? prev.filename : null }));
        }}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>{preview.filename || t('expenses.preview', { defaultValue: 'Preview' })}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {preview.url && (preview.contentType || '').startsWith('image/') && (
                <img src={preview.url} alt={preview.filename || t('expenses.attachment', { defaultValue: 'attachment' })} className="max-w-full h-auto" />
              )}
              {preview.url && (preview.contentType || '').startsWith('application/pdf') && (
                <iframe src={preview.url} className="w-full h-[60vh]" title={preview.filename || t('expenses.attachment', { defaultValue: 'attachment' })} />
              )}
              {preview.url && !(preview.contentType || '').startsWith('image/') && !(preview.contentType || '').startsWith('application/pdf') && (
                <div className="text-center p-8">
                  <Package className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">{t('expenses.preview_not_supported', { defaultValue: 'Preview not supported for this file type' })}</p>
                </div>
              )}
              {preview.url && (
                <Button variant="outline" className="mt-4" onClick={() => {
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
      </div>
    </>
  );
}
