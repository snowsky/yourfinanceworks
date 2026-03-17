import { API_BASE_URL, apiRequest } from './_base';

export interface InvestmentPortfolio {
  id: number;
  name: string;
  portfolio_type: string;
  description?: string;
  is_archived: boolean;
  currency: string;
  holdings_count?: number;
  total_value?: number;
  total_cost?: number;
  target_allocations?: Record<string, number>;
  created_at?: string;
  updated_at?: string;
}

export interface DeletedPortfolio extends InvestmentPortfolio {
  deleted_at?: string | null;
  deleted_by?: number | null;
  deleted_by_username?: string | null;
}

// ... rest of the code remains the same ...
export interface PortfolioListResponse {
  items: InvestmentPortfolio[];
  total: number;
}

export interface PerformanceMetrics {
  total_value: number;
  total_cost: number;
  total_gain_loss: number;
  total_return_percentage: number;
  unrealized_gain_loss: number;
  realized_gain_loss: number;
}

export interface AssetAllocation {
  total_value: number;
  allocations: {
    [key: string]: {
      value: number;
      percentage: number;
      holdings_count: number;
    };
  };
}

export interface RebalanceAction {
  asset_class: string;
  security_symbol?: string;
  action_type: 'BUY' | 'SELL';
  amount: number;
  percentage_drift: number;
}

export interface RebalanceReport {
  portfolio_id: number;
  total_value: number;
  current_allocations: Record<string, number>;
  target_allocations: Record<string, number>;
  drifts: Record<string, number>;
  recommended_actions: RebalanceAction[];
  is_balanced: boolean;
  summary: string;
}

export interface DividendSummary {
  total_dividends: number;
  dividend_transactions: any[];
  period_start: string;
  period_end: string;
}

export interface InvestmentTransaction {
  id: number;
  portfolio_id: number;
  holding_id?: number | null;
  transaction_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'INTEREST' | 'FEE' | 'DEPOSIT' | 'WITHDRAWAL' | 'TRANSFER_IN' | 'TRANSFER_OUT';
  transaction_date: string;
  quantity?: number | null;
  price_per_share?: number | null;
  total_amount: number;
  fees: number;
  realized_gain?: number | null;
  dividend_type?: string | null;
  payment_date?: string | null;
  ex_dividend_date?: string | null;
  notes?: string | null;
  created_at: string;
  security_symbol?: string;
  security_name?: string;
}


export interface AggregatedAnalytics {
  portfolio_type_filter: string;
  portfolio_count: number;
  total_value: number;
  total_cost: number;
  total_gain_loss: number;
  total_return_percentage: number;
  unrealized_gain_loss: number;
  realized_gain_loss: number;
  asset_allocation: {
    [key: string]: {
      value: number;
      percentage: number;
      holdings_count: number;
    };
  };
  dividend_income_last_12_months: number;
}

