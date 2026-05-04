import React, { useEffect, useState } from "react";
import { Loader2, Share2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { settingsApi, type ShareAccessType, type SharingSettings } from "@/lib/api";

interface SharingSettingsTabProps {
  isAdmin: boolean;
}

const DEFAULT_SHARING_SETTINGS: SharingSettings = {
  default_access_type: "public",
  default_expiration_hours: 24,
  allow_public_links: true,
  allow_password_links: true,
  allow_question_links: true,
  default_one_time: false,
  require_expiration: true,
};

export const SharingSettingsTab: React.FC<SharingSettingsTabProps> = ({ isAdmin }) => {
  const queryClient = useQueryClient();
  const [sharingSettings, setSharingSettings] = useState<SharingSettings>(DEFAULT_SHARING_SETTINGS);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsApi.getSettings(),
    enabled: isAdmin,
  });

  useEffect(() => {
    if (settings?.sharing_settings) {
      setSharingSettings({ ...DEFAULT_SHARING_SETTINGS, ...settings.sharing_settings });
    }
  }, [settings]);

  const updateSettingsMutation = useMutation({
    mutationFn: (data: SharingSettings) => settingsApi.updateSettings({ sharing_settings: data }),
    onSuccess: () => {
      toast.success("Sharing settings saved");
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error) => {
      console.error("Failed to save sharing settings:", error);
      toast.error("Failed to save sharing settings");
    },
  });

  const setValue = <K extends keyof SharingSettings>(key: K, value: SharingSettings[K]) => {
    setSharingSettings((prev) => ({ ...prev, [key]: value }));
  };

  const accessOptions = [
    { value: "public" as const, label: "Anyone with link", enabled: sharingSettings.allow_public_links },
    { value: "password" as const, label: "Password", enabled: sharingSettings.allow_password_links },
    { value: "question" as const, label: "Question and answer", enabled: sharingSettings.allow_question_links },
  ];

  const handleMethodToggle = (key: keyof Pick<SharingSettings, "allow_public_links" | "allow_password_links" | "allow_question_links">, checked: boolean) => {
    const next = { ...sharingSettings, [key]: checked };
    const defaultStillAllowed =
      (next.default_access_type === "public" && next.allow_public_links) ||
      (next.default_access_type === "password" && next.allow_password_links) ||
      (next.default_access_type === "question" && next.allow_question_links);

    if (!defaultStillAllowed) {
      const fallback = accessOptions.find((option) => {
        if (option.value === "public") return key === "allow_public_links" ? checked : sharingSettings.allow_public_links;
        if (option.value === "password") return key === "allow_password_links" ? checked : sharingSettings.allow_password_links;
        return key === "allow_question_links" ? checked : sharingSettings.allow_question_links;
      });
      next.default_access_type = fallback?.value ?? "public";
      if (!fallback) {
        next.allow_public_links = true;
      }
    }
    setSharingSettings(next);
  };

  const handleSave = () => {
    if (!isAdmin) return;
    if (sharingSettings.require_expiration && sharingSettings.default_expiration_hours === 0) {
      toast.error("Default expiration is required");
      return;
    }
    updateSettingsMutation.mutate(sharingSettings);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
            <Share2 className="w-4 h-4 text-primary" />
            Share Defaults
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="space-y-6">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Default access</Label>
              <Select
                value={sharingSettings.default_access_type}
                onValueChange={(value) => setValue("default_access_type", value as ShareAccessType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {accessOptions.filter((option) => option.enabled).map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="default-expiration">Default expiration hours</Label>
              <Input
                id="default-expiration"
                type="number"
                min={sharingSettings.require_expiration ? 1 : 0}
                max={8760}
                value={sharingSettings.default_expiration_hours}
                onChange={(event) => setValue("default_expiration_hours", Number(event.target.value))}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <Label htmlFor="default-one-time">One-time by default</Label>
                <p className="text-xs text-muted-foreground">New share links default to a single successful view.</p>
              </div>
              <Switch id="default-one-time" checked={sharingSettings.default_one_time} onCheckedChange={(checked) => setValue("default_one_time", checked)} />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <Label htmlFor="require-expiration">Require expiration</Label>
                <p className="text-xs text-muted-foreground">Prevent never-expiring links from being created by default.</p>
              </div>
              <Switch id="require-expiration" checked={sharingSettings.require_expiration} onCheckedChange={(checked) => setValue("require_expiration", checked)} />
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="text-base font-semibold">Allowed Share Methods</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="allow-public">Public link</Label>
            <Switch id="allow-public" checked={sharingSettings.allow_public_links} onCheckedChange={(checked) => handleMethodToggle("allow_public_links", checked)} />
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="allow-password">Password</Label>
            <Switch id="allow-password" checked={sharingSettings.allow_password_links} onCheckedChange={(checked) => handleMethodToggle("allow_password_links", checked)} />
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <Label htmlFor="allow-question">Question and answer</Label>
            <Switch id="allow-question" checked={sharingSettings.allow_question_links} onCheckedChange={(checked) => handleMethodToggle("allow_question_links", checked)} />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <div className="flex justify-end">
        <ProfessionalButton onClick={handleSave} loading={updateSettingsMutation.isPending} variant="gradient" size="lg">
          Save Changes
        </ProfessionalButton>
      </div>
    </div>
  );
};
