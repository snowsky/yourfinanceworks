import React, { useEffect, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { Label } from './label';
import { currencyApi } from '@/lib/api';

interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
}

interface CurrencySelectorProps {
  value: string;
  onValueChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  onCurrenciesLoaded?: () => void;
}

const FALLBACK_CURRENCIES: Currency[] = [
  { id: 1, code: 'USD', name: 'US Dollar', symbol: '$', decimal_places: 2, is_active: true },
];

export function CurrencySelector({
  value,
  onValueChange,
  label = "Currency",
  placeholder = "Select currency",
  disabled = false,
  className = "",
  onCurrenciesLoaded,
}: CurrencySelectorProps) {
  // Handle empty/null values by using fallback - ensure we always have a value
  const effectiveValue = value || "USD";

  // Fetch currencies with React Query for better caching
  const { data: currenciesData = FALLBACK_CURRENCIES, isLoading: loading, error: apiError } = useQuery({
    queryKey: ['currencies'],
    queryFn: () => currencyApi.getSupportedCurrencies(),
    staleTime: 1000 * 60 * 30, // 30 minutes cache
    gcTime: 1000 * 60 * 60, // 1 hour garbage collection
    retry: 1,
  });

  const [error, setError] = useState<string | null>(null);
  const hasNotifiedRef = useRef(false);

  useEffect(() => {
    if (apiError) {
      setError('API unavailable - using default currencies');
    } else {
      setError(null);
    }
  }, [apiError]);

  useEffect(() => {
    if (!loading && !hasNotifiedRef.current && onCurrenciesLoaded) {
      hasNotifiedRef.current = true;
      onCurrenciesLoaded();
    }
  }, [loading, onCurrenciesLoaded]);

  const currencies = Array.isArray(currenciesData) ? currenciesData : FALLBACK_CURRENCIES;
  const activeCurrencies = currencies.filter(c => c.is_active);

  const formatCurrency = (currency: Currency) => {
    return `${currency.code} - ${currency.name} (${currency.symbol})`;
  };

  if (loading) {
    return (
      <div className={className}>
        <Select value={effectiveValue} onValueChange={onValueChange} disabled>
          <SelectTrigger>
            <SelectValue placeholder="Loading currencies..." />
          </SelectTrigger>
        </Select>
      </div>
    );
  }

  return (
    <div className={className}>
      <Select key={effectiveValue} value={effectiveValue} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger>
          <SelectValue placeholder={placeholder}>
            {effectiveValue && activeCurrencies.find(c => c.code === effectiveValue) 
              ? formatCurrency(activeCurrencies.find(c => c.code === effectiveValue)!)
              : placeholder}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {activeCurrencies.map((currency) => (
            <SelectItem key={currency.code} value={currency.code}>
              {formatCurrency(currency)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && (
        <div className="text-xs text-yellow-600 mt-1">
          {error}
        </div>
      )}
    </div>
  );
}

export default CurrencySelector;
