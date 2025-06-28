import { toast } from 'sonner';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Type definitions
export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  balance: number;
  paid_amount: number;
  preferred_currency?: string;
  created_at: string;
  updated_at: string;
}

export interface ClientNote {
  id: number;
  note: string;
  user_id: number;
  client_id: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id?: number;
  description: string;
  quantity: number;
  price: number;
  amount: number;
  invoice_id?: number;
}

export type InvoiceStatus = "draft" | "pending" | "paid" | "overdue" | "partially_paid";

export interface Invoice {
  id: number;
  number: string;
  client_id: number;
  client_name: string;
  client_email: string;
  date: string;
  due_date: string;
  amount: number;
  currency?: string;
  paid_amount: number;
  status: InvoiceStatus;
  notes?: string;
  items: InvoiceItem[];
  created_at: string;
  updated_at: string;
  is_recurring?: boolean;
  recurring_frequency?: string;
}

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

// Add settings types
export interface CompanyInfo {
  name: string;
  email: string;
  phone: string;
  address: string;
  tax_id: string;
  logo?: string;
}

export interface InvoiceSettings {
  prefix: string;
  next_number: string;
  terms: string;
  notes?: string;
  send_copy: boolean;
  auto_reminders: boolean;
}

export interface Settings {
  company_info: CompanyInfo;
  invoice_settings: InvoiceSettings;
}

// Generic API request function with error handling
export async function apiRequest<T>(url: string, options: RequestInit = {}, config: { isLogin?: boolean } = {}): Promise<T> {
  try {
    // Get JWT token from localStorage
    const token = localStorage.getItem('token');
    
    const requestUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    console.log(`Making API request to ${requestUrl}`, options);
    const response = await fetch(requestUrl, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      // Try to parse error response
      let errorData;
      try {
        errorData = await response.json();
      } catch (e) {
        // If JSON parsing fails, use status text
        throw new Error(`Error: ${response.status} ${response.statusText}`);
      }

      // Handle authentication errors
      if (!config.isLogin && (response.status === 401 || response.status === 403)) {
        // Clear invalid token and redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        throw new Error('Authentication failed. Please log in again.');
      }

      // Better handle validation errors (422)
      if (response.status === 422 && errorData.detail) {
        // Format validation errors nicely
        if (Array.isArray(errorData.detail)) {
          // Format validation errors from FastAPI
          const errorMessages = errorData.detail.map((err: any) => {
            const field = err.loc.slice(1).join('.');
            return `${field}: ${err.msg}`;
          }).join('; ');
          
          console.error('Validation error:', errorMessages);
          toast.error(`Validation error: ${errorMessages}`);
          throw new Error(`Validation error: ${errorMessages}`);
        } else {
          // Handle other error detail formats
          console.error('API error:', errorData.detail);
          toast.error(String(errorData.detail));
          throw new Error(String(errorData.detail));
        }
      }

      // Handle other errors
      const errorMessage = errorData.detail || `Error: ${response.status} ${response.statusText}`;
      toast.error(errorMessage);
      throw new Error(errorMessage);
    }

    // For DELETE requests with 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return await response.json() as T;
  } catch (error) {
    console.error('API request failed:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    toast.error(`Request failed: ${errorMessage}`);
    throw error;
  }
}

// Client API methods
export const clientApi = {
  getClients: () => apiRequest<Client[]>('/clients/'),
  getClient: (id: number) => apiRequest<Client>(`/clients/${id}`),
  createClient: (client: Omit<Client, 'id' | 'created_at' | 'updated_at'>) => 
    apiRequest<Client>('/clients/', {
      method: 'POST',
      body: JSON.stringify(client),
    }),
  updateClient: (id: number, client: Partial<Client>) => 
    apiRequest<Client>(`/clients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(client),
    }),
  deleteClient: (id: number) => 
    apiRequest(`/clients/${id}`, {
      method: 'DELETE',
    }),
};

// CRM API methods
export const crmApi = {
    getNotesForClient: (clientId: number) =>
        apiRequest<ClientNote[]>(`/crm/clients/${clientId}/notes`),
    createNoteForClient: (clientId: number, note: { note: string }) =>
        apiRequest<ClientNote>(`/crm/clients/${clientId}/notes`, {
            method: 'POST',
            body: JSON.stringify(note),
        }),
    updateNoteForClient: (clientId: number, noteId: number, note: { note: string }) =>
        apiRequest<ClientNote>(`/crm/clients/${clientId}/notes/${noteId}`, {
            method: 'PUT',
            body: JSON.stringify(note),
        }),
    deleteNoteForClient: (clientId: number, noteId: number) =>
        apiRequest(`/crm/clients/${clientId}/notes/${noteId}`, {
            method: 'DELETE',
        }),
};

// Currency API methods
export const currencyApi = {
    getSupportedCurrencies: () => apiRequest<any>('/currency/supported'),
};

// Auth API methods
export const authApi = {
  login: (email: string, password: string) =>
    apiRequest<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, { isLogin: true }),
  register: (userData: any) =>
    apiRequest<any>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),
};

// Invoice API methods
export const invoiceApi = {
  getInvoices: async (status?: string): Promise<Invoice[]> => {
    try {
      const response = await apiRequest<any[]>(`/invoices/${status ? `?status_filter=${status}` : ''}`);
      
      // Map API response to frontend Invoice interface
      const mappedInvoices: Invoice[] = response.map(apiInvoice => ({
        id: apiInvoice.id,
        number: apiInvoice.number || '',
        client_id: apiInvoice.client_id,
        client_name: apiInvoice.client_name || '',
        client_email: '', // API doesn't return this
        date: apiInvoice.created_at || apiInvoice.date || '',
        due_date: apiInvoice.due_date || '',
        amount: apiInvoice.amount || 0,
        paid_amount: apiInvoice.total_paid || 0, // Map total_paid to paid_amount
        status: apiInvoice.status || 'pending',
        notes: apiInvoice.notes || '',
        items: [], // API doesn't return items for list view
        created_at: apiInvoice.created_at || '',
        updated_at: apiInvoice.updated_at || '',
        is_recurring: apiInvoice.is_recurring,
        recurring_frequency: apiInvoice.recurring_frequency,
      }));
      
      console.log("Mapped invoices with paid amounts:", mappedInvoices);
      return mappedInvoices;
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      throw error;
    }
  },
  getInvoice: async (id: number) => {
    try {
      // Get invoice data from API
      const apiResponse = await apiRequest<any>(`/invoices/${id}`);
      
      console.log("API response for invoice:", apiResponse);
      
      // Map API response to frontend Invoice interface
      const invoice: Invoice = {
        id: apiResponse.id,
        number: apiResponse.number || '',
        client_id: apiResponse.client_id,
        client_name: apiResponse.client_name || '',
        client_email: '', // API doesn't return this, we'll need to fetch it separately or leave empty
        date: apiResponse.created_at || apiResponse.date || '', // Use created_at as fallback for date
        due_date: apiResponse.due_date || '',
        amount: apiResponse.amount || 0,
        paid_amount: apiResponse.total_paid || 0, // API returns total_paid, not paid_amount
        status: apiResponse.status || 'pending',
        notes: apiResponse.notes || '',
        items: apiResponse.items && Array.isArray(apiResponse.items) ? apiResponse.items.map((item: any) => ({
          id: item.id,
          description: item.description || '',
          quantity: item.quantity || 1,
          price: item.price || 0,
          amount: item.amount || (item.quantity || 1) * (item.price || 0)
        })) : [],
        created_at: apiResponse.created_at || '',
        updated_at: apiResponse.updated_at || '',
        is_recurring: apiResponse.is_recurring,
        recurring_frequency: apiResponse.recurring_frequency,
      };
      
      console.log("Mapped invoice object:", invoice);
      
      return invoice;
    } catch (error) {
      console.error("Error fetching invoice:", error);
      throw error;
    }
  },
  createInvoice: (invoiceData: Omit<Invoice, 'id' | 'created_at' | 'updated_at'>) => 
    apiRequest<Invoice>('/invoices/', {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    }),
  updateInvoice: (id: number, invoiceData: Partial<Invoice>) =>
    apiRequest<Invoice>(`/invoices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(invoiceData),
    }),
  deleteInvoice: (id: number) => 
    apiRequest(`/invoices/${id}`, {
      method: 'DELETE',
    }),
};

