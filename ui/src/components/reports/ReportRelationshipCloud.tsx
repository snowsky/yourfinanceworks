import type { FC } from 'react';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, FileText, Receipt, Landmark, Loader2, Network, Unlink } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { bankStatementApi, expenseApi, invoiceApi, type ReportFilters } from '@/lib/api';

type SupportedReportType = 'invoice' | 'expense' | 'statement';

interface ReportRelationshipCloudProps {
  reportType: string;
  filters: ReportFilters;
}

type CloudNodeType = 'statement' | 'invoice' | 'expense';

interface CloudNode {
  id: string;
  entityId: number;
  type: CloudNodeType;
  title: string;
  subtitle: string;
  status?: string | null;
  x: number;
  y: number;
}

interface CloudEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

const MAX_INVOICES = 40;
const MAX_EXPENSES = 60;
const MAX_STATEMENTS = 30;

const isSupportedReportType = (value: string): value is SupportedReportType =>
  value === 'invoice' || value === 'expense' || value === 'statement';

const matchesDateRange = (value: string | null | undefined, filters: ReportFilters) => {
  if (!value) return true;
  const candidate = new Date(value);
  if (Number.isNaN(candidate.getTime())) return true;

  if (filters.date_from) {
    const from = new Date(`${filters.date_from}T00:00:00`);
    if (candidate < from) return false;
  }

  if (filters.date_to) {
    const to = new Date(`${filters.date_to}T23:59:59`);
    if (candidate > to) return false;
  }

  return true;
};

