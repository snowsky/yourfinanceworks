export interface DiscountRule {
  id: number;
  name: string;
  type: 'percentage' | 'fixed';
  value: number;
  min_amount?: number;
  max_amount?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InvoiceHistory {
  id: number;
  invoice_id: number;
  tenant_id: number;
  user_id: number;
  action: string;
  details?: string;
  previous_values?: Record<string, any>;
  current_values?: Record<string, any>;
  created_at: string;
  user_name?: string;
}

export interface InvoiceHistoryCreate {
  invoice_id: number;
  tenant_id: number;
  user_id: number;
  action: string;
  details?: string;
  previous_values?: Record<string, any>;
  current_values?: Record<string, any>;
} 