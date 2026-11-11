import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { clientPortalApi, clientPortalSession } from '@/lib/api/client-portal';
import { PoweredBy } from '@/components/sharing/PoweredBy';

export default function PortalVerify() {
  const { t } = useTranslation();
  const { token = '' } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    clientPortalApi
      .verify(token)
      .then((res) => {
        if (cancelled) return;
        clientPortalSession.setToken(res.access_token);
        navigate('/portal/dashboard', { replace: true });
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

  const slug = clientPortalSession.getSlug();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-card text-card-foreground shadow-sm border border-border p-8 text-center">
        {error ? (
          <div role="alert" className="flex flex-col items-center gap-3">
            <AlertCircle className="h-8 w-8 text-destructive" aria-hidden="true" />
            <h1 className="text-base font-semibold">{t('portal.verify.failedTitle')}</h1>
            <p className="text-sm text-muted-foreground">{error}</p>
            {slug && (
              <a
                href={`/portal/${slug}`}
                className="mt-2 text-sm font-semibold text-primary hover:text-primary/80 transition-colors"
              >
                {t('portal.verify.requestNew')}
              </a>
            )}
          </div>
        ) : (
          <div role="status" className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{t('portal.verify.signingIn')}</p>
          </div>
        )}
      </div>
      <PoweredBy className="mt-6" />
    </div>
  );
}
