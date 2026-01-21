import React from "react";
import { CurrencyManager } from "@/components/ui/currency-manager";

interface CurrenciesTabProps {
    isAdmin: boolean;
}

export const CurrenciesTab: React.FC<CurrenciesTabProps> = ({ isAdmin }) => {
    return (
        <div className="space-y-6">
            <CurrencyManager />
        </div>
    );
};
