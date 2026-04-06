import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ThemeSwitcher } from "@/components/ui/theme-switcher";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import {
  TrendingUp, BarChart3, Shield, AlertCircle, CheckCircle2,
} from "lucide-react";
import { authApi, API_BASE_URL, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

const BRAND_FEATURES = [
  {
    icon: TrendingUp,
    title: "Real-time Financial Insights",
    desc: "Live cash flow, revenue, and expense tracking across all accounts.",
  },
  {
    icon: BarChart3,
    title: "AI-Powered Analytics",
    desc: "Intelligent forecasting and anomaly detection, built in.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    desc: "Bank-grade encryption with multi-tenant data isolation.",
  },
];

const TRUST_BADGES = ["256-bit SSL", "ISO 27001", "SOC 2 Type II"];

// Real Microsoft 4-square logo
const MicrosoftIcon = () => (
  <svg className="h-4 w-4 flex-shrink-0" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M0 0h11.5v11.5H0z" fill="#F25022" />
    <path d="M12.5 0H24v11.5H12.5z" fill="#7FBA00" />
    <path d="M0 12.5h11.5V24H0z" fill="#00A4EF" />
    <path d="M12.5 12.5H24V24H12.5z" fill="#FFB900" />
  </svg>
);

const GoogleIcon = () => (
  <svg className="h-4 w-4 flex-shrink-0" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
);

const Login = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ssoStatus, setSsoStatus] = useState<{ google: boolean; microsoft: boolean; has_sso: boolean } | null>(null);
  const navigate = useNavigate();

  const clearError = () => setError(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const data = await authApi.login(email, password);
      localStorage.removeItem("selected_tenant_id");
      localStorage.removeItem("token");
      localStorage.setItem("user", JSON.stringify(data.user));
      window.dispatchEvent(new Event("auth-changed"));
      toast.success(t("auth.login_success"));
      const redirectTo = new URLSearchParams(window.location.search).get("redirect") || "/dashboard";
      navigate(redirectTo, { replace: true });
    } catch (err: any) {
      setError(getErrorMessage(err, t));
    } finally {
      setIsLoading(false);
    }
  };

  // Handle OAuth callback via URL hash (e.g. /#/oauth-callback?token=...)
  useEffect(() => {
    const hash = window.location.hash || "";
    if (!hash.startsWith("#/oauth-callback")) return;
    const queryString = hash.slice(hash.indexOf("?") + 1);
    const params = new URLSearchParams(queryString);
    const token = params.get("token");
    const userB64 = params.get("user");
    const next = params.get("next") || "/dashboard";
    if (token && userB64) {
      try {
        const user = JSON.parse(atob(userB64.replace(/-/g, "+").replace(/_/g, "/")));
        localStorage.setItem("user", JSON.stringify(user));
        window.dispatchEvent(new Event("auth-changed"));
        window.history.replaceState(null, "", next);
        navigate(next, { replace: true });
      } catch {
        toast.error(t("errors.unknown_error"));
      }
    }
  }, [navigate, t]);

  useEffect(() => {
    // Fail closed: do not expose SSO buttons if the status API fails
    authApi.getSSOStatus()
      .then(setSsoStatus)
      .catch(() => setSsoStatus({ google: false, microsoft: false, has_sso: false }));

    const errorParam = new URLSearchParams(window.location.search).get("error");
    if (errorParam === "sso_license_required") setError(t("auth.sso_license_required_recovery"));
    else if (errorParam === "sso_registration_disabled") setError(t("auth.sso_registration_disabled"));
    else if (errorParam === "tenant_limit_reached") setError(t("auth.tenant_limit_reached"));
  }, [t]);

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* ── Left brand panel (desktop only) ── */}
      <div className="hidden lg:flex lg:w-[44%] xl:w-2/5 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex-col justify-between p-12 relative overflow-hidden flex-shrink-0">
        {/* Subtle dot-grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `radial-gradient(circle, #ffffff 1px, transparent 1px)`,
            backgroundSize: "28px 28px",
          }}
        />
        {/* Accent glow */}
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-primary/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

        {/* Logo */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shadow-lg shadow-primary/30">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="text-white text-lg font-bold tracking-tight leading-none">YourFinanceWORKS</span>
              <p className="text-slate-400 text-xs mt-0.5">Financial Management Platform</p>
            </div>
          </div>
        </div>

        {/* Feature list */}
        <div className="relative z-10 space-y-8">
          <h2 className="text-white text-2xl font-semibold leading-snug">
            The smarter way to manage your business finances.
          </h2>
          <div className="space-y-5">
            {BRAND_FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex gap-4">
                <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-white font-medium text-sm">{title}</p>
                  <p className="text-slate-400 text-sm mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Trust badges */}
        <div className="relative z-10 flex items-center gap-2 flex-wrap">
          {TRUST_BADGES.map((badge) => (
            <div key={badge} className="flex items-center gap-1.5 bg-white/10 rounded-full px-3 py-1">
              <CheckCircle2 className="h-3 w-3 text-emerald-400 flex-shrink-0" />
              <span className="text-slate-300 text-xs font-medium">{badge}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex flex-col items-center justify-center py-12 px-6 sm:px-10 overflow-y-auto">
        {/* Mobile-only logo */}
        <div className="lg:hidden mb-8 text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <div className="w-9 h-9 bg-primary rounded-xl flex items-center justify-center shadow">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <span className="text-slate-900 dark:text-white text-lg font-bold tracking-tight">YourFinanceWORKS</span>
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-xs">Financial Management Platform</p>
        </div>

        <div className="w-full max-w-sm">
          {/* Heading */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {t("auth.login")}
            </h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
              {t("auth.login_description")}
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div
              role="alert"
              aria-live="assertive"
              className="mb-5 flex items-start gap-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300 px-4 py-3 rounded-xl"
            >
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Login form */}
          <form onSubmit={handleLogin} className="space-y-4">
            <ProfessionalInput
              id="email"
              type="email"
              label={t("auth.email")}
              placeholder={t("auth.email_placeholder")}
              value={email}
              onChange={(e) => { setEmail(e.target.value); clearError(); }}
              autoComplete="email"
              required
              inputSize="lg"
            />

            <div className="space-y-1">
              <ProfessionalInput
                id="password"
                type="password"
                label={t("auth.password")}
                placeholder={t("auth.password_placeholder")}
                value={password}
                onChange={(e) => { setPassword(e.target.value); clearError(); }}
                autoComplete="current-password"
                required
                inputSize="lg"
              />
              <div className="flex justify-end pt-1">
                <Link
                  to="/forgot-password"
                  className="text-xs text-primary hover:text-primary/80 transition-colors"
                >
                  {t("auth.forgot_password")}
                </Link>
              </div>
            </div>

            <ProfessionalButton
              type="submit"
              variant="gradient"
              size="xl"
              className="w-full mt-2"
              loading={isLoading}
            >
              {!isLoading && t("auth.login")}
            </ProfessionalButton>
          </form>

          {/* SSO section */}
          {ssoStatus?.has_sso && (
            <>
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-slate-200 dark:border-slate-700" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-slate-50 dark:bg-slate-950 px-3 text-slate-400 tracking-wide">
                    {t("auth.or_continue_with")}
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                {ssoStatus.google && (
                  <ProfessionalButton
                    type="button"
                    variant="outline"
                    className="w-full gap-3"
                    onClick={() =>
                      (window.location.href = `${API_BASE_URL}/auth/google/login?next=${encodeURIComponent("/dashboard")}`)
                    }
                  >
                    <GoogleIcon />
                    {t("auth.sign_in_with_google")}
                  </ProfessionalButton>
                )}
                {ssoStatus.microsoft && (
                  <ProfessionalButton
                    type="button"
                    variant="outline"
                    className="w-full gap-3"
                    onClick={() =>
                      (window.location.href = `${API_BASE_URL}/auth/azure/login?next=${encodeURIComponent("/dashboard")}`)
                    }
                  >
                    <MicrosoftIcon />
                    {t("auth.sign_in_with_microsoft")}
                  </ProfessionalButton>
                )}
              </div>
            </>
          )}

          {/* Sign-up link */}
          <p className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
            {t("auth.no_account")}{" "}
            <Link
              to="/signup"
              className="text-primary hover:text-primary/80 font-semibold transition-colors"
            >
              {t("auth.signup.homepage")}
            </Link>
          </p>
        </div>

        {/* Locale / theme controls */}
        <div className="mt-10 flex items-center gap-4">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
      </div>
    </div>
  );
};

export default Login;
