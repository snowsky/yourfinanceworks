import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { Mail, CheckCircle2, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { clientPortalApi, clientPortalSession, type PortalBranding } from '@/lib/api/client-portal';
import { readableTextColor } from '@/lib/invoice-branding';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { PoweredBy } from '@/components/sharing/PoweredBy';

export default function PortalLogin() {
  const { t } = useTranslation();
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
      setError(err instanceof Error ? err.message : t('portal.genericError'));
    } finally {
      setSubmitting(false);
    }
  };

  if (notFound) {
    return (
      <Shell brand={brand}>
        <div role="alert" className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-destructive" aria-hidden="true" />
          <h1 className="text-base font-semibold text-foreground">{t('portal.notFound.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('portal.notFound.description')}</p>
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
            className="h-14 w-14 rounded-lg bg-white object-contain p-0.5 mb-3"
          />
        )}
        <h1 className="text-xl font-bold tracking-tight text-foreground">
          {branding?.company_name || t('portal.defaultName')}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{t('portal.login.subtitle')}</p>
      </div>

      {sent ? (
        <div role="status" className="flex flex-col items-center gap-3 text-center py-4">
          {/* Theme colour, not the tenant's: a dark brand colour would vanish on a dark card */}
          <CheckCircle2 className="h-10 w-10 text-success" aria-hidden="true" />
          <p className="font-medium text-foreground">{t('portal.login.sentTitle')}</p>
          <p className="text-sm text-muted-foreground">{t('portal.login.sentBody', { email })}</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <ProfessionalInput
            id="portal-email"
            type="email"
            label={t('portal.login.emailLabel')}
            placeholder={t('portal.login.emailPlaceholder')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            leftIcon={<Mail className="h-full w-full" aria-hidden="true" />}
            autoComplete="email"
            required
            inputSize="lg"
          />
          {error && (
            <p role="alert" className="text-sm text-destructive">{error}</p>
          )}
          <ProfessionalButton
            type="submit"
            size="xl"
            className="w-full hover:opacity-90"
            loading={submitting}
            disabled={!email}
            style={{ backgroundColor: brand, color: onText }}
          >
            {submitting ? t('portal.login.sending') : t('portal.login.submit')}
          </ProfessionalButton>
        </form>
      )}

      {branding?.footer_text && (
        <p className="mt-6 text-center text-xs text-muted-foreground">{branding.footer_text}</p>
      )}
    </Shell>
  );
}

function Shell({ brand, children }: { brand: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-card text-card-foreground shadow-sm border border-border">
        <div className="h-1.5" style={{ backgroundColor: brand }} />
        <div className="p-8">{children}</div>
      </div>
      <PoweredBy className="mt-6" />
    </div>
  );
}
