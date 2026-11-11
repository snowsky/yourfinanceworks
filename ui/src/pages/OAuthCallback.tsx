import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { BrandMark } from '@/components/auth/BrandMark';

const OAuthCallback = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const userB64 = params.get('user');
    const next = params.get('next') || '/dashboard';
    if (userB64) {
      try {
        const userJson = atob(userB64.replace(/-/g, '+').replace(/_/g, '/'));
        const user = JSON.parse(userJson);
        // token is delivered via httpOnly cookie set by the SSO backend redirect
        localStorage.removeItem('token'); // clear any pre-migration token
        localStorage.setItem('user', JSON.stringify(user));
        // Dispatch custom event to notify FeatureContext
        window.dispatchEvent(new Event('auth-changed'));
        navigate(next, { replace: true });
        return;
      } catch (e) {
        console.error('Failed to process OAuth callback:', e);
        toast.error(t('auth.oauth_failed'));
      }
    } else {
      toast.error(t('auth.oauth_invalid'));
    }
    navigate('/login', { replace: true });
  }, [location.search, navigate, t]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-8 bg-background text-foreground px-6">
      <BrandMark />
      <div role="status" aria-live="polite" className="flex items-center gap-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        {t('auth.signing_in')}
      </div>
    </div>
  );
};

export default OAuthCallback;
