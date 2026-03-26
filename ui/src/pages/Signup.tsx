import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Building2, UserPlus, CheckCircle, XCircle, Loader2,
  AlertCircle, CheckCircle2, TrendingUp, BarChart3, Shield,
} from "lucide-react";
import { authApi, API_BASE_URL, getErrorMessage } from "@/lib/api";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ThemeSwitcher } from "@/components/ui/theme-switcher";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { ProfessionalButton } from "@/components/ui/professional-button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PasswordRequirements {
  min_length: number;
  complexity: {
    require_uppercase: boolean;
    require_lowercase: boolean;
    require_numbers: boolean;
    require_special_chars: boolean;
    special_chars: string;
  };
  requirements: string[];
}

type AvailabilityStatus = {
  checking: boolean;
  available: boolean | null;
  message: string;
  /** Structured code so UI logic doesn't rely on message string matching */
  code: "taken" | "not_found" | "available" | "error" | null;
};

const INITIAL_STATUS: AvailabilityStatus = {
  checking: false,
  available: null,
  message: "",
  code: null,
};

// ─── Brand panel constants ────────────────────────────────────────────────────

const BRAND_FEATURES = [
  {
    icon: TrendingUp,
    title: "Multi-entity Support",
    desc: "Manage invoices and accounts across multiple organizations.",
  },
  {
    icon: BarChart3,
    title: "Automated Reconciliation",
    desc: "AI-assisted bank statement matching and bookkeeping.",
  },
  {
    icon: Shield,
    title: "Role-based Access Control",
    desc: "Granular permissions for every team member.",
  },
];

const TRUST_BADGES = ["256-bit SSL", "ISO 27001", "SOC 2 Type II"];

// ─── SSO icons ────────────────────────────────────────────────────────────────

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

// ─── Availability status message ──────────────────────────────────────────────

const StatusMessage = ({ status }: { status: AvailabilityStatus }) => {
  if (!status.message) return null;
  const isSuccess = status.available === true;
  const isError = status.available === false;
  return (
    <div
      className={`mt-2 p-3 rounded-lg text-xs font-medium ${
        isSuccess
          ? "bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
          : isError
          ? "bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300"
          : "bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300"
      }`}
    >
      {status.message}
    </div>
  );
};

// ─── Component ────────────────────────────────────────────────────────────────

