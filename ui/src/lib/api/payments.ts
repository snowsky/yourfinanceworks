import { apiRequest } from './_base';

export interface Payment {
  id: number;
  invoice_id: number;
  invoice_number: string;
  client_name: string;
  amount: number;
  currency?: string;
  payment_date: string;
  payment_method: string;
  reference_number?: string;
  notes?: string;
  status: 'completed' | 'pending' | 'failed';
  tenant_id: number;
  created_at: string;
  updated_at: string;
}

// Payment API methods
export const paymentApi = {
  getPayments: async (params: { limit?: number; offset?: number; paymentMethod?: string } = {}) => {
    const { limit = 10, offset = 0, paymentMethod } = params;
    const searchParams = new URLSearchParams({
      limit: String(limit),
      skip: String(offset),
    });

    if (paymentMethod) {
      searchParams.set('payment_method', paymentMethod);
    }

    const response = await apiRequest<{ success: boolean; data: Payment[]; count: number; chart_data: any }>(
      `/payments/?${searchParams.toString()}`
    );
    return response;
  },
  getPayment: (id: number) => apiRequest<Payment>(`/payments/${id}`),
  createPayment: (payment: {
    invoice_id: number;
    amount: number;
    payment_date: string;
    payment_method: string;
    reference_number?: string;
    notes?: string;
  }) =>
    apiRequest<Payment>("/payments/", {
      method: 'POST',
      body: JSON.stringify(payment),
    }),
  updatePayment: (id: number, payment: Partial<Payment>) =>
    apiRequest<Payment>(`/payments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payment),
    }),
  deletePayment: (id: number) =>
    apiRequest(`/payments/${id}`, {
      method: 'DELETE',
    }),
  getStripeHistory: async (limit: number = 20) => {
    const response = await apiRequest<{ success: boolean; data: any[] }>(`/payments/stripe/history?limit=${limit}`);
    return response;
  },
};
