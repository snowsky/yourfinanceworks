import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';

const OAuthCallback = () => {
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
        toast.error('Authentication failed.');
      }
    } else {
      toast.error('Invalid OAuth callback.');
    }
    navigate('/login', { replace: true });
  }, [location.search, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Signing you in...</p>
      </div>
    </div>
  );
};

export default OAuthCallback;


