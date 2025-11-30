/**
 * Authentication and Role-Based Access Control Utilities
 * Consolidates repetitive auth logic across the application
 */

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  first_name?: string;
  last_name?: string;
  tenant_id?: number;
  is_superuser?: boolean;
}

export type UserRole = 'admin' | 'user' | 'viewer';

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

    console.log('getCurrentUserRole:', {
      user,
      role,
      userRole: user?.role
    });

    return role;
  } catch (error) {
    console.error('Error getting user role:', error);
    return 'user';
  }
};

/**
 * Check if current user is authenticated
 * @returns boolean
 */
export const isAuthenticated = (): boolean => {
  const token = localStorage.getItem('token');
  const user = localStorage.getItem('user');
  const authenticated = !!(token && user);

  console.log('isAuthenticated check:', {
    hasToken: !!token,
    hasUser: !!user,
    authenticated
  });

  return authenticated;
};

/**
 * Check if current user has admin role
 * @returns boolean
 */
export const isAdmin = (): boolean => {
  return getCurrentUserRole() === 'admin';
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
  const currentRole = getCurrentUserRole();
  const hasAccess = allowedRoles.includes(currentRole);

  console.log('hasRole check:', {
    currentRole,
    allowedRoles,
    hasAccess
  });

  return hasAccess;
};

/**
 * Check if current user can access a specific feature
 * @param feature Feature name for debugging
 * @param allowedRoles Array of allowed roles
 * @returns boolean
 */
export const canAccess = (feature: string, allowedRoles: UserRole[]): boolean => {
  const hasAccess = hasRole(allowedRoles);
  if (!hasAccess) {
    console.log(`Access denied to ${feature}. Required roles: ${allowedRoles.join(', ')}, Current role: ${getCurrentUserRole()}`);
  }
  return hasAccess;
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

  // Prevent editing expenses that are in approval workflow
  const approvalStatuses = ['pending_approval', 'approved', 'rejected', 'resubmitted'];
  if (approvalStatuses.includes(expense.status)) {
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
 * Clear authentication data and redirect to login
 */
export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem('selected_tenant_id');
  // Dispatch custom event to notify FeatureContext
  window.dispatchEvent(new Event('auth-changed'));
  window.location.href = '/login';
};

/**
 * Check authentication and redirect if needed
 * @param redirectOnFailure Whether to redirect to login on failure (default: true)
 * @returns boolean indicating if user is authenticated
 */
export const ensureAuthenticated = (redirectOnFailure: boolean = true): boolean => {
  const token = localStorage.getItem('token');
  const user = localStorage.getItem('user');

  const isAuthenticated = !!(token && user);

  if (!isAuthenticated && redirectOnFailure) {
    console.warn('Authentication check failed, redirecting to login');
    window.location.href = '/login';
  }

  return isAuthenticated;
}; 