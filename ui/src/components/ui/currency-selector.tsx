import React, { useEffect, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { Label } from './label';

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
}

// Fallback currencies that will always be available
const FALLBACK_CURRENCIES: Currency[] = [
  { id: 1, code: 'USD', name: 'US Dollar', symbol: '$', decimal_places: 2, is_active: true },
  { id: 2, code: 'EUR', name: 'Euro', symbol: '€', decimal_places: 2, is_active: true },
  { id: 3, code: 'GBP', name: 'British Pound', symbol: '£', decimal_places: 2, is_active: true },
  { id: 4, code: 'CAD', name: 'Canadian Dollar', symbol: 'C$', decimal_places: 2, is_active: true },
  { id: 5, code: 'AUD', name: 'Australian Dollar', symbol: 'A$', decimal_places: 2, is_active: true },
  { id: 6, code: 'JPY', name: 'Japanese Yen', symbol: '¥', decimal_places: 0, is_active: true }
];

export function CurrencySelector({
  value,
  onValueChange,
  label = "Currency",
  placeholder = "Select currency",
  disabled = false,
  className = ""
}: CurrencySelectorProps) {
  const [currencies, setCurrencies] = useState<Currency[]>(FALLBACK_CURRENCIES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

  useEffect(() => {
    fetchCurrencies();
  }, []);

  const fetchCurrencies = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        console.log('No auth token, using fallback currencies');
        setUsingFallback(true);
        setLoading(false);
        return;
      }

      console.log('Fetching currencies from API...');
      const response = await fetch('/api/currency/supported', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('Currency API response:', data);
      
      if (data.currencies && data.currencies.length > 0) {
        setCurrencies(data.currencies);
        setUsingFallback(false);
        console.log('Successfully loaded currencies from API');
      } else {
        console.log('API returned empty currencies, using fallback');
        setUsingFallback(true);
      }
    } catch (err) {
      console.error('Error fetching currencies:', err);
      setError(`Failed to load currencies: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setUsingFallback(true);
      console.log('Using fallback currencies due to error');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (currency: Currency) => {
    return `${currency.code} - ${currency.name} (${currency.symbol})`;
  };

  if (loading) {
    return (
      <div className={className}>
        <Select disabled>
          <SelectTrigger>
            <SelectValue placeholder="Loading currencies..." />
          </SelectTrigger>
        </Select>
      </div>
    );
  }

  return (
    <div className={className}>
      <Select value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {currencies.map((currency) => (
            <SelectItem key={currency.code} value={currency.code}>
              {formatCurrency(currency)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {usingFallback && (
        <div className="text-xs text-yellow-600 mt-1">
          Using default currencies (API not available)
        </div>
      )}
      {error && (
        <div className="text-xs text-red-600 mt-1">
          {error}
        </div>
      )}
    </div>
  );
}

export default CurrencySelector; 