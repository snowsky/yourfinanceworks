import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Edit, Trash2, UserPlus } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { superAdminApi, apiRequest } from '../../lib/api';
import { toast } from 'sonner';
import type { Tenant, User } from './types';

interface UsersTabProps {
  users: User[];
  tenants: Tenant[];
  selectedTenantForUsers: Tenant | null;
  onSelectedTenantChange: (tenant: Tenant | null) => void;
  onUsersChanged: (tenantId?: number) => void;
}

export const UsersTab: React.FC<UsersTabProps> = ({
  users,
  tenants,
  selectedTenantForUsers,
  onSelectedTenantChange,
  onUsersChanged,
}) => {
  const { t } = useTranslation();
  const { user: currentUser, refreshAuth } = useAuth();

  const [showCreateUser, setShowCreateUser] = useState(false);
  const [createUserForm, setCreateUserForm] = useState({
    email: '', first_name: '', last_name: '', role: 'user', password: '',
    tenant_ids: [] as string[], primary_tenant_id: '', tenant_roles: {} as Record<string, string>, is_sso: false,
  });
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editUserForm, setEditUserForm] = useState({
    first_name: '', last_name: '', email: '', role: 'user', password: '',
    tenant_ids: [] as string[], primary_tenant_id: '', tenant_roles: {} as Record<string, string>,
  });
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [promoteEmail, setPromoteEmail] = useState('');
  const [promoteLoading, setPromoteLoading] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  const superUsers = users.filter(u => u.is_superuser).length;

  const handleCreateUser = async () => {
    try {
      await apiRequest('/super-admin/users', {
        method: 'POST',
        body: JSON.stringify(createUserForm),
      }, { skipTenant: true });
      setShowCreateUser(false);
      setCreateUserForm({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {}, is_sso: false });
      toast.success('User created successfully');
      onUsersChanged(selectedTenantForUsers?.id);
    } catch (err: any) {
      const errorMessage = err?.detail || err?.message || 'Failed to create user';
      toast.error(errorMessage);
    }
  };

  const handleEditUser = async (user: User) => {
    try {
      const userDetails = await apiRequest<{
        first_name: string;
        last_name: string;
        email: string;
        role: string;
        tenant_id: number;
        tenant_ids?: string[];
        primary_tenant_id?: string;
        tenant_roles?: Record<string, string>;
      }>(`/super-admin/users/${user.id}`, {}, { skipTenant: true });

      setEditUser(user);
      setEditUserForm({
        first_name: userDetails.first_name || '',
        last_name: userDetails.last_name || '',
        email: userDetails.email,
        role: userDetails.role,
        password: '',
        tenant_ids: userDetails.tenant_ids || [userDetails.tenant_id.toString()],
        primary_tenant_id: userDetails.primary_tenant_id || userDetails.tenant_id.toString(),
        tenant_roles: userDetails.tenant_roles || {},
      });
    } catch (err) {
      toast.error('Failed to load user details');
      setEditUser(user);
      setEditUserForm({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email,
        role: user.role,
        password: '',
        tenant_ids: [user.tenant_id.toString()],
        primary_tenant_id: user.tenant_id.toString(),
        tenant_roles: { [user.tenant_id.toString()]: user.role },
      });
    }
  };

  const handleUpdateUser = async () => {
    if (!editUser) return;
    try {
      await apiRequest<any>(`/super-admin/users/${editUser.id}`, {
        method: 'PUT',
        body: JSON.stringify(editUserForm),
      }, { skipTenant: true });
      setEditUser(null);
      toast.success('User updated successfully');
      onUsersChanged(selectedTenantForUsers?.id);
      if (currentUser && editUser.id === currentUser.id) {
        refreshAuth();
      }
    } catch (err) {
      toast.error('Failed to update user');
    }
  };

  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      await apiRequest(`/super-admin/users/${userToDelete.id}`, {
        method: 'DELETE',
      }, { skipTenant: true });
      toast.success('User deleted successfully');
      setUserToDelete(null);
      onUsersChanged(selectedTenantForUsers?.id);
    } catch (err) {
      toast.error('Failed to delete user');
      setUserToDelete(null);
    }
  };

  const handleToggleUserStatus = async (user: User) => {
    try {
      await apiRequest(`/super-admin/users/${user.id}/toggle-status`, {
        method: 'PATCH',
      }, { skipTenant: true });
      toast.success(`User ${user.is_active ? 'disabled' : 'enabled'} successfully`);
      onUsersChanged(selectedTenantForUsers?.id);
    } catch (err) {
      toast.error('Failed to toggle user status');
    }
  };

  const handlePromote = async (e: React.FormEvent) => {
    e.preventDefault();
    setPromoteLoading(true);
    setPromoteError(null);
    try {
      const data = await apiRequest<{ message: string }>('/super-admin/promote', {
        method: 'POST',
        body: JSON.stringify({ email: promoteEmail }),
      }, { skipTenant: true });
      toast.success(data.message || 'User promoted to super admin!');
      setPromoteEmail('');
      setPromoteError(null);
      onUsersChanged(selectedTenantForUsers?.id);
    } catch (err: any) {
      const errorMsg = err?.detail || err?.message || 'Failed to promote user';
      setPromoteError(errorMsg);
    } finally {
      setPromoteLoading(false);
    }
  };

  return (
    <>
      <ProfessionalCard className="slide-in">
        <div className="p-6 border-b border-border/50">
          <form onSubmit={handlePromote} className="flex flex-col md:flex-row items-center gap-4">
            <Label htmlFor="promote-email" className="font-medium whitespace-nowrap">{t('superAdmin.promote_user_label')}</Label>
            <Input
              id="promote-email"
              type="email"
              placeholder={t('superAdmin.promote_user_placeholder')}
              value={promoteEmail}
              onChange={e => { setPromoteEmail(e.target.value); setPromoteError(null); }}
              className="max-w-xs"
              required
            />
            <Button type="submit" disabled={promoteLoading || !promoteEmail}>
              {promoteLoading ? t('superAdmin.promoting_button') : t('superAdmin.promote_button')}
            </Button>
            {promoteError && (
              <div className="text-destructive text-sm" role="alert">{promoteError}</div>
            )}
          </form>
        </div>
      </ProfessionalCard>
      <ProfessionalCard className="slide-in">
        <div className="p-6">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
            <h2 className="text-xl font-semibold">{t('superAdmin.users_management_title')}</h2>
            <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto">
              <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-start">
                <Label className="whitespace-nowrap">{t('superAdmin.filter_by_organization')}</Label>
                <Select
                  value={selectedTenantForUsers?.id?.toString() || 'all'}
                  onValueChange={(value) => onSelectedTenantChange(value === 'all' ? null : tenants.find(t => t.id.toString() === value) || null)}
                >
                  <SelectTrigger className="w-full sm:w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('superAdmin.all_organizations')}</SelectItem>
                    {tenants.map(tenant => (
                      <SelectItem key={tenant.id} value={tenant.id.toString()}>{tenant.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Dialog open={showCreateUser} onOpenChange={setShowCreateUser}>
                <DialogTrigger asChild>
                  <Button className="w-full sm:w-auto">
                    <UserPlus className="h-4 w-4 mr-2" />
                    {t('superAdmin.create_user_button')}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t('superAdmin.create_new_user_title')}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="user-email">{t('superAdmin.email_label')}</Label>
                      <Input
                        id="user-email"
                        type="email"
                        value={createUserForm.email}
                        onChange={(e) => setCreateUserForm(prev => ({ ...prev, email: e.target.value }))}
                        placeholder={t('superAdmin.email_placeholder')}
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="user-first-name">{t('superAdmin.first_name_label')}</Label>
                        <Input
                          id="user-first-name"
                          value={createUserForm.first_name}
                          onChange={(e) => setCreateUserForm(prev => ({ ...prev, first_name: e.target.value }))}
                          placeholder={t('superAdmin.first_name_placeholder')}
                        />
                      </div>
                      <div>
                        <Label htmlFor="user-last-name">{t('superAdmin.last_name_label')}</Label>
                        <Input
                          id="user-last-name"
                          value={createUserForm.last_name}
                          onChange={(e) => setCreateUserForm(prev => ({ ...prev, last_name: e.target.value }))}
                          placeholder={t('superAdmin.last_name_placeholder')}
                        />
                      </div>
                    </div>
                    <div>
                      <Label>{t('superAdmin.organizations_and_roles_label')}</Label>
                      <div className="space-y-2 max-h-48 overflow-y-auto border rounded p-2">
                        {tenants.map(tenant => {
                          const tenantId = tenant.id.toString();
                          const isSelected = createUserForm.tenant_ids.includes(tenantId);
                          return (
                            <div key={tenant.id} className="flex items-center justify-between space-x-2 p-2 rounded">
                              <label className="flex items-center space-x-2">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => {
                                    setCreateUserForm(prev => {
                                      if (e.target.checked) {
                                        return {
                                          ...prev,
                                          tenant_ids: [...prev.tenant_ids, tenantId],
                                          primary_tenant_id: prev.primary_tenant_id || tenantId,
                                          tenant_roles: { ...prev.tenant_roles, [tenantId]: 'user' },
                                        };
                                      } else {
                                        const newTenantIds = prev.tenant_ids.filter(id => id !== tenantId);
                                        const newTenantRoles = { ...prev.tenant_roles };
                                        delete newTenantRoles[tenantId];
                                        return {
                                          ...prev,
                                          tenant_ids: newTenantIds,
                                          primary_tenant_id: prev.primary_tenant_id === tenantId ? newTenantIds[0] || '' : prev.primary_tenant_id,
                                          tenant_roles: newTenantRoles,
                                        };
                                      }
                                    });
                                  }}
                                />
                                <span className="text-sm">{tenant.name}</span>
                              </label>
                              {isSelected && (
                                <Select
                                  value={createUserForm.tenant_roles[tenantId] || 'user'}
                                  onValueChange={(value) => setCreateUserForm(prev => ({
                                    ...prev,
                                    tenant_roles: { ...prev.tenant_roles, [tenantId]: value },
                                  }))}
                                >
                                  <SelectTrigger className="w-24">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="admin">Admin</SelectItem>
                                    <SelectItem value="user">User</SelectItem>
                                    <SelectItem value="viewer">Viewer</SelectItem>
                                  </SelectContent>
                                </Select>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    <div className="space-y-3">
                      <Label className="text-base font-medium">Authentication Method</Label>
                      <div className="flex items-center space-x-3">
                        <input
                          type="radio"
                          id="auth-password"
                          name="auth-method"
                          checked={!createUserForm.is_sso}
                          onChange={() => setCreateUserForm(prev => ({ ...prev, is_sso: false, password: '' }))}
                          className="w-4 h-4"
                        />
                        <Label htmlFor="auth-password" className="text-sm font-normal cursor-pointer">
                          Password Authentication
                        </Label>
                      </div>
                      <div className="flex items-center space-x-3">
                        <input
                          type="radio"
                          id="auth-sso"
                          name="auth-method"
                          checked={createUserForm.is_sso}
                          onChange={() => setCreateUserForm(prev => ({ ...prev, is_sso: true, password: '' }))}
                          className="w-4 h-4"
                        />
                        <Label htmlFor="auth-sso" className="text-sm font-normal cursor-pointer">
                          Single Sign-On (SSO)
                        </Label>
                      </div>
                    </div>
                    {!createUserForm.is_sso && (
                      <div>
                        <Label htmlFor="user-password">{t('superAdmin.password_label')}</Label>
                        <Input
                          id="user-password"
                          type="password"
                          value={createUserForm.password}
                          onChange={(e) => setCreateUserForm(prev => ({ ...prev, password: e.target.value }))}
                          placeholder={t('superAdmin.password_placeholder')}
                          required
                        />
                      </div>
                    )}
                    {createUserForm.is_sso && (
                      <div className="p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <p className="text-sm text-blue-800 dark:text-blue-200">
                          <strong>SSO User:</strong> The user will be able to sign in using any configured SSO provider.
                          No password is required for SSO users.
                        </p>
                      </div>
                    )}
                    <Button onClick={handleCreateUser} className="w-full">{t('superAdmin.create_user_button')}</Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('superAdmin.name_header')}</TableHead>
                  <TableHead>{t('superAdmin.email_header')}</TableHead>
                  <TableHead>{t('superAdmin.organization_header')}</TableHead>
                  <TableHead>{t('superAdmin.role_header')}</TableHead>
                  <TableHead>{t('superAdmin.status_header')}</TableHead>
                  <TableHead>{t('superAdmin.created_at_header')}</TableHead>
                  <TableHead>{t('superAdmin.actions_header')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users
                  .slice()
                  .sort((a, b) => {
                    if (currentUser && a.id === currentUser.id) return -1;
                    if (currentUser && b.id === currentUser.id) return 1;
                    const aName = `${a.first_name} ${a.last_name}`.trim();
                    const bName = `${b.first_name} ${b.last_name}`.trim();
                    return aName.localeCompare(bName);
                  })
                  .map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">
                        {user.first_name} {user.last_name}
                        {user.is_superuser && (
                          <Badge variant="outline" className="ml-2">{t('superAdmin.super_user_badge')}</Badge>
                        )}
                      </TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>{user.tenant_name}</TableCell>
                      <TableCell>
                        <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                          {t(`superAdmin.role_${user.role}_label`)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? 'default' : 'secondary'}>
                          {user.is_active ? t('superAdmin.active_status') : t('superAdmin.inactive_status')}
                        </Badge>
                      </TableCell>
                      <TableCell>{new Date(user.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button size="sm" variant="outline" onClick={() => handleEditUser(user)}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          {currentUser && user.id !== currentUser.id && (
                            <Button
                              size="sm"
                              variant={user.is_active ? 'destructive' : 'default'}
                              onClick={() => handleToggleUserStatus(user)}
                            >
                              {user.is_active ? t('superAdmin.disable_button') : t('superAdmin.enable_button')}
                            </Button>
                          )}
                          {currentUser && user.id !== currentUser.id && (
                            <Button size="sm" variant="outline" onClick={() => setUserToDelete(user)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                          {user.is_superuser && currentUser && user.email !== currentUser.email && superUsers > 1 && (
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={async () => {
                                if (window.confirm(t('superAdmin.confirm_remove_super_admin'))) {
                                  try {
                                    await superAdminApi.demoteSuperAdmin(user.email);
                                    toast.success(t('superAdmin.remove_super_admin_success'));
                                    onUsersChanged(selectedTenantForUsers?.id);
                                  } catch (err: any) {
                                    toast.error(err?.message || t('superAdmin.remove_super_admin_failed'));
                                  }
                                }
                              }}
                            >
                              {t('superAdmin.remove_super_admin_button')}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </ProfessionalCard>

      {/* Edit User Dialog */}
      <Dialog open={!!editUser} onOpenChange={open => { if (!open) setEditUser(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.edit_user_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-user-first-name">{t('superAdmin.first_name_label')}</Label>
              <Input id="edit-user-first-name" value={editUserForm.first_name} onChange={e => setEditUserForm(prev => ({ ...prev, first_name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-last-name">{t('superAdmin.last_name_label')}</Label>
              <Input id="edit-user-last-name" value={editUserForm.last_name} onChange={e => setEditUserForm(prev => ({ ...prev, last_name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-email">{t('superAdmin.email_label')}</Label>
              <Input id="edit-user-email" type="email" value={editUserForm.email} onChange={e => setEditUserForm(prev => ({ ...prev, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-user-role">{t('superAdmin.role_label')}</Label>
              <Select value={editUserForm.role} onValueChange={value => setEditUserForm(prev => ({ ...prev, role: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">{t('superAdmin.role_admin_label')}</SelectItem>
                  <SelectItem value="user">{t('superAdmin.role_user_label')}</SelectItem>
                  <SelectItem value="viewer">{t('superAdmin.role_viewer_label')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="edit-user-password">{t('superAdmin.password_label_edit')}</Label>
              <Input id="edit-user-password" type="password" value={editUserForm.password} onChange={e => setEditUserForm(prev => ({ ...prev, password: e.target.value }))} />
            </div>
            <div>
              <Label>{t('superAdmin.organizations_and_roles_label')}</Label>
              <div className="space-y-2 max-h-48 overflow-y-auto border rounded p-2">
                {tenants.map(tenant => {
                  const isOwnOrg = editUser && tenant.id === editUser.tenant_id;
                  const tenantId = tenant.id.toString();
                  const isSelected = editUserForm.tenant_ids.includes(tenantId);
                  return (
                    <div key={tenant.id} className={`flex items-center justify-between space-x-2 ${isOwnOrg ? 'bg-gray-50' : ''} p-2 rounded`}>
                      <label className={`flex items-center space-x-2 ${isOwnOrg ? 'text-gray-600' : ''}`}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={!!isOwnOrg}
                          onChange={(e) => {
                            setEditUserForm(prev => {
                              if (e.target.checked) {
                                return {
                                  ...prev,
                                  tenant_ids: [...prev.tenant_ids, tenantId],
                                  primary_tenant_id: prev.primary_tenant_id || tenantId,
                                  tenant_roles: { ...prev.tenant_roles, [tenantId]: 'user' },
                                };
                              } else {
                                const newTenantIds = prev.tenant_ids.filter(id => id !== tenantId);
                                const newTenantRoles = { ...prev.tenant_roles };
                                delete newTenantRoles[tenantId];
                                return {
                                  ...prev,
                                  tenant_ids: newTenantIds,
                                  primary_tenant_id: prev.primary_tenant_id === tenantId ? newTenantIds[0] || '' : prev.primary_tenant_id,
                                  tenant_roles: newTenantRoles,
                                };
                              }
                            });
                          }}
                        />
                        <span className="text-sm">{tenant.name}{isOwnOrg ? ` (${t('superAdmin.home_organization_badge')})` : ''}</span>
                      </label>
                      {isSelected && (
                        <Select
                          value={editUserForm.tenant_roles[tenantId] || 'user'}
                          onValueChange={(value) => setEditUserForm(prev => ({
                            ...prev,
                            tenant_roles: { ...prev.tenant_roles, [tenantId]: value },
                          }))}
                        >
                          <SelectTrigger className="w-24">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="admin">{t('superAdmin.role_admin_label')}</SelectItem>
                            <SelectItem value="user">{t('superAdmin.role_user_label')}</SelectItem>
                            <SelectItem value="viewer">{t('superAdmin.role_viewer_label')}</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            <Button onClick={handleUpdateUser} className="w-full">{t('superAdmin.update_user_button')}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Dialog */}
      <Dialog open={!!userToDelete} onOpenChange={open => { if (!open) setUserToDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.delete_user_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>{String(t('superAdmin.delete_user_confirmation_text', { userEmail: userToDelete?.email || '' } as any))}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setUserToDelete(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmDeleteUser}>{t('superAdmin.delete_button')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
