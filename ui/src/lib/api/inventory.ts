import { API_BASE_URL, apiRequest } from './_base';
import type { Expense } from './expenses';

// Inventory Management Types
export interface InventoryCategory {
  id: number;
  name: string;
  description?: string;
  color?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryItem {
  id: number;
  name: string;
  description?: string;
  sku?: string;
  category_id?: number;
  category?: InventoryCategory;
  unit_price: number;
  cost_price?: number;
  currency: string;
  track_stock: boolean;
  current_stock: number;
  minimum_stock: number;
  unit_of_measure: string;
  item_type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockMovement {
  id: number;
  item_id: number;
  movement_type: string;
  quantity: number;
  unit_cost?: number;
  reference_type?: string;
  reference_id?: number;
  notes?: string;
  user_id: number;
  movement_date: string;
  created_at: string;
  item?: InventoryItem;
}

export interface StockMovementCreate {
  item_id: number;
  movement_type: string;
  quantity: number;
  unit_cost?: number;
  reference_type?: string;
  reference_id?: number;
  notes?: string;
  movement_date: string;
}

export interface InventoryAnalytics {
  total_items: number;
  active_items: number;
  low_stock_items: number;
  total_value: number;
  currency: string;
}

export interface InventorySearchFilters {
  query?: string;
  category_id?: number;
  item_type?: string;
  is_active?: boolean;
  track_stock?: boolean;
  low_stock_only?: boolean;
  min_price?: number;
  max_price?: number;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface InventoryValueReport {
  total_inventory_value: number;
  total_cost_value: number;
  potential_profit: number;
  currency: string;
  items: any[];
}

export interface InventoryPurchaseItem {
  item_id: number;
  quantity: number;
  unit_cost: number;
  item_name?: string;
}

export interface InventoryPurchaseCreate {
  vendor: string;
  reference_number?: string;
  purchase_date: string;
  currency: string;
  items: InventoryPurchaseItem[];
  notes?: string;
  payment_method?: string;
  tax_rate?: number;
}

export interface LowStockAlert {
  item_id: number;
  item_name: string;
  sku?: string;
  current_stock: number;
  minimum_stock: number;
  sold_last_30_days: number;
  daily_sales_rate: number;
  days_until_empty?: number;
  weeks_stock_remaining?: number;
  alert_level: 'critical' | 'warning' | 'normal';
  message: string;
}

export interface LowStockAlertsResponse {
  generated_at: string;
  threshold_days: number;
  alerts: LowStockAlert[];
  summary: {
    total_items: number;
    critical_alerts: number;
    warning_alerts: number;
    normal_items: number;
  };
}

// Invoice-Inventory Linking Interfaces
export interface InvoiceInventoryLink {
  id: number;
  number: string;
  amount: number;
  currency: string;
  status: string;
  due_date?: string;
  created_at: string;
  client_id: number;
  invoice_items: Array<{
    quantity: number;
    price: number;
    amount: number;
  }>;
  stock_movements: Array<{
    id: number;
    quantity: number;
    movement_type: string;
    movement_date: string;
    notes?: string;
  }>;
}

export interface InventoryStockSummary {
  item_id: number;
  movement_summary: Record<string, {
    total_quantity: number;
    count: number;
  }>;
  recent_movements: Array<{
    id: number;
    movement_type: string;
    quantity: number;
    reference_type?: string;
    reference_id?: number;
    movement_date: string;
    notes?: string;
  }>;
  linked_references: {
    invoices: Array<{
      id: number;
      number: string;
      amount: number;
      currency: string;
      status: string;
      client_id: number;
    }>;
    expenses: Array<{
      id: number;
      amount: number;
      currency: string;
      category?: string;
      vendor?: string;
    }>;
  };
  period_days: number;
}

export interface ProfitabilityAnalysis {
  period: {
    start_date: string;
    end_date: string;
  };
  summary: {
    total_revenue: number;
    total_cost: number;
    total_profit: number;
    overall_margin_percent: number;
  };
  items: any[];
}

export interface InventoryTurnoverAnalysis {
  analysis_period_months: number;
  summary: {
    total_inventory_value: number;
    total_cogs: number;
    overall_turnover_ratio: number;
    items_analyzed: number;
  };
  turnover_categories: {
    excellent: number;
    good: number;
    fair: number;
    slow: number;
    very_slow: number;
  };
  items: any[];
}

export interface CategoryPerformanceReport {
  period: {
    start_date: string;
    end_date: string;
  };
  categories: any[];
  summary: {
    total_categories: number;
    total_revenue: number;
    total_inventory_value: number;
  };
}

export interface InventoryDashboardData {
  analytics: InventoryAnalytics;
  alerts: {
    critical_alerts: number;
    warning_alerts: number;
    normal_items: number;
  };
  recent_activity: {
    period_days: number;
    total_sold: number;
    total_revenue: number;
    invoice_count: number;
  };
  top_selling_items: Array<{
    item_name: string;
    total_sold: number;
    total_revenue: number;
  }>;
  generated_at: string;
}

// === INVENTORY MANAGEMENT API ===

export const inventoryApi = {
  // Categories
  getCategories: (activeOnly = true) =>
    apiRequest<InventoryCategory[]>(`/inventory/categories?active_only=${activeOnly}`),

  getCategory: (id: number) =>
    apiRequest<InventoryCategory>(`/inventory/categories/${id}`),

  createCategory: (category: Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>) =>
    apiRequest<InventoryCategory>('/inventory/categories', {
      method: 'POST',
      body: JSON.stringify(category),
    }),

  updateCategory: (id: number, category: Partial<Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>>) =>
    apiRequest<InventoryCategory>(`/inventory/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(category),
    }),

  deleteCategory: (id: number) =>
    apiRequest(`/inventory/categories/${id}`, {
      method: 'DELETE',
    }),

  // Items
  getItems: (params?: {
    skip?: number;
    limit?: number;
    query?: string;
    category_id?: number;
    item_type?: string;
    is_active?: boolean;
    track_stock?: boolean;
    low_stock_only?: boolean;
    min_price?: number;
    max_price?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set('skip', params.skip.toString());
    if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString());
    if (params?.query) searchParams.set('query', params.query);
    if (params?.category_id !== undefined) searchParams.set('category_id', params.category_id.toString());
    if (params?.item_type) searchParams.set('item_type', params.item_type);
    if (params?.is_active !== undefined) searchParams.set('is_active', params.is_active.toString());
    if (params?.track_stock !== undefined) searchParams.set('track_stock', params.track_stock.toString());
    if (params?.low_stock_only !== undefined) searchParams.set('low_stock_only', params.low_stock_only.toString());
    if (params?.min_price !== undefined) searchParams.set('min_price', params.min_price.toString());
    if (params?.max_price !== undefined) searchParams.set('max_price', params.max_price.toString());

    const queryString = searchParams.toString();
    return apiRequest<InventoryListResponse>(`/inventory/items${queryString ? `?${queryString}` : ''}`);
  },

  searchItems: (query: string, limit = 50) =>
    apiRequest<{ results: InventoryItem[]; total: number }>(`/inventory/items/search?q=${encodeURIComponent(query)}&limit=${limit}`),

  getItem: (id: number) =>
    apiRequest<InventoryItem>(`/inventory/items/${id}`),

  createItem: (item: Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>) =>
    apiRequest<InventoryItem>('/inventory/items', {
      method: 'POST',
      body: JSON.stringify(item),
    }),

  updateItem: (id: number, item: Partial<Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>>) =>
    apiRequest<InventoryItem>(`/inventory/items/${id}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    }),

  deleteItem: (id: number) =>
    apiRequest(`/inventory/items/${id}`, {
      method: 'DELETE',
    }),

  // Stock Management
  adjustStock: (itemId: number, quantity: number, reason: string) =>
    apiRequest(`/inventory/items/${itemId}/stock/adjust`, {
      method: 'POST',
      body: JSON.stringify({ quantity, reason }),
    }),

  getStockMovements: (itemId: number, limit = 50, movementType?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (movementType) params.set('movement_type', movementType);
    return apiRequest<StockMovement[]>(`/inventory/items/${itemId}/stock/movements?${params.toString()}`);
  },

  getStockMovementsByReference: (referenceType: string, referenceId: number) =>
    apiRequest<StockMovement[]>(`/inventory/movements/by-reference/${referenceType}/${referenceId}`),

  // Invoice-Inventory Linking
  getInvoicesLinkedToInventoryItem: (itemId: number) =>
    apiRequest<InvoiceInventoryLink[]>(`/inventory/items/${itemId}/linked-invoices`),

  getInventoryItemStockSummary: (itemId: number, days = 30) =>
    apiRequest<InventoryStockSummary>(`/inventory/items/${itemId}/stock-movement-summary?days=${days}`),

  getLowStockAlerts: (thresholdDays = 30) =>
    apiRequest<LowStockAlertsResponse>(`/inventory/alerts/low-stock?threshold_days=${thresholdDays}`),

  checkStockAvailability: (itemId: number, requestedQuantity: number) =>
    apiRequest(`/inventory/items/${itemId}/availability?requested_quantity=${requestedQuantity}`),

  // Analytics & Reporting
  getAnalytics: () =>
    apiRequest<InventoryAnalytics>('/inventory/analytics'),

  getAdvancedAnalytics: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest(`/inventory/analytics/advanced${queryString ? `?${queryString}` : ''}`);
  },

  getSalesVelocity: (days = 30) =>
    apiRequest(`/inventory/analytics/sales-velocity?days=${days}`),

  getForecasting: (forecastDays = 90) =>
    apiRequest(`/inventory/analytics/forecasting?forecast_days=${forecastDays}`),

  getValueReport: () =>
    apiRequest<InventoryValueReport>('/inventory/reports/value'),

  getProfitabilityAnalysis: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest<ProfitabilityAnalysis>(`/inventory/reports/profitability${queryString ? `?${queryString}` : ''}`);
  },

