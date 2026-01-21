import { useState, useEffect } from 'react';
import { currencyApi } from '@/lib/api';

// Shared cache for currency data to prevent duplicate API calls
const currencyCache = {
  data: null as any,
  isLoading: false,
  promise: null as Promise<any> | null,
  lastFetch: 0,
  CACHE_DURATION: 5 * 60 * 1000, // 5 minutes
  listeners: new Set<() => void>(),
};

const fetchCurrenciesWithCache = async (forceRefresh = false) => {
  // Return cached data if still valid (unless force refresh)
  if (!forceRefresh && currencyCache.data && (Date.now() - currencyCache.lastFetch) < currencyCache.CACHE_DURATION) {
    return currencyCache.data;
  }

  // If already loading, return the existing promise
  if (currencyCache.isLoading && currencyCache.promise) {
    return currencyCache.promise;
  }

  // Start new fetch
  currencyCache.isLoading = true;
  currencyCache.promise = currencyApi.getSupportedCurrencies();
  
  try {
    const data = await currencyCache.promise;
    currencyCache.data = data;
    currencyCache.lastFetch = Date.now();
    return data;
  } finally {
    currencyCache.isLoading = false;
    currencyCache.promise = null;
  }
};

export const useCurrencyCache = () => {
  const [currencies, setCurrencies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCurrencies = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCurrenciesWithCache();
        setCurrencies(data || []);
      } catch (err) {
        setError('Failed to fetch currencies');
        console.error('Failed to fetch currencies:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCurrencies();
  }, []);

  return { currencies, loading, error, refetch: fetchCurrenciesWithCache };
};

// Export the cache function for direct use in components
export { fetchCurrenciesWithCache };
