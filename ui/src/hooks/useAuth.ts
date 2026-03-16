import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  getCurrentUser,
  hasRole as checkHasRole,
  canAccess as checkCanAccess,
  User,
  UserRole
} from '@/utils/auth';
import { authApi } from '@/lib/api';

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

  // Load authentication state — verify with server so the httpOnly cookie
  // is the source of truth, not localStorage (prevents localStorage spoofing).
  const loadAuthState = useCallback(async () => {
    try {
      // Fast path: show cached user data immediately while we verify
      const cachedUser = getCurrentUser();
      if (cachedUser) {
        setUser(cachedUser);
        setUserRole(cachedUser.role ?? 'user');
        setIsAuthenticated(true);
      }

      // Server-side verification: confirm the session cookie is valid
      const serverUser: User = await authApi.getCurrentUser();
      // Sync canonical data from server back to localStorage
      localStorage.setItem('user', JSON.stringify(serverUser));
      setUser(serverUser);
      setUserRole(serverUser.role ?? 'user');
      setIsAuthenticated(true);
    } catch (error: any) {
      const status = error?.response?.status ?? error?.status;
      if (status === 401 || status === 403) {
        // Cookie is invalid/expired — clear stale local state
        localStorage.removeItem('user');
        localStorage.removeItem('token');
        setUser(null);
        setUserRole('user');
        setIsAuthenticated(false);
      } else {
        // Network error or server down — fall back to cached state
        const cachedUser = getCurrentUser();
        setUser(cachedUser);
        setUserRole(cachedUser?.role ?? 'user');
        setIsAuthenticated(!!cachedUser);
      }
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

    // Dispatch custom event to notify FeatureContext
    window.dispatchEvent(new Event('auth-changed'));

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