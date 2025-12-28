import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Trash2, Edit, UserPlus, Building, Database, Users, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { toast } from 'sonner';
import { useTranslation } from "react-i18next";
import { superAdminApi, apiRequest } from '../lib/api';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';

interface Tenant {
  id: number;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  user_count: number;
  subdomain?: string;
  default_currency: string;
}

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  tenant_id: number;
  tenant_name: string;
  created_at: string;
}

interface DatabaseStatus {
  tenant_id: number;
  tenant_name: string;
  database_name: string;
  status: string;
  message?: string;
  error?: string;
}

const SuperAdminDashboard: React.FC = () => {
  const { user } = useAuth();
  const { t } = useTranslation();

  // Check if user is super admin BEFORE any hooks are called
  if (!user?.is_superuser) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-background flex items-center justify-center">
        <Alert className="max-w-md">
          <ShieldCheck className="h-4 w-4" />
          <AlertDescription>
            {t('superAdmin.need_super_admin_access')}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return <SuperAdminDashboardContent user={user} t={t} />;
};

// Separate component for the main dashboard content
const SuperAdminDashboardContent: React.FC<{ user: any; t: (key: string, options?: any) => string }> = ({ user, t }) => {
  // All hooks at the top!
  const { user: currentUser } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [databases, setDatabases] = useState<DatabaseStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('tenants');

  // Form states
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [selectedTenantForUsers, setSelectedTenantForUsers] = useState<Tenant | null>(null);
  const [createTenantForm, setCreateTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [createUserForm, setCreateUserForm] = useState({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {} });
  const [promoteEmail, setPromoteEmail] = useState('');
  const [promoteLoading, setPromoteLoading] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  // --- Add state for edit modals ---
  const [editTenant, setEditTenant] = useState<Tenant | null>(null);
  const [editTenantForm, setEditTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editUserForm, setEditUserForm] = useState({ first_name: '', last_name: '', email: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {} });

  // --- Add state for delete confirmation dialogs ---
  const [tenantToDelete, setTenantToDelete] = useState<Tenant | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Add state for recreate database confirmation
  const [dbToRecreate, setDbToRecreate] = useState<DatabaseStatus | null>(null);

  const fetchTenants = useCallback(async () => {
    try {
      const data = await apiRequest<Tenant[]>('/super-admin/tenants', {}, { skipTenant: true });
      setTenants(data);
    } catch (err) {
      setError('Failed to fetch tenants');
    }
  }, []);

  const fetchUsers = useCallback(async (tenantId?: number) => {
    try {
      const url = tenantId ? `/super-admin/users?tenant_id=${tenantId}` : '/super-admin/users';
      const data = await apiRequest<User[]>(url, {}, { skipTenant: true });
      setUsers(data);
    } catch (err) {
      setError('Failed to fetch users');
    }
  }, []);

  const fetchDatabaseOverview = useCallback(async () => {
    try {
      const data = await apiRequest<{ databases: DatabaseStatus[] }>('/super-admin/database/overview', {}, { skipTenant: true });
      setDatabases(data.databases || []);
    } catch (err) {
      setError('Failed to fetch database overview');
    }
  }, []);

  const handleCreateTenant = async () => {
    try {
      await apiRequest('/super-admin/tenants', {
        method: 'POST',
        body: JSON.stringify(createTenantForm)
      }, { skipTenant: true });

      setShowCreateTenant(false);
      setCreateTenantForm({ name: '', email: '', default_currency: 'USD' });
      toast.success('Organization created successfully');
      fetchTenants();
      fetchUsers(selectedTenantForUsers?.id); // Refresh users list to show the auto-created admin user
      fetchDatabaseOverview(); // Refresh databases list to show the new tenant database
    } catch (err: any) {
      const errorMessage = err?.detail || err?.message || 'Failed to create organization';

      // Handle validation errors with user-friendly messages
      if (errorMessage.includes('email') && errorMessage.includes('valid email address')) {
        toast.error('Please enter a valid email address');
      } else if (errorMessage.includes('email') && errorMessage.includes('already registered')) {
        toast.error('Email is already registered. Please use a different email.');
      } else if (errorMessage.includes('name') && errorMessage.includes('already exists')) {
        toast.error('Organization name already exists. Please choose a different name.');
      } else if (errorMessage.startsWith('Validation error:')) {
        toast.error('Please check your input and try again');
      } else {
        toast.error(errorMessage);
      }
    }
  };

  const handleCreateUser = async () => {
    try {
      await apiRequest('/super-admin/users', {
        method: 'POST',
        body: JSON.stringify(createUserForm)
      }, { skipTenant: true });

      setShowCreateUser(false);
      setCreateUserForm({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {} });
      toast.success('User created successfully');
      fetchUsers(selectedTenantForUsers?.id);
    } catch (err: any) {
      const errorMessage = err?.detail || err?.message || 'Failed to create user';
      toast.error(errorMessage);
    }
  };

  // --- Updated Delete Tenant Handler ---
  const handleDeleteTenant = (tenant: Tenant) => {
    setTenantToDelete(tenant);
  };
  const confirmDeleteTenant = async () => {
    if (!tenantToDelete) return;
    try {
      await apiRequest(`/super-admin/tenants/${tenantToDelete.id}`, {
        method: 'DELETE'
      }, { skipTenant: true });
      toast.success('Tenant deleted successfully');
      setTenantToDelete(null);
      // Remove tenant from state
      setTenants(prev => prev.filter(t => t.id !== tenantToDelete.id));
      // Refresh users and databases lists
      fetchUsers(selectedTenantForUsers?.id);
      fetchDatabaseOverview();
    } catch (err) {
      toast.error('Failed to delete tenant');
      setTenantToDelete(null);
    }
  };

  // --- Updated Delete User Handler ---
  const handleDeleteUser = (user: User) => {
    setUserToDelete(user);
  };
  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      await apiRequest(`/super-admin/users/${userToDelete.id}`, {
        method: 'DELETE'
      }, { skipTenant: true });
      toast.success('User deleted successfully');
      setUserToDelete(null);
      fetchUsers(selectedTenantForUsers?.id);
    } catch (err) {
      toast.error('Failed to delete user');
      setUserToDelete(null);
    }
  };

  const handleRecreateDatabase = (db: DatabaseStatus) => {
    setDbToRecreate(db);
  };
  const confirmRecreateDatabase = async () => {
    if (!dbToRecreate) return;
    try {
      await apiRequest(`/super-admin/tenants/${dbToRecreate.tenant_id}/database/recreate`, {
        method: 'POST'
      }, { skipTenant: true });
      toast.success('Database recreated successfully');
      setDbToRecreate(null);
      fetchDatabaseOverview();
    } catch (err) {
      toast.error('Failed to recreate database');
      setDbToRecreate(null);
    }
  };

  const handlePromote = async (e: React.FormEvent) => {
    e.preventDefault();
    setPromoteLoading(true);
    setPromoteError(null);
    try {
      const response = await fetch('/api/v1/super-admin/promote', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ email: promoteEmail })
      });
      let data: any = {};
      try {
        data = await response.json();
      } catch { }
      if (response.ok) {
        toast.success(data.message || 'User promoted to super admin!');
        setPromoteEmail('');
        setPromoteError(null);
        fetchUsers(selectedTenantForUsers?.id);
      } else {
        const errorMsg =
          (response.status === 404 && 'User does not exist') ||
          data.detail ||
          data.message ||
          'Failed to promote user';
        setPromoteError(errorMsg);
      }
    } catch (err) {
      setPromoteError('Failed to promote user');
    } finally {
      setPromoteLoading(false);
    }
  };

  // --- Edit Tenant Handler ---
  const handleEditTenant = (tenant: Tenant) => {
    setEditTenant(tenant);
    setEditTenantForm({
      name: tenant.name,
      email: tenant.email,
      default_currency: tenant.default_currency || 'USD',
    });
  };
  const handleUpdateTenant = async () => {
    if (!editTenant) return;
    try {
      const response = await fetch(`/api/v1/super-admin/tenants/${editTenant.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(editTenantForm)
      });
      if (!response.ok) throw new Error('Failed to update tenant');
      setEditTenant(null);
      toast.success('Tenant updated successfully');
      fetchTenants();
    } catch (err) {
      toast.error('Failed to update tenant');
    }
  };

  // --- Edit User Handler ---
  const handleEditUser = async (user: User) => {
    try {
      // Fetch detailed user info including tenant memberships
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
        first_name: userDetails.first_name,
        last_name: userDetails.last_name,
        email: userDetails.email,
        role: userDetails.role,
        password: '',
        tenant_ids: userDetails.tenant_ids || [userDetails.tenant_id.toString()],
        primary_tenant_id: userDetails.primary_tenant_id || userDetails.tenant_id.toString(),
        tenant_roles: userDetails.tenant_roles || {}
      });
    } catch (err) {
      toast.error('Failed to load user details');
      // Fallback to basic user info
      setEditUser(user);
      setEditUserForm({
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email,
        role: user.role,
        password: '',
        tenant_ids: [user.tenant_id.toString()],
        primary_tenant_id: user.tenant_id.toString(),
        tenant_roles: { [user.tenant_id.toString()]: user.role }
      });
    }
  };
  const handleUpdateUser = async () => {
    if (!editUser) return;
    try {
      // Store original values to compare for Organizations & Roles changes
      const originalTenantIds = editUserForm.tenant_ids;
      const originalPrimaryTenantId = editUserForm.primary_tenant_id;
      const originalTenantRoles = editUserForm.tenant_roles;

      const response = await fetch(`/api/v1/super-admin/users/${editUser.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(editUserForm)
      });
      if (!response.ok) throw new Error('Failed to update user');

      // Check if Organizations & Roles were changed
      const updatedData = await response.json();
      const orgRolesChanged =
        JSON.stringify(originalTenantIds) !== JSON.stringify(updatedData.tenant_ids || originalTenantIds) ||
        originalPrimaryTenantId !== updatedData.primary_tenant_id ||
        JSON.stringify(originalTenantRoles) !== JSON.stringify(updatedData.tenant_roles || originalTenantRoles);

      setEditUser(null);
      toast.success('User updated successfully');
      fetchUsers(selectedTenantForUsers?.id);

      // Refresh page if Organizations & Roles were changed
      if (orgRolesChanged) {
        window.location.reload();
      }
    } catch (err) {
      toast.error('Failed to update user');
    }
  };

  // Load initial data on component mount
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        await fetchTenants();
        await fetchUsers();
        await fetchDatabaseOverview();
      } catch (err) {
        console.error('SuperAdmin: Error loading initial data:', err);
        // Error is already handled by individual fetch functions
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []); // Empty dependency array - only run once on mount

  // Load users when selected tenant changes (but not on initial load)
  useEffect(() => {
    // Only fetch if selectedTenantForUsers has been explicitly changed by user
    // Skip the initial null state by checking if loading is complete
    if (!loading) {
      fetchUsers(selectedTenantForUsers?.id);
    }
  }, [selectedTenantForUsers, loading, fetchUsers]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Loading super admin dashboard...</p>
        </div>
      </div>
    );
  }

  const totalUsers = users.length;
  const activeTenants = tenants.filter(t => t.is_active).length;
  const healthyDatabases = databases.filter(db => db.status === 'connected').length;
  const superUsers = users.filter(u => u.is_superuser).length;
  const unhealthyDatabases = databases.filter(db => db.status !== 'connected');
  const systemHealthy = unhealthyDatabases.length === 0;

  // Find tenants whose email does not exist in the users list
  // Only compute this when viewing all organizations (no filter), since the users list is filtered otherwise
  const tenantEmailsMissingUsers = selectedTenantForUsers
    ? []
    : tenants.filter(
      t => t.email && !users.some(u => u.email === t.email)
    );

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('superAdmin.dashboard_title')}
          description={t('superAdmin.dashboard_description')}
        />

        {/* Alert for tenants whose email is missing in users */}
        {tenantEmailsMissingUsers.length > 0 && (
          <Alert className="mb-6" variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <b>{t('superAdmin.warning_tenant_email_missing')}:</b><br />
              <ul className="list-disc ml-6 mt-2">
                {tenantEmailsMissingUsers.map(t => (
                  <li key={t.id}>
                    <b>{t.name}</b>: <span className="text-red-600">{t.email}</span>
                  </li>
                ))}
              </ul>
              {t('superAdmin.tenant_admin_login_hint')}
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert className="mb-6" variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mb-8">
          <ProfessionalCard className="slide-in">
            <div className="p-6">
              <form onSubmit={handlePromote} className="flex flex-col md:flex-row items-center gap-4">
                <Label htmlFor="promote-email" className="font-medium">{t('superAdmin.promote_user_label')}</Label>
                <Input
                  id="promote-email"
                  type="email"
                  placeholder={t('superAdmin.promote_user_placeholder')}
                  value={promoteEmail}
                  onChange={e => {
                    setPromoteEmail(e.target.value);
                    setPromoteError(null);
                  }}
                  className="max-w-xs"
                  required
                />
                <Button type="submit" disabled={promoteLoading || !promoteEmail}>
                  {promoteLoading ? t('superAdmin.promoting_button') : t('superAdmin.promote_button')}
                </Button>
                {promoteError && (
                  <div className="text-red-600 text-sm mt-2" role="alert">{promoteError}</div>
                )}
              </form>
            </div>
          </ProfessionalCard>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <ProfessionalCard className="border border-border/50 hover:border-border/80 transition-all duration-200 slide-in">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('superAdmin.total_organizations_label')}</p>
                  <p className="text-2xl font-bold mt-1">{tenants.length}</p>
                </div>
                <Building className="h-8 w-8 text-primary/60" />
              </div>
              <p className="text-sm text-muted-foreground mt-3">{activeTenants} {t('superAdmin.active_label')}</p>
            </div>
          </ProfessionalCard>

          <ProfessionalCard className="border border-border/50 hover:border-border/80 transition-all duration-200 slide-in">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('superAdmin.total_users_label')}</p>
                  <p className="text-2xl font-bold mt-1">{totalUsers}</p>
                </div>
                <Users className="h-8 w-8 text-primary/60" />
              </div>
              <p className="text-sm text-muted-foreground mt-3">{superUsers} {t('superAdmin.super_users')}</p>
            </div>
          </ProfessionalCard>

          <ProfessionalCard className="border border-border/50 hover:border-border/80 transition-all duration-200 slide-in">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('superAdmin.databases_label')}</p>
                  <p className="text-2xl font-bold mt-1">{databases.length}</p>
                </div>
                <Database className="h-8 w-8 text-primary/60" />
              </div>
              <p className="text-sm text-muted-foreground mt-3">{healthyDatabases} {t('superAdmin.healthy_databases')}</p>
            </div>
          </ProfessionalCard>

          <ProfessionalCard className="border border-border/50 hover:border-border/80 transition-all duration-200 slide-in">
            <div className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{t('superAdmin.system_status_label')}</p>
                  <p className={`text-2xl font-bold mt-1 ${systemHealthy ? 'text-green-600' : 'text-red-600'}`}>
                    {systemHealthy ? t('superAdmin.all_systems_operational') : `${unhealthyDatabases.length} ${t('superAdmin.issues_detected')}`}
                  </p>
                </div>
                {systemHealthy ? (
                  <ShieldCheck className="h-8 w-8 text-green-600/60" />
                ) : (
                  <AlertTriangle className="h-8 w-8 text-red-600/60" />
                )}
              </div>
            </div>
          </ProfessionalCard>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3 bg-gradient-to-r from-muted/50 to-muted/30 border border-border/50 rounded-lg p-1">
            <TabsTrigger value="tenants" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">Organizations</TabsTrigger>
            <TabsTrigger value="users" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">{t('superAdmin.users_tab')}</TabsTrigger>
            <TabsTrigger value="databases" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">{t('superAdmin.databases_tab')}</TabsTrigger>
          </TabsList>

          <TabsContent value="tenants" className="space-y-4">
            <ProfessionalCard className="slide-in">
              <div className="p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-semibold">{t('superAdmin.organizations_management_title')}</h2>
                  <Dialog open={showCreateTenant} onOpenChange={setShowCreateTenant}>
                    <DialogTrigger asChild>
                      <Button>
                        <Building className="h-4 w-4 mr-2" />
                        {t('superAdmin.create_organization_button')}
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>{t('superAdmin.create_new_organization_title')}</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="tenant-name">{t('superAdmin.organization_name_label')}</Label>
                          <Input
                            id="tenant-name"
                            value={createTenantForm.name}
                            onChange={(e) => setCreateTenantForm(prev => ({ ...prev, name: e.target.value }))}
                            placeholder={t('superAdmin.organization_name_placeholder')}
                          />
                        </div>
                        <div>
                          <Label htmlFor="tenant-email">{t('superAdmin.email_label')}</Label>
                          <Input
                            id="tenant-email"
                            type="email"
                            value={createTenantForm.email}
                            onChange={(e) => setCreateTenantForm(prev => ({ ...prev, email: e.target.value }))}
                            placeholder={t('superAdmin.email_placeholder')}
                          />
                        </div>
                        <div>
                          <Label htmlFor="tenant-currency">{t('superAdmin.default_currency_label')}</Label>
                          <CurrencySelector
                            value={createTenantForm.default_currency}
                            onValueChange={(value) => setCreateTenantForm(prev => ({ ...prev, default_currency: value }))}
                            placeholder={t('superAdmin.select_currency')}
                          />
                        </div>
                        <Button onClick={handleCreateTenant} className="w-full">{t('superAdmin.create_organization_button')}</Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('superAdmin.name_header')}</TableHead>
                        <TableHead>{t('superAdmin.email_header')}</TableHead>
                        <TableHead>{t('superAdmin.users_header')}</TableHead>
                        <TableHead>{t('superAdmin.currency_header')}</TableHead>
                        <TableHead>{t('superAdmin.status_header')}</TableHead>
                        <TableHead>{t('superAdmin.created_at_header')}</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tenants
                        .slice()
                        .sort((a, b) => a.name.localeCompare(b.name))
                        .map((tenant) => (
                          <TableRow key={tenant.id}>
                            <TableCell className="font-medium">{tenant.name}</TableCell>
                            <TableCell>{tenant.email}</TableCell>
                            <TableCell>{tenant.user_count}</TableCell>
                            <TableCell>{tenant.default_currency}</TableCell>
                            <TableCell>
                              <Badge variant={tenant.is_active ? "default" : "secondary"}>
                                {tenant.is_active ? t('superAdmin.active_status') : t('superAdmin.inactive_status')}
                              </Badge>
                            </TableCell>
                            <TableCell>{new Date(tenant.created_at).toLocaleDateString()}</TableCell>
                            <TableCell>
                              <div className="flex space-x-2">
                                <Button size="sm" variant="outline" onClick={() => handleEditTenant(tenant)}>
                                  <Edit className="h-4 w-4" />
                                </Button>
                                {currentUser && tenant.id !== currentUser.tenant_id && (
                                  <Button
                                    size="sm"
                                    variant={tenant.is_active ? "destructive" : "default"}
                                    onClick={async () => {
                                      try {
                                        await apiRequest(`/super-admin/tenants/${tenant.id}/toggle-status`, {
                                          method: 'PATCH'
                                        }, { skipTenant: true });
                                        toast.success(`Organization ${tenant.is_active ? 'disabled' : 'enabled'} successfully`);
                                        fetchTenants();
                                      } catch (err) {
                                        toast.error('Failed to toggle organization status');
                                      }
                                    }}
                                  >
                                    {tenant.is_active ? t('superAdmin.disable_button') : t('superAdmin.enable_button')}
                                  </Button>
                                )}
                                {currentUser && tenant.id !== currentUser.tenant_id && (
                                  <Button size="sm" variant="outline" onClick={() => handleDeleteTenant(tenant)}>
                                    <Trash2 className="h-4 w-4" />
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
          </TabsContent>

          <TabsContent value="users" className="space-y-4">
            <ProfessionalCard className="slide-in">
              <div className="p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-semibold">{t('superAdmin.users_management_title')}</h2>
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <Label>{t('superAdmin.filter_by_organization')}</Label>
                      <Select value={selectedTenantForUsers?.id?.toString() || 'all'} onValueChange={(value) => setSelectedTenantForUsers(value === 'all' ? null : tenants.find(t => t.id.toString() === value) || null)}>
                        <SelectTrigger className="w-48">
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
                        <Button>
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
                          <div className="grid grid-cols-2 gap-4">
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
                                                tenant_roles: { ...prev.tenant_roles, [tenantId]: 'user' }
                                              };
                                            } else {
                                              const newTenantIds = prev.tenant_ids.filter(id => id !== tenantId);
                                              const newTenantRoles = { ...prev.tenant_roles };
                                              delete newTenantRoles[tenantId];
                                              return {
                                                ...prev,
                                                tenant_ids: newTenantIds,
                                                primary_tenant_id: prev.primary_tenant_id === tenantId ? newTenantIds[0] || '' : prev.primary_tenant_id,
                                                tenant_roles: newTenantRoles
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
                                          tenant_roles: { ...prev.tenant_roles, [tenantId]: value }
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

                          <div>
                            <Label htmlFor="user-password">{t('superAdmin.password_label')}</Label>
                            <Input
                              id="user-password"
                              type="password"
                              value={createUserForm.password}
                              onChange={(e) => setCreateUserForm(prev => ({ ...prev, password: e.target.value }))}
                              placeholder={t('superAdmin.password_placeholder')}
                            />
                          </div>
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
                          // Current user first
                          if (currentUser && a.id === currentUser.id) return -1;
                          if (currentUser && b.id === currentUser.id) return 1;
                          // Then sort by name
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
                              <Badge variant={user.is_active ? "default" : "secondary"}>
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
                                    variant={user.is_active ? "destructive" : "default"}
                                    onClick={async () => {
                                      try {
                                        await apiRequest(`/super-admin/users/${user.id}/toggle-status`, {
                                          method: 'PATCH'
                                        }, { skipTenant: true });
                                        toast.success(`User ${user.is_active ? 'disabled' : 'enabled'} successfully`);
                                        fetchUsers(selectedTenantForUsers?.id);
                                      } catch (err) {
                                        toast.error('Failed to toggle user status');
                                      }
                                    }}
                                  >
                                    {user.is_active ? t('superAdmin.disable_button') : t('superAdmin.enable_button')}
                                  </Button>
                                )}
                                {currentUser && user.id !== currentUser.id && (
                                  <Button size="sm" variant="outline" onClick={() => handleDeleteUser(user)}>
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
                                          fetchUsers(selectedTenantForUsers?.id);
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
          </TabsContent>

          <TabsContent value="databases" className="space-y-4">
            <ProfessionalCard className="slide-in">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-6">{t('superAdmin.database_management_title')}</h2>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('superAdmin.tenant_header')}</TableHead>
                        <TableHead>{t('superAdmin.database_header')}</TableHead>
                        <TableHead>{t('superAdmin.status_header')}</TableHead>
                        <TableHead>{t('superAdmin.message_header')}</TableHead>
                        <TableHead>{t('superAdmin.actions_header')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {databases.map((db) => (
                        <TableRow key={db.tenant_id}>
                          <TableCell className="font-medium">{db.tenant_name}</TableCell>
                          <TableCell>{db.database_name}</TableCell>
                          <TableCell>
                            <Badge variant={db.status === 'connected' ? 'default' : 'destructive'}>
                              {db.status}
                            </Badge>
                          </TableCell>
                          <TableCell>{db.message || db.error || '-'}</TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRecreateDatabase(db)}
                            >
                              <Database className="h-4 w-4 mr-2" />
                              {t('superAdmin.recreate_database_button')}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </ProfessionalCard>
          </TabsContent>
        </Tabs>
      </div>

      {/* Edit Tenant Dialog */}
      <Dialog open={!!editTenant} onOpenChange={open => { if (!open) setEditTenant(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.edit_organization_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-tenant-name">{t('superAdmin.organization_name_label')}</Label>
              <Input id="edit-tenant-name" value={editTenantForm.name} onChange={e => setEditTenantForm(prev => ({ ...prev, name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-email">{t('superAdmin.email_label')}</Label>
              <Input id="edit-tenant-email" type="email" value={editTenantForm.email} onChange={e => setEditTenantForm(prev => ({ ...prev, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-currency">{t('superAdmin.default_currency_label')}</Label>
              <CurrencySelector
                value={editTenantForm.default_currency}
                onValueChange={value => setEditTenantForm(prev => ({ ...prev, default_currency: value }))}
                placeholder={t('superAdmin.select_currency')}
              />
            </div>
            <Button onClick={handleUpdateTenant} className="w-full">{t('superAdmin.update_tenant_button')}</Button>
          </div>
        </DialogContent>
      </Dialog>

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
                          disabled={isOwnOrg}
                          onChange={(e) => {
                            setEditUserForm(prev => {
                              if (e.target.checked) {
                                return {
                                  ...prev,
                                  tenant_ids: [...prev.tenant_ids, tenantId],
                                  primary_tenant_id: prev.primary_tenant_id || tenantId,
                                  tenant_roles: { ...prev.tenant_roles, [tenantId]: 'user' }
                                };
                              } else {
                                const newTenantIds = prev.tenant_ids.filter(id => id !== tenantId);
                                const newTenantRoles = { ...prev.tenant_roles };
                                delete newTenantRoles[tenantId];
                                return {
                                  ...prev,
                                  tenant_ids: newTenantIds,
                                  primary_tenant_id: prev.primary_tenant_id === tenantId ? newTenantIds[0] || '' : prev.primary_tenant_id,
                                  tenant_roles: newTenantRoles
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
                            tenant_roles: { ...prev.tenant_roles, [tenantId]: value }
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

      {/* Delete Tenant Confirmation Dialog */}
      <Dialog open={!!tenantToDelete} onOpenChange={open => { if (!open) setTenantToDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.delete_tenant_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>{t('superAdmin.delete_tenant_confirmation_text', { tenantName: tenantToDelete?.name || '' } as any)}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setTenantToDelete(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmDeleteTenant}>{t('superAdmin.delete_button')}</Button>
            </div>
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
            <p>{t('superAdmin.delete_user_confirmation_text', { userEmail: userToDelete?.email || '' } as any)}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setUserToDelete(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmDeleteUser}>{t('superAdmin.delete_button')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Recreate Database Confirmation Dialog */}
      <Dialog open={!!dbToRecreate} onOpenChange={open => { if (!open) setDbToRecreate(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.recreate_database_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>{t('superAdmin.recreate_database_confirmation_text', { tenantName: dbToRecreate?.tenant_name || '' } as any)}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDbToRecreate(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmRecreateDatabase}>{t('superAdmin.recreate_button')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default function SuperAdminDashboardPage() {
  return (
    <SuperAdminDashboard />
  );
} 