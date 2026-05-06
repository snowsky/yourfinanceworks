import React from 'react';
import {
  AlertCircle,
  BadgeCheck,
  Copy,
  CreditCard,
  FileKey2,
  FileText,
  IdCard,
  KeyRound,
  Lock,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { apiRequest } from '@/lib/api';

type Category = 'credit_card' | 'ssl_certificate' | 'id_card' | 'document' | 'secret';
type ExpiryStatus = 'expired' | 'expiring_soon' | 'valid';

interface DocVaultEntry {
  id: number;
  category: Category;
  title: string;
  owner_name?: string | null;
  issuer?: string | null;
  expiry_date?: string | null;
  issue_date?: string | null;
  public_metadata: Record<string, any>;
  sensitive_payload: Record<string, any>;
  notes?: string | null;
  tags: string[];
  thumbnail_data_url?: string | null;
  file_name?: string | null;
  file_mime_type?: string | null;
  file_size?: number | null;
  file_data_url?: string | null;
  expiry_status: ExpiryStatus;
  days_delta?: number | null;
  alerting: boolean;
  sensitive_available: boolean;
  created_at: string;
}

const emptyForm = {
  title: '',
  owner_name: '',
  issuer: '',
  expiry_date: '',
  issue_date: '',
  notes: '',
  tags: '',
  network: 'Visa',
  card_number: '',
  expiry_mm_yy: '',
  bank: '',
  domain: '',
  card_type: '',
  issuing_authority: '',
  password: '',
  private_key: '',
};

const tabConfig: Array<{ id: Category | 'all'; label: string; icon: React.ElementType }> = [
  { id: 'credit_card', label: 'Credit Cards', icon: CreditCard },
  { id: 'ssl_certificate', label: 'SSL Certificates', icon: ShieldCheck },
  { id: 'id_card', label: 'ID & Health Cards', icon: IdCard },
  { id: 'document', label: 'Documents', icon: FileText },
  { id: 'secret', label: 'Passwords & Keys', icon: FileKey2 },
];

const networkStyles: Record<string, string> = {
  Visa: 'from-slate-950 to-blue-900',
  Mastercard: 'from-zinc-950 to-neutral-800',
  Amex: 'from-blue-700 to-sky-500',
  Discover: 'from-orange-600 to-amber-400',
  UnionPay: 'from-red-700 to-rose-500',
};

function expiryPreview(category: Category, expiry: string): { status: ExpiryStatus; days: number | null } {
  if (!expiry) return { status: 'valid', days: null };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(expiry);
  const days = Math.ceil((target.getTime() - today.getTime()) / 86400000);
  if (days < 0) return { status: 'expired', days };
  const windowDays = category === 'credit_card' ? 60 : 30;
  return { status: days <= windowDays ? 'expiring_soon' : 'valid', days };
}

function statusText(entry: Pick<DocVaultEntry, 'expiry_status' | 'days_delta'>) {
  if (entry.days_delta == null) return 'No expiry';
  if (entry.expiry_status === 'expired') return `${Math.abs(entry.days_delta)} days expired`;
  if (entry.expiry_status === 'expiring_soon') return `${entry.days_delta} days left`;
  return `${entry.days_delta} days left`;
}

function StatusBadge({ status, days }: { status: ExpiryStatus; days: number | null | undefined }) {
  const tone = status === 'expired'
    ? 'bg-red-100 text-red-700 border-red-200'
    : status === 'expiring_soon'
      ? 'bg-yellow-100 text-yellow-800 border-yellow-200'
      : 'bg-emerald-100 text-emerald-700 border-emerald-200';
  return <Badge variant="outline" className={tone}>{statusText({ expiry_status: status, days_delta: days })}</Badge>;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function fileSize(bytes?: number | null) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function CardVisual({ form }: { form: typeof emptyForm }) {
  const number = form.card_number.replace(/\D/g, '');
  const last4 = number.slice(-4).padStart(4, '•');
  return (
    <div className={`aspect-[1.586/1] w-full rounded-xl bg-gradient-to-br ${networkStyles[form.network] || networkStyles.Visa} p-5 text-white shadow-lg`}>
      <div className="flex items-start justify-between">
        <div className="h-8 w-11 rounded-md bg-gradient-to-br from-yellow-200 to-yellow-600 shadow-inner" />
        <span className="text-lg font-semibold">{form.network}</span>
      </div>
      <div className="mt-8 font-mono text-xl tracking-widest">•••• •••• •••• {last4}</div>
      <div className="mt-6 flex justify-between text-xs uppercase">
        <div>
          <div className="text-white/60">Cardholder</div>
          <div className="font-semibold">{form.owner_name || 'NAME'}</div>
        </div>
        <div>
          <div className="text-white/60">Expires</div>
          <div className="font-semibold">{form.expiry_mm_yy || 'MM/YY'}</div>
        </div>
      </div>
    </div>
  );
}

export default function DocVault() {
  const [entries, setEntries] = React.useState<DocVaultEntry[]>([]);
  const [activeTab, setActiveTab] = React.useState<Category>('credit_card');
  const [query, setQuery] = React.useState('');
  const [tagFilter, setTagFilter] = React.useState('');
  const [form, setForm] = React.useState(emptyForm);
  const [scanDraft, setScanDraft] = React.useState<Record<string, any> | null>(null);
  const [unlocking, setUnlocking] = React.useState<DocVaultEntry | null>(null);
  const [unlocked, setUnlocked] = React.useState<DocVaultEntry | null>(null);
  const [mfaCode, setMfaCode] = React.useState('');
  const [mfaFactor, setMfaFactor] = React.useState('google_auth');
  const [selectedFile, setSelectedFile] = React.useState<{ name: string; type: string; size: number; dataUrl: string } | null>(null);

  const loadEntries = React.useCallback(async () => {
    const data = await apiRequest<DocVaultEntry[]>('/docvault');
    setEntries(data);
  }, []);

  React.useEffect(() => {
    loadEntries().catch((error) => toast.error(error.message || 'Failed to load DocVault'));
  }, [loadEntries]);

  const current = entries.filter((entry) => entry.category === activeTab);
  const filtered = current.filter((entry) => {
    const textMatch = !query || `${entry.title} ${entry.file_name || ''}`.toLowerCase().includes(query.toLowerCase());
    const tagMatch = !tagFilter || entry.tags.includes(tagFilter);
    return textMatch && tagMatch;
  });
  const alertCount = entries.filter((entry) => entry.alerting).length;
  const allTags = Array.from(new Set(entries.flatMap((entry) => entry.tags))).sort();
  const summary = {
    expired: current.filter((entry) => entry.expiry_status === 'expired').length,
    expiring: current.filter((entry) => entry.expiry_status === 'expiring_soon').length,
    valid: current.filter((entry) => entry.expiry_status === 'valid').length,
  };

  async function handleScan(file: File) {
    const dataUrl = await readFileAsDataUrl(file);
    const data = await apiRequest<any>('/docvault/scan-card', {
      method: 'POST',
      body: JSON.stringify({ category: activeTab === 'id_card' ? 'id_card' : 'credit_card', file_name: file.name, image_data_url: dataUrl }),
    });
    setScanDraft({ ...data.extracted, thumbnail_data_url: dataUrl, confidence: data.confidence });
  }

  function applyScanDraft() {
    if (!scanDraft) return;
    if (activeTab === 'credit_card') {
      setForm((prev) => ({
        ...prev,
        title: scanDraft.card_label || prev.title,
        network: scanDraft.network || prev.network,
        card_number: scanDraft.card_number || prev.card_number,
        expiry_mm_yy: scanDraft.expiry || prev.expiry_mm_yy,
        owner_name: scanDraft.cardholder_name || prev.owner_name,
        bank: scanDraft.bank || prev.bank,
      }));
    } else {
      setForm((prev) => ({
        ...prev,
        title: scanDraft.card_type || prev.title,
        owner_name: scanDraft.holder_name || prev.owner_name,
        expiry_date: scanDraft.expiry_date || prev.expiry_date,
        issuer: scanDraft.issuing_authority || prev.issuer,
        card_type: scanDraft.card_type || prev.card_type,
      }));
    }
    setSelectedFile(scanDraft.thumbnail_data_url ? { name: 'card-photo', type: 'image/*', size: 0, dataUrl: scanDraft.thumbnail_data_url } : null);
    setScanDraft(null);
  }

  async function handleFile(file: File) {
    const dataUrl = await readFileAsDataUrl(file);
    setSelectedFile({ name: file.name, type: file.type || 'application/octet-stream', size: file.size, dataUrl });
  }

  async function saveEntry() {
    const metadata: Record<string, any> = {};
    const sensitive: Record<string, any> = {};
    let title = form.title.trim();
    let issuer = form.issuer.trim();
    let expiryDate = form.expiry_date || null;

    if (activeTab === 'credit_card') {
      metadata.network = form.network;
      metadata.bank = form.bank;
      metadata.expiry_mm_yy = form.expiry_mm_yy;
      sensitive.card_number = form.card_number.replace(/\s/g, '');
      sensitive.last4 = sensitive.card_number.slice(-4);
      title = title || `${form.network} ${sensitive.last4 || 'Card'}`;
      issuer = issuer || form.bank;
      if (form.expiry_mm_yy.match(/^\d{2}\/\d{2}$/)) {
        const [month, year] = form.expiry_mm_yy.split('/');
        expiryDate = `20${year}-${month}-01`;
      }
    }
    if (activeTab === 'ssl_certificate') metadata.domain = form.domain;
    if (activeTab === 'id_card') metadata.card_type = form.card_type;
    if (activeTab === 'secret') {
      sensitive.password = form.password;
      sensitive.private_key = form.private_key;
    }

    if (!title) {
      toast.error('Add a title before saving');
      return;
    }

    await apiRequest<DocVaultEntry>('/docvault', {
      method: 'POST',
      body: JSON.stringify({
        category: activeTab,
        title,
        owner_name: form.owner_name || null,
        issuer: issuer || null,
        expiry_date: expiryDate,
        issue_date: form.issue_date || null,
        public_metadata: metadata,
        sensitive_payload: sensitive,
        notes: form.notes || null,
        tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
        thumbnail_data_url: activeTab === 'id_card' ? selectedFile?.dataUrl : null,
        file_name: selectedFile?.name || null,
        file_mime_type: selectedFile?.type || null,
        file_size: selectedFile?.size || null,
        file_data_url: activeTab === 'document' ? selectedFile?.dataUrl : null,
      }),
    });
    setForm(emptyForm);
    setSelectedFile(null);
    await loadEntries();
    toast.success('Saved to DocVault');
  }

  async function deleteEntry(entry: DocVaultEntry) {
    await apiRequest(`/docvault/${entry.id}`, { method: 'DELETE' });
    await loadEntries();
    toast.success('Entry removed');
  }

  async function unlockEntry() {
    if (!unlocking) return;
    const data = await apiRequest<DocVaultEntry>(`/docvault/${unlocking.id}/unlock`, {
      method: 'POST',
      body: JSON.stringify({ factor_id: mfaFactor, user_input: mfaCode }),
    });
    setUnlocked(data);
    setUnlocking(null);
    setMfaCode('');
  }

  const preview = expiryPreview(activeTab, form.expiry_date);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">DocVault</h1>
            <p className="text-sm text-muted-foreground">Document and expiry manager with MFA-gated sensitive details.</p>
          </div>
          <Badge variant={alertCount ? 'destructive' : 'outline'} className="gap-2 px-3 py-1.5">
            <AlertCircle className="h-4 w-4" />
            {alertCount} expiry alerts
          </Badge>
        </div>

        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as Category)}>
          <TabsList className="grid h-auto w-full grid-cols-2 gap-1 md:grid-cols-5">
            {tabConfig.map((tab) => {
              const Icon = tab.icon;
              return (
                <TabsTrigger key={tab.id} value={tab.id} className="gap-2">
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {tabConfig.map((tab) => (
            <TabsContent key={tab.id} value={tab.id} className="space-y-5">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-800">
                  <div className="text-xs font-medium uppercase">Expired</div>
                  <div className="text-2xl font-bold">{summary.expired}</div>
                </div>
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-yellow-900">
                  <div className="text-xs font-medium uppercase">Expiring Soon</div>
                  <div className="text-2xl font-bold">{summary.expiring}</div>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-800">
                  <div className="text-xs font-medium uppercase">Valid</div>
                  <div className="text-2xl font-bold">{summary.valid}</div>
                </div>
              </div>

              <div className="grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Plus className="h-4 w-4" />
                      Add {tab.label.slice(0, -1)}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {activeTab === 'credit_card' && <CardVisual form={form} />}

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label>Title</Label>
                        <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                      </div>
                      <div className="space-y-1.5">
                        <Label>Holder</Label>
                        <Input value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} />
                      </div>
                    </div>

                    {activeTab === 'credit_card' && (
                      <>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="space-y-1.5">
                            <Label>Network</Label>
                            <Select value={form.network} onValueChange={(network) => setForm({ ...form, network })}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {Object.keys(networkStyles).map((network) => <SelectItem key={network} value={network}>{network}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1.5">
                            <Label>Expiry MM/YY</Label>
                            <Input placeholder="08/28" value={form.expiry_mm_yy} onChange={(e) => setForm({ ...form, expiry_mm_yy: e.target.value })} />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <Label>Card Number</Label>
                          <Input value={form.card_number} onChange={(e) => setForm({ ...form, card_number: e.target.value })} />
                        </div>
                        <div className="space-y-1.5">
                          <Label>Bank</Label>
                          <Input value={form.bank} onChange={(e) => setForm({ ...form, bank: e.target.value })} />
                        </div>
                      </>
                    )}

                    {activeTab === 'ssl_certificate' && (
                      <>
                        <div className="space-y-1.5">
                          <Label>Domain</Label>
                          <Input value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value, title: e.target.value || form.title })} />
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="space-y-1.5">
                            <Label>Issuer</Label>
                            <Input value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
                          </div>
                          <div className="space-y-1.5">
                            <Label>Issue Date</Label>
                            <Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
                          </div>
                        </div>
                      </>
                    )}

                    {activeTab === 'id_card' && (
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label>Card Type</Label>
                          <Input value={form.card_type} onChange={(e) => setForm({ ...form, card_type: e.target.value })} />
                        </div>
                        <div className="space-y-1.5">
                          <Label>Issuing Authority</Label>
                          <Input value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
                        </div>
                      </div>
                    )}

                    {activeTab === 'secret' && (
                      <>
                        <div className="space-y-1.5">
                          <Label>Password</Label>
                          <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
                        </div>
                        <div className="space-y-1.5">
                          <Label>Private Key</Label>
                          <Textarea value={form.private_key} onChange={(e) => setForm({ ...form, private_key: e.target.value })} />
                        </div>
                      </>
                    )}

                    {activeTab !== 'credit_card' && activeTab !== 'document' && activeTab !== 'secret' && (
                      <div className="space-y-1.5">
                        <Label>Expiry Date</Label>
                        <div className="flex gap-2">
                          <Input type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
                          <StatusBadge status={preview.status} days={preview.days} />
                        </div>
                      </div>
                    )}

                    {(activeTab === 'credit_card' || activeTab === 'id_card' || activeTab === 'document') && (
                      <div className="rounded-lg border border-dashed p-4">
                        <Label className="mb-2 flex items-center gap-2">
                          <Upload className="h-4 w-4" />
                          {activeTab === 'document' ? 'Upload Document' : 'AI Scan'}
                        </Label>
                        <Input
                          type="file"
                          accept={activeTab === 'document' ? undefined : 'image/*'}
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            if (!file) return;
                            if (activeTab === 'document') handleFile(file);
                            else handleScan(file).catch((error) => toast.error(error.message || 'Scan failed'));
                          }}
                        />
                        {selectedFile && <div className="mt-2 text-xs text-muted-foreground">{selectedFile.name} · {fileSize(selectedFile.size)}</div>}
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <Label>Tags</Label>
                      <Input placeholder="finance, renewal, personal" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Notes</Label>
                      <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
                    </div>
                    <Button className="w-full" onClick={() => saveEntry().catch((error) => toast.error(error.message || 'Save failed'))}>
                      Save to Vault
                    </Button>
                  </CardContent>
                </Card>

                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <div className="relative min-w-[240px] flex-1">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input className="pl-9" placeholder="Filter by name" value={query} onChange={(e) => setQuery(e.target.value)} />
                    </div>
                    <Select value={tagFilter || 'all'} onValueChange={(value) => setTagFilter(value === 'all' ? '' : value)}>
                      <SelectTrigger className="w-[200px]"><SelectValue placeholder="Filter by tag" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All tags</SelectItem>
                        {allTags.map((tag) => <SelectItem key={tag} value={tag}>{tag}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid gap-3">
                    {filtered.map((entry) => (
                      <Card key={entry.id} className="overflow-hidden">
                        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                          <div className="flex min-w-0 gap-3">
                            {entry.thumbnail_data_url ? (
                              <img src={entry.thumbnail_data_url} alt="" className="h-16 w-24 rounded-md border object-cover" />
                            ) : (
                              <div className="flex h-16 w-16 items-center justify-center rounded-md bg-muted">
                                {entry.category === 'credit_card' ? <CreditCard className="h-6 w-6" /> : entry.category === 'secret' ? <KeyRound className="h-6 w-6" /> : <FileText className="h-6 w-6" />}
                              </div>
                            )}
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="truncate font-semibold">{entry.title}</h3>
                                <StatusBadge status={entry.expiry_status} days={entry.days_delta} />
                              </div>
                              <div className="mt-1 text-sm text-muted-foreground">
                                {entry.category === 'credit_card' && `${entry.public_metadata.network || 'Card'} ending ${entry.sensitive_payload.last4 || '----'}`}
                                {entry.category === 'ssl_certificate' && `${entry.public_metadata.domain || entry.title} · ${entry.issuer || 'Unknown issuer'}`}
                                {entry.category === 'id_card' && `${entry.public_metadata.card_type || 'ID'} · ${entry.issuer || 'Unknown authority'}`}
                                {entry.category === 'document' && `${entry.file_name || 'File'} · ${fileSize(entry.file_size)}`}
                                {entry.category === 'secret' && 'Password / private key'}
                              </div>
                              <div className="mt-2 flex flex-wrap gap-1">
                                {entry.tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={() => setUnlocking(entry)}>
                              <Lock className="mr-2 h-4 w-4" />
                              Details
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => deleteEntry(entry).catch((error) => toast.error(error.message || 'Delete failed'))}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                    {filtered.length === 0 && (
                      <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
                        No DocVault entries in this tab yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>

      <Dialog open={!!scanDraft} onOpenChange={(open) => !open && setScanDraft(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5" /> Confirm AI scan</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {scanDraft && Object.entries(scanDraft).filter(([key]) => key !== 'thumbnail_data_url').map(([key, value]) => (
              <div key={key} className="grid grid-cols-[150px_1fr] gap-2 text-sm">
                <span className="font-medium capitalize text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                <Input value={String(value ?? '')} onChange={(event) => setScanDraft({ ...scanDraft, [key]: event.target.value })} />
              </div>
            ))}
            <Button className="w-full" onClick={applyScanDraft}>Use corrected values</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!unlocking} onOpenChange={(open) => !open && setUnlocking(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Lock className="h-5 w-5" /> Unlock vault details</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Enter your authenticator code. If MFA is disabled, type UNLOCK to confirm.</p>
            <Select value={mfaFactor} onValueChange={setMfaFactor}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="google_auth">Google Authenticator</SelectItem>
                <SelectItem value="ms_auth">Microsoft Authenticator</SelectItem>
              </SelectContent>
            </Select>
            <Input value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} placeholder="6-digit code or UNLOCK" />
            <Button className="w-full" onClick={() => unlockEntry().catch((error) => toast.error(error.message || 'Unlock failed'))}>Unlock</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!unlocked} onOpenChange={(open) => !open && setUnlocked(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><BadgeCheck className="h-5 w-5" /> Vault details</DialogTitle>
          </DialogHeader>
          {unlocked && (
            <div className="space-y-3">
              <div className="rounded-lg border p-3">
                <div className="font-semibold">{unlocked.title}</div>
                <div className="text-sm text-muted-foreground">{unlocked.notes || 'No private notes'}</div>
              </div>
              <pre className="max-h-72 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(unlocked.sensitive_payload, null, 2)}</pre>
              {unlocked.file_data_url && <Button variant="outline" onClick={() => window.open(unlocked.file_data_url!, '_blank')}>Open file</Button>}
              <Button
                variant="outline"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(unlocked.sensitive_payload, null, 2));
                  toast.success('Copied vault details');
                }}
              >
                <Copy className="mr-2 h-4 w-4" />
                Copy details
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