export const investmentApi = {
  list: async (params: {
    skip?: number;
    limit?: number;
    search?: string;
    portfolio_type?: string;
    label?: string;
    include_archived?: boolean;
  } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.skip !== undefined) searchParams.set('skip', params.skip.toString());
    if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
    if (params.search) searchParams.set('search', params.search);
    if (params.portfolio_type) searchParams.set('portfolio_type', params.portfolio_type);
    if (params.label) searchParams.set('label', params.label);
    if (params.include_archived !== undefined) searchParams.set('include_archived', params.include_archived.toString());

    return apiRequest<PortfolioListResponse>(`/investments/portfolios?${searchParams.toString()}`);
  },

  get: (id: number) => apiRequest<InvestmentPortfolio>(`/investments/portfolios/${id}`),

  create: (data: any) => apiRequest<InvestmentPortfolio>('/investments/portfolios', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  update: (id: number, data: any) => apiRequest<InvestmentPortfolio>(`/investments/portfolios/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),

  delete: (id: number) => apiRequest(`/investments/portfolios/${id}`, { method: 'DELETE' }),

  getDeleted: (skip: number = 0, limit: number = 10) =>
    apiRequest<PortfolioListResponse & { items: DeletedPortfolio[] }>(`/investments/portfolios/deleted?skip=${skip}&limit=${limit}`),

  restore: (id: number) => apiRequest(`/investments/portfolios/${id}/restore`, { method: 'POST' }),

  permanentDelete: (id: number) => apiRequest(`/investments/portfolios/${id}/permanent`, { method: 'DELETE' }),

  emptyRecycleBin: () => apiRequest('/investments/portfolios/recycle-bin/empty', { method: 'POST' }),

  getPerformance: (id: number) =>
    apiRequest<PerformanceMetrics>(`/investments/portfolios/${id}/performance`),

  getAssetAllocation: (portfolioId: number) =>
    apiRequest<AssetAllocation>(`/investments/portfolios/${portfolioId}/allocation`),

  getRebalanceReport: (portfolioId: number) =>
    apiRequest<RebalanceReport>(`/investments/portfolios/${portfolioId}/rebalance`),

  getDividends: (portfolioId: number, params: { start_date?: string; end_date?: string } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.start_date) searchParams.set('start_date', params.start_date);
    if (params.end_date) searchParams.set('end_date', params.end_date);
    return apiRequest<DividendSummary>(`/investments/portfolios/${portfolioId}/dividends?${searchParams.toString()}`);
  },

  getAggregatedAnalytics: (portfolio_type?: string) => {
    const searchParams = new URLSearchParams();
    if (portfolio_type) searchParams.set('portfolio_type', portfolio_type.toUpperCase());
    return apiRequest<AggregatedAnalytics>(`/investments/analytics/aggregated?${searchParams.toString()}`);
  },

  getDividendYields: (portfolioId: number) =>
    apiRequest<Record<string, number>>(`/investments/portfolios/${portfolioId}/dividends/yields`),

  getDividendFrequency: (portfolioId: number) =>
    apiRequest<Record<string, any>>(`/investments/portfolios/${portfolioId}/dividends/frequency`),

  getDividendForecast: (portfolioId: number, forecastMonths: number = 12) =>
    apiRequest<any>(`/investments/portfolios/${portfolioId}/dividends/forecast?forecast_months=${forecastMonths}`),

  getDiversificationAnalysis: (portfolioId: number) =>
    apiRequest<any>(`/investments/portfolios/${portfolioId}/diversification`),

  getTransactions: (portfolioId: number, params: { start_date?: string; end_date?: string } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.start_date) searchParams.set('start_date', params.start_date);
    if (params.end_date) searchParams.set('end_date', params.end_date);
    return apiRequest<InvestmentTransaction[]>(`/investments/portfolios/${portfolioId}/transactions?${searchParams.toString()}`);
  },


  getPriceStatus: () =>
    apiRequest<{ fresh_prices: number; stale_prices: number; without_prices: number }>(
      '/investments/holdings/price-status'
    ),

  updatePrices: () =>
    apiRequest<{ success: number; failed: number; total: number }>(
      '/investments/holdings/update-prices',
      { method: 'POST' }
    ),

  downloadHoldingsFileBlob: async (
    attachmentId: number
  ): Promise<{ blob: Blob; filename: string; contentType: string }> => {
    const tenantId = getTenantId();
    const base = API_BASE_URL.replace(/\/$/, '');
    const url = `${base}/investments/holdings-files/${attachmentId}/download`;
    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const resp = await fetch(url, { method: 'GET', headers, credentials: 'include' });

    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(text || `Failed to fetch file (${resp.status})`);
    }

    const cd = resp.headers.get('content-disposition') || '';
    const ct = resp.headers.get('content-type') || '';
    let filename = `holdings-${attachmentId}.pdf`;

    try {
      const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
      const raw = decodeURIComponent((m?.[1] || m?.[2] || '').trim());
      if (raw) filename = raw;
    } catch { /* noop */ }

    const blob = await resp.blob();
    const type = ct || blob.type || 'application/pdf';
    // Ensure blob type matches if missing
    const normalizedBlob = blob.type === type ? blob : new Blob([blob], { type });

    return { blob: normalizedBlob, filename, contentType: type };
  },

  // Cross-Portfolio Analysis
  getCrossPortfolioSummary: (portfolioIds?: number[]) => {
    const params = portfolioIds ? `?portfolio_ids=${portfolioIds.join(',')}` : '';
    return apiRequest<any>(`/investments/cross-portfolio/summary${params}`);
  },

  getConsolidatedHoldings: (portfolioIds?: number[]) => {
    const params = portfolioIds ? `?portfolio_ids=${portfolioIds.join(',')}` : '';
    return apiRequest<any>(`/investments/cross-portfolio/consolidated-holdings${params}`);
  },

  getOverlapAnalysis: (portfolioIds?: number[]) => {
    const params = portfolioIds ? `?portfolio_ids=${portfolioIds.join(',')}` : '';
    return apiRequest<any>(`/investments/cross-portfolio/overlap-analysis${params}`);
  },

  getStockComparison: (symbol: string, portfolioIds?: number[]) => {
    const params = portfolioIds ? `?portfolio_ids=${portfolioIds.join(',')}` : '';
    return apiRequest<any>(`/investments/cross-portfolio/stock-comparison/${encodeURIComponent(symbol)}${params}`);
  },

  getExposureReport: (portfolioIds?: number[]) => {
    const params = portfolioIds ? `?portfolio_ids=${portfolioIds.join(',')}` : '';
    return apiRequest<any>(`/investments/cross-portfolio/exposure-report${params}`);
  },

  getMonthlyComparison: (months: number = 6, portfolioIds?: number[]) => {
    const searchParams = new URLSearchParams();
    searchParams.set('months', months.toString());
    if (portfolioIds) searchParams.set('portfolio_ids', portfolioIds.join(','));
    return apiRequest<any>(`/investments/cross-portfolio/monthly-comparison?${searchParams.toString()}`);
  },
};
