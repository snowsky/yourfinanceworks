import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ShareAccessRequiredError, shareTokenApi, type ShareAccessRequirement } from '@/lib/api/share-tokens';
import { AlertCircle, FileText, Receipt, CreditCard, Users, Landmark, TrendingUp, Download, LockKeyhole } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DEFAULT_BRANDING, isHexColor, readableTextColor } from '@/lib/invoice-branding';

const RECORD_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  invoice: FileText,
  expense: Receipt,
  payment: CreditCard,
  client: Users,
  bank_statement: Landmark,
  portfolio: TrendingUp,
  docvault_item: LockKeyhole,
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
  const b = data.branding || null;
  const brandColor = b && isHexColor(b.brand_color) ? b.brand_color : DEFAULT_BRANDING.brand_color;
  const accentColor = b && isHexColor(b.accent_color) ? b.accent_color : DEFAULT_BRANDING.accent_color;
  const headerText = readableTextColor(brandColor);

  return (
    <div className="space-y-6">
      {b && (
        <div
          className="px-5 py-4 flex items-start justify-between gap-4 rounded-lg"
          style={{ backgroundColor: brandColor, color: headerText }}
        >
          <div className="flex items-center gap-3 min-w-0">
            {b.company_logo_url && (
              <img src={b.company_logo_url} alt="" className="h-12 w-12 rounded bg-white/95 object-contain p-1 shrink-0" />
            )}
            <div className="min-w-0">
              {b.company_name && <p className="font-bold text-lg leading-tight truncate">{b.company_name}</p>}
              <p className="text-xs opacity-80 leading-tight">
                {[b.company_email, b.company_phone].filter(Boolean).join(' · ')}
              </p>
              {b.company_address && <p className="text-xs opacity-80 leading-tight">{b.company_address}</p>}
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs uppercase tracking-wide opacity-80">Invoice</p>
            <p className="font-mono font-bold">{data.number}</p>
            <p className="text-xs capitalize opacity-80">{data.status}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        {!b && <div><span className="text-muted-foreground">Invoice #</span><p className="font-medium">{data.number}</p></div>}
        {!b && <div><span className="text-muted-foreground">Status</span><p className="font-medium capitalize">{data.status}</p></div>}
        <div><span className="text-muted-foreground">Due date</span><p className="font-medium">{formatDate(data.due_date)}</p></div>
        <div><span className="text-muted-foreground">Bill to</span><p className="font-medium">{data.client_name || '—'}{data.client_company ? ` · ${data.client_company}` : ''}</p></div>
        {data.description && <div className="col-span-2"><span className="text-muted-foreground">Description</span><p className="font-medium">{data.description}</p></div>}
      </div>
      {data.items?.length > 0 && (
        <div>
          <p className="text-sm font-semibold mb-2">Line items</p>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-muted-foreground" style={{ borderBottom: `2px solid ${accentColor}` }}>
                <th className="text-left py-1">Description</th><th className="text-right py-1">Qty</th><th className="text-right py-1">Price</th><th className="text-right py-1">Amount</th>
              </tr>
            </thead>
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
        <p className="text-base font-bold" style={b ? { color: brandColor } : undefined}>Total: {formatCurrency(data.amount, data.currency)}</p>
      </div>
      {b?.footer_text && (
        <p className="pt-3 border-t text-xs text-muted-foreground text-center">{b.footer_text}</p>
      )}
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
  const transactions = (data.transactions || []) as Array<Record<string, unknown>>;
  const hasBalance = transactions.some((tx) => tx.balance != null);
  const hasCategory = transactions.some((tx) => tx.category);
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DocVaultItemView({ data }: { data: any }) {
  const metadata = data.public_metadata || {};
  const cloud = metadata.cloud_integration;
  const documentLabel = metadata.document_label;
  const approvalStatus = metadata.approval_status;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div><span className="text-muted-foreground">Title</span><p className="font-medium">{data.title || '—'}</p></div>
        <div><span className="text-muted-foreground">Type</span><p className="font-medium capitalize">{String(data.category || '').replace(/_/g, ' ')}</p></div>
        {data.owner_name && <div><span className="text-muted-foreground">Owner</span><p className="font-medium">{data.owner_name}</p></div>}
        {data.issuer && <div><span className="text-muted-foreground">Issuer</span><p className="font-medium">{data.issuer}</p></div>}
        {data.issue_date && <div><span className="text-muted-foreground">Issue date</span><p className="font-medium">{formatDate(data.issue_date)}</p></div>}
        {data.expiry_date && <div><span className="text-muted-foreground">Expiry date</span><p className="font-medium">{formatDate(data.expiry_date)}</p></div>}
        {data.file_name && <div><span className="text-muted-foreground">File</span><p className="font-medium">{data.file_name}</p></div>}
        {cloud?.provider_label && <div><span className="text-muted-foreground">Cloud source</span><p className="font-medium">{cloud.provider_label}</p></div>}
        {documentLabel && <div><span className="text-muted-foreground">Label</span><p className="font-medium capitalize">{String(documentLabel).replace(/_/g, ' ')}</p></div>}
        {approvalStatus && <div><span className="text-muted-foreground">Approval</span><p className="font-medium capitalize">{String(approvalStatus).replace(/_/g, ' ')}</p></div>}
        <div><span className="text-muted-foreground">Created</span><p className="font-medium">{formatDate(data.created_at)}</p></div>
      </div>
      {data.tags?.length > 0 && (
        <div>
          <span className="text-sm text-muted-foreground">Tags</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.tags.map((tag: string) => (
              <span key={tag} className="rounded-md border px-2 py-1 text-xs">{tag}</span>
            ))}
          </div>
        </div>
      )}
      <p className="text-sm text-muted-foreground">
        Sensitive vault details and file contents are not included in shared DocVault item views.
      </p>
    </div>
  );
}

function escapeCsvField(value: unknown): string {
  const str = value == null ? '' : String(value);
  return str.includes(',') || str.includes('"') || str.includes('\n')
    ? `"${str.replace(/"/g, '""')}"`
    : str;
}

function buildCsv(rows: unknown[][]): string {
  return rows.map(row => row.map(escapeCsvField).join(',')).join('\n');
}

function downloadCsv(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildRecordCsv(recordType: string, data: any): { csv: string; filename: string } | null {
  if (recordType === 'bank_statement' && data.transactions?.length > 0) {
    const header = ['Date', 'Description', 'Type', 'Category', 'Amount', 'Balance'];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rows = data.transactions.map((tx: any) => [
      tx.date,
      tx.description,
      tx.transaction_type,
      tx.category ?? '',
      (tx.transaction_type === 'credit' ? 1 : -1) * Math.abs(tx.amount),
      tx.balance ?? '',
    ]);
    const base = (data.original_filename as string).replace(/\.[^.]+$/, '');
    return { csv: buildCsv([header, ...rows]), filename: `${base}-transactions.csv` };
  }
  if (recordType === 'invoice' && data.items?.length > 0) {
    const header = ['Description', 'Quantity', 'Price', 'Amount', 'Unit'];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rows = data.items.map((item: any) => [
      item.description, item.quantity, item.price, item.amount, item.unit_of_measure ?? '',
    ]);
    return { csv: buildCsv([header, ...rows]), filename: `invoice-${data.number}-items.csv` };
  }
  if (recordType === 'portfolio' && data.holdings?.length > 0) {
    const header = ['Symbol', 'Name', 'Type', 'Asset Class', 'Quantity', 'Currency'];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rows = data.holdings.map((h: any) => [
      h.security_symbol, h.security_name ?? '', h.security_type, h.asset_class, h.quantity, h.currency,
    ]);
    return { csv: buildCsv([header, ...rows]), filename: `${data.name}-holdings.csv` };
  }
  return null;
}

const RECORD_LABELS: Record<string, string> = {
  invoice: 'Invoice',
  expense: 'Expense',
  payment: 'Payment',
  client: 'Client',
  bank_statement: 'Bank Statement',
  portfolio: 'Investment Portfolio',
  docvault_item: 'DocVault Item',
};

export default function SharedRecord() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessRequirement, setAccessRequirement] = useState<ShareAccessRequirement | null>(null);
  const [verificationValue, setVerificationValue] = useState('');
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    shareTokenApi.getPublicRecord(token)
      .then((record) => {
        setData(record);
        setError(null);
        setAccessRequirement(null);
      })
      .catch((e: Error) => {
        if (e instanceof ShareAccessRequiredError) {
          setAccessRequirement(e.requirement);
          setError(null);
          return;
        }
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const handleVerify = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token || !accessRequirement) return;
    setVerifying(true);
    setError(null);
    try {
      const record = await shareTokenApi.getPublicRecord(token, {
        password: accessRequirement.access_type === 'password' ? verificationValue : undefined,
        security_answer: accessRequirement.access_type === 'question' ? verificationValue : undefined,
      });
      setData(record);
      setAccessRequirement(null);
      setVerificationValue('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to verify this shared link');
    } finally {
      setVerifying(false);
    }
  };

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

        {accessRequirement && !data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <LockKeyhole className="h-5 w-5" />
                Verification Required
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form className="space-y-4" onSubmit={handleVerify}>
                <div className="space-y-2">
                  <Label htmlFor="share-verification">
                    {accessRequirement.access_type === 'question'
                      ? accessRequirement.security_question || 'Answer the security question'
                      : 'Password'}
                  </Label>
                  <Input
                    id="share-verification"
                    type="password"
                    value={verificationValue}
                    onChange={(event) => setVerificationValue(event.target.value)}
                    autoFocus
                  />
                </div>
                <Button type="submit" disabled={verifying || !verificationValue.trim()}>
                  {verifying ? 'Verifying...' : 'View Record'}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {data && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Icon className="h-5 w-5" />
                  {label}
                </CardTitle>
                {(() => {
                  const exportable = buildRecordCsv(recordType, data);
                  if (!exportable) return null;
                  return (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => downloadCsv(exportable.csv, exportable.filename)}
                    >
                      <Download className="h-4 w-4 mr-1" />
                      Export CSV
                    </Button>
                  );
                })()}
              </div>
            </CardHeader>
            <CardContent>
              {recordType === 'invoice' && <InvoiceView data={data} />}
              {recordType === 'expense' && <ExpenseView data={data} />}
              {recordType === 'payment' && <PaymentView data={data} />}
              {recordType === 'client' && <ClientView data={data} />}
              {recordType === 'bank_statement' && <BankStatementView data={data} />}
              {recordType === 'portfolio' && <PortfolioView data={data} />}
              {recordType === 'docvault_item' && <DocVaultItemView data={data} />}
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
