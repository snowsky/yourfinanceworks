import { apiRequest } from './_base';

// Currency API methods
export const currencyApi = {
  getSupportedCurrencies: () => apiRequest<any>("/currency/supported?active_only=false"),
  createCustomCurrency: (data: any) => apiRequest<any>("/currency/custom", {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateCustomCurrency: (id: number, data: any) => apiRequest<any>(`/currency/custom/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteCustomCurrency: (id: number) => apiRequest<any>(`/currency/custom/${id}`, {
    method: 'DELETE',
  }),
};
