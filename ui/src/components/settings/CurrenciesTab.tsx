import React from "react";
import { CurrencyManager } from "@/components/ui/currency-manager";
interface CurrenciesTabProps {
    isAdmin: boolean;
}

export const CurrenciesTab: React.FC<CurrenciesTabProps> = () => {
    return <CurrencyManager />;
};
