import React from "react";
import { CurrencyManager } from "@/components/ui/currency-manager";
import { Activity } from "lucide-react";
import { useTranslation } from "react-i18next";

interface CurrenciesTabProps {
    isAdmin: boolean;
}

export const CurrenciesTab: React.FC<CurrenciesTabProps> = ({ isAdmin }) => {
    const { t } = useTranslation();
    return (
        <div className="space-y-6">
            {/* Gradient Banner */}
            <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 backdrop-blur-sm">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Activity className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">{t('settings.tabs.currencies', 'Currencies')}</h2>
                        <p className="text-muted-foreground mt-0.5">{t('settings.currencies.description', 'Manage supported currencies and exchange rates')}</p>
                    </div>
                </div>
            </div>
            <CurrencyManager />
        </div>
    );
};
