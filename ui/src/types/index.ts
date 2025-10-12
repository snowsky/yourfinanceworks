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

// Approval workflow types
export interface ExpenseApproval {
  id: number;
  expense_id: number;
  approver_id: number;
  approval_rule_id?: number;
  status: 'pending' | 'approved' | 'rejected';
  rejection_reason?: string;
  notes?: string;
  submitted_at: string;
  decided_at?: string;
  approval_level: number;
  is_current_level: boolean;
  expense?: {
    id: number;
    amount: number;
    currency: string;
    expense_date: string;
    category: string;
    vendor?: string;
    status: string;
    notes?: string;
  };
  approver?: {
    id: number;
    name: string;
    email: string;
  };
  approval_rule?: {
    id: number;
    name: string;
    min_amount: number;
    max_amount?: number;
  };
}

export interface User {
  id: number;
  name: string;
  email: string;
  role?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}


export interface ApprovalHistoryEntry {
  id: number;
  expense_id: number;
  approver_id: number;
  action: 'submitted' | 'approved' | 'rejected' | 'delegated';
  status: 'pending' | 'approved' | 'rejected';
  notes?: string;
  rejection_reason?: string;
  approval_level: number;
  timestamp: string;
  approver?: {
    id: number;
    name: string;
    email: string;
  };
}

export interface ApprovalDashboardStats {
  pending_count: number;
  approved_today: number;
  rejected_today: number;
  overdue_count: number;
  average_approval_time_hours: number;
}

// Approval delegation types
export interface ApprovalDelegate {
  id: number;
  approver_id: number;
  delegate_id: number;
  start_date: string;
  end_date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  approver?: {
    id: number;
    name: string;
    email: string;
  };
  delegate?: {
    id: number;
    name: string;
    email: string;
  };
}

export interface ApprovalDelegateCreate {
  approver_id: number;
  delegate_id: number;
  start_date: string;
  end_date: string;
  is_active?: boolean;
}

export interface ApprovalDelegateUpdate {
  start_date?: string;
  end_date?: string;
  is_active?: boolean;
} 