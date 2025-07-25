import AsyncStorage from '@react-native-async-storage/async-storage';

// API Configuration
// For development, use your computer's IP address instead of localhost
// You can find your IP with: ifconfig (Mac/Linux) or ipconfig (Windows)
const API_BASE_URL = __DEV__ 
  ? 'http://10.0.0.211:8000/api/v1' // Use your computer's IP address
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

export type InvoiceStatus = "draft" | "pending" | "paid" | "overdue" | "partially_paid";

export interface Invoice {
  id: number;
  number: string;
  amount: number;
  currency: string;
  date: string;
  due_date: string;
  status: InvoiceStatus;
  notes?: string;
  client_id: number;
  client_name: string;
  client_email: string;
  paid_amount: number;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  total_paid: number;
  is_recurring?: boolean;
  recurring_frequency?: string;
  discount_type?: string;
  discount_value?: number;
  subtotal?: number;
  items?: InvoiceItem[];
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

// Settings types
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

export interface DashboardStats {
  totalIncome: Record<string, number>;
  pendingInvoices: Record<string, number>;
  totalClients: number;
  invoicesPaid: number;
  invoicesPending: number;
  invoicesOverdue: number;
  monthlyStats?: {
    currentMonth: number;
    previousMonth: number;
    percentageChange: number;
  };
}

export interface CreateInvoiceData {
  client_id: number;
  amount: number;
  currency: string;
  date: string;
  due_date: string;
  status: InvoiceStatus;
  notes?: string;
  items: InvoiceItemCreate[];
  is_recurring?: boolean;
  recurring_frequency?: string;
  discount_type?: string;
  discount_value?: number;
  paid_amount?: number;
}

export interface UpdateInvoiceData {
  client_id: number;
  amount: number;
  currency: string;
  date: string;
  due_date: string;
  status: InvoiceStatus;
  notes?: string;
  items: InvoiceItemUpdate[];
  is_recurring?: boolean;
  recurring_frequency?: string;
  discount_type?: string;
  discount_value?: number;
  paid_amount?: number;
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
  preferred_currency?: string;
}

// Generic API request function with enhanced error handling
export async function apiRequest<T>(
  url: string, 
  options: RequestInit = {}, 
  config: { isLogin?: boolean } = {}
): Promise<T> {
  try {
    // Get JWT token and user from AsyncStorage
    const token = await AsyncStorage.getItem(TOKEN_KEY);
    const userData = await AsyncStorage.getItem(USER_KEY);
    const user = userData ? JSON.parse(userData) : null;
    const tenantId = user?.tenant_id;
    
    const requestUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    console.log(`Making API request to ${requestUrl}`, options);
    
    const response = await fetch(requestUrl, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...(tenantId && { 'X-Tenant-ID': tenantId }),
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
        await AsyncStorage.removeItem(TOKEN_KEY);
        await AsyncStorage.removeItem(USER_KEY);
        throw new Error('Authentication failed. Please log in again.');
      }

      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error(`API request failed for ${url}:`, error);
    throw error;
  }
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

  // HTTP Request Helper with enhanced error handling
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    config: { isLogin?: boolean } = {}
  ): Promise<T> {
    const token = await this.getToken();
    const userData = await AsyncStorage.getItem(USER_KEY);
    const user = userData ? JSON.parse(userData) : null;
    const tenantId = user?.tenant_id;
    const url = `${this.baseURL}${endpoint}`;

    const requestOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...(tenantId && { 'X-Tenant-ID': tenantId }),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, requestOptions);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        // Handle authentication errors
        if (!config.isLogin && (response.status === 401 || response.status === 403)) {
          // Check if it's a tenant context error
          if (errorData.detail && errorData.detail.includes('Tenant context required')) {
            await this.removeToken();
            await this.removeUser();
            throw new Error('Session expired. Please log in again.');
          } else if (response.status === 401) {
            // 401 Unauthorized - token is invalid/expired
            await this.removeToken();
            await this.removeUser();
            throw new Error('Authentication failed. Please log in again.');
          } else {
            // 403 Forbidden - user lacks permissions
            throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
          }
        }

