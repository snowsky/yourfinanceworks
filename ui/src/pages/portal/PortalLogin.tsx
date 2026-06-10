import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { Mail, CheckCircle2, AlertCircle } from 'lucide-react';
import { clientPortalApi, clientPortalSession, type PortalBranding } from '@/lib/api/client-portal';
import { readableTextColor } from '@/lib/invoice-branding';

export default function PortalLogin() {
  const { slug = '' } = useParams<{ slug: string }>();
  const [branding, setBranding] = useState<PortalBranding | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    clientPortalSession.setSlug(slug);
    clientPortalApi.getBranding(slug).then(setBranding).catch(() => setNotFound(true));
  }, [slug]);

  const brand = branding?.brand_color || '#1e3a8a';
  const onText = readableTextColor(brand);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await clientPortalApi.requestLink(slug, email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setSubmitting(false);
    }
  };

  if (notFound) {
    return (
      <Shell brand={brand}>
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <p className="font-semibold">Portal not found</p>
          <p className="text-sm text-gray-500">This link may be incorrect or no longer active.</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell brand={brand}>
      <div className="flex flex-col items-center text-center mb-6">
        {branding?.company_logo_url && (
          <img
            src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${branding.company_logo_url}`}
            alt=""
            className="h-14 w-14 rounded-lg object-contain mb-3"
          />
        )}
        <h1 className="text-xl font-bold">{branding?.company_name || 'Invoice portal'}</h1>
        <p className="text-sm text-gray-500 mt-1">Sign in to view your invoices</p>
      </div>

      {sent ? (
        <div className="flex flex-col items-center gap-3 text-center py-4">
          <CheckCircle2 className="h-10 w-10" style={{ color: brand }} />
          <p className="font-medium">Check your email</p>
          <p className="text-sm text-gray-500">
            If <span className="font-medium">{email}</span> matches an account, a secure sign-in link is on its way.
            It expires in 60 minutes.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">Email address</label>
            <div className="mt-1 relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg border border-gray-300 pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2"
                style={{ ['--tw-ring-color' as string]: brand }}
              />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={submitting || !email}
            className="w-full rounded-lg py-2.5 text-sm font-semibold disabled:opacity-60"
            style={{ backgroundColor: brand, color: onText }}
          >
            {submitting ? 'Sending…' : 'Email me a sign-in link'}
          </button>
        </form>
      )}

      {branding?.footer_text && (
        <p className="mt-6 text-center text-xs text-gray-400">{branding.footer_text}</p>
      )}
    </Shell>
  );
}

function Shell({ brand, children }: { brand: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-sm border p-8">
        <div className="h-1.5 -mx-8 -mt-8 mb-6 rounded-t-2xl" style={{ backgroundColor: brand }} />
        {children}
      </div>
      <p className="mt-6 text-center text-xs text-gray-400">
        Powered by <a href="/" className="underline">YourFinanceWORKS</a>
      </p>
    </div>
  );
}
