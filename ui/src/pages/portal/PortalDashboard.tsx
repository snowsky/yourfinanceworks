import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, LogOut, Loader2, FileText, Pencil, Check, X } from 'lucide-react';
import {
  clientPortalApi,
  clientPortalSession,
  ClientPortalAuthError,
  type PortalBranding,
  type PortalInvoice,
  type PortalProfile,
} from '@/lib/api/client-portal';
import { readableTextColor } from '@/lib/invoice-branding';

function fmt(amount: number, currency = 'USD') {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

const STATUS_STYLES: Record<string, string> = {
  paid: 'bg-success/10 text-success',
  partially_paid: 'bg-warning/10 text-warning',
  overdue: 'bg-destructive/10 text-destructive',
  pending: 'bg-primary/10 text-primary',
};

export default function PortalDashboard() {
  const navigate = useNavigate();
  const [branding, setBranding] = useState<PortalBranding | null>(null);
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [invoices, setInvoices] = useState<PortalInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = () => {
    clientPortalSession.clear();
    const slug = clientPortalSession.getSlug();
    navigate(slug ? `/portal/${slug}` : '/', { replace: true });
  };

  useEffect(() => {
    if (!clientPortalSession.getToken()) {
      logout();
      return;
    }
    const slug = clientPortalSession.getSlug();
    Promise.all([
      clientPortalApi.getMe(),
      clientPortalApi.getInvoices(),
      slug ? clientPortalApi.getBranding(slug).catch(() => null) : Promise.resolve(null),
    ])
      .then(([me, inv, brand]) => {
        setProfile(me);
        setInvoices(inv.invoices);
        setBranding(brand);
      })
      .catch((e) => {
        if (e instanceof ClientPortalAuthError) {
          logout();
          return;
        }
        setError(e instanceof Error ? e.message : 'Failed to load your portal.');
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const brand = branding?.brand_color || '#1e3a8a';
  const onBrand = readableTextColor(brand);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const totalOutstanding = invoices.reduce((s, i) => s + (i.outstanding || 0), 0);
  const currency = invoices[0]?.currency || 'USD';

  return (
    <div className="min-h-screen bg-background">
      <header className="px-6 py-4 flex items-center justify-between" style={{ backgroundColor: brand, color: onBrand }}>
        <div className="flex items-center gap-3 min-w-0">
          {branding?.company_logo_url && (
            <img
              src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${branding.company_logo_url}`}
              alt=""
              className="h-9 w-9 rounded bg-white/95 object-contain p-0.5"
            />
          )}
          <span className="font-bold truncate">{branding?.company_name || 'Invoice portal'}</span>
        </div>
        <button onClick={logout} className="flex items-center gap-1.5 text-sm opacity-90 hover:opacity-100">
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </header>

      <main className="max-w-3xl mx-auto p-6 space-y-6">
        {error && <div className="rounded-lg bg-destructive/10 text-destructive text-sm px-4 py-3">{error}</div>}

        <div className="rounded-xl bg-card border p-5">
          <p className="text-sm text-muted-foreground">Total outstanding</p>
          <p className="text-3xl font-bold tabular-nums" style={{ color: brand }}>{fmt(totalOutstanding, currency)}</p>
          <p className="text-sm text-muted-foreground mt-1">{invoices.length} invoice{invoices.length === 1 ? '' : 's'}</p>
        </div>

        {profile && <ProfileCard profile={profile} brand={brand} onSaved={setProfile} />}

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground">Your invoices</h2>
          {invoices.length === 0 ? (
            <div className="rounded-xl bg-card border p-8 text-center text-muted-foreground">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No invoices yet.</p>
            </div>
          ) : (
            invoices.map((inv) => (
              <div key={inv.id} className="rounded-xl bg-card border p-4 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold">{inv.number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[inv.status] || 'bg-muted text-muted-foreground'}`}>
                      {inv.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Due {fmtDate(inv.due_date)}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold tabular-nums">{fmt(inv.amount, inv.currency)}</p>
                  {inv.outstanding > 0 ? (
                    <p className="text-xs text-muted-foreground">{fmt(inv.outstanding, inv.currency)} due</p>
                  ) : (
                    <p className="text-xs text-success">Paid</p>
                  )}
                </div>
                <button
                  onClick={() => clientPortalApi.downloadPdf(inv.id, inv.number).catch(() => setError('Failed to download PDF.'))}
                  title="Download PDF"
                  className="shrink-0 rounded-lg border p-2 hover:bg-muted"
                >
                  <Download className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
            ))
          )}
        </div>

        {branding?.footer_text && <p className="text-center text-xs text-muted-foreground">{branding.footer_text}</p>}
      </main>
    </div>
  );
}

function ProfileCard({ profile, brand, onSaved }: { profile: PortalProfile; brand: string; onSaved: (p: PortalProfile) => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(profile.name || '');
  const [phone, setPhone] = useState(profile.phone || '');
  const [address, setAddress] = useState(profile.address || '');
  const [saving, setSaving] = useState(false);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await clientPortalApi.updateMe({ name, phone, address });
      onSaved(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl bg-card border p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Your details</h2>
        {!editing && (
          <button onClick={() => setEditing(true)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <Pencil className="h-3.5 w-3.5" /> Edit
          </button>
        )}
      </div>
      {editing ? (
        <form onSubmit={save} className="space-y-3">
          <Field label="Name" value={name} onChange={setName} />
          <Field label="Phone" value={phone} onChange={setPhone} />
          <Field label="Address" value={address} onChange={setAddress} />
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: brand }}>
              <Check className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm">
              <X className="h-3.5 w-3.5" /> Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Detail label="Name" value={profile.name} />
          <Detail label="Email" value={profile.email} />
          <Detail label="Phone" value={profile.phone} />
          <Detail label="Address" value={profile.address} />
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-muted-foreground">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value || '—'}</p>
    </div>
  );
}