const formatMoney = (amount?: number, currency?: string) => {
  if (typeof amount !== 'number') return '';
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency || 'USD'} ${amount.toFixed(0)}`;
  }
};

const truncate = (value: string, max = 28) => (
  value.length > max ? `${value.slice(0, max - 1)}...` : value
);

const isPresent = <T,>(value: T | null | undefined): value is T => value != null;

const nodeColors: Record<CloudNodeType, string> = {
  statement: 'border-sky-300 bg-sky-50 text-sky-950',
  invoice: 'border-emerald-300 bg-emerald-50 text-emerald-950',
  expense: 'border-amber-300 bg-amber-50 text-amber-950',
};

export const ReportRelationshipCloud: FC<ReportRelationshipCloudProps> = ({
  reportType,
  filters,
}) => {
  const navigate = useNavigate();

  const enabled = isSupportedReportType(reportType);

  const invoicesQuery = useQuery({
    queryKey: ['report-cloud', 'invoices'],
    queryFn: () => invoiceApi.getInvoices(undefined, undefined, 0, MAX_INVOICES),
    enabled,
    staleTime: 60_000,
  });

  const expensesQuery = useQuery({
    queryKey: ['report-cloud', 'expenses'],
    queryFn: () => expenseApi.getExpensesPaginated({ skip: 0, limit: MAX_EXPENSES }),
    enabled,
    staleTime: 60_000,
  });

  const statementsQuery = useQuery({
    queryKey: ['report-cloud', 'statements'],
    queryFn: () => bankStatementApi.list(0, MAX_STATEMENTS),
    enabled,
    staleTime: 60_000,
  });

  const graph = useMemo(() => {
    if (!enabled) {
      return null;
    }

    const invoices = (invoicesQuery.data?.items || []).filter((invoice) => {
      if (!matchesDateRange(invoice.date || invoice.created_at, filters)) return false;
      if (filters.client_ids?.length && !filters.client_ids.includes(invoice.client_id)) return false;
      if (filters.status?.length && !filters.status.includes(invoice.status)) return false;
      if (typeof filters.amount_min === 'number' && invoice.amount < filters.amount_min) return false;
      if (typeof filters.amount_max === 'number' && invoice.amount > filters.amount_max) return false;
      return true;
    });

    const expenses = (expensesQuery.data?.expenses || []).filter((expense) => {
      if (!matchesDateRange(expense.expense_date, filters)) return false;
      if (filters.client_ids?.length && expense.client_id && !filters.client_ids.includes(expense.client_id)) return false;
      if (filters.status?.length && !filters.status.includes(expense.status)) return false;
      if (filters.categories?.length && !filters.categories.includes(expense.category)) return false;
      if (filters.labels?.length) {
        const labels = expense.labels || [];
        if (!filters.labels.some((label) => labels.includes(label))) return false;
      }
      if (typeof filters.amount_min === 'number' && expense.amount < filters.amount_min) return false;
      if (typeof filters.amount_max === 'number' && expense.amount > filters.amount_max) return false;
      return true;
    });

    const statements = (statementsQuery.data?.statements || []).filter((statement) =>
      matchesDateRange(statement.created_at, filters)
    );

    const invoiceMap = new Map(invoices.map((invoice) => [invoice.id, invoice]));
    const expenseMap = new Map(expenses.map((expense) => [expense.id, expense]));
    const statementMap = new Map(statements.map((statement) => [statement.id, statement]));

    const focalInvoiceIds = new Set<number>();
    const focalExpenseIds = new Set<number>();
    const focalStatementIds = new Set<number>();

    if (reportType === 'invoice') {
      invoices.forEach((invoice) => focalInvoiceIds.add(invoice.id));
      expenses.forEach((expense) => {
        if (expense.invoice_id && focalInvoiceIds.has(expense.invoice_id)) {
          focalExpenseIds.add(expense.id);
        }
      });
      invoices.forEach((invoice) => {
        if (invoice.statement_id) focalStatementIds.add(invoice.statement_id);
      });
      expenses.forEach((expense) => {
        if (focalExpenseIds.has(expense.id) && expense.statement_id) {
          focalStatementIds.add(expense.statement_id);
        }
      });
    }

    if (reportType === 'expense') {
      expenses.forEach((expense) => focalExpenseIds.add(expense.id));
      expenses.forEach((expense) => {
        if (expense.invoice_id) focalInvoiceIds.add(expense.invoice_id);
        if (expense.statement_id) focalStatementIds.add(expense.statement_id);
      });
      invoices.forEach((invoice) => {
        if (focalInvoiceIds.has(invoice.id) && invoice.statement_id) {
          focalStatementIds.add(invoice.statement_id);
        }
      });
    }

    if (reportType === 'statement') {
      statements.forEach((statement) => focalStatementIds.add(statement.id));
      invoices.forEach((invoice) => {
        if (invoice.statement_id && focalStatementIds.has(invoice.statement_id)) {
          focalInvoiceIds.add(invoice.id);
        }
      });
      expenses.forEach((expense) => {
        if (expense.statement_id && focalStatementIds.has(expense.statement_id)) {
          focalExpenseIds.add(expense.id);
        }
      });
      expenses.forEach((expense) => {
        if (focalExpenseIds.has(expense.id) && expense.invoice_id) {
          focalInvoiceIds.add(expense.invoice_id);
        }
      });
    }

    const selectedStatements = [...focalStatementIds].map((id) => statementMap.get(id)).filter(isPresent);
    const selectedInvoices = [...focalInvoiceIds].map((id) => invoiceMap.get(id)).filter(isPresent);
    const selectedExpenses = [...focalExpenseIds].map((id) => expenseMap.get(id)).filter(isPresent);

    const nodes: CloudNode[] = [];
    const edges: CloudEdge[] = [];

    const columns = [
      { type: 'statement' as const, x: 14, items: selectedStatements },
      { type: 'invoice' as const, x: 50, items: selectedInvoices },
      { type: 'expense' as const, x: 86, items: selectedExpenses },
    ];

    columns.forEach((column) => {
      const spacing = 100 / (column.items.length + 1);
      column.items.forEach((item, index) => {
        if (!item) return;
        if (column.type === 'statement') {
          nodes.push({
            id: `statement-${item.id}`,
            entityId: item.id,
            type: 'statement',
            title: truncate(item.original_filename || `Statement #${item.id}`),
            subtitle: `${item.extracted_count || 0} txns`,
            status: item.status,
            x: column.x,
            y: Math.max(14, Math.min(86, spacing * (index + 1))),
          });
        }
        if (column.type === 'invoice') {
          nodes.push({
            id: `invoice-${item.id}`,
            entityId: item.id,
            type: 'invoice',
            title: truncate(item.number),
            subtitle: `${item.client_name || 'Client'} • ${formatMoney(item.amount, item.currency)}`,
            status: item.status,
            x: column.x,
            y: Math.max(14, Math.min(86, spacing * (index + 1))),
          });
        }
        if (column.type === 'expense') {
          nodes.push({
            id: `expense-${item.id}`,
            entityId: item.id,
            type: 'expense',
            title: truncate(item.vendor || item.category || `Expense #${item.id}`),
            subtitle: `${item.category} • ${formatMoney(item.amount, item.currency)}`,
            status: item.status,
            x: column.x,
            y: Math.max(14, Math.min(86, spacing * (index + 1))),
          });
        }
      });
    });

    selectedInvoices.forEach((invoice) => {
      if (invoice?.statement_id && focalStatementIds.has(invoice.statement_id)) {
        edges.push({
          id: `statement-invoice-${invoice.id}`,
          source: `statement-${invoice.statement_id}`,
          target: `invoice-${invoice.id}`,
          label: 'statement link',
        });
      }
    });

    selectedExpenses.forEach((expense) => {
      if (expense?.invoice_id && focalInvoiceIds.has(expense.invoice_id)) {
        edges.push({
          id: `invoice-expense-${expense.id}`,
          source: `invoice-${expense.invoice_id}`,
          target: `expense-${expense.id}`,
          label: 'invoice link',
        });
      }
      if (expense?.statement_id && focalStatementIds.has(expense.statement_id)) {
        edges.push({
          id: `statement-expense-${expense.id}`,
          source: `statement-${expense.statement_id}`,
          target: `expense-${expense.id}`,
          label: 'transaction match',
        });
      }
    });

    return {
      nodes,
      edges,
      stats: {
        statements: selectedStatements.length,
        invoices: selectedInvoices.length,
        expenses: selectedExpenses.length,
        orphanExpenses: selectedExpenses.filter((expense) => !expense?.invoice_id && !expense?.statement_id).length,
      },
    };
  }, [
    enabled,
    expensesQuery.data?.expenses,
    filters,
    invoicesQuery.data?.items,
    reportType,
    statementsQuery.data?.statements,
  ]);

  if (!enabled) {
    return null;
  }

  const isLoading = invoicesQuery.isLoading || expensesQuery.isLoading || statementsQuery.isLoading;
  const hasError = invoicesQuery.isError || expensesQuery.isError || statementsQuery.isError;

  const nodeById = new Map(graph?.nodes.map((node) => [node.id, node]) || []);

  const openNode = (node: CloudNode) => {
    if (node.type === 'statement') navigate(`/statements?id=${node.entityId}`);
    if (node.type === 'invoice') navigate(`/invoices/${node.entityId}`);
    if (node.type === 'expense') navigate(`/expenses/${node.entityId}`);
  };

  return (
    <Card className="slide-in overflow-hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Network className="h-5 w-5" />
          Relationship Cloud
        </CardTitle>
        <CardDescription>
          Visual map of how statements, invoices, and expenses connect inside the current report scope.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Building relationship map...
            </div>
          </div>
        ) : hasError ? (
          <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
            The relationship cloud could not be loaded right now.
          </div>
        ) : !graph || graph.nodes.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
            No linked statement, invoice, or expense records were found for the current report filters.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{graph.stats.statements} statements</Badge>
              <Badge variant="outline">{graph.stats.invoices} invoices</Badge>
              <Badge variant="outline">{graph.stats.expenses} expenses</Badge>
              {graph.stats.orphanExpenses > 0 && (
                <Badge variant="secondary" className="gap-1">
                  <Unlink className="h-3 w-3" />
                  {graph.stats.orphanExpenses} orphan expenses
                </Badge>
              )}
            </div>

            <div className="relative min-h-[320px] rounded-2xl border bg-gradient-to-br from-background via-muted/20 to-background">
              <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                {graph.edges.map((edge) => {
                  const source = nodeById.get(edge.source);
                  const target = nodeById.get(edge.target);
                  if (!source || !target) return null;
                  return (
                    <g key={edge.id}>
                      <line
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke="currentColor"
                        strokeWidth="0.5"
                        className="text-border"
                        strokeDasharray={edge.label === 'transaction match' ? '2 1.5' : undefined}
                      />
                    </g>
                  );
                })}
              </svg>

              {graph.nodes.map((node) => {
                const Icon = node.type === 'statement' ? Landmark : node.type === 'invoice' ? FileText : Receipt;
                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => openNode(node)}
                    className={`absolute w-40 -translate-x-1/2 -translate-y-1/2 rounded-xl border p-3 text-left shadow-sm transition hover:scale-[1.02] hover:shadow-md ${nodeColors[node.type]}`}
                    style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="rounded-lg bg-white/70 p-1.5">
                        <Icon className="h-4 w-4" />
                      </div>
                      {node.status ? (
                        <Badge variant="secondary" className="max-w-[68px] truncate text-[10px]">
                          {node.status}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="text-sm font-semibold leading-tight">{node.title}</div>
                    <div className="mt-1 text-xs opacity-80">{node.subtitle}</div>
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><Landmark className="h-3.5 w-3.5" /> Statement</span>
              <span className="inline-flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> Invoice</span>
              <span className="inline-flex items-center gap-1"><Receipt className="h-3.5 w-3.5" /> Expense</span>
            </div>

            <div className="flex justify-end">
              <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/statements')}>
                Explore statements
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};
