import { downloadCsvExport } from './_base';

export interface AccountingExportJournalParams {
  [key: string]: string | number | boolean | undefined;
  date_from?: string;
  date_to?: string;
  include_drafts?: boolean;
  tax_only?: boolean;
  include_expenses?: boolean;
  include_invoices?: boolean;
  include_payments?: boolean;
}

export interface AccountingExportTaxSummaryParams {
  [key: string]: string | number | boolean | undefined;
  date_from?: string;
  date_to?: string;
  include_drafts?: boolean;
  include_expenses?: boolean;
  include_invoices?: boolean;
}

export const accountingExportApi = {
  downloadJournal: (params: AccountingExportJournalParams = {}) =>
    downloadCsvExport('/accounting-export/journal', params),

  downloadTaxSummary: (params: AccountingExportTaxSummaryParams = {}) =>
    downloadCsvExport('/accounting-export/tax-summary', params),
};
