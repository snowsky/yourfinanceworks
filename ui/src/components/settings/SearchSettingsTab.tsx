import React from "react";
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
    return (
        <FeatureGate
            feature="advanced_search"
            fallback={
                <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
                    <ProfessionalCardContent className="p-12 text-center">
                        <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                            <Search className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-foreground mb-3">Business License Required</h3>
                        <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                            Advanced search capabilities provide powerful full-text search, intelligent filtering, and fast indexing across all your invoices and documents.
                            Upgrade to a business license to access professional search features and improve your document discovery workflow.
                        </p>
                        <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                            <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                                <Shield className="h-4 w-4 text-primary" />
                                With Business License, you get:
                            </h4>
                            <ul className="text-left space-y-3 text-sm text-foreground/80">
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Full-text search across all invoices and documents</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>OpenSearch integration with advanced indexing</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Intelligent search filters and faceted search</span>
                                </li>
                                <li className="flex items-start">
                                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                                    <span>Real-time search indexing and status monitoring</span>
                                </li>
                            </ul>
                        </div>
                        <div className="flex justify-center gap-4">
                            <ProfessionalButton
                                variant="gradient"
                                onClick={() => window.location.href = '/settings?tab=license'}
                                size="lg"
                            >
                                Activate Business License
                            </ProfessionalButton>
                            <ProfessionalButton
                                variant="outline"
                                onClick={() => window.open('https://docs.example.com/advanced-search', '_blank')}
                                size="lg"
                            >
                                Learn More
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
    );
};
