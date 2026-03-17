import { apiRequest } from './_base';

// Discount rule types
export interface DiscountRule {
  id: number;
  name: string;
  min_amount: number;
  discount_type: 'percentage' | 'fixed';
  discount_value: number;
  is_active: boolean;
  priority: number;
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

export interface DiscountCalculation {
  discount_type: 'percentage' | 'fixed' | 'none';
  discount_value: number;
  discount_amount: number;
  applied_rule?: {
    id: number;
    name: string;
    min_amount: number;
  };
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

// Discount Rules API methods
export const discountRulesApi = {
  getDiscountRules: () => apiRequest<DiscountRule[]>("/discount-rules/"),
  getDiscountRule: (id: number) => apiRequest<DiscountRule>(`/discount-rules/${id}`),
  createDiscountRule: (discountRule: DiscountRuleCreate) =>
    apiRequest<DiscountRule>("/discount-rules/", {
      method: 'POST',
      body: JSON.stringify(discountRule),
    }),
  updateDiscountRule: (id: number, discountRule: DiscountRuleUpdate) =>
    apiRequest<DiscountRule>(`/discount-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(discountRule),
    }),
  deleteDiscountRule: (id: number) =>
    apiRequest(`/discount-rules/${id}`, {
      method: 'DELETE',
    }),
  calculateDiscount: (subtotal: number) => {
    console.log("Sending discount calculation request:", {
      url: `/discount-rules/calculate`,
      subtotal: subtotal
    });
    return apiRequest<DiscountCalculation>(`/discount-rules/calculate`, {
      method: 'POST',
      body: JSON.stringify({ subtotal: subtotal, currency: "USD" }),
    });
  },
};
