import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Save, Smartphone } from "lucide-react";
import { toast } from "sonner";

import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardDescription,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ExpenseMobileServiceSettings, settingsApi, getErrorMessage } from "@/lib/api";

const EXPENSE_SETTINGS_KEY = "expense_settings";

type DigestInterval = "daily" | "weekly" | "monthly";
type RecipientMode = "me" | "admins" | "custom";
type DuplicateDetection = "off" | "warn" | "block";
type ReminderFrequency = "off" | "daily" | "every_2_days" | "weekly";

interface ExpenseSettings {
  digest: {
    enabled: boolean;
    interval: DigestInterval;
    delivery_time: string;
    timezone: string;
    include_no_activity: boolean;
    recipients: {
      mode: RecipientMode;
      custom_emails: string;
    };
    include_sections: {
      totals_by_category: boolean;
      top_vendors: boolean;
      pending_approvals: boolean;
      rejected_expenses: boolean;
    };
  };
  policy: {
    auto_approve_enabled: boolean;
    auto_approve_under_amount: number;
    level2_approval_threshold: number;
    escalation_after_hours: number;
    require_rejection_comment: boolean;
  };
  validation: {
    receipt_required_over_amount: number;
    enforce_allowed_categories: boolean;
    allowed_categories: string;
    daily_limit_per_category: number;
    duplicate_detection: DuplicateDetection;
  };
  defaults: {
    currency: string;
    tax_rate: number;
    reimbursable_default: boolean;
    payment_method: string;
    default_project: string;
    default_category: string;
    default_tags: string;
  };
  submission: {
    submission_window_days: number;
    lock_after_month_close: boolean;
    require_fields_before_submit: boolean;
    allow_edit_after_approval: boolean;
  };
  notifications: {
    notify_manager_on_submission: boolean;
    notify_employee_on_approval: boolean;
    notify_employee_on_rejection: boolean;
    pending_approval_reminder: ReminderFrequency;
  };
}

interface ExpensesSettingsTabProps {
  isAdmin: boolean;
}

const defaultExpenseSettings: ExpenseSettings = {
  digest: {
    enabled: true,
    interval: "weekly",
    delivery_time: "09:00",
    timezone: "UTC",
    include_no_activity: false,
    recipients: {
      mode: "admins",
      custom_emails: "",
    },
    include_sections: {
      totals_by_category: true,
      top_vendors: true,
      pending_approvals: true,
      rejected_expenses: true,
    },
  },
  policy: {
    auto_approve_enabled: false,
    auto_approve_under_amount: 100,
    level2_approval_threshold: 1000,
    escalation_after_hours: 48,
    require_rejection_comment: true,
  },
  validation: {
    receipt_required_over_amount: 50,
    enforce_allowed_categories: false,
    allowed_categories: "",
    daily_limit_per_category: 500,
    duplicate_detection: "warn",
  },
  defaults: {
    currency: "USD",
    tax_rate: 0,
    reimbursable_default: true,
    payment_method: "",
    default_project: "",
    default_category: "",
    default_tags: "",
  },
  submission: {
    submission_window_days: 30,
    lock_after_month_close: false,
    require_fields_before_submit: true,
    allow_edit_after_approval: false,
  },
  notifications: {
    notify_manager_on_submission: true,
    notify_employee_on_approval: true,
    notify_employee_on_rejection: true,
    pending_approval_reminder: "daily",
  },
};

const defaultExpenseMobileSettings: ExpenseMobileServiceSettings = {
  enabled: false,
  app_id: "",
  signup_enabled: true,
  default_role: "user",
  allowed_auth_methods: {
    password: true,
    google: false,
    microsoft: false,
  },
  branding: {
    title: "",
    subtitle: "",
    accent_color: "#10b981",
    logo_url: "",
  },
};

