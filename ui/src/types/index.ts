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
  currency: string;
}

export interface DiscountRuleCreate {
  name: string;
  min_amount: number;
  discount_type: 'percentage' | 'fixed';
  discount_value: number;
  is_active?: boolean;
  priority?: number;
  currency: string;
}

export interface DiscountRuleUpdate {
  name?: string;
  min_amount?: number;
  discount_type?: 'percentage' | 'fixed';
  discount_value?: number;
  is_active?: boolean;
  priority?: number;
  currency?: string;
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

export interface Payment {
  id: number;
  invoice_id: number;
  amount: number;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference_number?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  status: string;
  user_id?: number;
  user_name?: string;
} 