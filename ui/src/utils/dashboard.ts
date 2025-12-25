/**
 * Dashboard utility functions
 */

// Import the shared currency cache
import { fetchCurrenciesWithCache } from '@/hooks/useCurrencyCache';

// Cache for currency symbol mappings
let currencySymbolCache: { [key: string]: string } | null = null;
let cacheTimestamp: number = 0;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

/**
 * Fetches currency symbol mappings from the API
 * @returns Promise<{ [symbol: string]: string }> - Mapping of symbols to ISO codes
 */
async function getCurrencySymbolMappings(): Promise<{ [key: string]: string }> {
  const now = Date.now();

  // Return cached data if it's still valid
  if (currencySymbolCache && (now - cacheTimestamp) < CACHE_DURATION) {
    return currencySymbolCache;
  }

  try {
    // Import the API function dynamically to avoid circular dependencies
    const currencies = await fetchCurrenciesWithCache();

    // Build symbol to code mapping from API response
    const symbolMap: { [key: string]: string } = {};
    currencies.forEach((currency: any) => {
      if (currency.symbol && currency.code) {
        symbolMap[currency.symbol] = currency.code;
      }
    });

    // Add common fallbacks if not present
    const fallbacks = {
      '$': 'USD',
      '€': 'EUR',
      '£': 'GBP',
      '¥': 'JPY',
      '₹': 'INR',
      '₽': 'RUB',
      'C$': 'CAD',
      'A$': 'AUD'
    };

    Object.entries(fallbacks).forEach(([symbol, code]) => {
      if (!symbolMap[symbol]) {
        symbolMap[symbol] = code;
      }
    });

    // Cache the result
    currencySymbolCache = symbolMap;
    cacheTimestamp = now;

    return symbolMap;
  } catch (error) {
    console.warn('Failed to fetch currency mappings from API, using fallbacks:', error);

    // Return fallback mappings if API fails
    const fallbackMap = {
      '$': 'USD',
      '€': 'EUR',
      '£': 'GBP',
      '¥': 'JPY',
      '₹': 'INR',
      '₽': 'RUB',
      'C$': 'CAD',
      'A$': 'AUD'
    };

    currencySymbolCache = fallbackMap;
    cacheTimestamp = now;

    return fallbackMap;
  }
}

/**
 * Safely formats an amount with currency, handling encrypted or invalid currency codes
 * @param amount - The numeric amount to format
 * @param currency - The currency code (e.g., 'USD', 'EUR') or symbol (e.g., '$', '€')
 * @param locale - The locale for formatting (defaults to 'en-US')
 * @returns Formatted currency string or null if amount is invalid
 */
export async function formatCurrency(amount?: number, currency?: string, locale: string = 'en-US'): Promise<string | null> {
  if (!amount || amount === 0) return null;
  if (!currency) return `${amount.toFixed(2)}`;

  // Check if currency looks like an encrypted string (base64)
  const isEncrypted = /^[A-Za-z0-9+/]+=*$/.test(currency) && currency.length > 20;

  let safeCurrency = currency;

  // If currency is encrypted, invalid, or too long, use USD as default
  if (isEncrypted || currency.length > 10) {
    console.warn(`Invalid or encrypted currency code detected: ${currency}, using USD`);
    safeCurrency = 'USD';
  }
  // If it's not a 3-letter ISO code, try to convert from symbol
  else if (!/^[A-Z]{3}$/.test(currency)) {
    try {
      const currencySymbolMap = await getCurrencySymbolMappings();
      if (currencySymbolMap[currency]) {
        safeCurrency = currencySymbolMap[currency];
      } else {
        console.warn(`Unknown currency symbol: ${currency}, using USD`);
        safeCurrency = 'USD';
      }
    } catch (error) {
      console.warn(`Failed to resolve currency symbol ${currency}, using USD:`, error);
      safeCurrency = 'USD';
    }
  }

  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: safeCurrency
    }).format(amount);
  } catch (error) {
    // If currency is still invalid, fall back to USD
    console.warn(`Failed to format currency with ${safeCurrency}, falling back to USD:`, error);
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'USD'
      }).format(amount);
    } catch (fallbackError) {
      // If even USD fails, return a simple formatted number
      console.error('Currency formatting completely failed, returning simple format:', fallbackError);
      return `$${amount.toFixed(2)}`;
    }
  }
}

