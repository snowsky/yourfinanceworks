import type { FC } from 'react';
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, FileText, Landmark, Link2, Receipt, TrendingUp } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { reportApi, type RelationshipCloudResponse, type ReportFilters } from '@/lib/api';

type SupportedReportType = 'invoice' | 'expense' | 'statement';

interface ReportRelationshipSummaryProps {
  reportType: string;
  filters: ReportFilters;
}

const isSupportedReportType = (value: string): value is SupportedReportType =>
  value === 'invoice' || value === 'expense' || value === 'statement';

export const ReportRelationshipSummary: FC<ReportRelationshipSummaryProps> = ({
  reportType,
  filters,
}) => {
  const enabled = isSupportedReportType(reportType);

  const cloudQuery = useQuery({
    queryKey: ['report-cloud', reportType, filters],
    queryFn: () => reportApi.getRelationshipCloud({
      report_type: reportType as SupportedReportType,
      filters,
      limit: 40,
    }),
    enabled,
    staleTime: 60_000,
  });

  const summary = useMemo(() => {
    const data = cloudQuery.data as RelationshipCloudResponse | undefined;
    if (!data) return null;

    const invoiceExpenseEdges = data.edges.filter((edge) => edge.label === 'invoice link').length;
    const statementEdges = data.edges.filter((edge) => edge.label !== 'invoice link').length;
    const totalLinked = data.edges.length;
    const totalNodes = data.nodes.length;
    const linkageCoverage = totalNodes > 0 ? Math.round((Math.min(totalLinked * 2, totalNodes) / totalNodes) * 100) : 0;

    return {
      statements: data.stats.statements,
      invoices: data.stats.invoices,
      expenses: data.stats.expenses,
      orphanExpenses: data.stats.orphan_expenses,
      invoiceExpenseEdges,
      statementEdges,
      totalLinked,
      linkageCoverage,
    };
  }, [cloudQuery.data]);

  if (!enabled) return null;

  return (
    <Card className="slide-in">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="h-5 w-5" />
          Relationship Summary
        </CardTitle>
        <CardDescription>
          Quick health check for linked statements, invoices, and expenses in this report.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!summary ? (
          <div className="text-sm text-muted-foreground">
            {cloudQuery.isLoading ? 'Loading relationship summary...' : 'No relationship summary available for this report scope.'}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border p-3">
                <div className="mb-1 flex items-center gap-1 text-muted-foreground">
                  <Landmark className="h-3.5 w-3.5" />
                  <span className="text-xs">Statements</span>
                </div>
                <div className="text-lg font-semibold">{summary.statements}</div>
              </div>
              <div className="rounded-lg border p-3">
                <div className="mb-1 flex items-center gap-1 text-muted-foreground">
                  <FileText className="h-3.5 w-3.5" />
                  <span className="text-xs">Invoices</span>
                </div>
                <div className="text-lg font-semibold">{summary.invoices}</div>
              </div>
              <div className="rounded-lg border p-3">
                <div className="mb-1 flex items-center gap-1 text-muted-foreground">
                  <Receipt className="h-3.5 w-3.5" />
                  <span className="text-xs">Expenses</span>
                </div>
                <div className="text-lg font-semibold">{summary.expenses}</div>
              </div>
            </div>

            <div className="rounded-xl border bg-muted/30 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium">Linkage coverage</span>
                <Badge variant={summary.linkageCoverage >= 60 ? 'default' : 'secondary'}>
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {summary.linkageCoverage}%
                </Badge>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${summary.linkageCoverage}%` }}
                />
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                <span>Invoice to expense links</span>
                <span className="font-medium">{summary.invoiceExpenseEdges}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                <span>Statement-linked records</span>
                <span className="font-medium">{summary.statementEdges}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                <span>Total visible relationships</span>
                <span className="font-medium">{summary.totalLinked}</span>
              </div>
            </div>

            {summary.orphanExpenses > 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <div className="mb-1 flex items-center gap-2 font-medium">
                  <AlertTriangle className="h-4 w-4" />
                  {summary.orphanExpenses} orphan expenses detected
                </div>
                <p>These expenses are visible in the report scope but are not linked to an invoice or statement transaction.</p>
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                All visible expenses are attached to an invoice or statement chain.
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};
