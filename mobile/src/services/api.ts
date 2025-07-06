import AsyncStorage from '@react-native-async-storage/async-storage';

// API Configuration
// For development, use your computer's IP address instead of localhost
// You can find your IP with: ifconfig (Mac/Linux) or ipconfig (Windows)
const API_BASE_URL = __DEV__ 
  ? 'http://10.0.0.225:8000/api' // Replace with your actual IP address
  : 'https://your-production-api.com/api'; // Replace with your production URL
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'user_data';

// Types
export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  tenant_id: string;
  is_active: boolean;
  is_verified: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Client {
  id: number;
  tenant_id: string;
  name: string;
  email: string;
  phone?: string;
  address?: string;
  balance: number;
  paid_amount: number;
  preferred_currency?: string;
  created_at: string;
  updated_at: string;
}

export interface InvoiceItem {
  id?: number;
  invoice_id?: number;
  description: string;
  quantity: number;
  price: number;
  amount: number;
}

export interface InvoiceItemCreate {
  description: string;
  quantity: number;
  price: number;
}

export interface InvoiceItemUpdate {
  id?: number;
  description: string;
  quantity: number;
  price: number;
}

export interface Invoice {
  id: number;
  number: string;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  notes?: string;
  client_id: number;
  client_name: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  total_paid: number;
  is_recurring?: boolean;
  recurring_frequency?: string;
  items?: InvoiceItem[];
}

export interface DashboardStats {
  totalIncome: number;
  pendingInvoices: number;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
}

export interface CreateInvoiceData {
  client_id: number;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  notes?: string;
  items: InvoiceItemCreate[];
  is_recurring?: boolean;
  recurring_frequency?: string;
}

export interface UpdateInvoiceData {
  client_id: number;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  notes?: string;
  items: InvoiceItemUpdate[];
  is_recurring?: boolean;
  recurring_frequency?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignupData {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  organization_name?: string;
}

export interface CreateClientData {
  name: string;
  email: string;
  phone?: string;
  address?: string;
}

// API Service Class
class ApiService {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  // Token Management
  private async getToken(): Promise<string | null> {
    try {
      return await AsyncStorage.getItem(TOKEN_KEY);
    } catch (error) {
      console.error('Error getting token:', error);
      return null;
    }
  }

  private async setToken(token: string): Promise<void> {
    try {
      await AsyncStorage.setItem(TOKEN_KEY, token);
    } catch (error) {
      console.error('Error setting token:', error);
    }
  }

  private async removeToken(): Promise<void> {
    try {
      await AsyncStorage.removeItem(TOKEN_KEY);
    } catch (error) {
      console.error('Error removing token:', error);
    }
  }

  private async getUser(): Promise<User | null> {
    try {
      const userData = await AsyncStorage.getItem(USER_KEY);
      return userData ? JSON.parse(userData) : null;
    } catch (error) {
      console.error('Error getting user:', error);
      return null;
    }
  }

  private async setUser(user: User): Promise<void> {
    try {
      await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch (error) {
      console.error('Error setting user:', error);
    }
  }

  private async removeUser(): Promise<void> {
    try {
      await AsyncStorage.removeItem(USER_KEY);
    } catch (error) {
      console.error('Error removing user:', error);
    }
  }

  // HTTP Request Helper
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await this.getToken();
    const url = `${this.baseURL}${endpoint}`;

    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  // Authentication Methods
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });

    await this.setToken(response.access_token);
    await this.setUser(response.user);

    return response;
  }

  async signup(data: SignupData): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        ...data,
        tenant_id: null, // Will create new tenant
        is_active: true,
        is_verified: true,
        is_superuser: false,
      }),
    });

    await this.setToken(response.access_token);
    await this.setUser(response.user);

    return response;
  }

  async logout(): Promise<void> {
    await this.removeToken();
    await this.removeUser();
  }

  async getCurrentUser(): Promise<User | null> {
    try {
      return await this.request<User>('/auth/me');
    } catch (error) {
      console.error('Error getting current user:', error);
      return null;
    }
  }

  // Client Methods
  async getClients(): Promise<Client[]> {
    return await this.request<Client[]>('/clients/');
  }

  async getClient(clientId: number): Promise<Client> {
    return await this.request<Client>(`/clients/${clientId}`);
  }

  async createClient(clientData: CreateClientData): Promise<Client> {
    return await this.request<Client>('/clients/', {
      method: 'POST',
      body: JSON.stringify(clientData),
    });
  }

  async updateClient(clientId: number, clientData: Partial<Client>): Promise<Client> {
    return await this.request<Client>(`/clients/${clientId}`, {
      method: 'PUT',
      body: JSON.stringify(clientData),
    });
  }

  async deleteClient(clientId: number): Promise<void> {
    await this.request(`/clients/${clientId}`, {
      method: 'DELETE',
    });
  }

  // Invoice Methods
  async getInvoices(statusFilter?: string): Promise<Invoice[]> {
    const params = statusFilter && statusFilter !== 'all' ? `?status_filter=${statusFilter}` : '';
    return await this.request<Invoice[]>(`/invoices/${params}`);
  }

  async getInvoice(invoiceId: number): Promise<Invoice> {
    return await this.request<Invoice>(`/invoices/${invoiceId}`);
  }

  async createInvoice(invoiceData: CreateInvoiceData): Promise<Invoice> {
    return await this.request<Invoice>('/invoices/', {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    });
  }

  async updateInvoice(invoiceId: number, invoiceData: UpdateInvoiceData): Promise<Invoice> {
    return await this.request<Invoice>(`/invoices/${invoiceId}`, {
      method: 'PUT',
      body: JSON.stringify(invoiceData),
    });
  }

  async deleteInvoice(invoiceId: number): Promise<void> {
    await this.request(`/invoices/${invoiceId}`, {
      method: 'DELETE',
    });
  }

  async sendInvoiceEmail(invoiceId: number): Promise<void> {
    await this.request(`/invoices/${invoiceId}/send-email`, {
      method: 'POST',
    });
  }

  // Dashboard Methods
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      const [totalIncome, invoices] = await Promise.all([
        this.request<{ total_income: number }>('/invoices/stats/total-income'),
        this.getInvoices(),
      ]);

      const stats: DashboardStats = {
        totalIncome: totalIncome.total_income || 0,
        pendingInvoices: invoices.filter(inv => inv.status === 'pending').reduce((sum, inv) => sum + inv.amount, 0),
        totalClients: (await this.getClients()).length,
        invoicesPaid: invoices.filter(inv => inv.status === 'paid').length,
        invoicesPending: invoices.filter(inv => inv.status === 'pending').length,
        invoicesOverdue: invoices.filter(inv => inv.status === 'overdue').length,
      };

      return stats;
    } catch (error) {
      console.error('Error getting dashboard stats:', error);
      // Return default stats on error
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

  // Utility Methods
  async isAuthenticated(): Promise<boolean> {
    const token = await this.getToken();
    if (!token) return false;

    try {
      const user = await this.getCurrentUser();
      return !!user;
    } catch (error) {
      return false;
    }
  }

  async getStoredUser(): Promise<User | null> {
    return await this.getUser();
  }
}

// Export singleton instance
const apiService = new ApiService();
export default apiService; 