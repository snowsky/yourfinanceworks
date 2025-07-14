import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { 
  getCurrentUser, 
  getCurrentUserRole, 
  isAuthenticated as checkIsAuthenticated,
  isAdmin as checkIsAdmin,
  isUser as checkIsUser, 
  isViewer as checkIsViewer,
  canPerformActions as checkCanPerformActions,
  hasRole as checkHasRole,
  canAccess as checkCanAccess,
  User,
  UserRole
} from '@/utils/auth';

export interface UseAuthReturn {
  // State
  user: User | null;
  userRole: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Role checks
  isAdmin: boolean;
  isUser: boolean;
  isViewer: boolean;
  canPerformActions: boolean;
  
  // Functions
  hasRole: (allowedRoles: UserRole[]) => boolean;
  canAccess: (feature: string, allowedRoles: UserRole[]) => boolean;
  logout: () => void;
  refreshAuth: () => void;
}

/**
 * Custom hook for authentication and role-based access control
 * Provides reactive state management for user authentication and roles
 */
export const useAuth = (): UseAuthReturn => {
  const [user, setUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<UserRole>('user');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  // Derived state
  const isAdmin = userRole === 'admin';
  const isUser = userRole === 'user';
  const isViewer = userRole === 'viewer';
  const canPerformActions = isAdmin || isUser;
  
  // Load authentication state
  const loadAuthState = useCallback(() => {
    try {
      const currentUser = getCurrentUser();
      const currentRole = getCurrentUserRole();
      const authenticated = checkIsAuthenticated();
      
      setUser(currentUser);
      setUserRole(currentRole);
      setIsAuthenticated(authenticated);
      
      console.log('useAuth: Auth state loaded', {
        user: currentUser,
        role: currentRole,
        authenticated
      });
    } catch (error) {
      console.error('useAuth: Error loading auth state:', error);
      setUser(null);
      setUserRole('user');
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Refresh authentication state
  const refreshAuth = useCallback(() => {
    console.log('useAuth: Refreshing auth state');
    loadAuthState();
  }, [loadAuthState]);
  
  // Logout function
  const logout = useCallback(() => {
    console.log('useAuth: Logging out');
    
    // Clear local state
    setUser(null);
    setUserRole('user');
    setIsAuthenticated(false);
    
    // Clear localStorage
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    
    // Clear React Query cache
    queryClient.clear();
    
    // Navigate to login
    navigate('/login');
  }, [navigate, queryClient]);
  
  // Role checking functions
  const hasRole = useCallback((allowedRoles: UserRole[]): boolean => {
    return checkHasRole(allowedRoles);
  }, []);
  
  const canAccess = useCallback((feature: string, allowedRoles: UserRole[]): boolean => {
    return checkCanAccess(feature, allowedRoles);
  }, []);
  
  // Load auth state on mount
  useEffect(() => {
    loadAuthState();
  }, [loadAuthState]);
  
  // Listen for localStorage changes (for multi-tab support)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'token' || e.key === 'user') {
        console.log('useAuth: Storage change detected, refreshing auth state');
        refreshAuth();
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [refreshAuth]);
  
  // Listen for custom auth events
  useEffect(() => {
    const handleAuthUpdate = () => {
      console.log('useAuth: Auth update event received');
      refreshAuth();
    };
    
    window.addEventListener('auth-updated', handleAuthUpdate);
    
    return () => {
      window.removeEventListener('auth-updated', handleAuthUpdate);
    };
  }, [refreshAuth]);
  
  return {
    // State
    user,
    userRole,
    isAuthenticated,
    isLoading,
    
    // Role checks
    isAdmin,
    isUser,
    isViewer,
    canPerformActions,
    
    // Functions
    hasRole,
    canAccess,
    logout,
    refreshAuth,
  };
}; 