// Payment API methods
export const paymentApi = {
  getPayments: () => apiRequest<Payment[]>('/payments/'),
  getPayment: (id: number) => apiRequest<Payment>(`/payments/${id}`),
  createPayment: (payment: {
    invoice_id: number;
    amount: number;
    payment_date: string;
    payment_method: string;
    reference_number?: string;
    notes?: string;
  }) => 
    apiRequest<Payment>('/payments/', {
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
};

// Dashboard API
export const dashboardApi = {
  getStats: async () => {
    try {
      const [clients, invoices, payments] = await Promise.all([
        clientApi.getClients(),
        invoiceApi.getInvoices(),
        paymentApi.getPayments(),
      ]);
      
      const totalClients = clients.length;
      const totalIncome = invoices
        .filter(invoice => invoice.status === 'paid' || invoice.status === 'partially_paid')
        .reduce((sum, invoice) => sum + invoice.paid_amount, 0);
      const pendingInvoices = invoices
        .filter(invoice => invoice.status === 'pending' || invoice.status === 'overdue')
        .reduce((sum, invoice) => sum + (invoice.amount - (invoice.paid_amount || 0)), 0);
      
      const invoicesPaid = invoices.filter(invoice => invoice.status === 'paid').length;
      const invoicesPending = invoices.filter(invoice => invoice.status === 'pending').length;
      const invoicesOverdue = invoices.filter(invoice => invoice.status === 'overdue').length;
      
      return {
        totalIncome,
        pendingInvoices,
        totalClients,
        invoicesPaid,
        invoicesPending,
        invoicesOverdue,
      };
    } catch (error) {
      console.error('Failed to get dashboard stats:', error);
      return {
        totalIncome: 0,
        pendingInvoices: 0,
        totalClients: 0,
        invoicesPaid: 0,
        invoicesPending: 0,
        invoicesOverdue: 0,
      };
    }
  }
};

// Settings API methods
export const settingsApi = {
  getSettings: () => apiRequest<Settings>('/settings/'),
  updateSettings: (settings: Partial<Settings>) => 
    apiRequest<Settings>('/settings/', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),
  exportData: async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/settings/export-data`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to export data');
    }
    
    // Get filename from response headers or create a default one
    const contentDisposition = response.headers.get('content-disposition');
    let filename = `data_export_${new Date().toISOString().split('T')[0]}.sqlite`;
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }
    
    // Create blob and download
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
  importData: async (file: File) => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/settings/import-data`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to import data');
    }
    
    return await response.json();
  },
}; 