const Signup: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    confirmPassword: "",
    organization_name: "",
    requested_role: "user",
    message: "",
  });
  const [signupMode, setSignupMode] = useState<"create" | "join">("create");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [orgStatus, setOrgStatus] = useState<AvailabilityStatus>(INITIAL_STATUS);
  const [emailStatus, setEmailStatus] = useState<AvailabilityStatus>(INITIAL_STATUS);
  const [ssoStatus, setSsoStatus] = useState<{ google: boolean; microsoft: boolean; has_sso: boolean } | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [passwordRequirements, setPasswordRequirements] = useState<PasswordRequirements | null>(null);

  // Memoized special-char regex — only recomputed when the chars string changes
  const specialCharRegex = useMemo(() => {
    if (!passwordRequirements) return null;
    const escaped = passwordRequirements.complexity.special_chars.replace(
      /[.*+?^${}()|[\]\\]/g,
      "\\$&"
    );
    return new RegExp(`[${escaped}]`);
  }, [passwordRequirements]);

  // ── Availability checks ───────────────────────────────────────────────────

  const checkOrgAvailability = useCallback(
    async (name: string) => {
      if (!name) { setOrgStatus(INITIAL_STATUS); return; }
      if (name.length < 2) {
        setOrgStatus({ checking: false, available: false, code: null, message: t("auth.signup.availability.org_min_length") });
        return;
      }
      setOrgStatus({ checking: true, available: null, code: null, message: t("auth.signup.availability.checking") });
      try {
        if (signupMode === "create") {
          const result = await authApi.checkOrganizationNameAvailability(name);
          setOrgStatus({
            checking: false,
            available: result.available,
            code: result.available ? "available" : "taken",
            message: result.available
              ? t("auth.signup.availability.org_available")
              : t("auth.signup.availability.org_taken"),
          });
        } else {
          const result = await authApi.lookupOrganization(name);
          setOrgStatus({
            checking: false,
            available: result.exists,
            code: result.exists ? "available" : "not_found",
            message: result.exists
              ? t("auth.signup.availability.org_available")
              : t("auth.signup.availability.org_not_found", { name }),
          });
        }
      } catch {
        setOrgStatus({ checking: false, available: null, code: "error", message: t("auth.signup.availability.error_checking") });
      }
    },
    [signupMode, t]
  );

  const checkEmailAvailability = useCallback(
    async (email: string) => {
      if (!email) { setEmailStatus(INITIAL_STATUS); return; }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setEmailStatus({ checking: false, available: false, code: null, message: t("auth.signup.availability.valid_email") });
        return;
      }
      setEmailStatus({ checking: true, available: null, code: null, message: t("auth.signup.availability.checking") });
      try {
        const result = await authApi.checkEmailAvailability(email);
        setEmailStatus({
          checking: false,
          available: result.available,
          code: result.available ? "available" : "taken",
          message: result.available
            ? t("auth.signup.availability.email_available")
            : t("auth.signup.availability.email_taken"),
        });
      } catch {
        setEmailStatus({ checking: false, available: null, code: "error", message: t("auth.signup.availability.error_checking") });
      }
    },
    [t]
  );

  // Debounce availability checks (500 ms)
  useEffect(() => {
    const id = setTimeout(() => { if (formData.organization_name) checkOrgAvailability(formData.organization_name); }, 500);
    return () => clearTimeout(id);
  }, [formData.organization_name, checkOrgAvailability]);

  useEffect(() => {
    const id = setTimeout(() => { if (formData.email) checkEmailAvailability(formData.email); }, 500);
    return () => clearTimeout(id);
  }, [formData.email, checkEmailAvailability]);

  // ── Bootstrap ─────────────────────────────────────────────────────────────

  useEffect(() => {
    // Fail closed: do not expose SSO buttons if the status API fails
    authApi.getSSOStatus()
      .then(setSsoStatus)
      .catch(() => setSsoStatus({ google: false, microsoft: false, has_sso: false }));

    authApi.getPasswordRequirements()
      .then(setPasswordRequirements)
      .catch(() =>
        setPasswordRequirements({
          min_length: 8,
          complexity: {
            require_uppercase: true,
            require_lowercase: true,
            require_numbers: true,
            require_special_chars: true,
            special_chars: "!@#$%^&*()_+-=[]{}|;:,.<>?",
          },
          requirements: [],
        })
      );
  }, []);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const switchMode = (mode: "create" | "join") => {
    setSignupMode(mode);
    setOrgStatus(INITIAL_STATUS);
    if (formData.organization_name && mode === "create") {
      checkOrgAvailability(formData.organization_name);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (formData.password !== formData.confirmPassword) {
      const msg = t("auth.signup.validation.passwords_not_match");
      setError(msg); toast.error(msg); setLoading(false); return;
    }

    if (!passwordRequirements) {
      const msg = "Password requirements not loaded. Please try again.";
      setError(msg); toast.error(msg); setLoading(false); return;
    }

    // Password complexity validation
    const pw = formData.password;
    const c = passwordRequirements.complexity;
    const errors: string[] = [];
    if (pw.length < passwordRequirements.min_length)
      errors.push(t("auth.signup.validation.password_min_length", { min_length: passwordRequirements.min_length }));
    if (c.require_uppercase && !/[A-Z]/.test(pw))
      errors.push(t("auth.signup.req_uppercase", { defaultValue: "One uppercase letter required" }));
    if (c.require_lowercase && !/[a-z]/.test(pw))
      errors.push(t("auth.signup.req_lowercase", { defaultValue: "One lowercase letter required" }));
    if (c.require_numbers && !/\d/.test(pw))
      errors.push(t("auth.signup.req_number", { defaultValue: "One number required" }));
    if (c.require_special_chars && specialCharRegex && !specialCharRegex.test(pw))
      errors.push(t("auth.signup.req_special_char", { defaultValue: "One special character required" }));

    if (errors.length > 0) {
      const msg = errors.join(". ");
      setError(msg); toast.error(msg); setLoading(false); return;
    }

    if (emailStatus.available === false) {
      const msg = t("auth.signup.validation.email_not_available");
      setError(msg); toast.error(msg); setLoading(false); return;
    }
    if (emailStatus.checking) {
      const msg = t("auth.signup.validation.waiting_email_check");
      setError(msg); toast.error(msg); setLoading(false); return;
    }
    if (orgStatus.available === false) {
      const msg = t("auth.signup.validation.org_not_available");
      setError(msg); toast.error(msg); setLoading(false); return;
    }
    if (orgStatus.checking) {
      const msg = t("auth.signup.validation.waiting_org_check");
      setError(msg); toast.error(msg); setLoading(false); return;
    }

    try {
      if (signupMode === "create") {
        const data = await authApi.register(formData);
        localStorage.removeItem("selected_tenant_id");
        localStorage.removeItem("token");
        localStorage.setItem("user", JSON.stringify(data.user));
        window.dispatchEvent(new Event("auth-changed"));
        navigate("/dashboard");
      } else {
        const result = await authApi.submitJoinRequest({
          email: formData.email,
          first_name: formData.first_name,
          last_name: formData.last_name,
          password: formData.password,
          organization_name: formData.organization_name,
          requested_role: formData.requested_role,
          message: formData.message,
        });
        if (result.success) {
          setSuccessMessage(result.message);
          setShowSuccessModal(true);
        } else {
          setError(result.message);
          toast.error(result.message);
        }
      }
    } catch (err: any) {
      const msg = getErrorMessage(err, t);
      setError(msg); toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // ── Password checker helpers ───────────────────────────────────────────────

  const pwChecks = useMemo(() => {
    if (!passwordRequirements || !formData.password) return null;
    const pw = formData.password;
    const c = passwordRequirements.complexity;
    return {
      length: pw.length >= passwordRequirements.min_length,
      upper: !c.require_uppercase || /[A-Z]/.test(pw),
      lower: !c.require_lowercase || /[a-z]/.test(pw),
      number: !c.require_numbers || /\d/.test(pw),
      special: !c.require_special_chars || (specialCharRegex ? specialCharRegex.test(pw) : true),
    };
  }, [formData.password, passwordRequirements, specialCharRegex]);

  const CheckItem = ({ met, label }: { met: boolean; label: string }) => (
    <div className={`flex items-center gap-1.5 text-xs ${met ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400 dark:text-slate-500"}`}>
      {met ? <CheckCircle className="h-3 w-3 flex-shrink-0" /> : <XCircle className="h-3 w-3 flex-shrink-0" />}
      {label}
    </div>
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950">
      {/* ── Left brand panel (desktop only) ── */}
      <div className="hidden lg:flex lg:w-[44%] xl:w-2/5 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex-col justify-between p-12 relative overflow-hidden flex-shrink-0">
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `radial-gradient(circle, #ffffff 1px, transparent 1px)`,
            backgroundSize: "28px 28px",
          }}
        />
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

        {/* Features */}
        <div className="relative z-10 space-y-8">
          <h2 className="text-white text-2xl font-semibold leading-snug">
            Everything your finance team needs, in one place.
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
      <div className="flex-1 flex flex-col items-center justify-start py-12 px-6 sm:px-10 overflow-y-auto">
        {/* Mobile-only logo */}
        <div className="lg:hidden mb-8 text-center w-full">
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
              {t("auth.signup.title")}
            </h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
              {t("auth.signup.subtitle")}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Error banner */}
            {error && (
              <div
                role="alert"
                aria-live="assertive"
                className="flex items-start gap-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300 px-4 py-3 rounded-xl"
              >
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
            )}

            {/* Mode selector */}
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">
                {t("auth.signup.how_to_get_started")}
              </p>
              <div className="grid grid-cols-2 gap-2">
                <ProfessionalButton
                  type="button"
                  variant={signupMode === "create" ? "gradient" : "outline"}
                  className="w-full py-2.5 text-xs"
                  onClick={() => switchMode("create")}
                >
                  <Building2 className="h-3.5 w-3.5 flex-shrink-0" />
                  {t("auth.signup.create_organization")}
                </ProfessionalButton>
                <ProfessionalButton
                  type="button"
                  variant={signupMode === "join" ? "gradient" : "outline"}
                  className="w-full py-2.5 text-xs"
                  onClick={() => switchMode("join")}
                >
                  <UserPlus className="h-3.5 w-3.5 flex-shrink-0" />
                  {t("auth.signup.join_organization")}
                </ProfessionalButton>
              </div>
            </div>

            {/* Organization name */}
            <div>
              <div className="relative">
                <ProfessionalInput
                  id="organization_name"
                  name="organization_name"
                  type="text"
                  label={t("auth.signup.organization_name")}
                  placeholder={
                    signupMode === "create"
                      ? t("auth.signup.organization_placeholder")
                      : t("auth.signup.availability.org_not_found", { name: "" }).replace("' not found.", "")
                        .replace("Organization '", "")
                        || "Enter organization name to join"
                  }
                  value={formData.organization_name}
                  onChange={handleChange}
                  autoComplete="organization"
                  required
                  inputSize="lg"
                  leftIcon={<Building2 />}
                  rightIcon={
                    orgStatus.checking ? (
                      <Loader2 className="animate-spin text-slate-400" />
                    ) : orgStatus.available === true ? (
                      <CheckCircle className="text-emerald-500" />
                    ) : orgStatus.available === false ? (
                      <XCircle className="text-red-500" />
                    ) : undefined
                  }
                  error={orgStatus.available === false}
                />
              </div>
              <StatusMessage status={orgStatus} />
              {orgStatus.code === "taken" && (
                <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                  {t("auth.signup.tips.org_taken_tip")}
                </p>
              )}
            </div>

            {/* First + Last name – side by side */}
            <div className="grid grid-cols-2 gap-3">
              <ProfessionalInput
                id="first_name"
                name="first_name"
                type="text"
                label={t("auth.signup.first_name")}
                placeholder={t("auth.signup.first_name_placeholder")}
                value={formData.first_name}
                onChange={handleChange}
                autoComplete="given-name"
                required
                inputSize="lg"
              />
              <ProfessionalInput
                id="last_name"
                name="last_name"
                type="text"
                label={t("auth.signup.last_name")}
                placeholder={t("auth.signup.last_name_placeholder")}
                value={formData.last_name}
                onChange={handleChange}
                autoComplete="family-name"
                required
                inputSize="lg"
              />
            </div>

            {/* Email */}
            <div>
              <ProfessionalInput
                id="email"
                name="email"
                type="email"
                label={t("auth.signup.email_address")}
                placeholder={t("auth.signup.email_placeholder")}
                value={formData.email}
                onChange={handleChange}
                autoComplete="email"
                required
                inputSize="lg"
                rightIcon={
                  emailStatus.checking ? (
                    <Loader2 className="animate-spin text-slate-400" />
                  ) : emailStatus.available === true ? (
                    <CheckCircle className="text-emerald-500" />
                  ) : emailStatus.available === false ? (
                    <XCircle className="text-red-500" />
                  ) : undefined
                }
                error={emailStatus.available === false}
              />
              <StatusMessage status={emailStatus} />
              {emailStatus.code === "taken" && (
                <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                  {t("auth.signup.tips.email_taken_tip")}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <ProfessionalInput
                id="password"
                name="password"
                type="password"
                label={t("auth.signup.password")}
                placeholder={t("auth.signup.password_placeholder")}
                value={formData.password}
                onChange={handleChange}
                autoComplete="new-password"
                required
                inputSize="lg"
              />
              {/* Live password requirements */}
              {formData.password && pwChecks && passwordRequirements && (
                <div className="mt-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700/50">
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
                    {t("auth.signup.password_requirements_label", { defaultValue: "Password requirements" })}
                  </p>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <CheckItem
                      met={pwChecks.length}
                      label={t("auth.signup.req_min_length", {
                        min_length: passwordRequirements.min_length,
                        defaultValue: `At least ${passwordRequirements.min_length} characters`,
                      })}
                    />
                    {passwordRequirements.complexity.require_uppercase && (
                      <CheckItem met={pwChecks.upper} label={t("auth.signup.req_uppercase", { defaultValue: "Uppercase letter" })} />
                    )}
                    {passwordRequirements.complexity.require_lowercase && (
                      <CheckItem met={pwChecks.lower} label={t("auth.signup.req_lowercase", { defaultValue: "Lowercase letter" })} />
                    )}
                    {passwordRequirements.complexity.require_numbers && (
                      <CheckItem met={pwChecks.number} label={t("auth.signup.req_number", { defaultValue: "Number" })} />
                    )}
                    {passwordRequirements.complexity.require_special_chars && (
                      <CheckItem met={pwChecks.special} label={t("auth.signup.req_special_char", { defaultValue: "Special character" })} />
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <ProfessionalInput
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              label={t("auth.signup.confirm_password")}
              placeholder={t("auth.signup.confirm_password_placeholder")}
              value={formData.confirmPassword}
              onChange={handleChange}
              autoComplete="new-password"
              required
              inputSize="lg"
              error={!!formData.confirmPassword && formData.password !== formData.confirmPassword}
            />

            {/* Join-mode extra fields */}
            {signupMode === "join" && (
              <>
                {/* Role selector */}
                <div className="space-y-2">
                  <label
                    htmlFor="requested_role"
                    className="text-sm font-medium leading-none text-slate-900 dark:text-slate-100"
                  >
                    {t("auth.signup.requested_role", { defaultValue: "Requested Role" })}
                  </label>
                  <select
                    id="requested_role"
                    name="requested_role"
                    value={formData.requested_role}
                    onChange={handleChange}
                    className="flex h-12 w-full rounded-lg border border-input bg-background px-3 text-sm transition-all hover:border-ring/50 focus:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>

                {/* Message */}
                <ProfessionalTextarea
                  id="message"
                  name="message"
                  label={t("auth.signup.message_to_admin", { defaultValue: "Message to Admin (Optional)" })}
                  placeholder={t("auth.signup.message_to_admin_placeholder", {
                    defaultValue: "Tell the admin why you want to join this organization...",
                  })}
                  value={formData.message}
                  onChange={handleChange}
                  rows={3}
                />
              </>
            )}

            {/* Submit */}
            <ProfessionalButton
              type="submit"
              variant="gradient"
              size="xl"
              className="w-full"
              loading={loading}
            >
              {!loading && (
                signupMode === "create"
                  ? t("auth.signup.create_account")
                  : t("auth.signup.request_to_join", { defaultValue: "Request to Join" })
              )}
            </ProfessionalButton>

            {/* Terms */}
            <p className="text-center text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              {t("auth.signup.terms_agreement", { defaultValue: "By creating an account, you agree to our" })}{" "}
              <a href="/terms" className="text-primary hover:text-primary/80 transition-colors font-medium">
                {t("auth.signup.terms", { defaultValue: "Terms of Service" })}
              </a>{" "}
              {t("auth.signup.and", { defaultValue: "and" })}{" "}
              <a href="/privacy" className="text-primary hover:text-primary/80 transition-colors font-medium">
                {t("auth.signup.privacy_policy", { defaultValue: "Privacy Policy" })}
              </a>
              .
            </p>
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
                    {t("auth.signup.or_continue_with")}
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
                    {t("auth.signup.sign_up_with_google")}
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
                    {t("auth.signup.sign_up_with_microsoft")}
                  </ProfessionalButton>
                )}
              </div>
            </>
          )}

          {/* Sign-in link */}
          <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
            {t("auth.signup.already_have_account")}{" "}
            <Link to="/login" className="text-primary hover:text-primary/80 font-semibold transition-colors">
              {t("auth.signup.sign_in")}
            </Link>
          </p>
        </div>

        {/* Locale / theme controls */}
        <div className="mt-10 flex items-center gap-4">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>
      </div>

      {/* Join-request success modal */}
      <Dialog
        open={showSuccessModal}
        onOpenChange={(open) => {
          setShowSuccessModal(open);
          if (!open) navigate("/login");
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t("auth.signup.join_request_submitted", { defaultValue: "Join Request Submitted" })}
            </DialogTitle>
            <DialogDescription>{successMessage}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => { setShowSuccessModal(false); navigate("/login"); }}>
              {t("auth.signup.ok", { defaultValue: "OK" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Signup;
