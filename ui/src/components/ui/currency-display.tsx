import React from 'react';

interface CurrencyDisplayProps {
  amount: number;
  currency: string;
  className?: string;
  showCode?: boolean;
}

// Common currency symbols
const currencySymbols: { [key: string]: { symbol: string; decimals: number } } = {
  'USD': { symbol: '$', decimals: 2 },
  'EUR': { symbol: '€', decimals: 2 },
  'GBP': { symbol: '£', decimals: 2 },
  'CAD': { symbol: 'C$', decimals: 2 },
  'AUD': { symbol: 'A$', decimals: 2 },
  'JPY': { symbol: '¥', decimals: 0 },
  'CHF': { symbol: 'CHF', decimals: 2 },
  'CNY': { symbol: '¥', decimals: 2 },
  'INR': { symbol: '₹', decimals: 2 },
  'BRL': { symbol: 'R$', decimals: 2 }
};

export function CurrencyDisplay({ 
  amount, 
  currency, 
  className = "", 
  showCode = false 
}: CurrencyDisplayProps) {
  const formatCurrency = (amount: number, currencyCode: string) => {
    const currencyInfo = currencySymbols[currencyCode.toUpperCase()];
    
    if (currencyInfo) {
      const formattedAmount = amount.toFixed(currencyInfo.decimals);
      const symbol = currencyInfo.symbol;
      
      if (showCode) {
        return `${symbol}${formattedAmount} ${currencyCode}`;
      }
      return `${symbol}${formattedAmount}`;
    }
    
    // Fallback for unknown currencies
    const formattedAmount = amount.toFixed(2);
    return `${formattedAmount} ${currencyCode}`;
  };

  return (
    <span className={className}>
      {formatCurrency(amount, currency)}
    </span>
  );
}

export default CurrencyDisplay; 