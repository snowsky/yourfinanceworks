import React from "react";
import { useTranslation } from "react-i18next";
import { Rows2, Clock, BarChart2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    ProfessionalCard,
    ProfessionalCardHeader,
    ProfessionalCardTitle,
    ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { useListDensity } from "@/hooks/use-list-density";
import { useAppearanceSettings } from "@/hooks/useAppearanceSettings";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { updateCurrentUser } from "@/utils/auth";
import { toast } from "sonner";

export const AppearanceTab: React.FC = () => {
    const { t } = useTranslation();
    const queryClient = useQueryClient();
    const { density, toggleDensity } = useListDensity();
    const { settings, update } = useAppearanceSettings();

    const { data: user } = useQuery({
        queryKey: ['currentUser'],
        queryFn: () => authApi.getCurrentUser(),
    });

    const handleShowAnalyticsChange = async (checked: boolean) => {
        try {
            await authApi.updateCurrentUser({ show_analytics: checked });
            updateCurrentUser({ show_analytics: checked });
            queryClient.invalidateQueries({ queryKey: ['currentUser'] });
        } catch {
            toast.error(t('settings.failed_to_update_profile'));
        }
    };

    return (
        <div className="space-y-6">
            {/* Tables */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Rows2 className="w-4 h-4 text-primary" />
                        {t('settings.appearance.tables', 'Tables')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="list_density" className="text-base font-semibold">
                                {t('settings.profile.compact_density', 'Compact table density')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.profile.compact_density_description', 'Show more rows by reducing table row padding.')}
                            </p>
                        </div>
                        <Switch
                            id="list_density"
                            checked={density === "compact"}
                            onCheckedChange={toggleDensity}
                        />
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Navigation */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <BarChart2 className="w-4 h-4 text-primary" />
                        {t('settings.appearance.navigation', 'Navigation')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent>
                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="show_analytics" className="text-base font-semibold">
                                {t('settings.profile.show_analytics_menu')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.profile.show_analytics_menu_description')}
                            </p>
                        </div>
                        <Switch
                            id="show_analytics"
                            checked={user?.show_analytics ?? true}
                            onCheckedChange={handleShowAnalyticsChange}
                        />
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Header Clock */}
            <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                    <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
                        <Clock className="w-4 h-4 text-primary" />
                        {t('settings.appearance.header_clock', 'Header Clock')}
                    </ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-3">
                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="show_clock" className="text-base font-semibold">
                                {t('settings.appearance.show_clock', 'Show clock')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.appearance.show_clock_description', 'Display a live clock in the top header.')}
                            </p>
                        </div>
                        <Switch
                            id="show_clock"
                            checked={settings.showClock}
                            onCheckedChange={(checked) => update({ showClock: checked })}
                        />
                    </div>

                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="show_local_clock" className="text-base font-semibold">
                                {t('settings.appearance.show_local_clock', 'Show local clock')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.appearance.show_local_clock_description', 'Display a clock in your browser\'s local timezone.')}
                            </p>
                        </div>
                        <Switch
                            id="show_local_clock"
                            checked={settings.showLocalClock}
                            disabled={!settings.showClock}
                            onCheckedChange={(checked) => update({ showLocalClock: checked })}
                        />
                    </div>

                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="show_utc_clock" className="text-base font-semibold">
                                {t('settings.appearance.show_utc_clock', 'Show UTC clock')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.appearance.show_utc_clock_description', 'Display a second clock in Coordinated Universal Time (UTC).')}
                            </p>
                        </div>
                        <Switch
                            id="show_utc_clock"
                            checked={settings.showUTCClock}
                            disabled={!settings.showClock}
                            onCheckedChange={(checked) => update({ showUTCClock: checked })}
                        />
                    </div>

                    <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="space-y-0.5">
                            <Label htmlFor="show_date" className="text-base font-semibold">
                                {t('settings.appearance.show_date', 'Show date')}
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                {t('settings.appearance.show_date_description', 'Display the current date alongside the clock.')}
                            </p>
                        </div>
                        <Switch
                            id="show_date"
                            checked={settings.showDate}
                            disabled={!settings.showClock}
                            onCheckedChange={(checked) => update({ showDate: checked })}
                        />
                    </div>
                </ProfessionalCardContent>
            </ProfessionalCard>
        </div>
    );
};
