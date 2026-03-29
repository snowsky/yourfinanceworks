import React from "react";
import { useTranslation } from "react-i18next";
import { Rows2, Clock } from "lucide-react";
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

export const AppearanceTab: React.FC = () => {
    const { t } = useTranslation();
    const { density, toggleDensity } = useListDensity();
    const { settings, update } = useAppearanceSettings();

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