        // Handle 400 errors that might be tenant context issues
        if (response.status === 400 && errorData.detail && errorData.detail.includes('Tenant context required')) {
          await this.removeToken();
          await this.removeUser();
          throw new Error('Session expired. Please log in again.');
        }

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
    }, { isLogin: true });

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
      }),
    }, { isLogin: true });

    await this.setToken(response.access_token);
    await this.setUser(response.user);

    return response;
  }

  async checkEmailAvailability(email: string): Promise<{ available: boolean; email: string }> {
    return await this.request<{ available: boolean; email: string }>(`/auth/check-email-availability?email=${encodeURIComponent(email)}`, {
      method: 'GET',
    }, { isLogin: true });
  }

  async requestPasswordReset(email: string): Promise<{ message: string; success: boolean }> {
    return await this.request<{ message: string; success: boolean }>(`/auth/request-password-reset`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    }, { isLogin: true });
  }

  async resetPassword(token: string, newPassword: string): Promise<{ message: string; success: boolean }> {
    return await this.request<{ message: string; success: boolean }>(`/auth/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }, { isLogin: true });
  }

  async logout(): Promise<void> {
    await this.removeToken();
    await this.removeUser();
  }

  async getCurrentUser(): Promise<User | null> {
    try {
      return await this.request<User>('/auth/me');
    } catch (error) {
      console.error('Failed to get current user:', error);
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
    const params = statusFilter ? `?status_filter=${statusFilter}` : '';
    const response = await this.request<any[]>(`/invoices/${params}`);
    return response.map(invoice => ({
      ...invoice,
      items: invoice.items || [],
      currency: invoice.currency || 'USD'
    }));
  }

  async getInvoice(invoiceId: number): Promise<Invoice> {
    const response = await this.request<any>(`/invoices/${invoiceId}`);
    return {
      ...response,
      items: response.items || [],
      currency: response.currency || 'USD'
    };
  }

  async createInvoice(invoiceData: CreateInvoiceData): Promise<Invoice> {
    return await this.request<Invoice>('/invoices/', {
      method: 'POST',
      body: JSON.stringify(invoiceData),
    });
  }

  async updateInvoice(invoiceId: number, invoiceData: UpdateInvoiceData): Promise<Invoice> {
    const response = await this.request<any>(`/invoices/${invoiceId}`, {
      method: 'PUT',
      body: JSON.stringify(invoiceData),
    });
    return {
      ...response,
      items: response.items || [],
      currency: response.currency || 'USD'
    };
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

  // Payment Methods
  async getPayments(): Promise<Payment[]> {
    const response = await this.request<{ success: boolean; data: Payment[]; count: number; chart_data: any }>('/payments/');
    return response.data || [];
  }

  async createPayment(paymentData: Partial<Payment>): Promise<Payment> {
    return await this.request<Payment>('/payments/', {
      method: 'POST',
      body: JSON.stringify(paymentData),
    });
  }

  // Settings Methods
  async getSettings(): Promise<Settings> {
    return await this.request<Settings>('/settings/');
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return await this.request<Settings>('/settings/', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  // Discount Rules Methods
  async getDiscountRules(): Promise<DiscountRule[]> {
    return await this.request<DiscountRule[]>('/discount-rules/');
  }

  async getDiscountRule(ruleId: number): Promise<DiscountRule> {
    return await this.request<DiscountRule>(`/discount-rules/${ruleId}/`);
  }

  async createDiscountRule(ruleData: DiscountRuleCreate): Promise<DiscountRule> {
    return await this.request<DiscountRule>('/discount-rules/', {
      method: 'POST',
      body: JSON.stringify(ruleData),
    });
  }

  async updateDiscountRule(ruleId: number, ruleData: DiscountRuleUpdate): Promise<DiscountRule> {
    return await this.request<DiscountRule>(`/discount-rules/${ruleId}/`, {
      method: 'PUT',
      body: JSON.stringify(ruleData),
    });
  }

  async deleteDiscountRule(ruleId: number): Promise<void> {
    await this.request(`/discount-rules/${ruleId}/`, {
      method: 'DELETE',
    });
  }

  async calculateDiscount(amount: number, currency: string): Promise<DiscountCalculation> {
    return await this.request<DiscountCalculation>('/discount-rules/calculate', {
      method: 'POST',
      body: JSON.stringify({ amount, currency }),
    });
  }

  // Dashboard Methods
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      const [invoices, clients] = await Promise.all([
        this.request<Invoice[]>('/invoices/'),
        this.request<Client[]>('/clients/')
      ]);

      // Group income by currency
      const totalIncome: Record<string, number> = {};
      const pendingInvoices: Record<string, number> = {};
      
      invoices.forEach(invoice => {
        const currency = invoice.currency || 'USD';
        
        // Calculate total income (paid invoices)
        if (invoice.status === 'paid' || invoice.status === 'partially_paid') {
          const paidAmount = invoice.paid_amount || 0;
          totalIncome[currency] = (totalIncome[currency] || 0) + paidAmount;
        }
        
        // Calculate pending amount (unpaid invoices)
        if (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid') {
          const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
          if (outstandingAmount > 0) {
            pendingInvoices[currency] = (pendingInvoices[currency] || 0) + outstandingAmount;
          }
        }
      });

      // Count invoices by status
      const invoicesPaid = (invoices || []).filter(inv => inv.status === 'paid').length;
      const invoicesPending = (invoices || []).filter(inv => inv.status === 'pending').length;
      const invoicesOverdue = (invoices || []).filter(inv => inv.status === 'overdue').length;

      // Calculate trends (current month vs previous month)
      const now = new Date();
      const currentMonth = now.getMonth();
      const currentYear = now.getFullYear();
      const previousMonth = currentMonth === 0 ? 11 : currentMonth - 1;
      const previousYear = currentMonth === 0 ? currentYear - 1 : currentYear;

      // Helper function to calculate monthly totals
      const calculateMonthlyTotal = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   (invoice.status === 'paid' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => sum + (invoice.paid_amount || 0), 0);
      };

      // Helper function to calculate monthly pending
      const calculateMonthlyPending = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => {
            const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
            return sum + (outstandingAmount > 0 ? outstandingAmount : 0);
          }, 0);
      };

      // Helper function to calculate monthly clients
      const calculateMonthlyClients = (targetMonth: number, targetYear: number) => {
        const clientIds = new Set();
        (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear;
          })
          .forEach(invoice => clientIds.add(invoice.client_id));
        return clientIds.size;
      };

      // Helper function to calculate monthly overdue
      const calculateMonthlyOverdue = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth && 
                   invoiceDate.getFullYear() === targetYear &&
                   invoice.status === 'overdue';
          }).length;
      };

      // Calculate current and previous month totals
      const currentMonthIncome = calculateMonthlyTotal(currentMonth, currentYear);
      const previousMonthIncome = calculateMonthlyTotal(previousMonth, previousYear);
      const currentMonthPending = calculateMonthlyPending(currentMonth, currentYear);
      const previousMonthPending = calculateMonthlyPending(previousMonth, previousYear);
      const currentMonthClients = calculateMonthlyClients(currentMonth, currentYear);
      const previousMonthClients = calculateMonthlyClients(previousMonth, previousYear);
      const currentMonthOverdue = calculateMonthlyOverdue(currentMonth, currentYear);
      const previousMonthOverdue = calculateMonthlyOverdue(previousMonth, previousYear);

      // Calculate percentage changes
      const calculatePercentageChange = (current: number, previous: number) => {
        if (previous === 0) return current > 0 ? 100 : 0;
        return ((current - previous) / previous) * 100;
      };

      const incomeTrend = calculatePercentageChange(currentMonthIncome, previousMonthIncome);
      const pendingTrend = calculatePercentageChange(currentMonthPending, previousMonthPending);
      const clientsTrend = calculatePercentageChange(currentMonthClients, previousMonthClients);
      const overdueTrend = calculatePercentageChange(currentMonthOverdue, previousMonthOverdue);

      return {
        totalIncome,
        pendingInvoices,
        totalClients: clients.length,
        invoicesPaid,
        invoicesPending,
        invoicesOverdue,
        monthlyStats: {
          currentMonth: currentMonthIncome,
          previousMonth: previousMonthIncome,
          percentageChange: Math.round(incomeTrend * 10) / 10
        }
      };
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
      // Return default stats if API fails
      return {
        totalIncome: {},
        pendingInvoices: {},
        totalClients: 0,
        invoicesPaid: 0,
        invoicesPending: 0,
        invoicesOverdue: 0,
      };
    }
  }

  // Utility Methods
  async isAuthenticated(): Promise<boolean> {
    try {
      const token = await this.getToken();
      if (!token) return false;
      
      // Verify token is still valid
      await this.getCurrentUser();
      return true;
    } catch (error) {
      return false;
    }
  }

  async getStoredUser(): Promise<User | null> {
    return await this.getUser();
  }
}

const apiService = new ApiService();
export default apiService; 