/**
 * Synchronous version of formatCurrency for cases where async is not possible
 * Uses cached currency mappings or fallbacks to common symbols
 * @param amount - The numeric amount to format
 * @param currency - The currency code or symbol
 * @param locale - The locale for formatting (defaults to 'en-US')
 * @returns Formatted currency string or null if amount is invalid
 */
export function formatCurrencySync(amount?: number, currency?: string, locale: string = 'en-US'): string | null {
  if (!amount || amount === 0) return null;
  if (!currency) return `${amount.toFixed(2)}`;

  // Check if currency looks like an encrypted string (base64)
  const isEncrypted = /^[A-Za-z0-9+/]+=*$/.test(currency) && currency.length > 20;

  let safeCurrency = currency;

  // If currency is encrypted, invalid, or too long, use USD as default
  if (isEncrypted || currency.length > 10) {
    safeCurrency = 'USD';
  }
  // If it's not a 3-letter ISO code, try to convert from symbol using cached data
  else if (!/^[A-Z]{3}$/.test(currency)) {
    const fallbackMap = currencySymbolCache || {
      '$': 'USD',
      '€': 'EUR',
      '£': 'GBP',
      '¥': 'JPY',
      '₹': 'INR',
      '₽': 'RUB',
      'C$': 'CAD',
      'A$': 'AUD'
    };

    safeCurrency = fallbackMap[currency] || 'USD';
  }

  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: safeCurrency
    }).format(amount);
  } catch (error) {
    // If currency is still invalid, fall back to USD
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'USD'
      }).format(amount);
    } catch (fallbackError) {
      // If even USD fails, return a simple formatted number
      return `$${amount.toFixed(2)}`;
    }
  }
}

/**
 * Triggers a dashboard refresh event that components can listen to
 * This is useful when data is created/updated in other parts of the app
 * and the dashboard needs to refresh its data
 */
export function refreshDashboard() {
  // Dispatch a custom event that the dashboard can listen to
  window.dispatchEvent(new CustomEvent('dashboard-refresh'));
}

/**
 * Triggers a refresh of recent activity specifically
 */
export function refreshRecentActivity() {
  window.dispatchEvent(new CustomEvent('recent-activity-refresh'));
}

/**
 * Triggers a refresh of recent invoices specifically
 */
export function refreshRecentInvoices() {
  window.dispatchEvent(new CustomEvent('recent-invoices-refresh'));
}

/**
 * Triggers a refresh of dashboard stats
 */
export function refreshDashboardStats() {
  window.dispatchEvent(new CustomEvent('dashboard-stats-refresh'));
}
/**
 * 
Helper functions to log activities and trigger dashboard refresh
 * These can be called from other parts of the app when actions are performed
 */

/**
 * Log a new invoice creation and refresh dashboard
 */
export function logInvoiceActivity(invoiceNumber: string, clientName: string) {
  // In a real implementation, this would send the activity to the backend
  console.log(`Activity logged: Invoice ${invoiceNumber} created for ${clientName}`);
  refreshDashboard();
}

/**
 * Log a new client creation and refresh dashboard
 */
export function logClientActivity(clientName: string) {
  console.log(`Activity logged: New client ${clientName} added`);
  refreshDashboard();
}

/**
 * Log an expense approval and refresh dashboard
 */
export function logApprovalActivity(expenseType: string, amount: number, status: string) {
  console.log(`Activity logged: ${expenseType} expense ${status} for $${amount}`);
  refreshDashboard();
}

/**
 * Log a reminder sent and refresh dashboard
 */
export function logReminderActivity(type: string, target: string) {
  console.log(`Activity logged: ${type} reminder sent to ${target}`);
  refreshDashboard();
}

/**
 * Log a report generation and refresh dashboard
 */
export function logReportActivity(reportType: string, period: string) {
  console.log(`Activity logged: ${reportType} report generated for ${period}`);
  refreshDashboard();
}