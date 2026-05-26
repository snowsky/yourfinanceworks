import { useQuery } from '@tanstack/react-query';

import {
  ComponentCatalog,
  EffectivePermission,
  PermissionLevel,
  UserPermissions,
  getComponentCatalog,
  getMyPermissions,
  hasLevel,
} from '@/lib/api/permissions';
import { getCurrentUser } from '@/utils/auth';

export function useMyPermissions() {
  const user = getCurrentUser();
  return useQuery<UserPermissions | null>({
    queryKey: ['permissions', 'me', user?.id],
    queryFn: async () => (user?.id ? await getMyPermissions() : null),
    enabled: !!user?.id,
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 10,
  });
}

export function useComponentCatalog() {
  return useQuery<ComponentCatalog>({
    queryKey: ['permissions', 'components'],
    queryFn: getComponentCatalog,
    staleTime: 1000 * 60 * 30,
    gcTime: 1000 * 60 * 60,
  });
}

export interface PermissionChecker {
  hasPermission: (component: string, required: PermissionLevel) => boolean;
  effectiveLevel: (component: string) => PermissionLevel | null;
  isLoading: boolean;
  isSuperuser: boolean;
}

/**
 * Hook returning a permission-checker for the current user.
 *
 * - Super admins always pass.
 * - Until the request resolves, every check returns `false` to fail closed.
 */
export function usePermissionChecker(): PermissionChecker {
  const { data, isLoading } = useMyPermissions();
  const isSuperuser = !!data?.is_superuser;
  const lookup = new Map<string, EffectivePermission>(
    (data?.permissions ?? []).map((p) => [p.component, p]),
  );

  return {
    isLoading,
    isSuperuser,
    effectiveLevel: (component) => lookup.get(component)?.effective_level ?? null,
    hasPermission: (component, required) => {
      if (isSuperuser) return true;
      const effective = lookup.get(component)?.effective_level;
      if (!effective) return false;
      return hasLevel(effective, required);
    },
  };
}
