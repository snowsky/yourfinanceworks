import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ArrowLeft } from "lucide-react";
import { AuthLayout, AuthHeading, AuthErrorBanner } from "@/components/auth/AuthLayout";
import { authApi, API_BASE_URL, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

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
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaSessionId, setMfaSessionId] = useState<string | null>(null);
  const [mfaFactorId, setMfaFactorId] = useState<string | null>(null);
  const [mfaFactorLabel, setMfaFactorLabel] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaLoading, setMfaLoading] = useState(false);
  const navigate = useNavigate();

  const clearError = () => setError(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const data = await authApi.login(email, password);
      if (data?.mfa_required && data?.mfa_session_id) {
        setMfaRequired(true);
        setMfaSessionId(data.mfa_session_id);
        setMfaFactorId(data.current_factor_id || null);
        setMfaFactorLabel(data.current_factor_label || null);
        setMfaCode('');
        toast.info(t("auth.mfa.required"));
        return;
      }

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

  const handleMFAVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaSessionId || !mfaFactorId) {
      setError(t("auth.mfa.missing_session"));
      return;
    }

    setMfaLoading(true);
    setError(null);
    try {
      const result = await authApi.verifyMFAAttempt({
        session_id: mfaSessionId,
        factor_id: mfaFactorId,
        user_input: mfaCode,
        window: 1,
      });

      if (!result?.is_complete) {
        if (result?.reset) {
          toast.error(t("auth.mfa.chain_restarted"));
        }
        setMfaFactorId(result.next_factor_id || null);
        setMfaFactorLabel(result.next_factor_label || null);
        setMfaCode('');
        return;
      }

      localStorage.removeItem("selected_tenant_id");
      localStorage.removeItem("token");
      localStorage.setItem("user", JSON.stringify(result.user));
      window.dispatchEvent(new Event("auth-changed"));
      toast.success(t("auth.login_success"));
      const redirectTo = new URLSearchParams(window.location.search).get("next")
        || new URLSearchParams(window.location.search).get("redirect")
        || "/dashboard";
      navigate(redirectTo, { replace: true });
    } catch (err: any) {
      setError(getErrorMessage(err, t));
    } finally {
      setMfaLoading(false);
    }
  };

  const handleBackToSignIn = () => {
    setMfaRequired(false);
    setMfaSessionId(null);
    setMfaFactorId(null);
    setMfaFactorLabel(null);
    setMfaCode("");
    setPassword("");
    setError(null);
    // Drop a stale ?mfa_session so a reload does not reopen the code prompt
    const url = new URL(window.location.href);
    if (url.searchParams.has("mfa_session")) {
      url.searchParams.delete("mfa_session");
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
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
    else if (errorParam === "mfa_setup_incomplete") setError(t("auth.mfa.setup_incomplete"));

    const params = new URLSearchParams(window.location.search);
    const mfaSession = params.get('mfa_session');
    if (mfaSession) {
      setMfaRequired(true);
      setMfaSessionId(mfaSession);
      authApi.getMFAAttempt(mfaSession)
        .then((session) => {
          setMfaFactorId(session.current_factor_id);
          setMfaFactorLabel(session.current_factor_label || null);
        })
        .catch(() => {
          setError(t("auth.mfa.session_expired"));
          setMfaRequired(false);
          setMfaSessionId(null);
        });
    }
  }, [t]);

  return (
    <AuthLayout>
          <AuthHeading
            title={mfaRequired ? t("auth.mfa.title") : t("auth.login")}
            description={mfaRequired ? t("auth.mfa.description") : t("auth.login_description")}
          />

          <AuthErrorBanner message={error} />

          {/* SSO section */}
          {!mfaRequired && ssoStatus?.has_sso && (
            <>
              <div className="space-y-3">
                {ssoStatus.google && (
                  <ProfessionalButton
                    type="button"
                    variant="outline"
                    className="w-full gap-3"
                    onClick={() => {
                      const redirectTo = new URLSearchParams(window.location.search).get("redirect") || "/dashboard";
                      window.location.href = `${API_BASE_URL}/auth/google/login?next=${encodeURIComponent(redirectTo)}`;
                    }}
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
                    onClick={() => {
                      const redirectTo = new URLSearchParams(window.location.search).get("redirect") || "/dashboard";
                      window.location.href = `${API_BASE_URL}/auth/azure/login?next=${encodeURIComponent(redirectTo)}`;
                    }}
                  >
                    <MicrosoftIcon />
                    {t("auth.sign_in_with_microsoft")}
                  </ProfessionalButton>
                )}
              </div>
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-3 text-muted-foreground tracking-wide">
                    {t("auth.or_sign_in_with_email")}
                  </span>
                </div>
              </div>
            </>
          )}

          {!mfaRequired && (
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

            <div className="relative">
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
              {/* After the input in the DOM so Tab goes email → password → here */}
              <Link
                to="/forgot-password"
                className="absolute right-0 top-0 text-sm leading-none text-primary hover:text-primary/80 transition-colors"
              >
                {t("auth.forgot_password")}
              </Link>
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
          )}

          {mfaRequired && (
            <form onSubmit={handleMFAVerify} className="space-y-4">
              <p className="rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
                {t("auth.mfa.current_step")}{" "}
                <span className="font-medium text-foreground">
                  {mfaFactorLabel || t("auth.mfa.default_factor")}
                </span>
              </p>
              <ProfessionalInput
                id="mfa_code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                label={t("auth.mfa.code_label")}
                placeholder={t("auth.mfa.code_placeholder")}
                value={mfaCode}
                onChange={(e) => { setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6)); clearError(); }}
                autoComplete="one-time-code"
                autoFocus
                required
                inputSize="lg"
                className="font-mono tracking-[0.3em] placeholder:font-sans placeholder:tracking-normal"
              />
              <ProfessionalButton
                type="submit"
                variant="gradient"
                size="xl"
                className="w-full mt-2"
                loading={mfaLoading}
              >
                {!mfaLoading && t("auth.mfa.verify")}
              </ProfessionalButton>
              <button
                type="button"
                onClick={handleBackToSignIn}
                className="mx-auto flex items-center justify-center gap-2 pt-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                {t("auth.mfa.back_to_sign_in")}
              </button>
            </form>
          )}

          {/* Sign-up link */}
          {!mfaRequired && (
          <p className="mt-8 text-center text-sm text-muted-foreground">
            {t("auth.no_account")}{" "}
            <Link
              to="/signup"
              className="text-primary hover:text-primary/80 font-semibold transition-colors"
            >
              {t("auth.signup.homepage")}
            </Link>
          </p>
          )}
    </AuthLayout>
  );
};

export default Login;