const toNumber = (value: unknown, fallback: number): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeExpenseSettings = (value: unknown): ExpenseSettings => {
  if (!value || typeof value !== "object") {
    return defaultExpenseSettings;
  }

  const raw = value as Partial<ExpenseSettings>;
  const digest = raw.digest ?? {};
  const recipients = digest.recipients ?? {};
  const includeSections = digest.include_sections ?? {};
  const policy = raw.policy ?? {};
  const validation = raw.validation ?? {};
  const defaults = raw.defaults ?? {};
  const submission = raw.submission ?? {};
  const notifications = raw.notifications ?? {};

  return {
    digest: {
      ...defaultExpenseSettings.digest,
      ...digest,
      delivery_time: String(digest.delivery_time ?? defaultExpenseSettings.digest.delivery_time),
      timezone: String(digest.timezone ?? defaultExpenseSettings.digest.timezone),
      interval: (["daily", "weekly", "monthly"].includes(String(digest.interval))
        ? digest.interval
        : defaultExpenseSettings.digest.interval) as DigestInterval,
      recipients: {
        ...defaultExpenseSettings.digest.recipients,
        ...recipients,
        mode: (["me", "admins", "custom"].includes(String(recipients.mode))
          ? recipients.mode
          : defaultExpenseSettings.digest.recipients.mode) as RecipientMode,
        custom_emails: String(
          recipients.custom_emails ?? defaultExpenseSettings.digest.recipients.custom_emails
        ),
      },
      include_sections: {
        ...defaultExpenseSettings.digest.include_sections,
        ...includeSections,
      },
    },
    policy: {
      ...defaultExpenseSettings.policy,
      ...policy,
      auto_approve_under_amount: toNumber(
        policy.auto_approve_under_amount,
        defaultExpenseSettings.policy.auto_approve_under_amount
      ),
      level2_approval_threshold: toNumber(
        policy.level2_approval_threshold,
        defaultExpenseSettings.policy.level2_approval_threshold
      ),
      escalation_after_hours: toNumber(
        policy.escalation_after_hours,
        defaultExpenseSettings.policy.escalation_after_hours
      ),
    },
    validation: {
      ...defaultExpenseSettings.validation,
      ...validation,
      receipt_required_over_amount: toNumber(
        validation.receipt_required_over_amount,
        defaultExpenseSettings.validation.receipt_required_over_amount
      ),
      daily_limit_per_category: toNumber(
        validation.daily_limit_per_category,
        defaultExpenseSettings.validation.daily_limit_per_category
      ),
      duplicate_detection: (["off", "warn", "block"].includes(String(validation.duplicate_detection))
        ? validation.duplicate_detection
        : defaultExpenseSettings.validation.duplicate_detection) as DuplicateDetection,
      allowed_categories: String(validation.allowed_categories ?? defaultExpenseSettings.validation.allowed_categories),
    },
    defaults: {
      ...defaultExpenseSettings.defaults,
      ...defaults,
      currency: String(defaults.currency ?? defaultExpenseSettings.defaults.currency),
      tax_rate: toNumber(defaults.tax_rate, defaultExpenseSettings.defaults.tax_rate),
      payment_method: String(defaults.payment_method ?? defaultExpenseSettings.defaults.payment_method),
      default_project: String(defaults.default_project ?? defaultExpenseSettings.defaults.default_project),
      default_category: String(defaults.default_category ?? defaultExpenseSettings.defaults.default_category),
      default_tags: String(defaults.default_tags ?? defaultExpenseSettings.defaults.default_tags),
    },
    submission: {
      ...defaultExpenseSettings.submission,
      ...submission,
      submission_window_days: toNumber(
        submission.submission_window_days,
        defaultExpenseSettings.submission.submission_window_days
      ),
    },
    notifications: {
      ...defaultExpenseSettings.notifications,
      ...notifications,
      pending_approval_reminder: (
        ["off", "daily", "every_2_days", "weekly"].includes(String(notifications.pending_approval_reminder))
          ? notifications.pending_approval_reminder
          : defaultExpenseSettings.notifications.pending_approval_reminder
      ) as ReminderFrequency,
    },
  };
};

