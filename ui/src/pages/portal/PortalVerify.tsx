import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { clientPortalApi, clientPortalSession } from '@/lib/api/client-portal';

export default function PortalVerify() {
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-sm border p-8 text-center">
        {error ? (
          <div className="flex flex-col items-center gap-3">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <p className="font-semibold">Sign-in failed</p>
            <p className="text-sm text-gray-500">{error}</p>
            {clientPortalSession.getSlug() && (
              <a
                href={`/portal/${clientPortalSession.getSlug()}`}
                className="text-sm font-medium underline mt-2"
              >
                Request a new link
              </a>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            <p className="text-sm text-gray-500">Signing you in…</p>
          </div>
        )}
      </div>
    </div>
  );
}
