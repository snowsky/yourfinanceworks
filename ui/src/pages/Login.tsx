import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ProfessionalCard, MetricCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ThemeSwitcher } from "@/components/ui/theme-switcher";
import { Eye, EyeOff } from "lucide-react";
import { authApi, API_BASE_URL } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/components/ui/language-switcher';
import { getErrorMessage } from '@/lib/api';

const Login = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ssoStatus, setSsoStatus] = useState<{ google: boolean; microsoft: boolean; has_sso: boolean } | null>(null);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const data = await authApi.login(email, password);
      // Clear any previous tenant selection
      localStorage.removeItem('selected_tenant_id');
      // Store token and user info
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      // Dispatch custom event to notify FeatureContext
      window.dispatchEvent(new Event('auth-changed'));
      toast.success(t('auth.login_success'));

      navigate("/dashboard");
    } catch (error: any) {
      const errorMessage = getErrorMessage(error, t);
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    const next = encodeURIComponent('/dashboard');
    const url = `${API_BASE_URL}/auth/google/login?next=${next}`;
    window.location.href = url;
  };

  const handleAzureLogin = () => {
    const next = encodeURIComponent('/dashboard');
    const url = `${API_BASE_URL}/auth/azure/login?next=${next}`;
    window.location.href = url;
  };

  // Handle OAuth callback via URL hash (e.g., /#/oauth-callback?token=...)
  useEffect(() => {
    const hash = window.location.hash || '';
    if (hash.startsWith('#/oauth-callback')) {
      const queryIndex = hash.indexOf('?');
      const queryString = queryIndex >= 0 ? hash.slice(queryIndex + 1) : '';
      const params = new URLSearchParams(queryString);
      const token = params.get('token');
      const userB64 = params.get('user');
      const next = params.get('next') || '/dashboard';
      if (token && userB64) {
        try {
          const userJson = atob(userB64.replace(/-/g, '+').replace(/_/g, '/'));
          const user = JSON.parse(userJson);
          localStorage.setItem('token', token);
          localStorage.setItem('user', JSON.stringify(user));
          // Dispatch custom event to notify FeatureContext
          window.dispatchEvent(new Event('auth-changed'));
          // Clear hash and navigate
          window.history.replaceState(null, '', next);
          navigate(next, { replace: true });
          return;
        } catch (e) {
          console.error('Failed to process OAuth callback:', e);
          toast.error(t('errors.unknown_error'));
        }
      }
    }
  }, [navigate]);

  // Fetch SSO status and handle URL errors on component mount
  useEffect(() => {
    const fetchSSOStatus = async () => {
      try {
        const status = await authApi.getSSOStatus();
        setSsoStatus(status);
      } catch (error) {
        console.error('Failed to fetch SSO status:', error);
        // Default to showing SSO if API fails
        setSsoStatus({ google: true, microsoft: true, has_sso: true });
      }
    };

    fetchSSOStatus();

    // Handle URL errors (like sso_license_required)
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    if (errorParam === 'sso_license_required') {
      setError(t('auth.sso_license_required_recovery'));
    }
  }, [t]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 py-12 px-4 sm:px-6 lg:px-8 transition-colors duration-300">

      {/* Professional Header Section */}
      <div className="w-full max-w-md mb-6">
        <div className="text-center space-y-3">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300 bg-clip-text text-transparent">{t('auth.login')}</h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm font-medium">
            {t('auth.login_description')}
          </p>
        </div>
      </div>

      <div className="w-full max-w-md bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl shadow-lg dark:shadow-2xl border border-slate-200 dark:border-slate-800/50">
        <div className="p-8 space-y-6">
          {error && (
            <div className="bg-red-50 dark:bg-red-500/10 border border-red-300 dark:border-red-500/50 text-red-700 dark:text-red-200 px-4 py-3.5 rounded-xl backdrop-blur-sm shadow-sm" role="alert">
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}
          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-semibold text-slate-900 dark:text-slate-100">{t('auth.email')}</Label>
              <Input
                id="email"
                type="email"
                placeholder={t('auth.email_placeholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                className="bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700/50 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-primary focus:ring-2 focus:ring-primary/50 transition-all shadow-sm hover:border-slate-400 dark:hover:border-slate-600 h-11 rounded-lg"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-semibold text-slate-900 dark:text-slate-100">{t('auth.password')}</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder={t('auth.password_placeholder')}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  className="bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700/50 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-primary focus:ring-2 focus:ring-primary/50 transition-all shadow-sm hover:border-slate-400 dark:hover:border-slate-600 h-11 rounded-lg"
                />
                <ProfessionalButton
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </ProfessionalButton>
              </div>
            </div>
            <ProfessionalButton type="submit" variant="gradient" className="w-full py-3 text-sm font-semibold shadow-lg hover:shadow-xl transition-all" disabled={isLoading}>
              {isLoading ? t('auth.signing_in') : t('auth.login')}
            </ProfessionalButton>

            <div className="text-center">
              <Link
                to="/forgot-password"
                className="text-sm text-blue-600 dark:text-primary hover:text-blue-500 dark:hover:text-primary/80 transition-colors"
              >
                {t('auth.forgot_password')}
              </Link>
            </div>
          </form>

          {ssoStatus?.has_sso && (
            <>
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-slate-300/50 dark:border-slate-600/30" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white dark:bg-slate-800/50 px-3 text-slate-500 dark:text-slate-400 backdrop-blur-sm rounded-lg border border-slate-200/50 dark:border-slate-600/20">{t('auth.or_continue_with')}</span>
                </div>
              </div>

              {ssoStatus.google && (
                <ProfessionalButton
                  type="button"
                  variant="outline"
                  className="w-full bg-white dark:bg-slate-800/50 border-slate-300 dark:border-slate-600/50 text-slate-700 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:border-slate-400 dark:hover:border-slate-500/50"
                  onClick={handleGoogleLogin}
                >
                  <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  {t('auth.sign_in_with_google')}
                </ProfessionalButton>
              )}

              {ssoStatus.microsoft && (
                <ProfessionalButton
                  type="button"
                  variant="outline"
                  className="w-full bg-white dark:bg-slate-800/50 border-slate-300 dark:border-slate-600/50 text-slate-700 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:border-slate-400 dark:hover:border-slate-500/50"
                  onClick={handleAzureLogin}
                >
                  <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                    <path
                      d="M12.5 1.5L5.5 3.5v7c0 5.5 3.8 10.7 7 12 3.2-1.3 7-6.5 7-12v-7l-7-2z"
                      fill="#00BCF2"
                    />
                    <path
                      d="M12.5 1.5v21c3.2-1.3 7-6.5 7-12v-7l-7-2z"
                      fill="#0078D4"
                    />
                  </svg>
                  {t('auth.sign_in_with_microsoft')}
                </ProfessionalButton>
              )}
            </>
          )}

          <div className="text-center text-sm">
            <span className="text-slate-600 dark:text-slate-400">{t('auth.no_account')}</span>{" "}
            <Link to="/signup" className="text-blue-600 dark:text-primary hover:text-blue-500 dark:hover:text-primary/80 underline underline-offset-4 transition-colors">
              {t('auth.signup.homepage')}
            </Link>
          </div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-center gap-4">
        <LanguageSwitcher />
        <ThemeSwitcher />
      </div>
    </div>
  );
};

export default Login; 