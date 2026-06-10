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
  paid: 'bg-emerald-100 text-emerald-700',
  partially_paid: 'bg-amber-100 text-amber-700',
  overdue: 'bg-red-100 text-red-700',
  pending: 'bg-blue-100 text-blue-700',
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const totalOutstanding = invoices.reduce((s, i) => s + (i.outstanding || 0), 0);
  const currency = invoices[0]?.currency || 'USD';

  return (
    <div className="min-h-screen bg-gray-50">
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
        {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}

        <div className="rounded-xl bg-white border p-5">
          <p className="text-sm text-gray-500">Total outstanding</p>
          <p className="text-3xl font-bold tabular-nums" style={{ color: brand }}>{fmt(totalOutstanding, currency)}</p>
          <p className="text-sm text-gray-500 mt-1">{invoices.length} invoice{invoices.length === 1 ? '' : 's'}</p>
        </div>

        {profile && <ProfileCard profile={profile} brand={brand} onSaved={setProfile} />}

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Your invoices</h2>
          {invoices.length === 0 ? (
            <div className="rounded-xl bg-white border p-8 text-center text-gray-500">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">No invoices yet.</p>
            </div>
          ) : (
            invoices.map((inv) => (
              <div key={inv.id} className="rounded-xl bg-white border p-4 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold">{inv.number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[inv.status] || 'bg-gray-100 text-gray-600'}`}>
                      {inv.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Due {fmtDate(inv.due_date)}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold tabular-nums">{fmt(inv.amount, inv.currency)}</p>
                  {inv.outstanding > 0 ? (
                    <p className="text-xs text-gray-500">{fmt(inv.outstanding, inv.currency)} due</p>
                  ) : (
                    <p className="text-xs text-emerald-600">Paid</p>
                  )}
                </div>
                <button
                  onClick={() => clientPortalApi.downloadPdf(inv.id, inv.number).catch(() => setError('Failed to download PDF.'))}
                  title="Download PDF"
                  className="shrink-0 rounded-lg border p-2 hover:bg-gray-50"
                >
                  <Download className="h-4 w-4 text-gray-600" />
                </button>
              </div>
            ))
          )}
        </div>

        {branding?.footer_text && <p className="text-center text-xs text-gray-400">{branding.footer_text}</p>}
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
    <div className="rounded-xl bg-white border p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700">Your details</h2>
        {!editing && (
          <button onClick={() => setEditing(true)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800">
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
      <label className="text-xs text-gray-500">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300" />
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="font-medium">{value || '—'}</p>
    </div>
  );
}
