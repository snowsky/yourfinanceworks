import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Trash2, Edit, UserPlus, Building, Database, Users, ShieldCheck, AlertTriangle, Eye, RotateCcw, Shield } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { MetricCard } from '@/components/ui/professional-card';
import { toast } from 'sonner';
import { useTranslation } from "react-i18next";
import { useFeatures } from '@/contexts/FeatureContext';
import { superAdminApi, apiRequest } from '../lib/api';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { FeatureGate } from '@/components/FeatureGate';
import { TenantLicenseMonitoring } from './TenantLicenseMonitoring';

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

interface Anomaly {
  id: number;
  tenant_id: number;
  tenant_name: string;
  entity_type: string;
  entity_id: number;
  risk_score: number;
  risk_level: string;
  reason: string;
  rule_id: string;
  details: any;
  created_at: string;
}

const SuperAdminDashboard: React.FC = () => {
  const { user, refreshAuth } = useAuth();
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

  return <SuperAdminDashboardContent user={user} refreshAuth={refreshAuth} t={t} />;
};

// Separate component for the main dashboard content
const SuperAdminDashboardContent: React.FC<{ user: any; refreshAuth: () => void; t: (key: string, options?: any) => string }> = ({ user, refreshAuth, t }) => {
  // All hooks at the top!
  const { user: currentUser } = useAuth();
  const { isFeatureEnabled } = useFeatures();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [databases, setDatabases] = useState<DatabaseStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('tenants');

  const isAnomaliesEnabled = isFeatureEnabled('anomaly_detection');

  // Form states
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [selectedTenantForUsers, setSelectedTenantForUsers] = useState<Tenant | null>(null);
  const [createTenantForm, setCreateTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [createUserForm, setCreateUserForm] = useState({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {}, is_sso: false });
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

  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);

  // Pagination for anomalies
  const [anomaliesPage, setAnomaliesPage] = useState(1);
  const [anomaliesPageSize, setAnomaliesPageSize] = useState(20);
  const [totalAnomalies, setTotalAnomalies] = useState(0);

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

  const fetchAnomalies = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      const skip = (anomaliesPage - 1) * anomaliesPageSize;
      params.set('skip', skip.toString());
      params.set('limit', anomaliesPageSize.toString());

      const queryString = params.toString();
      const data = await apiRequest<{
        items: Anomaly[];
        total: number;
        skip: number;
        limit: number;
      }>(`/super-admin/anomalies${queryString ? `?${queryString}` : ''}`, {}, { skipTenant: true });

      setAnomalies(data.items || []);
      setTotalAnomalies(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
      setAnomalies([]);
      setTotalAnomalies(0);
    }
  }, [anomaliesPage, anomaliesPageSize]);

  const handleRunAudit = async () => {
    try {
      const result = await apiRequest<{ message: string }>(
        '/super-admin/anomalies/audit',
        { method: 'POST' },
        { skipTenant: true }
      );
      toast.success(result.message);
      fetchAnomalies();
    } catch (err) {
      toast.error('Failed to trigger platform audit scan');
    }
  };

  const handleReprocessAll = async () => {
    try {
      const result = await apiRequest<{ message: string }>(
        '/super-admin/anomalies/reprocess',
        { method: 'POST' },
        { skipTenant: true }
      );
      toast.success(result.message);
      fetchAnomalies();
    } catch (err) {
      toast.error('Failed to trigger reprocess scan');
    }
  };

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
      setCreateUserForm({ email: '', first_name: '', last_name: '', role: 'user', password: '', tenant_ids: [], primary_tenant_id: '', tenant_roles: {}, is_sso: false });
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

  const handleToggleTenantStatus = async (tenant: Tenant) => {
    try {
      await apiRequest(`/super-admin/tenants/${tenant.id}/toggle-status`, {
        method: 'PATCH'
      }, { skipTenant: true });
      toast.success(`Organization ${tenant.is_active ? 'disabled' : 'enabled'} successfully`);
      fetchTenants();
    } catch (err) {
      toast.error('Failed to toggle organization status');
    }
  };

  const handleToggleUserStatus = async (user: User) => {
    try {
      await apiRequest(`/super-admin/users/${user.id}/toggle-status`, {
        method: 'PATCH'
      }, { skipTenant: true });
      toast.success(`User ${user.is_active ? 'disabled' : 'enabled'} successfully`);
      fetchUsers(selectedTenantForUsers?.id);
    } catch (err) {
      toast.error('Failed to toggle user status');
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
      const data = await apiRequest<{ message: string }>('/super-admin/promote', {
        method: 'POST',
        body: JSON.stringify({ email: promoteEmail })
      }, { skipTenant: true });

      toast.success(data.message || 'User promoted to super admin!');
      setPromoteEmail('');
      setPromoteError(null);
      fetchUsers(selectedTenantForUsers?.id);
    } catch (err: any) {
      const errorMsg = err?.detail || err?.message || 'Failed to promote user';
      setPromoteError(errorMsg);
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
      await apiRequest(`/super-admin/tenants/${editTenant.id}`, {
        method: 'PUT',
        body: JSON.stringify(editTenantForm)
      }, { skipTenant: true });

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
        first_name: userDetails.first_name || '',
        last_name: userDetails.last_name || '',
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
        first_name: user.first_name || '',
        last_name: user.last_name || '',
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
      await apiRequest<any>(`/super-admin/users/${editUser.id}`, {
        method: 'PUT',
        body: JSON.stringify(editUserForm)
      }, { skipTenant: true });

      setEditUser(null);
      toast.success('User updated successfully');
      fetchUsers(selectedTenantForUsers?.id);

      // Refresh auth state if the edited user is the same as the logged-in user
      if (currentUser && editUser.id === currentUser.id) {
        refreshAuth();
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
        const fetches: Promise<void>[] = [fetchTenants(), fetchUsers(), fetchDatabaseOverview()];
        if (isAnomaliesEnabled) {
          fetches.push(fetchAnomalies());
        }
        await Promise.all(fetches);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isAnomaliesEnabled]); // Only refetch all data when feature status changes

  // Separate useEffect for anomalies pagination
  useEffect(() => {
    if (isAnomaliesEnabled) {
      fetchAnomalies();
    }
  }, [anomaliesPage, anomaliesPageSize, isAnomaliesEnabled]);

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
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading super admin dashboard...</p>
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

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title={t('superAdmin.total_organizations_label')}
            value={tenants.length}
            icon={Building}
            description={`${activeTenants} ${t('superAdmin.active_label')}`}
          />
          <MetricCard
            title={t('superAdmin.total_users_label')}
            value={totalUsers}
            icon={Users}
            description={`${superUsers} ${t('superAdmin.super_users')}`}
          />
          <MetricCard
            title={t('superAdmin.databases_label')}
            value={databases.length}
            icon={Database}
            description={`${healthyDatabases} ${t('superAdmin.healthy_databases')}`}
            variant={healthyDatabases < databases.length ? 'warning' : 'default'}
          />
          <MetricCard
            title={t('superAdmin.system_status_label')}
            value={systemHealthy ? t('superAdmin.all_systems_operational') : `${unhealthyDatabases.length} ${t('superAdmin.issues_detected')}`}
            icon={systemHealthy ? ShieldCheck : AlertTriangle}
            variant={systemHealthy ? 'success' : 'danger'}
          />
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full tabs-professional">
          <TabsList className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 h-auto p-1.5 bg-muted/50 rounded-xl border border-border/50">
            <TabsTrigger value="tenants" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.organizations_tab')}</TabsTrigger>
            <TabsTrigger value="users" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.users_tab')}</TabsTrigger>
            <TabsTrigger value="databases" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.databases_tab')}</TabsTrigger>
            <TabsTrigger value="anomalies" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center flex items-center gap-2">
              {t('superAdmin.financeworks_insights_tab')}
              {isAnomaliesEnabled && totalAnomalies > 0 && (
                <Badge variant="destructive" className="ml-1 h-5 px-1.5 flex items-center justify-center text-[10px]">
                  {totalAnomalies}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="licensing" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.licensing_tab')}</TabsTrigger>
          </TabsList>

          <TabsContent value="tenants" className="space-y-4">
            <ProfessionalCard className="slide-in">
              <div className="p-6">
                <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
                  <h2 className="text-xl font-semibold">{t('superAdmin.organizations_management_title')}</h2>
                  <Dialog open={showCreateTenant} onOpenChange={setShowCreateTenant}>
                    <DialogTrigger asChild>
                      <Button className="w-full sm:w-auto">
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
                                    onClick={() => handleToggleTenantStatus(tenant)}
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
              <div className="p-6 border-b border-border/50">
                <form onSubmit={handlePromote} className="flex flex-col md:flex-row items-center gap-4">
                  <Label htmlFor="promote-email" className="font-medium whitespace-nowrap">{t('superAdmin.promote_user_label')}</Label>
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
                      <Select value={selectedTenantForUsers?.id?.toString() || 'all'} onValueChange={(value) => setSelectedTenantForUsers(value === 'all' ? null : tenants.find(t => t.id.toString() === value) || null)}>
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

                          {/* SSO Option */}
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

                          {/* Password Field - Only show for non-SSO users */}
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

                          {/* SSO Info Message - Show for SSO users */}
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
                                    onClick={() => handleToggleUserStatus(user)}
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
                            {currentUser && db.tenant_id !== currentUser.tenant_id ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRecreateDatabase(db)}
                              >
                                <Database className="h-4 w-4 mr-2" />
                                {t('superAdmin.recreate_database_button')}
                              </Button>
                            ) : (
                              <div className="text-sm text-muted-foreground italic">
                                {t('superAdmin.own_database')}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </ProfessionalCard>
          </TabsContent>


          <TabsContent value="anomalies" className="space-y-4">
            <FeatureGate
              feature="anomaly_detection"
              fallback={
                <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
                  <div className="p-12 text-center">
                    <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                      <AlertTriangle className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                    </div>
                    <h3 className="text-2xl font-bold text-foreground mb-3">{t('superAdmin.business_license_required')}</h3>
                    <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                      {t('superAdmin.business_license_description')}
                    </p>
                    <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                      <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                        <Shield className="h-4 w-4 text-primary" />
                        {t('superAdmin.with_business_license_get')}
                      </h4>
                      <ul className="text-left space-y-3 text-sm text-foreground/80">
                        <li className="flex items-start">
                          <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                          <span>{t('superAdmin.ai_powered_anomaly_detection')}</span>
                        </li>
                        <li className="flex items-start">
                          <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                          <span>{t('superAdmin.senior_forensic_auditor_ai')}</span>
                        </li>
                        <li className="flex items-start">
                          <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                          <span>{t('superAdmin.risk_scoring_intelligent_fraud_detection')}</span>
                        </li>
                        <li className="flex items-start">
                          <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                          <span>{t('superAdmin.cross_tenant_anomaly_monitoring')}</span>
                        </li>
                      </ul>
                    </div>
                    <div className="flex justify-center gap-4">
                      <Button
                        className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white"
                        onClick={() => window.location.href = '/settings?tab=license'}
                        size="lg"
                      >
                        {t('superAdmin.upgrade_to_business_license')}
                      </Button>
                    </div>
                  </div>
                </ProfessionalCard>
              }
            >
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="lg:col-span-3">
                  <ProfessionalCard className="slide-in">
                    <div className="p-6">
                      <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-5 w-5 text-red-500" />
                          <h2 className="text-xl font-semibold">{t('superAdmin.flagged_high_risk_items')}</h2>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={fetchAnomalies}>
                            <Database className="h-4 w-4 mr-2" />
                            {t('superAdmin.refresh_list')}
                          </Button>
                          <Button variant="outline" size="sm" onClick={handleReprocessAll} className="bg-orange-600 hover:bg-orange-700 text-white">
                            <RotateCcw className="h-4 w-4 mr-2" />
                            {t('superAdmin.reprocess_all')}
                          </Button>
                          <Button variant="default" size="sm" onClick={handleRunAudit} className="bg-red-600 hover:bg-red-700 text-white">
                            <ShieldCheck className="h-4 w-4 mr-2" />
                            {t('superAdmin.run_audit_scan')}
                          </Button>
                        </div>
                      </div>

                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Date</TableHead>
                            <TableHead>Organization</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Risk Level</TableHead>
                            <TableHead>Audit Reason</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {anomalies.length === 0 ? (
                            <TableRow>
                              <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                                {t('superAdmin.no_high_risk_items')}
                              </TableCell>
                            </TableRow>
                          ) : (
                            anomalies.map((anomaly) => (
                              <TableRow key={`${anomaly.tenant_id}-${anomaly.id}`}>
                                <TableCell className="whitespace-nowrap">
                                  {new Date(anomaly.created_at).toLocaleDateString()}
                                </TableCell>
                                <TableCell className="font-medium">{anomaly.tenant_name}</TableCell>
                                <TableCell className="capitalize">{anomaly.entity_type.replace('_', ' ')}</TableCell>
                                <TableCell>
                                  <Badge variant={
                                    anomaly.risk_level === 'critical' || anomaly.risk_level === 'high' 
                                      ? 'destructive' 
                                      : anomaly.risk_level === 'medium' 
                                        ? 'default' 
                                        : 'secondary'
                                  }>
                                    {anomaly.risk_level}
                                  </Badge>
                                </TableCell>
                                <TableCell className="max-w-md truncate" title={anomaly.reason}>
                                  {anomaly.reason}
                                </TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setSelectedAnomaly(anomaly)}
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))
                          )}
                        </TableBody>
                      </Table>

                      {/* Pagination */}
                      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
                        <div className="text-sm text-muted-foreground">
                          Showing <span className="font-medium text-foreground">{anomalies.length}</span> of <span className="font-medium text-foreground">{totalAnomalies}</span> results
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAnomaliesPage(prev => Math.max(1, prev - 1))}
                            disabled={anomaliesPage <= 1}
                            className="h-9 px-4"
                          >
                            {t('common.previous')}
                          </Button>
                          <div className="flex items-center gap-1">
                            {Array.from({ length: Math.ceil(totalAnomalies / anomaliesPageSize) }, (_, i) => i + 1)
                              .filter(p => p === 1 || p === Math.ceil(totalAnomalies / anomaliesPageSize) || Math.abs(p - anomaliesPage) <= 1)
                              .map((p, i, arr) => (
                                <div key={p} className="flex items-center">
                                  {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                                  <Button
                                    variant={anomaliesPage === p ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => setAnomaliesPage(p)}
                                    className="h-9 w-9 p-0"
                                  >
                                    {p}
                                  </Button>
                                </div>
                              ))}
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAnomaliesPage(prev => Math.min(Math.ceil(totalAnomalies / anomaliesPageSize), prev + 1))}
                            disabled={anomaliesPage >= Math.ceil(totalAnomalies / anomaliesPageSize)}
                            className="h-9 px-4"
                          >
                            {t('common.next')}
                          </Button>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
                          <Select value={String(anomaliesPageSize)} onValueChange={(v) => { setAnomaliesPageSize(Number(v)); setAnomaliesPage(1); }}>
                            <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="10">10</SelectItem>
                              <SelectItem value="20">20</SelectItem>
                              <SelectItem value="50">50</SelectItem>
                              <SelectItem value="100">100</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  </div>
                </ProfessionalCard>
              </div>

              <div className="lg:col-span-1">
                <ProfessionalCard className="bg-primary/5 border-primary/20 sticky top-6 slide-in">
                  <div className="p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <ShieldCheck className="h-5 w-5 text-primary" />
                      <h3 className="font-semibold text-primary">{t('superAdmin.auditor_recommendations')}</h3>
                    </div>
                    <div className="space-y-4">
                      <div className="text-sm">
                        <p className="font-medium text-primary/80 mb-1">{t('superAdmin.recommended_next_steps')}</p>
                        <ul className="list-disc pl-4 space-y-2 text-muted-foreground">
                          <li>{t('superAdmin.review_digital_audit_trail')}</li>
                          <li>{t('superAdmin.correlate_round_number_trends')}</li>
                          <li>{t('superAdmin.verify_physical_receipts')}</li>
                          <li>{t('superAdmin.cross_reference_split_transactions')}</li>
                        </ul>
                      </div>
                      <div className="pt-4 border-t border-primary/10">
                        <div className="p-3 bg-white/50 dark:bg-black/20 rounded-lg border border-primary/10">
                          <p className="text-[10px] uppercase tracking-wider font-bold text-primary/60 mb-1">{t('superAdmin.ai_insights_status')}</p>
                          <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-xs font-medium">{t('superAdmin.senior_forensic_auditor_active')}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </ProfessionalCard>
              </div>
            </div>
            </FeatureGate>
          </TabsContent>

          <TabsContent value="licensing" className="space-y-4">
            <TenantLicenseMonitoring />
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

      {/* Anomaly Details Dialog */}
      <Dialog open={!!selectedAnomaly} onOpenChange={open => { if (!open) setSelectedAnomaly(null); }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              Anomaly Details
            </DialogTitle>
          </DialogHeader>
          {selectedAnomaly && (
            <div className="space-y-6">
              {/* Basic Information */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Organization</Label>
                  <p className="font-semibold">{selectedAnomaly.tenant_name}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Entity Type</Label>
                  <p className="font-semibold capitalize">{selectedAnomaly.entity_type.replace('_', ' ')}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Entity ID</Label>
                  <p className="font-semibold">{selectedAnomaly.entity_id}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Detected On</Label>
                  <p className="font-semibold">{new Date(selectedAnomaly.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              {/* Risk Assessment */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Risk Assessment</Label>
                <div className="flex items-center gap-4">
                  <Badge variant={
                    selectedAnomaly.risk_level === 'critical' || selectedAnomaly.risk_level === 'high' 
                      ? 'destructive'
                      : selectedAnomaly.risk_level === 'medium'
                        ? 'default'
                        : 'secondary'
                  }>
                    {selectedAnomaly.risk_level.toUpperCase()}
                  </Badge>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Risk Score:</span>
                    <span className="font-semibold">{selectedAnomaly.risk_score}/100</span>
                  </div>
                </div>
              </div>

              {/* Detection Rule */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Detection Rule</Label>
                <p className="font-mono text-sm bg-muted/50 p-2 rounded">{selectedAnomaly.rule_id}</p>
              </div>

              {/* Reason */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Anomaly Reason</Label>
                <p className="text-sm leading-relaxed">{selectedAnomaly.reason}</p>
              </div>

              {/* Search Information */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Search Information</Label>
                <div className="bg-muted/30 p-3 rounded-lg">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="font-medium">Record Type:</span>
                      <span className="ml-2 capitalize">{selectedAnomaly.entity_type.replace('_', ' ')}</span>
                    </div>
                    <div>
                      <span className="font-medium">Record ID:</span>
                      <span className="ml-2">{selectedAnomaly.entity_id}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Use this information to search for the record in the respective {selectedAnomaly.entity_type.replace('_', ' ')} section.
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="secondary" onClick={() => setSelectedAnomaly(null)}>
                  Close
                </Button>
                {(() => {
                  const currentTenantId = localStorage.getItem('selected_tenant_id') || user?.tenant_id?.toString();
                  const isFromCurrentTenant = selectedAnomaly.tenant_id.toString() === currentTenantId;

                  if (isFromCurrentTenant) {
                    return (
                      <Button
                        onClick={() => {
                          // Navigate to the specific entity for further investigation
                          const entityType = selectedAnomaly.entity_type;
                          const entityId = selectedAnomaly.entity_id;
                          const path = `/${entityType}s/view/${entityId}`;
                          window.open(path, '_blank');
                        }}
                      >
                        Investigate Entity
                      </Button>
                    );
                  } else {
                    return (
                      <Button
                        variant="outline"
                        disabled
                        title={`This anomaly is from ${selectedAnomaly.tenant_name}. Switch to that organization to investigate.`}
                      >
                        Investigate Entity
                      </Button>
                    );
                  }
                })()}
              </div>
            </div>
          )}
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