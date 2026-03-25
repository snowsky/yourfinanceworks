import React from "react";
import { useTranslation } from "react-i18next";
import { Search, Shield, Database } from "lucide-react";
import { SearchStatus } from "@/components/search/SearchStatus";
import { FeatureGate } from "@/components/FeatureGate";
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';

interface SearchSettingsTabProps {
    isAdmin: boolean;
}

export const SearchSettingsTab: React.FC<SearchSettingsTabProps> = ({ isAdmin }) => {
    const { t } = useTranslation();
    return (
        <div className="space-y-6">
        <FeatureGate
            feature="advanced_search"
            fallback={
                <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
                    <ProfessionalCardContent className="p-12 text-center">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                            <Search className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-foreground mb-3">{t('settings.search_settings.business_license_required')}</h3>
                        <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                            {t('settings.search_settings.business_license_description')}
                        </p>
                        <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                            <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                                <Shield className="h-4 w-4 text-primary" />
                                {t('settings.search_settings.with_business_license_you_get')}
                            </h4>
                            <ul className="text-left space-y-3 text-sm text-foreground/80">
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>{t('settings.search_settings.full_text_search')}</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>{t('settings.search_settings.opensearch_integration')}</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>{t('settings.search_settings.intelligent_search_filters')}</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>{t('settings.search_settings.real_time_search_indexing')}</span>
                                </li>
                            </ul>
                        </div>
                        <div className="flex justify-center gap-4">
                            <ProfessionalButton
                                variant="gradient"
                                onClick={() => window.location.href = '/settings?tab=license'}
                                size="lg"
                            >
                                {t('settings.search_settings.activate_business_license')}
                            </ProfessionalButton>
                            <ProfessionalButton
                                variant="outline"
                                onClick={() => window.open('https://docs.example.com/advanced-search', '_blank')}
                                size="lg"
                            >
                                {t('settings.search_settings.learn_more')}
                            </ProfessionalButton>
                        </div>
                    </ProfessionalCardContent>
                </ProfessionalCard>
            }
        >
            <div className="space-y-6">
                <SearchStatus />
            </div>
        </FeatureGate>
        </div>
    );
};