const numericValue = (raw: string): number => {
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const ExpensesSettingsTab: React.FC<ExpensesSettingsTabProps> = ({ isAdmin }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState<ExpenseSettings>(defaultExpenseSettings);
  const [expenseMobile, setExpenseMobile] = useState<ExpenseMobileServiceSettings>(defaultExpenseMobileSettings);

  const { data, isLoading } = useQuery({
    queryKey: ["settings", EXPENSE_SETTINGS_KEY],
    queryFn: () => settingsApi.getSetting(EXPENSE_SETTINGS_KEY),
    enabled: isAdmin,
  });

  const { data: organizationSettings, isLoading: isOrganizationSettingsLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsApi.getSettings(),
    enabled: isAdmin,
  });

  useEffect(() => {
    if (data) {
      setSettings(normalizeExpenseSettings(data.value));
    }
  }, [data]);

  useEffect(() => {
    if (organizationSettings?.expense_mobile) {
      setExpenseMobile(organizationSettings.expense_mobile);
    }
  }, [organizationSettings]);

  const saveMutation = useMutation({
    mutationFn: (nextSettings: ExpenseSettings) =>
      Promise.all([
        settingsApi.updateSetting(EXPENSE_SETTINGS_KEY, nextSettings),
        settingsApi.updateSettings({ expense_mobile: expenseMobile }),
      ]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", EXPENSE_SETTINGS_KEY] });
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(t("settings.settings_saved_successfully", "Settings saved successfully"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    },
  });

  const updateExpenseMobile = (patch: Partial<ExpenseMobileServiceSettings>) => {
    setExpenseMobile((prev) => ({ ...prev, ...patch }));
  };

  const updateExpenseMobileBranding = (patch: Partial<ExpenseMobileServiceSettings["branding"]>) => {
    setExpenseMobile((prev) => ({
      ...prev,
      branding: {
        ...prev.branding,
        ...patch,
      },
    }));
  };

  const updateExpenseMobileAuthMethods = (
    patch: Partial<ExpenseMobileServiceSettings["allowed_auth_methods"]>
  ) => {
    setExpenseMobile((prev) => ({
      ...prev,
      allowed_auth_methods: {
        ...prev.allowed_auth_methods,
        ...patch,
      },
    }));
  };

  const testDigestMutation = useMutation({
    mutationFn: () => settingsApi.sendExpenseDigest(true),
    onSuccess: (result) => {
      const status = result?.status || "sent";
      toast.success(
        status === "sent"
          ? t("settings.expenses.digest.test_success", "Expense digest sent")
          : t("settings.expenses.digest.test_processed", "Expense digest processed")
      );
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    },
  });

  return (
    <div className="space-y-6">
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <Smartphone className="h-5 w-5 text-primary" />
            {t("settings.expenses.mobile.title", "Standalone Mobile Expense Service")}
          </ProfessionalCardTitle>
          <ProfessionalCardDescription>
            {t(
              "settings.expenses.mobile.description",
              "Configure the yfw-mobile expense app for this organization. End users never choose the organization in-app."
            )}
          </ProfessionalCardDescription>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-6">
          <div className="flex items-center justify-between gap-4 rounded-xl border border-border/50 bg-muted/20 p-4">
            <div className="space-y-1">
              <p className="font-medium">
                {t("settings.expenses.mobile.enabled", "Enable organization-bound mobile service")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  "settings.expenses.mobile.enabled_description",
                  "Allow the configured mobile app ID to sign in and save expenses into this organization."
                )}
              </p>
            </div>
            <Switch
              checked={expenseMobile.enabled}
              onCheckedChange={(checked) => updateExpenseMobile({ enabled: checked })}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ProfessionalInput
              label={t("settings.expenses.mobile.app_id", "Mobile App ID")}
              id="expense-mobile-app-id"
              name="expense-mobile-app-id"
              value={expenseMobile.app_id}
              onChange={(event) => updateExpenseMobile({ app_id: event.target.value })}
              helperText={t(
                "settings.expenses.mobile.app_id_hint",
                "Set the same value in EXPO_PUBLIC_EXPENSE_APP_ID for the mobile build."
              )}
            />
            <div className="space-y-2">
              <Label htmlFor="expense-mobile-default-role">
                {t("settings.expenses.mobile.default_role", "Default mobile signup role")}
              </Label>
              <Select
                value={expenseMobile.default_role}
                onValueChange={(value: ExpenseMobileServiceSettings["default_role"]) =>
                  updateExpenseMobile({ default_role: value })
                }
              >
                <SelectTrigger id="expense-mobile-default-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">{t("settings.roles.user", "User")}</SelectItem>
                  <SelectItem value="viewer">{t("settings.roles.viewer", "Viewer")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-xl border border-border/50 bg-muted/20 p-4">
            <div className="space-y-1">
              <p className="font-medium">{t("settings.expenses.mobile.signup", "Allow direct sign up")}</p>
              <p className="text-sm text-muted-foreground">
                {t(
                  "settings.expenses.mobile.signup_description",
                  "Let new mobile users create normal YFW accounts directly inside this organization."
                )}
              </p>
            </div>
            <Switch
              checked={expenseMobile.signup_enabled}
              onCheckedChange={(checked) => updateExpenseMobile({ signup_enabled: checked })}
            />
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <p className="font-medium">{t("settings.expenses.mobile.auth_methods", "Allowed auth methods")}</p>
              <p className="text-sm text-muted-foreground">
                {t(
                  "settings.expenses.mobile.auth_methods_description",
                  "Password is active now. SSO flags are stored for later rollout."
                )}
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                <Label htmlFor="expense-mobile-password">{t("settings.expenses.mobile.password", "Password")}</Label>
                <Switch
                  id="expense-mobile-password"
                  checked={expenseMobile.allowed_auth_methods.password}
                  onCheckedChange={(checked) => updateExpenseMobileAuthMethods({ password: checked })}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                <Label htmlFor="expense-mobile-google">{t("settings.expenses.mobile.google", "Google")}</Label>
                <Switch
                  id="expense-mobile-google"
                  checked={expenseMobile.allowed_auth_methods.google}
                  onCheckedChange={(checked) => updateExpenseMobileAuthMethods({ google: checked })}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                <Label htmlFor="expense-mobile-microsoft">{t("settings.expenses.mobile.microsoft", "Microsoft")}</Label>
                <Switch
                  id="expense-mobile-microsoft"
                  checked={expenseMobile.allowed_auth_methods.microsoft}
                  onCheckedChange={(checked) => updateExpenseMobileAuthMethods({ microsoft: checked })}
                />
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ProfessionalInput
              label={t("settings.expenses.mobile.mobile_title", "Mobile title")}
              id="expense-mobile-title"
              name="expense-mobile-title"
              value={expenseMobile.branding.title}
              onChange={(event) => updateExpenseMobileBranding({ title: event.target.value })}
            />
            <ProfessionalInput
              label={t("settings.expenses.mobile.accent_color", "Accent color")}
              id="expense-mobile-accent-color"
              name="expense-mobile-accent-color"
              value={expenseMobile.branding.accent_color}
              onChange={(event) => updateExpenseMobileBranding({ accent_color: event.target.value })}
            />
          </div>

          <ProfessionalTextarea
            label={t("settings.expenses.mobile.subtitle", "Mobile subtitle")}
            id="expense-mobile-subtitle"
            name="expense-mobile-subtitle"
            rows={3}
            value={expenseMobile.branding.subtitle}
            onChange={(event) => updateExpenseMobileBranding({ subtitle: event.target.value })}
          />
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t("settings.expenses.digest.title", "Expense Digest")}</ProfessionalCardTitle>
          <ProfessionalCardDescription>
            {t("settings.expenses.digest.description", "Configure recurring summary emails for expenses.")}
          </ProfessionalCardDescription>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-5">
          <div className="rounded-xl border border-border/50 bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <p className="font-medium">{t("settings.expenses.digest.enabled", "Enable Expense Digest")}</p>
                <p className="text-sm text-muted-foreground">
                  {t("settings.expenses.digest.enabled_description", "Send recurring expense summaries by email.")}
                </p>
              </div>
              <Switch
                checked={settings.digest.enabled}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({ ...prev, digest: { ...prev.digest, enabled: checked } }))
                }
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>{t("settings.expenses.digest.interval", "Interval")}</Label>
              <Select
                value={settings.digest.interval}
                onValueChange={(value: DigestInterval) =>
                  setSettings((prev) => ({ ...prev, digest: { ...prev.digest, interval: value } }))
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">{t("common.daily", "Daily")}</SelectItem>
                  <SelectItem value="weekly">{t("common.weekly", "Weekly")}</SelectItem>
                  <SelectItem value="monthly">{t("common.monthly", "Monthly")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <ProfessionalInput
              type="time"
              label={t("settings.expenses.digest.delivery_time", "Delivery Time")}
              value={settings.digest.delivery_time}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  digest: { ...prev.digest, delivery_time: event.target.value },
                }))
              }
            />
            <ProfessionalInput
              label={t("settings.expenses.digest.timezone", "Timezone")}
              value={settings.digest.timezone}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  digest: { ...prev.digest, timezone: event.target.value },
                }))
              }
              placeholder="America/Toronto"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>{t("settings.expenses.digest.recipient_mode", "Recipient Mode")}</Label>
              <Select
                value={settings.digest.recipients.mode}
                onValueChange={(value: RecipientMode) =>
                  setSettings((prev) => ({
                    ...prev,
                    digest: {
                      ...prev.digest,
                      recipients: { ...prev.digest.recipients, mode: value },
                    },
                  }))
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="me">{t("settings.expenses.digest.me", "Me only")}</SelectItem>
                  <SelectItem value="admins">{t("settings.expenses.digest.admins", "Admins")}</SelectItem>
                  <SelectItem value="custom">{t("settings.expenses.digest.custom", "Custom emails")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <ProfessionalInput
              label={t("settings.expenses.digest.custom_emails", "Custom Emails")}
              value={settings.digest.recipients.custom_emails}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  digest: {
                    ...prev.digest,
                    recipients: { ...prev.digest.recipients, custom_emails: event.target.value },
                  },
                }))
              }
              placeholder="finance@company.com, manager@company.com"
              disabled={settings.digest.recipients.mode !== "custom"}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.digest.include_totals", "Include totals by category")}</Label>
              <Switch
                checked={settings.digest.include_sections.totals_by_category}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    digest: {
                      ...prev.digest,
                      include_sections: { ...prev.digest.include_sections, totals_by_category: checked },
                    },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.digest.include_top_vendors", "Include top vendors")}</Label>
              <Switch
                checked={settings.digest.include_sections.top_vendors}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    digest: {
                      ...prev.digest,
                      include_sections: { ...prev.digest.include_sections, top_vendors: checked },
                    },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.digest.include_pending", "Include pending approvals")}</Label>
              <Switch
                checked={settings.digest.include_sections.pending_approvals}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    digest: {
                      ...prev.digest,
                      include_sections: { ...prev.digest.include_sections, pending_approvals: checked },
                    },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.digest.include_rejected", "Include rejected expenses")}</Label>
              <Switch
                checked={settings.digest.include_sections.rejected_expenses}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    digest: {
                      ...prev.digest,
                      include_sections: { ...prev.digest.include_sections, rejected_expenses: checked },
                    },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3 md:col-span-2">
              <Label>{t("settings.expenses.digest.include_no_activity", "Send email when there is no activity")}</Label>
              <Switch
                checked={settings.digest.include_no_activity}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({ ...prev, digest: { ...prev.digest, include_no_activity: checked } }))
                }
              />
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t("settings.expenses.policy.title", "Policy & Approval Rules")}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="grid gap-4 md:grid-cols-2">
          <div className="flex items-center justify-between rounded-lg border border-border/40 p-3 md:col-span-2">
            <Label>{t("settings.expenses.policy.auto_approve", "Enable auto-approval below threshold")}</Label>
            <Switch
              checked={settings.policy.auto_approve_enabled}
              onCheckedChange={(checked) =>
                setSettings((prev) => ({ ...prev, policy: { ...prev.policy, auto_approve_enabled: checked } }))
              }
            />
          </div>
          <ProfessionalInput
            type="number"
            label={t("settings.expenses.policy.auto_approve_under", "Auto-approve under amount")}
            value={settings.policy.auto_approve_under_amount}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                policy: { ...prev.policy, auto_approve_under_amount: numericValue(event.target.value) },
              }))
            }
          />
          <ProfessionalInput
            type="number"
            label={t("settings.expenses.policy.level2_threshold", "Level 2 approval threshold")}
            value={settings.policy.level2_approval_threshold}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                policy: { ...prev.policy, level2_approval_threshold: numericValue(event.target.value) },
              }))
            }
          />
          <ProfessionalInput
            type="number"
            label={t("settings.expenses.policy.escalation_hours", "Escalate pending approvals after hours")}
            value={settings.policy.escalation_after_hours}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                policy: { ...prev.policy, escalation_after_hours: numericValue(event.target.value) },
              }))
            }
          />
          <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
            <Label>{t("settings.expenses.policy.require_rejection_comment", "Require comment on rejection")}</Label>
            <Switch
              checked={settings.policy.require_rejection_comment}
              onCheckedChange={(checked) =>
                setSettings((prev) => ({ ...prev, policy: { ...prev.policy, require_rejection_comment: checked } }))
              }
            />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t("settings.expenses.validation.title", "Validation & Compliance")}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ProfessionalInput
              type="number"
              label={t("settings.expenses.validation.receipt_over", "Receipt required over amount")}
              value={settings.validation.receipt_required_over_amount}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  validation: {
                    ...prev.validation,
                    receipt_required_over_amount: numericValue(event.target.value),
                  },
                }))
              }
            />
            <ProfessionalInput
              type="number"
              label={t("settings.expenses.validation.daily_limit", "Daily limit per category")}
              value={settings.validation.daily_limit_per_category}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  validation: { ...prev.validation, daily_limit_per_category: numericValue(event.target.value) },
                }))
              }
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
            <Label>{t("settings.expenses.validation.allowed_categories_only", "Restrict to allowed categories")}</Label>
            <Switch
              checked={settings.validation.enforce_allowed_categories}
              onCheckedChange={(checked) =>
                setSettings((prev) => ({
                  ...prev,
                  validation: { ...prev.validation, enforce_allowed_categories: checked },
                }))
              }
            />
          </div>
          <ProfessionalTextarea
            label={t("settings.expenses.validation.allowed_categories", "Allowed categories (comma-separated)")}
            value={settings.validation.allowed_categories}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                validation: { ...prev.validation, allowed_categories: event.target.value },
              }))
            }
            rows={3}
            placeholder="Travel, Meals, Software, Office Supplies"
            disabled={!settings.validation.enforce_allowed_categories}
          />
          <div className="space-y-2">
            <Label>{t("settings.expenses.validation.duplicate_detection", "Duplicate detection mode")}</Label>
            <Select
              value={settings.validation.duplicate_detection}
              onValueChange={(value: DuplicateDetection) =>
                setSettings((prev) => ({
                  ...prev,
                  validation: { ...prev.validation, duplicate_detection: value },
                }))
              }
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="off">{t("settings.expenses.validation.off", "Off")}</SelectItem>
                <SelectItem value="warn">{t("settings.expenses.validation.warn", "Warn")}</SelectItem>
                <SelectItem value="block">{t("settings.expenses.validation.block", "Block")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t("settings.expenses.defaults.title", "Defaults")}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="grid gap-4 md:grid-cols-2">
          <ProfessionalInput
            label={t("settings.expenses.defaults.currency", "Default currency")}
            value={settings.defaults.currency}
            onChange={(event) =>
              setSettings((prev) => ({ ...prev, defaults: { ...prev.defaults, currency: event.target.value } }))
            }
          />
          <ProfessionalInput
            type="number"
            label={t("settings.expenses.defaults.tax_rate", "Default tax rate (%)")}
            value={settings.defaults.tax_rate}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                defaults: { ...prev.defaults, tax_rate: numericValue(event.target.value) },
              }))
            }
          />
          <ProfessionalInput
            label={t("settings.expenses.defaults.payment_method", "Default payment method")}
            value={settings.defaults.payment_method}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                defaults: { ...prev.defaults, payment_method: event.target.value },
              }))
            }
          />
          <ProfessionalInput
            label={t("settings.expenses.defaults.project", "Default project")}
            value={settings.defaults.default_project}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                defaults: { ...prev.defaults, default_project: event.target.value },
              }))
            }
          />
          <ProfessionalInput
            label={t("settings.expenses.defaults.category", "Default category")}
            value={settings.defaults.default_category}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                defaults: { ...prev.defaults, default_category: event.target.value },
              }))
            }
          />
          <ProfessionalInput
            label={t("settings.expenses.defaults.tags", "Default tags (comma-separated)")}
            value={settings.defaults.default_tags}
            onChange={(event) =>
              setSettings((prev) => ({
                ...prev,
                defaults: { ...prev.defaults, default_tags: event.target.value },
              }))
            }
          />
          <div className="flex items-center justify-between rounded-lg border border-border/40 p-3 md:col-span-2">
            <Label>{t("settings.expenses.defaults.reimbursable", "Reimbursable by default")}</Label>
            <Switch
              checked={settings.defaults.reimbursable_default}
              onCheckedChange={(checked) =>
                setSettings((prev) => ({
                  ...prev,
                  defaults: { ...prev.defaults, reimbursable_default: checked },
                }))
              }
            />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>{t("settings.expenses.submission.title", "Submission & Notifications")}</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ProfessionalInput
              type="number"
              label={t("settings.expenses.submission.window_days", "Submission window (days)")}
              value={settings.submission.submission_window_days}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  submission: { ...prev.submission, submission_window_days: numericValue(event.target.value) },
                }))
              }
            />
            <div className="space-y-2">
              <Label>{t("settings.expenses.notifications.pending_reminder", "Pending approval reminder cadence")}</Label>
              <Select
                value={settings.notifications.pending_approval_reminder}
                onValueChange={(value: ReminderFrequency) =>
                  setSettings((prev) => ({
                    ...prev,
                    notifications: { ...prev.notifications, pending_approval_reminder: value },
                  }))
                }
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="off">{t("settings.expenses.notifications.off", "Off")}</SelectItem>
                  <SelectItem value="daily">{t("common.daily", "Daily")}</SelectItem>
                  <SelectItem value="every_2_days">
                    {t("settings.expenses.notifications.every_2_days", "Every 2 days")}
                  </SelectItem>
                  <SelectItem value="weekly">{t("common.weekly", "Weekly")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.submission.lock_after_close", "Lock edits after month close")}</Label>
              <Switch
                checked={settings.submission.lock_after_month_close}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    submission: { ...prev.submission, lock_after_month_close: checked },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.submission.require_fields", "Require mandatory fields before submit")}</Label>
              <Switch
                checked={settings.submission.require_fields_before_submit}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    submission: { ...prev.submission, require_fields_before_submit: checked },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.submission.allow_edit_after_approval", "Allow edit after approval")}</Label>
              <Switch
                checked={settings.submission.allow_edit_after_approval}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    submission: { ...prev.submission, allow_edit_after_approval: checked },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.notifications.manager_on_submit", "Notify manager on submission")}</Label>
              <Switch
                checked={settings.notifications.notify_manager_on_submission}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    notifications: { ...prev.notifications, notify_manager_on_submission: checked },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.notifications.employee_on_approval", "Notify employee on approval")}</Label>
              <Switch
                checked={settings.notifications.notify_employee_on_approval}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    notifications: { ...prev.notifications, notify_employee_on_approval: checked },
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <Label>{t("settings.expenses.notifications.employee_on_rejection", "Notify employee on rejection")}</Label>
              <Switch
                checked={settings.notifications.notify_employee_on_rejection}
                onCheckedChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    notifications: { ...prev.notifications, notify_employee_on_rejection: checked },
                  }))
                }
              />
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <div className="flex justify-end">
        <ProfessionalButton
          onClick={() => testDigestMutation.mutate()}
          disabled={isLoading || isOrganizationSettingsLoading || saveMutation.isPending || testDigestMutation.isPending}
          variant="outline"
          className="mr-2"
        >
          {testDigestMutation.isPending
            ? t("settings.sending", "Sending...")
            : t("settings.expenses.digest.send_test", "Send Test Digest")}
        </ProfessionalButton>
        <ProfessionalButton
          onClick={() => saveMutation.mutate(settings)}
          disabled={isLoading || isOrganizationSettingsLoading || saveMutation.isPending || testDigestMutation.isPending}
        >
          <Save className="mr-2 h-4 w-4" />
          {saveMutation.isPending
            ? t("settings.saving", "Saving...")
            : t("settings.save_changes", "Save Changes")}
        </ProfessionalButton>
      </div>
    </div>
  );
};
