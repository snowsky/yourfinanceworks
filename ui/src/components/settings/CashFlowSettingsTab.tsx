import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Database, FileText, Landmark, Save, ShieldAlert } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { cashflowApi, type CashFlowThresholdSettings } from "@/lib/api/cashflow";
import { getErrorMessage } from "@/lib/api";
import { FeatureGate } from "@/components/FeatureGate";
import { useFeatures } from "@/contexts/FeatureContext";

const defaultCashFlowSettings: CashFlowThresholdSettings = {
  safety_threshold: 10000,
  warning_threshold: 25000,
  currency: "USD",
  include_outstanding_invoices: true,
  include_recurring_invoices: true,
  include_upcoming_expenses: true,
  include_historical_averages: true,
  include_bank_statement_patterns: true,
  bank_statement_lookback_days: 120,
  bank_statement_min_occurrences: 2,
  bank_statement_intervals: [7, 14, 30, 90],
  bank_statement_inflow_categories: [],
  bank_statement_outflow_categories: [],
};

const intervalOptions = [
  { value: 7, label: "Weekly" },
  { value: 14, label: "Biweekly" },
  { value: 30, label: "Monthly" },
  { value: 90, label: "Quarterly" },
];

const normalizeSettings = (value: CashFlowThresholdSettings | undefined): CashFlowThresholdSettings => ({
  ...defaultCashFlowSettings,
  ...(value ?? {}),
  bank_statement_intervals:
    value?.bank_statement_intervals?.length ? value.bank_statement_intervals : defaultCashFlowSettings.bank_statement_intervals,
  bank_statement_inflow_categories: value?.bank_statement_inflow_categories ?? [],
  bank_statement_outflow_categories: value?.bank_statement_outflow_categories ?? [],
});

const parseCategoryList = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const formatCategoryList = (value: string[]): string => value.join(", ");

