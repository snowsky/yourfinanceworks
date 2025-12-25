import React, { useState, useEffect } from 'react';
import { fetchCurrenciesWithCache } from '@/hooks/useCurrencyCache';
import { AlertTriangle } from 'lucide-react';

interface CurrencyDisplayProps {
  amount: number;
  currency: string;
  className?: string;
  showCode?: boolean;
}

interface CurrencyInfo {
  symbol: string;
  decimals: number;
  is_active?: boolean;
}

// Common currency symbols (fallback)
const fallbackCurrencySymbols: { [key: string]: { symbol: string; decimals: number } } = {
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
  amount = 0,
  currency = 'USD',
  className = "",
  showCode = false
}: CurrencyDisplayProps) {
  const [currencyInfo, setCurrencyInfo] = useState<CurrencyInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [isInactive, setIsInactive] = useState(false);
  const safeCurrency = (currency && typeof currency === 'string') ? currency : 'USD';

  useEffect(() => {
    const fetchCurrencyInfo = async () => {
      try {
        const response = await fetchCurrenciesWithCache();
        const currencies = response.currencies || [];
        const foundCurrency = currencies.find(c => c.code === safeCurrency.toUpperCase());

        if (foundCurrency) {
          setCurrencyInfo({
            symbol: foundCurrency.symbol,
            decimals: foundCurrency.decimal_places,
            is_active: foundCurrency.is_active
          });
          setIsInactive(!foundCurrency.is_active);
        } else {
          // Use fallback for traditional currencies
          const fallback = fallbackCurrencySymbols[safeCurrency.toUpperCase()];
          setCurrencyInfo(fallback || { symbol: safeCurrency, decimals: 2, is_active: true });
          setIsInactive(false);
        }
      } catch (error) {
        console.error('Failed to fetch currency info:', error);
        // Use fallback
        const fallback = fallbackCurrencySymbols[safeCurrency.toUpperCase()];
        setCurrencyInfo(fallback || { symbol: safeCurrency, decimals: 2, is_active: true });
        setIsInactive(false);
      } finally {
        setLoading(false);
      }
    };

    fetchCurrencyInfo();
  }, [safeCurrency]);

  const formatCurrency = (amount: number = 0, currencyCode: string = 'USD') => {
    // Ensure we have a valid string
    const safeCurrencyCode = (currencyCode && typeof currencyCode === 'string') ? currencyCode : 'USD';

    if (loading || !currencyInfo) {
      // Show loading state or fallback
      const fallback = fallbackCurrencySymbols[safeCurrencyCode.toUpperCase()];
      const info = fallback || { symbol: safeCurrencyCode, decimals: 2 };
      const formattedAmount = amount.toFixed(info.decimals);
      return `${info.symbol}${formattedAmount}`;
    }

    const formattedAmount = amount.toFixed(currencyInfo.decimals);
    const symbol = currencyInfo.symbol;

    if (showCode) {
      return `${symbol}${formattedAmount} ${safeCurrencyCode}`;
    }
    return `${symbol}${formattedAmount}`;
  };

  return (
    <span className={`${className} ${isInactive ? 'text-orange-600' : ''}`}>
      {formatCurrency(amount, safeCurrency)}
      {isInactive && (
        <span title="This currency is inactive">
          <AlertTriangle className="inline h-3 w-3 ml-1 text-orange-500" />
        </span>
      )}
    </span>
  );
}

export default CurrencyDisplay; 