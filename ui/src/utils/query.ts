/**
 * React Query Utilities for Role-Based Access Control
 * Provides helpers for conditional fetching based on user roles
 */

import { UseQueryOptions } from '@tanstack/react-query';
import { isAuthenticated, isAdmin, hasRole, UserRole } from './auth';

/**
 * Create React Query options with role-based enabling
 * @param baseOptions Base query options
 * @param allowedRoles Array of roles that can access this query
 * @returns Query options with role-based enabling
 */
export function createRoleBasedQueryOptions<T>(
  baseOptions: UseQueryOptions<T>,
  allowedRoles: UserRole[]
): UseQueryOptions<T> {
  return {
    ...baseOptions,
    enabled: (() => {
      // Call auth functions dynamically each time query is evaluated
      const authenticated = isAuthenticated();
      const hasRequiredRole = hasRole(allowedRoles);
      const baseEnabled = baseOptions.enabled ?? true;
      
      console.log('Query enabled check:', { authenticated, hasRequiredRole, baseEnabled, allowedRoles });
      return authenticated && hasRequiredRole && baseEnabled;
    })(),
    retry: (failureCount, error: any) => {
      // Don't retry on authentication/authorization errors
      if (error?.message?.includes('403') || error?.message?.includes('401')) {
        return false;
      }
      return baseOptions.retry ? baseOptions.retry(failureCount, error) : failureCount < 3;
    },
  };
}

/**
 * Create React Query options for admin-only queries
 * @param baseOptions Base query options
 * @returns Query options enabled only for admin users
 */
export function createAdminOnlyQueryOptions<T>(
  baseOptions: UseQueryOptions<T>
): UseQueryOptions<T> {
  return createRoleBasedQueryOptions(baseOptions, ['admin']);
}

/**
 * Create React Query options for non-viewer queries (admin/user)
 * @param baseOptions Base query options
 * @returns Query options enabled for admin and user roles
 */
export function createNonViewerQueryOptions<T>(
  baseOptions: UseQueryOptions<T>
): UseQueryOptions<T> {
  return createRoleBasedQueryOptions(baseOptions, ['admin', 'user']);
}

/**
 * Create React Query options for authenticated users
 * @param baseOptions Base query options
 * @returns Query options enabled for any authenticated user
 */
export function createAuthenticatedQueryOptions<T>(
  baseOptions: UseQueryOptions<T>
): UseQueryOptions<T> {
  return {
    ...baseOptions,
    enabled: isAuthenticated() && (baseOptions.enabled ?? true),
    retry: (failureCount, error: any) => {
      // Don't retry on authentication errors
      if (error?.message?.includes('401')) {
        return false;
      }
      return baseOptions.retry ? baseOptions.retry(failureCount, error) : failureCount < 3;
    },
  };
}

/**
 * Common query configurations for settings (admin-only)
 */
export const settingsQueryConfig = {
  refetchInterval: 30000, // 30 seconds
  refetchOnWindowFocus: true,
  refetchOnMount: true,
  refetchOnReconnect: true,
  refetchIntervalInBackground: false,
  staleTime: 0,
};

/**
 * Create settings query options (admin-only with common config)
 * @param additionalOptions Additional options to merge
 * @returns Complete settings query options
 */
export function createSettingsQueryOptions<T>(
  additionalOptions: Partial<UseQueryOptions<T>> = {}
): UseQueryOptions<T> {
  return createAdminOnlyQueryOptions({
    ...settingsQueryConfig,
    ...additionalOptions,
  });
}

/**
 * Common query configurations for user data
 */
export const userDataQueryConfig = {
  refetchInterval: 60000, // 1 minute
  refetchOnWindowFocus: true,
  refetchOnMount: true,
  staleTime: 30000, // 30 seconds
};

/**
 * Create user data query options (authenticated users)
 * @param additionalOptions Additional options to merge
 * @returns Complete user data query options
 */
export function createUserDataQueryOptions<T>(
  additionalOptions: Partial<UseQueryOptions<T>> = {}
): UseQueryOptions<T> {
  return createAuthenticatedQueryOptions({
    ...userDataQueryConfig,
    ...additionalOptions,
  });
} 