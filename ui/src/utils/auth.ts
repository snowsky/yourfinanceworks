/**
 * Authentication and Role-Based Access Control Utilities
 * Consolidates repetitive auth logic across the application
 */

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'user' | 'viewer' | 'super_admin';
  first_name?: string;
  last_name?: string;
  tenant_id?: number;
  is_superuser?: boolean;
  show_analytics?: boolean;
}

export type UserRole = 'admin' | 'user' | 'viewer' | 'super_admin';

/**
 * Get current user data from localStorage
 * @returns User object or null if not authenticated
 */
export const getCurrentUser = (): User | null => {
  try {
    const userStr = localStorage.getItem('user');
    if (!userStr) return null;

    const user = JSON.parse(userStr);
    return user;
  } catch (error) {
    console.error('Error parsing user data from localStorage:', error);
    return null;
  }
};

/**
 * Get current user role from localStorage
 * @returns UserRole or 'user' as default
 */
export const getCurrentUserRole = (): UserRole => {
  try {
    const user = getCurrentUser();
    const role = user?.role || 'user';

    return role;
  } catch (error) {
    console.error('Error getting current user role:', error);
    return 'user';
  }
};

/**
 * Check if current user is authenticated (auth cookie is httpOnly, so we rely on user data presence)
 * @returns boolean
 */
export const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('user');
};

/**
 * Check if current user has admin role
 * @returns boolean
 */
export const isAdmin = (): boolean => {
  return getCurrentUserRole() === 'admin';
};

/**
 * Check if current user has super admin role
 * @returns boolean
 */
export const isSuperAdmin = (): boolean => {
  const user = getCurrentUser();
  return user?.role === 'super_admin' || user?.is_superuser === true;
};

/**
 * Check if current user has user role
 * @returns boolean
 */
export const isUser = (): boolean => {
  return getCurrentUserRole() === 'user';
};

/**
 * Check if current user has viewer role
 * @returns boolean
 */
export const isViewer = (): boolean => {
  return getCurrentUserRole() === 'viewer';
};

/**
 * Check if current user can perform actions (not a viewer)
 * @returns boolean
 */
export const canPerformActions = (): boolean => {
  const role = getCurrentUserRole();
  return role === 'admin' || role === 'user';
};

/**
 * Check if current user has one of the specified roles
 * @param allowedRoles Array of allowed roles
 * @returns boolean
 */
export const hasRole = (allowedRoles: UserRole[]): boolean => {
  return allowedRoles.includes(getCurrentUserRole());
};

export const canAccess = (_feature: string, allowedRoles: UserRole[]): boolean => {
  return hasRole(allowedRoles);
};

/**
 * Check if an expense can be edited by the current user
 * @param expense The expense to check
 * @returns boolean - true if the expense can be edited
 */
export const canEditExpense = (expense: { status: string }): boolean => {
  // First check if user has general action permissions
  if (!canPerformActions()) {
    return false;
  }

  // Prevent editing expenses that are in approval workflow (except rejected - users should be able to fix and resubmit)
  const approvalStatuses = ['pending_approval', 'approved', 'resubmitted'];
  if (approvalStatuses.includes(expense.status)) {
    return false;
  }

  return true;
};

/**
 * Check if an invoice can be edited by the current user
 * @param invoice The invoice to check
 * @returns boolean - true if the invoice can be edited
 */
export const canEditInvoice = (invoice: { status: string }): boolean => {
  // First check if user has general action permissions
  if (!canPerformActions()) {
    return false;
  }

  // Prevent editing invoices that are in approval workflow (except rejected - users should be able to fix and resubmit)
  const approvalStatuses = ['pending_approval', 'resubmitted'];
  if (approvalStatuses.includes(invoice.status)) {
    return false;
  }

  return true;
};

/**
 * Check if an invoice can be edited for payment updates specifically
 * @param invoice The invoice to check
 * @returns boolean - true if the invoice payment can be updated
 */
export const canEditInvoicePayment = (invoice: { status: string }): boolean => {
  // First check if user has general action permissions
  if (!canPerformActions()) {
    return false;
  }

  // Allow payment updates for approved invoices to support partial payments
  // Only block payment updates for invoices in pending approval or resubmitted status
  const blockedStatuses = ['pending_approval', 'resubmitted'];
  if (blockedStatuses.includes(invoice.status)) {
    return false;
  }

  return true;
};

/**
 * Check if an expense can be deleted by the current user
 * @param expense The expense to check
 * @returns boolean - true if the expense can be deleted
 */
export const canDeleteExpense = (expense: { status: string }): boolean => {
  // First check if user has general action permissions
  if (!canPerformActions()) {
    return false;
  }

  // Allow admins to delete expenses regardless of status
  if (isAdmin()) {
    return true;
  }

  // Prevent deleting expenses that are in approval workflow
  const approvalStatuses = ['pending_approval', 'approved', 'rejected', 'resubmitted'];
  if (approvalStatuses.includes(expense.status)) {
    return false;
  }

  return true;
};

/**
 * Update current user data in localStorage
 * @param userData Partial user data to update
 */
export const updateCurrentUser = (userData: Partial<User>): void => {
  try {
    const currentUser = getCurrentUser();
    if (!currentUser) return;

    const updatedUser = { ...currentUser, ...userData };
    localStorage.setItem('user', JSON.stringify(updatedUser));
    
    // Dispatch custom event to notify components of user data change
    window.dispatchEvent(new CustomEvent('user-updated', { detail: updatedUser }));
  } catch (error) {
    console.error('Error updating user data in localStorage:', error);
  }
};

/**
 * Clear authentication data and redirect to login
 */
export const logout = async () => {
  try {
    await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
  } catch {
    // proceed with local cleanup even if server call fails
  }
  localStorage.removeItem('user');
  localStorage.removeItem('selected_tenant_id');
  window.dispatchEvent(new Event('auth-changed'));
  window.location.href = '/login';
};

/**
 * Check authentication and redirect if needed
 * @param redirectOnFailure Whether to redirect to login on failure (default: true)
 * @returns boolean indicating if user is authenticated
 */
export const ensureAuthenticated = (redirectOnFailure: boolean = true): boolean => {
  const authenticated = isAuthenticated();
  if (!authenticated && redirectOnFailure) {
    window.location.href = '/login';
  }
  return authenticated;
}; 