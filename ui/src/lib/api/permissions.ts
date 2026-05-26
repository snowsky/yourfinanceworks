import { apiRequest } from './_base';

export type PermissionLevel = 'viewer' | 'user' | 'admin';

export interface ComponentDescriptor {
  key: string;
  label: string;
  category: 'core_financial' | 'secondary' | 'plugins' | 'admin' | string;
  description: string;
}

export interface ComponentCatalog {
  components: ComponentDescriptor[];
  levels: PermissionLevel[];
}

export interface EffectivePermission {
  component: string;
  role_level: PermissionLevel;
  grant_level: PermissionLevel | null;
  effective_level: PermissionLevel;
}

export interface UserPermissions {
  user_id: number;
  role: PermissionLevel;
  is_superuser: boolean;
  permissions: EffectivePermission[];
}

export interface PermissionAuditEntry {
  id: number;
  user_id: number;
  actor_user_id: number | null;
  actor_email: string | null;
  component: string;
  action: 'grant' | 'update' | 'revoke';
  previous_level: PermissionLevel | null;
  new_level: PermissionLevel | null;
  created_at: string;
}

export interface PermissionAuditResponse {
  entries: PermissionAuditEntry[];
}

const LEVEL_RANK: Record<PermissionLevel, number> = {
  viewer: 1,
  user: 2,
  admin: 3,
};

/** True iff `actual` is at least `required` in the viewer < user < admin order. */
export function hasLevel(actual: PermissionLevel, required: PermissionLevel): boolean {
  return LEVEL_RANK[actual] >= LEVEL_RANK[required];
}

export function getComponentCatalog(): Promise<ComponentCatalog> {
  return apiRequest<ComponentCatalog>('/permissions/components');
}

export function getMyPermissions(): Promise<UserPermissions> {
  return apiRequest<UserPermissions>('/permissions/me');
}

export function getUserPermissions(userId: number): Promise<UserPermissions> {
  return apiRequest<UserPermissions>(`/permissions/users/${userId}`);
}

export function setUserPermission(
  userId: number,
  component: string,
  level: PermissionLevel,
): Promise<EffectivePermission> {
  return apiRequest<EffectivePermission>(
    `/permissions/users/${userId}/components/${component}`,
    { method: 'PUT', body: JSON.stringify({ level }) },
  );
}

export function clearUserPermission(
  userId: number,
  component: string,
): Promise<EffectivePermission> {
  return apiRequest<EffectivePermission>(
    `/permissions/users/${userId}/components/${component}`,
    { method: 'DELETE' },
  );
}

export function getUserPermissionAudit(
  userId: number,
  limit = 100,
): Promise<PermissionAuditResponse> {
  return apiRequest<PermissionAuditResponse>(
    `/permissions/users/${userId}/audit?limit=${limit}`,
  );
}