  getTurnoverAnalysis: (months = 12) =>
    apiRequest<InventoryTurnoverAnalysis>(`/inventory/reports/turnover?months=${months}`),

  getCategoryPerformance: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const queryString = params.toString();
    return apiRequest<CategoryPerformanceReport>(`/inventory/reports/categories${queryString ? `?${queryString}` : ''}`);
  },

  getSalesVelocityReport: (days = 30) =>
    apiRequest(`/inventory/reports/sales-velocity?days=${days}`),

  getDashboardData: () =>
    apiRequest<InventoryDashboardData>('/inventory/reports/dashboard'),

  getStockMovementSummary: (itemId?: number, days = 30) => {
    const params = new URLSearchParams({ days: days.toString() });
    if (itemId !== undefined) params.set('item_id', itemId.toString());
    return apiRequest(`/inventory/reports/stock-movements?${params.toString()}`);
  },

  // Integration APIs
  populateInvoiceItem: (inventoryItemId: number, quantity = 1) =>
    apiRequest(`/inventory/invoice-items/populate?inventory_item_id=${inventoryItemId}&quantity=${quantity}`),

  validateInvoiceStock: (invoiceItems: any[]) =>
    apiRequest('/inventory/invoice-items/validate-stock', {
      method: 'POST',
      body: JSON.stringify({ invoice_items: invoiceItems }),
    }),

  getInvoiceInventorySummary: (invoiceId: number) =>
    apiRequest(`/inventory/invoice/${invoiceId}/inventory-summary`),

  createInventoryPurchase: (purchase: InventoryPurchaseCreate) =>
    apiRequest('/inventory/expenses/purchase', {
      method: 'POST',
      body: JSON.stringify(purchase),
    }),

  getInventoryPurchaseSummary: (params?: {
    start_date?: string;
    end_date?: string;
    vendor?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set('start_date', params.start_date);
    if (params?.end_date) searchParams.set('end_date', params.end_date);
    if (params?.vendor) searchParams.set('vendor', params.vendor);
    const queryString = searchParams.toString();
    return apiRequest(`/inventory/expenses/purchase-summary${queryString ? `?${queryString}` : ''}`);
  },

  getExpenseInventorySummary: (expenseId: number) =>
    apiRequest(`/inventory/expense/${expenseId}/inventory-summary`),

  // Bulk Operations
  createCategoriesBulk: (categories: Omit<InventoryCategory, 'id' | 'created_at' | 'updated_at'>[]) =>
    apiRequest<InventoryCategory[]>('/inventory/categories/bulk', {
      method: 'POST',
      body: JSON.stringify(categories),
    }),

  createItemsBulk: (items: Omit<InventoryItem, 'id' | 'created_at' | 'updated_at'>[]) =>
    apiRequest<InventoryItem[]>('/inventory/items/bulk', {
      method: 'POST',
      body: JSON.stringify(items),
    }),

  createStockMovementsBulk: (movements: StockMovementCreate[]) =>
    apiRequest<StockMovement[]>('/inventory/stock-movements/bulk', {
      method: 'POST',
      body: JSON.stringify(movements),
    }),

  // Barcode Management
  getItemByBarcode: (barcode: string) =>
    apiRequest<InventoryItem>(`/inventory/items/barcode/${encodeURIComponent(barcode)}`),

  updateItemBarcode: (itemId: number, barcodeData: {
    barcode: string;
    barcode_type?: string;
    barcode_format?: string;
  }) =>
    apiRequest(`/inventory/items/${itemId}/barcode`, {
      method: 'POST',
      body: JSON.stringify(barcodeData),
    }),

  validateBarcode: (barcode: string) =>
    apiRequest(`/inventory/barcode/validate`, {
      method: 'POST',
      body: JSON.stringify({ barcode }),
    }),

  getBarcodeSuggestions: (itemName: string, sku?: string) => {
    const params = new URLSearchParams({ item_name: itemName });
    if (sku) params.set('sku', sku);
    return apiRequest<{ suggestions: string[] }>(`/inventory/barcode/suggestions?${params.toString()}`);
  },

  bulkUpdateBarcodes: (barcodeUpdates: Array<{
    item_id: number;
    barcode: string;
    barcode_type?: string;
    barcode_format?: string;
  }>) =>
    apiRequest('/inventory/barcode/bulk-update', {
      method: 'POST',
      body: JSON.stringify(barcodeUpdates),
    }),

  // Import/Export
  uploadReceipt: async (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest<Expense>(`/expenses/${id}/receipt`, {
      method: 'POST',
      body: formData,
    });
  },
  acceptReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/accept-review`, { method: 'POST' }),
  reReview: (id: number) => apiRequest<Expense>(`/expenses/${id}/review`, { method: 'POST' }),
  importInventoryCSV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest('/inventory/import/csv', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set content-type for FormData
    });
  },

  exportInventoryCSV: async (params?: {
    include_inactive?: boolean;
    category_id?: number;
  }) => {
    const tenantId = localStorage.getItem('selected_tenant_id') ||
      (() => {
        try { const user = JSON.parse(localStorage.getItem('user') || '{}'); return user.tenant_id?.toString(); } catch { return undefined; }
      })();

    const searchParams = new URLSearchParams();
    if (params?.include_inactive) searchParams.set('include_inactive', 'true');
    if (params?.category_id) searchParams.set('category_id', params.category_id.toString());
    const queryString = searchParams.toString();

    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const response = await fetch(`${API_BASE_URL}/inventory/export/csv${queryString ? `?${queryString}` : ''}`, {
      method: 'GET',
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorText = await response.text();
      try { throw new Error(JSON.parse(errorText).detail || 'Export failed'); }
      catch { throw new Error(errorText || 'Export failed'); }
    }

    return response.blob();
  },
};
