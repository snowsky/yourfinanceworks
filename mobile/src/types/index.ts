// User types
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'user' | 'viewer';
  tenant_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Client types
export interface Client {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  country: string;
  preferred_currency: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  notes?: ClientNote[];
}

export interface ClientNote {
  id: number;
  client_id: number;
  content: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

// Invoice types
export interface Invoice {
  id: number;
  invoice_number: string;
  client_id: number;
  client: Client;
  issue_date: string;
  due_date: string;
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
  subtotal: number;
  tax_rate: number;
  tax_amount: number;
  total: number;
  currency: string;
  notes: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  items: InvoiceItem[];
}

export interface InvoiceItem {
  id: number;
  invoice_id: number;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
  created_at: string;
  updated_at: string;
}

// Payment types
export interface Payment {
  id: number;
  invoice_id: number;
  invoice: Invoice;
  amount: number;
  payment_date: string;
  payment_method: string;
  reference_number: string;
  notes: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
}

// Currency types
export interface Currency {
  code: string;
  name: string;
  symbol: string;
}

// Settings types
export interface Settings {
  id: number;
  tenant_id: string;
  company_name: string;
  company_address: string;
  company_email: string;
  company_phone: string;
  default_currency: string;
  tax_rate: number;
  email_enabled: boolean;
  email_provider: string;
  email_config: EmailConfig;
  created_at: string;
  updated_at: string;
}

export interface EmailConfig {
  provider: 'aws_ses' | 'azure' | 'mailgun';
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_region?: string;
  azure_connection_string?: string;
  mailgun_api_key?: string;
  mailgun_domain?: string;
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SignupRequest {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
}

// Form types
export interface CreateInvoiceRequest {
  client_id: number;
  issue_date: string;
  due_date: string;
  currency: string;
  notes?: string;
  items: CreateInvoiceItemRequest[];
}

export interface CreateInvoiceItemRequest {
  description: string;
  quantity: number;
  unit_price: number;
}

export interface CreateClientRequest {
  name: string;
  email: string;
  phone?: string;
  address?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  country?: string;
  preferred_currency?: string;
}

export interface CreatePaymentRequest {
  invoice_id: number;
  amount: number;
  payment_date: string;
  payment_method: string;
  reference_number?: string;
  notes?: string;
} 