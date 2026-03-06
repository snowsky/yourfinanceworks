import React, { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Download, FileSpreadsheet, AlertTriangle } from 'lucide-react';

import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { accountingExportApi, expenseApi, Invoice, invoiceApi } from '@/lib/api';

type ExportScope = 'processed' | 'all';

const TAX_AMOUNT_KEYS = ['tax_amount', 'output_tax', 'vat_amount'];

const toExportDateTime = (value?: string, endOfDay: boolean = false): string | undefined => {
  if (!value) return undefined;
  return `${value}T${endOfDay ? '23:59:59' : '00:00:00'}`;
};

const extractInvoiceTaxAmount = (invoice: Invoice): number => {
  const customFields = invoice.custom_fields || {};
  const fallback = (invoice as any)?.tax_amount;
  const raw =
    fallback ??
    TAX_AMOUNT_KEYS.map((key) => customFields?.[key]).find((value) => value !== undefined && value !== null);
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
};

const downloadBlobFile = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(link);
};

const AccountingTaxExport: React.FC = () => {
  const { t } = useTranslation();

  const [scope, setScope] = useState<ExportScope>('processed');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [journalSources, setJournalSources] = useState({
    include_expenses: true,
    include_invoices: true,
    include_payments: false,
    tax_only: false,
  });

  const [summarySources, setSummarySources] = useState({
    include_expenses: true,
    include_invoices: true,
  });

  const includeDrafts = scope === 'all';

  const qualityQuery = useQuery({
    queryKey: ['accounting-tax-export-quality', scope],
    queryFn: async () => {
      const [invoiceResponse, expenseResponse] = await Promise.all([
        invoiceApi.getInvoices(undefined, undefined, 0, 1000),
        expenseApi.getExpensesPaginated({ skip: 0, limit: 1000 }),
      ]);

      const invoices = invoiceResponse.items || [];
      const expenses = expenseResponse.expenses || [];

      const scopedInvoices =
        scope === 'processed'
          ? invoices.filter((invoice) => invoice.status !== 'draft' && invoice.status !== 'pending_approval')
          : invoices;
      const scopedExpenses =
        scope === 'processed'
          ? expenses.filter((expense) => expense.status !== 'draft' && expense.status !== 'pending_approval')
          : expenses;

      const invoicesMissingTax = scopedInvoices.filter((invoice) => extractInvoiceTaxAmount(invoice) <= 0).length;
      const expensesTaxMismatch = scopedExpenses.filter((expense) => {
        const taxAmount = Number(expense.tax_amount ?? 0);
        const taxRate = Number(expense.tax_rate ?? 0);
        return (taxAmount > 0 && taxRate <= 0) || (taxRate > 0 && taxAmount <= 0);
      }).length;

      return {
        invoiceCount: scopedInvoices.length,
        invoicesMissingTax,
        expenseCount: scopedExpenses.length,
        expensesTaxMismatch,
      };
    },
    staleTime: 60_000,
  });

  const journalDisabled = useMemo(
    () =>
      !journalSources.include_expenses && !journalSources.include_invoices && !journalSources.include_payments,
    [journalSources]
  );

  const summaryDisabled = useMemo(
    () => !summarySources.include_expenses && !summarySources.include_invoices,
    [summarySources]
  );

  const journalMutation = useMutation({
    mutationFn: async () =>
      accountingExportApi.downloadJournal({
        date_from: toExportDateTime(dateFrom),
        date_to: toExportDateTime(dateTo, true),
        include_drafts: includeDrafts,
        include_expenses: journalSources.include_expenses,
        include_invoices: journalSources.include_invoices,
        include_payments: journalSources.tax_only ? false : journalSources.include_payments,
        tax_only: journalSources.tax_only,
      }),
    onSuccess: ({ blob, filename }) => {
      downloadBlobFile(blob, filename || 'accounting_journal.csv');
      toast.success(t('reports.accounting_tax_export.journal_success', 'Journal export downloaded.'));
    },
    onError: (error: any) => {
      toast.error(error?.message || t('reports.accounting_tax_export.journal_error', 'Journal export failed.'));
    },
  });

  const summaryMutation = useMutation({
    mutationFn: async () =>
      accountingExportApi.downloadTaxSummary({
        date_from: toExportDateTime(dateFrom),
        date_to: toExportDateTime(dateTo, true),
        include_drafts: includeDrafts,
        include_expenses: summarySources.include_expenses,
        include_invoices: summarySources.include_invoices,
      }),
    onSuccess: ({ blob, filename }) => {
      downloadBlobFile(blob, filename || 'tax_summary.csv');
      toast.success(t('reports.accounting_tax_export.summary_success', 'Tax summary downloaded.'));
    },
    onError: (error: any) => {
      toast.error(error?.message || t('reports.accounting_tax_export.summary_error', 'Tax summary export failed.'));
    },
  });

  return (
    <div className="h-full space-y-6 fade-in">
      <PageHeader
        title={t('reports.accounting_tax_export.title', 'Accounting & Tax Export')}
        description={t(
          'reports.accounting_tax_export.description',
          'Dedicated accountant-facing exports, separate from processed-document exports.'
        )}
      />

      <FeatureGate
        feature="advanced_export"
        showUpgradePrompt={true}
        upgradeMessage={t(
          'reports.accounting_tax_export.upgrade_message',
          'Accounting and tax CSV exports require the advanced export feature.'
        )}
      >
        <ContentSection className="slide-in">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>{t('reports.accounting_tax_export.scope_title', 'Scope & Date Range')}</CardTitle>
                <CardDescription>
                  {t(
                    'reports.accounting_tax_export.scope_description',
                    'Use processed scope for accounting workflow; include unprocessed only when reconciling drafts.'
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('reports.accounting_tax_export.document_scope', 'Document Scope')}</Label>
                  <Select value={scope} onValueChange={(value) => setScope(value as ExportScope)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="processed">
                        {t('reports.accounting_tax_export.scope_processed', 'Processed documents only')}
                      </SelectItem>
                      <SelectItem value="all">
                        {t('reports.accounting_tax_export.scope_all', 'Include unprocessed/drafts')}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="date_from">{t('reports.date_from', 'Date From')}</Label>
                    <Input
                      id="date_from"
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="date_to">{t('reports.date_to', 'Date To')}</Label>
                    <Input id="date_to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('reports.accounting_tax_export.quality_title', 'Tax Data Quality')}</CardTitle>
                <CardDescription>
                  {t(
                    'reports.accounting_tax_export.quality_description',
                    'Quick checks before download to reduce accountant rework.'
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {qualityQuery.isLoading ? (
                  <p className="text-muted-foreground">{t('common.loading', 'Loading...')}</p>
                ) : qualityQuery.data ? (
                  <>
                    <p>
                      {t('reports.accounting_tax_export.invoice_count', 'Invoices in scope')}: {qualityQuery.data.invoiceCount}
                    </p>
                    <p>
                      {t('reports.accounting_tax_export.expense_count', 'Expenses in scope')}: {qualityQuery.data.expenseCount}
                    </p>
                    <div className="pt-2 border-t border-border/60 space-y-2">
                      <p className="text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="inline-block h-4 w-4 mr-1 align-text-bottom" />
                        {t('reports.accounting_tax_export.invoices_missing_tax', 'Invoices missing explicit tax amount')}:{' '}
                        {qualityQuery.data.invoicesMissingTax}
                      </p>
                      <p className="text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="inline-block h-4 w-4 mr-1 align-text-bottom" />
                        {t('reports.accounting_tax_export.expenses_tax_mismatch', 'Expenses with tax amount/rate mismatch')}:{' '}
                        {qualityQuery.data.expensesTaxMismatch}
                      </p>
                    </div>
                  </>
                ) : (
                  <p className="text-muted-foreground">
                    {t('reports.accounting_tax_export.quality_unavailable', 'Quality metrics unavailable.')}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('reports.accounting_tax_export.journal_title', 'Accounting Journal CSV')}</CardTitle>
                <CardDescription>
                  {t(
                    'reports.accounting_tax_export.journal_description',
                    'Double-entry export for accountant posting and reconciliation.'
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="journal-expenses"
                      checked={journalSources.include_expenses}
                      onCheckedChange={(checked) =>
                        setJournalSources((prev) => ({ ...prev, include_expenses: checked === true }))
                      }
                    />
                    <Label htmlFor="journal-expenses">{t('reports.accounting_tax_export.include_expenses', 'Include Expenses')}</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="journal-invoices"
                      checked={journalSources.include_invoices}
                      onCheckedChange={(checked) =>
                        setJournalSources((prev) => ({ ...prev, include_invoices: checked === true }))
                      }
                    />
                    <Label htmlFor="journal-invoices">{t('reports.accounting_tax_export.include_invoices', 'Include Invoices')}</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="journal-payments"
                      checked={journalSources.include_payments}
                      disabled={journalSources.tax_only}
                      onCheckedChange={(checked) =>
                        setJournalSources((prev) => ({ ...prev, include_payments: checked === true }))
                      }
                    />
                    <Label htmlFor="journal-payments">{t('reports.accounting_tax_export.include_payments', 'Include Payments')}</Label>
                  </div>
                  {journalSources.tax_only && (
                    <p className="text-xs text-muted-foreground pl-6">
                      {t(
                        'reports.accounting_tax_export.tax_only_payments_note',
                        'Payments are excluded in tax-only mode to keep tax-focused journal output.'
                      )}
                    </p>
                  )}
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="journal-tax-only"
                      checked={journalSources.tax_only}
                      onCheckedChange={(checked) =>
                        setJournalSources((prev) => {
                          const taxOnly = checked === true;
                          return {
                            ...prev,
                            tax_only: taxOnly,
                            include_payments: taxOnly ? false : prev.include_payments,
                          };
                        })
                      }
                    />
                    <Label htmlFor="journal-tax-only">{t('reports.accounting_tax_export.tax_only', 'Tax-relevant entries only')}</Label>
                  </div>
                </div>

                <Button
                  className="w-full"
                  onClick={() => journalMutation.mutate()}
                  disabled={journalDisabled || journalMutation.isPending}
                >
                  <FileSpreadsheet className="h-4 w-4 mr-2" />
                  {journalMutation.isPending
                    ? t('reports.accounting_tax_export.downloading', 'Downloading...')
                    : t('reports.accounting_tax_export.download_journal', 'Download Journal CSV')}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t('reports.accounting_tax_export.summary_title', 'Tax Summary CSV')}</CardTitle>
                <CardDescription>
                  {t(
                    'reports.accounting_tax_export.summary_description',
                    'Aggregated input/output tax by rate for filing and period review.'
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="summary-expenses"
                      checked={summarySources.include_expenses}
                      onCheckedChange={(checked) =>
                        setSummarySources((prev) => ({ ...prev, include_expenses: checked === true }))
                      }
                    />
                    <Label htmlFor="summary-expenses">{t('reports.accounting_tax_export.include_expenses', 'Include Expenses')}</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="summary-invoices"
                      checked={summarySources.include_invoices}
                      onCheckedChange={(checked) =>
                        setSummarySources((prev) => ({ ...prev, include_invoices: checked === true }))
                      }
                    />
                    <Label htmlFor="summary-invoices">{t('reports.accounting_tax_export.include_invoices', 'Include Invoices')}</Label>
                  </div>
                </div>

                <Button
                  className="w-full"
                  onClick={() => summaryMutation.mutate()}
                  disabled={summaryDisabled || summaryMutation.isPending}
                >
                  <Download className="h-4 w-4 mr-2" />
                  {summaryMutation.isPending
                    ? t('reports.accounting_tax_export.downloading', 'Downloading...')
                    : t('reports.accounting_tax_export.download_summary', 'Download Tax Summary CSV')}
                </Button>
              </CardContent>
            </Card>
          </div>
        </ContentSection>
      </FeatureGate>
    </div>
  );
};

export default AccountingTaxExport;
