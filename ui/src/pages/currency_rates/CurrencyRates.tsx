/**
 * Currency Rates Page
 *
 * A sample plugin page that demonstrates:
 *  1. Calling a plugin API endpoint from the frontend
 *  2. Using a 3rd-party external service (open.er-api.com) via the backend
 *  3. Showing the user whether data is live or from a static fallback
 *  4. A simple currency conversion calculator
 *
 * How the data flow works
 * -----------------------
 *
 *   [Browser]
 *      │  GET /api/v1/currency-rates?base=USD
 *      ▼
 *   [Plugin Router — api/plugins/currency_rates/router.py]
 *      │  1. Check module-level cache (1 h TTL)
 *      │  2. If stale → fetch https://open.er-api.com/v6/latest/USD
 *      │  3. If fetch fails → use FALLBACK_RATES (hardcoded static dict)
 *      ▼
 *   [Response JSON]
 *      { base, source: "live"|"fallback", fetched_at, rates: {...} }
 *      │
 *      ▼
 *   [This page — renders conversion calculator & source badge]
 *
 * Why go via the backend instead of calling the API directly from the browser?
 * ---------------------------------------------------------------------------
 *  • CORS: open.er-api.com doesn't allow arbitrary browser origins.
 *  • Caching: one server-side cache entry serves all users; avoids hammering
 *    the free tier rate limit (1,500 req/month).
 *  • Security: keeps the API URL and any future API key server-side.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { apiRequest } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Wifi, WifiOff, ArrowRight, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RatesResponse {
  base: string;
  source: 'live' | 'fallback';
  fetched_at: number;
  rates: Record<string, number>;
}

const COMMON_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'HKD', 'SGD', 'INR', 'BRL'];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CurrencyRates: React.FC = () => {
  const [data, setData] = useState<RatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [base, setBase] = useState('USD');
  const [amount, setAmount] = useState<number>(100);
  const [targetCurrency, setTargetCurrency] = useState('EUR');

  const fetchRates = useCallback(async (baseCurrency: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiRequest<RatesResponse>(
        `/currency-rates?base=${baseCurrency}`,
        { method: 'GET' }
      );
      setData(result);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to fetch rates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRates(base);
  }, [base, fetchRates]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------
  const rate = data?.rates?.[targetCurrency] ?? null;
  const converted = rate !== null ? (amount * rate).toFixed(4) : null;

  const fetchedAt = data?.fetched_at
    ? data.fetched_at > 0
      ? new Date(data.fetched_at * 1000).toLocaleString()
      : 'Static fallback'
    : null;

  const availableCurrencies = data
    ? [...new Set([...COMMON_CURRENCIES, ...Object.keys(data.rates)])].sort()
    : COMMON_CURRENCIES;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <TooltipProvider>
      <div className="max-w-3xl mx-auto p-6 space-y-6">

        {/* ── Header ── */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Currency Rates</h1>
          <p className="text-muted-foreground mt-1">
            Live exchange rates for invoicing in multiple currencies.
          </p>
        </div>

        {/* ── How it works ── */}
        <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/40">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-blue-800 dark:text-blue-300">
              <Info className="h-4 w-4" />
              How this plugin works
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-blue-700 dark:text-blue-400 space-y-2">
            <p>
              This is a <strong>sample plugin</strong> that demonstrates how YourFinanceWORKS plugins
              can integrate with third-party services.
            </p>
            <ol className="list-decimal list-inside space-y-1 ml-1">
              <li>
                Your browser calls <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">/api/v1/currency-rates</code> on <em>this server</em> — not the external API directly.
              </li>
              <li>
                The plugin's backend checks a <strong>1-hour server-side cache</strong>. If stale, it
                fetches fresh rates from{' '}
                <a href="https://open.er-api.com" target="_blank" rel="noopener noreferrer"
                   className="underline hover:no-underline">open.er-api.com</a>{' '}
                (free, no API key).
              </li>
              <li>
                If the external service is <strong>unreachable</strong>, the plugin automatically
                falls back to a set of hardcoded static rates so you're never left with a broken page.
              </li>
              <li>
                The <strong>source badge</strong> below always tells you whether you're seeing live
                or fallback data.
              </li>
            </ol>
            <p className="text-xs mt-2 opacity-75">
              This proxy pattern keeps external API calls server-side: it avoids browser CORS issues,
              protects any future API keys, and reduces calls against free-tier rate limits.
            </p>
          </CardContent>
        </Card>

        {/* ── Status bar ── */}
        {data && (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {data.source === 'live' ? (
              <Badge variant="outline" className="text-green-600 border-green-300 gap-1">
                <Wifi className="h-3 w-3" /> Live rates
              </Badge>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="outline" className="text-yellow-600 border-yellow-300 gap-1 cursor-help">
                    <WifiOff className="h-3 w-3" /> Fallback rates
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  The live API was unreachable. Showing approximate static rates.
                </TooltipContent>
              </Tooltip>
            )}
            {fetchedAt && <span className="text-xs">Updated: {fetchedAt}</span>}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-7 gap-1 text-xs"
              onClick={() => fetchRates(base)}
              disabled={loading}
            >
              <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded p-3">{error}</p>
        )}

        {/* ── Converter ── */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Converter</CardTitle>
            <CardDescription>Enter an amount and pick currencies to convert.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">

              {/* From */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground font-medium">From</label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    min={0}
                    value={amount}
                    onChange={e => setAmount(parseFloat(e.target.value) || 0)}
                    className="w-28"
                  />
                  <Select value={base} onValueChange={setBase}>
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {availableCurrencies.map(c => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <ArrowRight className="h-4 w-4 text-muted-foreground mt-5" />

              {/* To */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground font-medium">To</label>
                <div className="flex gap-2">
                  <div className="w-28 flex items-center px-3 rounded-md border bg-muted font-mono text-sm">
                    {loading ? '…' : (converted ?? '—')}
                  </div>
                  <Select value={targetCurrency} onValueChange={setTargetCurrency}>
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {availableCurrencies.map(c => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {rate !== null && (
              <p className="text-xs text-muted-foreground">
                1 {base} = {rate} {targetCurrency}
              </p>
            )}
          </CardContent>
        </Card>

        {/* ── Rate table ── */}
        {data && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Common rates (base: {data.base})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {COMMON_CURRENCIES.filter(c => c !== data.base && data.rates[c]).map(c => (
                  <div key={c} className="flex justify-between items-center px-3 py-2 rounded-md bg-muted/50 text-sm">
                    <span className="font-medium">{c}</span>
                    <span className="font-mono text-muted-foreground">{data.rates[c]?.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  );
};

export default CurrencyRates;
