import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { shareTokenApi } from '@/lib/api/share-tokens';
import { AlertCircle, FileText, Receipt, CreditCard, Users, Landmark, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const RECORD_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  invoice: FileText,
  expense: Receipt,
  payment: CreditCard,
  client: Users,
  bank_statement: Landmark,
  portfolio: TrendingUp,
};

function formatCurrency(amount: number | null | undefined, currency = 'USD') {
  if (amount == null) return '—';
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
}

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function InvoiceView({ data }: { data: any }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div><span className="text-muted-foreground">Invoice #</span><p className="font-medium">{data.number}</p></div>
        <div><span className="text-muted-foreground">Status</span><p className="font-medium capitalize">{data.status}</p></div>
        <div><span className="text-muted-foreground">Due date</span><p className="font-medium">{formatDate(data.due_date)}</p></div>
        <div><span className="text-muted-foreground">Client</span><p className="font-medium">{data.client_name || '—'}{data.client_company ? ` · ${data.client_company}` : ''}</p></div>
        {data.description && <div className="col-span-2"><span className="text-muted-foreground">Description</span><p className="font-medium">{data.description}</p></div>}
      </div>
      {data.items?.length > 0 && (
        <div>
          <p className="text-sm font-semibold mb-2">Line items</p>
          <table className="w-full text-sm border-collapse">
            <thead><tr className="border-b text-muted-foreground"><th className="text-left py-1">Description</th><th className="text-right py-1">Qty</th><th className="text-right py-1">Price</th><th className="text-right py-1">Amount</th></tr></thead>
            <tbody>
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              {data.items.map((item: any, i: number) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1">{item.description}</td>
                  <td className="text-right py-1">{item.quantity}</td>
                  <td className="text-right py-1">{formatCurrency(item.price, data.currency)}</td>
                  <td className="text-right py-1">{formatCurrency(item.amount, data.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="text-right space-y-1 text-sm">
        <p>Subtotal: {formatCurrency(data.subtotal, data.currency)}</p>
        {data.discount_value > 0 && <p>Discount ({data.discount_type}): {data.discount_type === 'percentage' ? `${data.discount_value}%` : formatCurrency(data.discount_value, data.currency)}</p>}
        <p className="text-base font-bold">Total: {formatCurrency(data.amount, data.currency)}</p>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ExpenseView({ data }: { data: any }) {
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div><span className="text-muted-foreground">Amount</span><p className="font-medium">{formatCurrency(data.total_amount ?? data.amount, data.currency)}</p></div>
      <div><span className="text-muted-foreground">Category</span><p className="font-medium">{data.category}</p></div>
      <div><span className="text-muted-foreground">Date</span><p className="font-medium">{formatDate(data.expense_date)}</p></div>
      <div><span className="text-muted-foreground">Status</span><p className="font-medium capitalize">{data.status}</p></div>
      {data.vendor && <div><span className="text-muted-foreground">Vendor</span><p className="font-medium">{data.vendor}</p></div>}
      {data.payment_method && <div><span className="text-muted-foreground">Payment method</span><p className="font-medium">{data.payment_method}</p></div>}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function PaymentView({ data }: { data: any }) {
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div><span className="text-muted-foreground">Amount</span><p className="font-medium">{formatCurrency(data.amount, data.currency)}</p></div>
      <div><span className="text-muted-foreground">Date</span><p className="font-medium">{formatDate(data.payment_date)}</p></div>
      <div><span className="text-muted-foreground">Method</span><p className="font-medium">{data.payment_method}</p></div>
      {data.invoice_number && <div><span className="text-muted-foreground">Invoice #</span><p className="font-medium">{data.invoice_number}</p></div>}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ClientView({ data }: { data: any }) {
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div><span className="text-muted-foreground">Name</span><p className="font-medium">{data.name || '—'}</p></div>
      {data.company && <div><span className="text-muted-foreground">Company</span><p className="font-medium">{data.company}</p></div>}
      <div><span className="text-muted-foreground">Member since</span><p className="font-medium">{formatDate(data.created_at)}</p></div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BankStatementView({ data }: { data: any }) {
  const hasBalance = data.transactions?.some((tx: any) => tx.balance != null);
  const hasCategory = data.transactions?.some((tx: any) => tx.category);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        {data.bank_name && <div className="col-span-2"><span className="text-muted-foreground">Bank</span><p className="font-medium">{data.bank_name}</p></div>}
        <div><span className="text-muted-foreground">File</span><p className="font-medium">{data.original_filename}</p></div>
        <div><span className="text-muted-foreground">Card type</span><p className="font-medium capitalize">{data.card_type}</p></div>
        <div><span className="text-muted-foreground">Status</span><p className="font-medium capitalize">{data.status}</p></div>
        <div><span className="text-muted-foreground">Transactions</span><p className="font-medium">{data.extracted_count}</p></div>
      </div>
      {data.transactions?.length > 0 ? (
        <div>
          <p className="text-sm font-semibold mb-2">Transactions ({data.transactions.length})</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse min-w-[480px]">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-1.5 pr-3">Date</th>
                  <th className="text-left py-1.5 pr-3">Description</th>
                  {hasCategory && <th className="text-left py-1.5 pr-3">Category</th>}
                  <th className="text-right py-1.5 pr-3">Amount</th>
                  {hasBalance && <th className="text-right py-1.5">Balance</th>}
                </tr>
              </thead>
              <tbody>
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {data.transactions.map((tx: any, i: number) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{formatDate(tx.date)}</td>
                    <td className="py-1.5 pr-3">{tx.description}</td>
                    {hasCategory && <td className="py-1.5 pr-3 text-muted-foreground capitalize">{tx.category || '—'}</td>}
                    <td className={`py-1.5 pr-3 text-right font-mono whitespace-nowrap ${tx.transaction_type === 'credit' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {tx.transaction_type === 'credit' ? '+' : '-'}{Math.abs(tx.amount).toFixed(2)}
                    </td>
                    {hasBalance && <td className="py-1.5 text-right font-mono text-muted-foreground whitespace-nowrap">{tx.balance != null ? tx.balance.toFixed(2) : '—'}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground italic">No transactions available.</p>
      )}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function PortfolioView({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div><span className="text-muted-foreground">Name</span><p className="font-medium">{data.name}</p></div>
        <div><span className="text-muted-foreground">Type</span><p className="font-medium capitalize">{data.portfolio_type}</p></div>
        <div><span className="text-muted-foreground">Currency</span><p className="font-medium">{data.currency}</p></div>
        <div><span className="text-muted-foreground">Created</span><p className="font-medium">{formatDate(data.created_at)}</p></div>
      </div>
      {data.holdings?.length > 0 && (
        <div>
          <p className="text-sm font-semibold mb-2">Holdings</p>
          <table className="w-full text-sm border-collapse">
            <thead><tr className="border-b text-muted-foreground"><th className="text-left py-1">Symbol</th><th className="text-left py-1">Name</th><th className="text-left py-1">Type</th><th className="text-right py-1">Quantity</th></tr></thead>
            <tbody>
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              {data.holdings.map((h: any, i: number) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1 font-mono font-medium">{h.security_symbol}</td>
                  <td className="py-1">{h.security_name || '—'}</td>
                  <td className="py-1 capitalize">{h.security_type}</td>
                  <td className="text-right py-1">{h.quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const RECORD_LABELS: Record<string, string> = {
  invoice: 'Invoice',
  expense: 'Expense',
  payment: 'Payment',
  client: 'Client',
  bank_statement: 'Bank Statement',
  portfolio: 'Investment Portfolio',
};

export default function SharedRecord() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    shareTokenApi.getPublicRecord(token)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  const recordType = (data?.record_type as string) ?? '';
  const Icon = RECORD_ICONS[recordType] ?? FileText;
  const label = RECORD_LABELS[recordType] ?? 'Record';

  const isBankStatement = recordType === 'bank_statement';

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-start p-6">
      <div className={`w-full ${isBankStatement ? 'max-w-4xl' : 'max-w-2xl'} space-y-6 mt-8`}>
        {loading && (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground text-sm">Loading…</CardContent>
          </Card>
        )}

        {error && (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center gap-3 text-center">
                <AlertCircle className="h-8 w-8 text-destructive" />
                <p className="font-medium">{error}</p>
                <p className="text-sm text-muted-foreground">This link may have been revoked or may have expired.</p>
              </div>
            </CardContent>
          </Card>
        )}

        {data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Icon className="h-5 w-5" />
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {recordType === 'invoice' && <InvoiceView data={data} />}
              {recordType === 'expense' && <ExpenseView data={data} />}
              {recordType === 'payment' && <PaymentView data={data} />}
              {recordType === 'client' && <ClientView data={data} />}
              {recordType === 'bank_statement' && <BankStatementView data={data} />}
              {recordType === 'portfolio' && <PortfolioView data={data} />}
            </CardContent>
          </Card>
        )}

        <p className="text-center text-xs text-muted-foreground">
          Powered by <a href="/" className="underline hover:text-foreground">YourFinanceWORKS</a>
        </p>
      </div>
    </div>
  );
}