export const CashFlowSettingsTab: React.FC = () => {
  const queryClient = useQueryClient();
  const { isFeatureEnabled } = useFeatures();
  const cashflowEnabled = isFeatureEnabled("cash_flow");
  const [settings, setSettings] = useState<CashFlowThresholdSettings>(defaultCashFlowSettings);
  const [inflowCategories, setInflowCategories] = useState("");
  const [outflowCategories, setOutflowCategories] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["cashflow-settings"],
    queryFn: () => cashflowApi.getThresholds(),
    enabled: cashflowEnabled,
  });

  useEffect(() => {
    if (!data) return;
    const normalized = normalizeSettings(data);
    setSettings(normalized);
    setInflowCategories(formatCategoryList(normalized.bank_statement_inflow_categories));
    setOutflowCategories(formatCategoryList(normalized.bank_statement_outflow_categories));
  }, [data]);

  const enabledSources = useMemo(
    () =>
      [
        settings.include_outstanding_invoices,
        settings.include_recurring_invoices,
        settings.include_upcoming_expenses,
        settings.include_historical_averages,
        settings.include_bank_statement_patterns,
      ].filter(Boolean).length,
    [settings]
  );

  const saveMutation = useMutation({
    mutationFn: (nextSettings: CashFlowThresholdSettings) =>
      cashflowApi.updateThresholds({
        ...nextSettings,
        bank_statement_inflow_categories: parseCategoryList(inflowCategories),
        bank_statement_outflow_categories: parseCategoryList(outflowCategories),
      }),
    onSuccess: (saved) => {
      const normalized = normalizeSettings(saved);
      setSettings(normalized);
      setInflowCategories(formatCategoryList(normalized.bank_statement_inflow_categories));
      setOutflowCategories(formatCategoryList(normalized.bank_statement_outflow_categories));
      queryClient.invalidateQueries({ queryKey: ["cashflow-settings"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow-forecast"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow-runway"] });
      queryClient.invalidateQueries({ queryKey: ["cashflow-alerts"] });
      toast.success("Cash flow settings saved");
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const updateSetting = <K extends keyof CashFlowThresholdSettings>(
    key: K,
    value: CashFlowThresholdSettings[K]
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const toggleInterval = (interval: number, checked: boolean) => {
    const current = new Set(settings.bank_statement_intervals);
    if (checked) current.add(interval);
    if (!checked && current.size > 1) current.delete(interval);
    updateSetting("bank_statement_intervals", Array.from(current).sort((a, b) => a - b));
  };

  return (
    <FeatureGate
      feature="cash_flow"
      showUpgradePrompt={true}
      upgradeMessage="Cash Flow settings require a commercial license."
      showExpiredContent={false}
    >
      <div className="space-y-5">
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="space-y-2">
              <ProfessionalCardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-primary" />
                Cash Flow Projection
              </ProfessionalCardTitle>
              <ProfessionalCardDescription>
                Choose which records contribute to projections and how bank statement transaction patterns are detected.
              </ProfessionalCardDescription>
            </div>
            <Badge variant="secondary">{enabledSources} sources enabled</Badge>
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="cashflow-safety">Safety threshold</Label>
              <ProfessionalInput
                id="cashflow-safety"
                type="number"
                min={0}
                value={settings.safety_threshold}
                onChange={(event) => updateSetting("safety_threshold", Number(event.target.value))}
                disabled={isLoading || saveMutation.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cashflow-warning">Warning threshold</Label>
              <ProfessionalInput
                id="cashflow-warning"
                type="number"
                min={0}
                value={settings.warning_threshold}
                onChange={(event) => updateSetting("warning_threshold", Number(event.target.value))}
                disabled={isLoading || saveMutation.isPending}
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <SourceToggle
              icon={<FileText className="h-4 w-4" />}
              title="Outstanding invoices"
              description="Open sent, pending, overdue, and partially paid invoices due in the forecast window."
              checked={settings.include_outstanding_invoices}
              onCheckedChange={(checked) => updateSetting("include_outstanding_invoices", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
            <SourceToggle
              icon={<FileText className="h-4 w-4" />}
              title="Recurring invoices"
              description="Future invoice occurrences projected from recurring invoice schedules."
              checked={settings.include_recurring_invoices}
              onCheckedChange={(checked) => updateSetting("include_recurring_invoices", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
            <SourceToggle
              icon={<ShieldAlert className="h-4 w-4" />}
              title="Upcoming expenses"
              description="Future-dated expenses recorded in the app."
              checked={settings.include_upcoming_expenses}
              onCheckedChange={(checked) => updateSetting("include_upcoming_expenses", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
            <SourceToggle
              icon={<Database className="h-4 w-4" />}
              title="Historical averages"
              description="Low-confidence projections from average payments and expenses when concrete entries are sparse."
              checked={settings.include_historical_averages}
              onCheckedChange={(checked) => updateSetting("include_historical_averages", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
            <SourceToggle
              icon={<Landmark className="h-4 w-4" />}
              title="Bank statement patterns"
              description="Recurring debits and credits such as mortgage, utilities, insurance, salary, and similar categories."
              checked={settings.include_bank_statement_patterns}
              onCheckedChange={(checked) => updateSetting("include_bank_statement_patterns", checked)}
              disabled={isLoading || saveMutation.isPending}
            />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <Landmark className="h-5 w-5 text-primary" />
            Bank Statement Pattern Rules
          </ProfessionalCardTitle>
          <ProfessionalCardDescription>
            Leave category lists empty to include every detected recurring bank statement category.
          </ProfessionalCardDescription>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="cashflow-min-occurrences">Minimum matching transactions</Label>
              <ProfessionalInput
                id="cashflow-min-occurrences"
                type="number"
                min={2}
                max={12}
                value={settings.bank_statement_min_occurrences}
                onChange={(event) => updateSetting("bank_statement_min_occurrences", Number(event.target.value))}
                disabled={isLoading || saveMutation.isPending || !settings.include_bank_statement_patterns}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Recurring intervals</Label>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {intervalOptions.map((option) => (
                <label key={option.value} className="flex items-center gap-2 rounded border p-3 text-sm">
                  <Checkbox
                    checked={settings.bank_statement_intervals.includes(option.value)}
                    onCheckedChange={(checked) => toggleInterval(option.value, checked === true)}
                    disabled={isLoading || saveMutation.isPending || !settings.include_bank_statement_patterns}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="cashflow-inflow-categories">Credit categories to include</Label>
              <ProfessionalInput
                id="cashflow-inflow-categories"
                value={inflowCategories}
                onChange={(event) => setInflowCategories(event.target.value)}
                placeholder="Salary, Interest, Refund"
                disabled={isLoading || saveMutation.isPending || !settings.include_bank_statement_patterns}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cashflow-outflow-categories">Debit categories to include</Label>
              <ProfessionalInput
                id="cashflow-outflow-categories"
                value={outflowCategories}
                onChange={(event) => setOutflowCategories(event.target.value)}
                placeholder="Mortgage, Utilities, Insurance"
                disabled={isLoading || saveMutation.isPending || !settings.include_bank_statement_patterns}
              />
            </div>
          </div>

          <div className="flex justify-end">
            <ProfessionalButton
              onClick={() => saveMutation.mutate(settings)}
              disabled={isLoading || saveMutation.isPending}
              className="gap-2"
            >
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? "Saving..." : "Save Cash Flow Settings"}
            </ProfessionalButton>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
      </div>
    </FeatureGate>
  );
};

const SourceToggle: React.FC<{
  icon: React.ReactNode;
  title: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}> = ({ icon, title, description, checked, disabled, onCheckedChange }) => (
  <div className="rounded-xl border border-border/50 bg-muted/20 p-4">
    <div className="flex items-start justify-between gap-4">
      <div className="flex gap-3">
        <div className="mt-0.5 text-primary">{icon}</div>
        <div className="space-y-1">
          <p className="font-medium text-foreground">{title}</p>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  </div>
);

export default CashFlowSettingsTab;
