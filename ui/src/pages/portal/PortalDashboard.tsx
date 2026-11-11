import { useEffect, useId, useState, type FormEvent } from 'react';
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
import { useTranslation } from 'react-i18next';
import { PoweredBy } from '@/components/sharing/PoweredBy';

function fmt(amount: number, currency = 'USD') {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function fmtDate(d: string | null) {
  if (!d) return '—';
  // A bare "2026-10-01" is a calendar date, not a moment. new Date() reads it as
  // UTC midnight, which shows as the previous day for anyone west of UTC.
  const dateOnly = d.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const date = dateOnly ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])) : new Date(d);
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

const STATUS_STYLES: Record<string, string> = {
  paid: 'bg-success/10 text-success',
  partially_paid: 'bg-warning/10 text-warning',
  overdue: 'bg-destructive/10 text-destructive',
  pending: 'bg-primary/10 text-primary',
};

export default function PortalDashboard() {
  const { t } = useTranslation();
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
        setError(e instanceof Error ? e.message : t('portal.dashboard.loadFailed'));
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const brand = branding?.brand_color || '#1e3a8a';
  const onBrand = readableTextColor(brand);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" role="status" aria-label={t('common.loading')} />
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
          <span className="font-bold truncate">{branding?.company_name || t('portal.defaultName')}</span>
        </div>
        <button onClick={logout} className="flex items-center gap-1.5 text-sm opacity-90 hover:opacity-100">
          <LogOut className="h-4 w-4" aria-hidden="true" /> {t('portal.dashboard.signOut')}
        </button>
      </header>

      <main className="max-w-3xl mx-auto p-6 space-y-6">
        {error && <div role="alert" className="rounded-lg bg-destructive/10 text-destructive text-sm px-4 py-3">{error}</div>}

        <div className="rounded-xl bg-card border p-5">
          <p className="text-sm text-muted-foreground">{t('portal.dashboard.totalOutstanding')}</p>
          <p className="text-3xl font-bold tabular-nums" style={{ color: brand }}>{fmt(totalOutstanding, currency)}</p>
          <p className="text-sm text-muted-foreground mt-1">{invoices.length === 1 ? t('portal.dashboard.oneInvoice') : t('portal.dashboard.manyInvoices', { count: invoices.length })}</p>
        </div>

        {profile && <ProfileCard profile={profile} brand={brand} onSaved={setProfile} />}

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground">{t('portal.dashboard.yourInvoices')}</h2>
          {invoices.length === 0 ? (
            <div className="rounded-xl bg-card border p-8 text-center text-muted-foreground">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-40" aria-hidden="true" />
              <p className="text-sm">{t('portal.dashboard.noInvoices')}</p>
            </div>
          ) : (
            invoices.map((inv) => (
              <div key={inv.id} className="rounded-xl bg-card border p-4 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-mono font-semibold whitespace-nowrap">{inv.number}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize whitespace-nowrap ${STATUS_STYLES[inv.status] || 'bg-muted text-muted-foreground'}`}>
                      {t(`portal.status.${inv.status}`, { defaultValue: inv.status.replace(/_/g, ' ') })}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{t('portal.dashboard.due', { date: fmtDate(inv.due_date) })}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-semibold tabular-nums">{fmt(inv.amount, inv.currency)}</p>
                  {inv.outstanding > 0 ? (
                    <p className="text-xs text-muted-foreground">{t('portal.dashboard.amountDue', { amount: fmt(inv.outstanding, inv.currency) })}</p>
                  ) : (
                    <p className="text-xs text-success">{t('portal.status.paid')}</p>
                  )}
                </div>
                <button
                  onClick={() => clientPortalApi.downloadPdf(inv.id, inv.number).catch(() => setError(t('portal.dashboard.downloadFailed')))}
                  title={t('portal.dashboard.downloadPdf')}
                  aria-label={t('portal.dashboard.downloadPdfFor', { number: inv.number })}
                  className="shrink-0 rounded-lg border p-2 hover:bg-muted"
                >
                  <Download className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                </button>
              </div>
            ))
          )}
        </div>

        {branding?.footer_text && <p className="text-center text-xs text-muted-foreground">{branding.footer_text}</p>}
        <PoweredBy />
      </main>
    </div>
  );
}

function ProfileCard({ profile, brand, onSaved }: { profile: PortalProfile; brand: string; onSaved: (p: PortalProfile) => void }) {
  const { t } = useTranslation();
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
        <h2 className="text-sm font-semibold text-muted-foreground">{t('portal.dashboard.yourDetails')}</h2>
        {!editing && (
          <button onClick={() => setEditing(true)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> {t('portal.dashboard.edit')}
          </button>
        )}
      </div>
      {editing ? (
        <form onSubmit={save} className="space-y-3">
          <Field label={t('portal.dashboard.name')} value={name} onChange={setName} />
          <Field label={t('portal.dashboard.phone')} value={phone} onChange={setPhone} />
          <Field label={t('portal.dashboard.address')} value={address} onChange={setAddress} />
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: brand }}>
              <Check className="h-3.5 w-3.5" aria-hidden="true" /> {saving ? t('portal.dashboard.saving') : t('portal.dashboard.save')}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm">
              <X className="h-3.5 w-3.5" aria-hidden="true" /> {t('portal.dashboard.cancel')}
            </button>
          </div>
        </form>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Detail label={t('portal.dashboard.name')} value={profile.name} />
          <Detail label={t('portal.dashboard.email')} value={profile.email} />
          <Detail label={t('portal.dashboard.phone')} value={profile.phone} />
          <Detail label={t('portal.dashboard.address')} value={profile.address} />
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="text-xs text-muted-foreground">{label}</label>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
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
