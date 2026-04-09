import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { CreditCard, Save, Shield, Sparkles } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { settingsApi, type PaymentSettings } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";

const PAYMENT_SETTINGS_KEY = "payment_settings";

const defaultPaymentSettings: PaymentSettings = {
  provider: "stripe",
  stripe: {
    enabled: false,
    accountLabel: "",
    publishableKey: "",
    secretKey: "",
    webhookSecret: "",
  },
};

const normalizePaymentSettings = (value: unknown): PaymentSettings => {
  if (!value || typeof value !== "object") {
    return defaultPaymentSettings;
  }

  const raw = value as Partial<PaymentSettings>;

  return {
    provider: raw.provider === "stripe" ? "stripe" : "stripe",
    stripe: {
      ...defaultPaymentSettings.stripe,
      ...(raw.stripe ?? {}),
    },
  };
};

export const PaymentSettingsTab: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState<PaymentSettings>(defaultPaymentSettings);

  const { data, isLoading } = useQuery({
    queryKey: ["settings", PAYMENT_SETTINGS_KEY],
    queryFn: () => settingsApi.getSetting(PAYMENT_SETTINGS_KEY),
  });

  useEffect(() => {
    if (data) {
      setSettings(normalizePaymentSettings(data.value));
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (nextSettings: PaymentSettings) =>
      settingsApi.updateSetting(PAYMENT_SETTINGS_KEY, nextSettings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", PAYMENT_SETTINGS_KEY] });
      toast.success(t("settings.payment_settings.saved", "Payment settings saved successfully"));
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    },
  });

  const handleStripeChange = (field: keyof PaymentSettings["stripe"], value: string | boolean) => {
    setSettings((prev) => ({
      ...prev,
      stripe: {
        ...prev.stripe,
        [field]: value,
      },
    }));
  };

  const isConfigured = Boolean(
    settings.stripe.enabled &&
      settings.stripe.publishableKey.trim() &&
      settings.stripe.secretKey.trim()
  );

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <ProfessionalCardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-primary" />
              {t("settings.payment_settings.title", "Payment")}
            </ProfessionalCardTitle>
            <ProfessionalCardDescription>
              {t(
                "settings.payment_settings.description",
                "Configure Stripe so your team can track Stripe activity from the Payments page."
              )}
            </ProfessionalCardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={isConfigured ? "default" : "outline"} className="gap-1">
              <Shield className="h-3.5 w-3.5" />
              {isConfigured
                ? t("settings.payment_settings.configured", "Configured")
                : t("settings.payment_settings.not_configured", "Not configured")}
            </Badge>
          </div>
        </div>
      </ProfessionalCardHeader>

      <ProfessionalCardContent className="space-y-6">
        <div className="rounded-xl border border-border/50 bg-muted/20 p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="font-medium text-foreground">
                {t("settings.payment_settings.enable_stripe", "Enable Stripe")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t(
                  "settings.payment_settings.enable_stripe_description",
                  "Turn on Stripe for this organization. Recent Stripe payments will appear in Payments."
                )}
              </p>
            </div>
            <Switch
              checked={settings.stripe.enabled}
              onCheckedChange={(checked) => handleStripeChange("enabled", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="stripe-account-label">
              {t("settings.payment_settings.account_label", "Account Label")}
            </Label>
            <ProfessionalInput
              id="stripe-account-label"
              value={settings.stripe.accountLabel}
              onChange={(event) => handleStripeChange("accountLabel", event.target.value)}
              placeholder={t(
                "settings.payment_settings.account_label_placeholder",
                "Main Stripe account"
              )}
              disabled={isLoading || saveMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-publishable-key">
              {t("settings.payment_settings.publishable_key", "Publishable Key")}
            </Label>
            <ProfessionalInput
              id="stripe-publishable-key"
              value={settings.stripe.publishableKey}
              onChange={(event) => handleStripeChange("publishableKey", event.target.value)}
              placeholder="pk_live_..."
              disabled={isLoading || saveMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-secret-key">
              {t("settings.payment_settings.secret_key", "Secret Key")}
            </Label>
            <ProfessionalInput
              id="stripe-secret-key"
              type="password"
              value={settings.stripe.secretKey}
              onChange={(event) => handleStripeChange("secretKey", event.target.value)}
              placeholder="sk_live_..."
              disabled={isLoading || saveMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="stripe-webhook-secret">
              {t("settings.payment_settings.webhook_secret", "Webhook Secret")}
            </Label>
            <ProfessionalInput
              id="stripe-webhook-secret"
              type="password"
              value={settings.stripe.webhookSecret}
              onChange={(event) => handleStripeChange("webhookSecret", event.target.value)}
              placeholder="whsec_..."
              disabled={isLoading || saveMutation.isPending}
            />
          </div>
        </div>

        <div className="flex justify-end">
          <ProfessionalButton
            onClick={() => saveMutation.mutate(settings)}
            disabled={isLoading || saveMutation.isPending}
          >
            <Save className="mr-2 h-4 w-4" />
            {saveMutation.isPending
              ? t("settings.saving", "Saving...")
              : t("settings.save_changes", "Save Changes")}
          </ProfessionalButton>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};
