import React, { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Building, Database, Users, ShieldCheck, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { MetricCard } from '@/components/ui/professional-card';
import { useTranslation } from 'react-i18next';
import { useFeatures } from '@/contexts/FeatureContext';
import { apiRequest } from '../lib/api';
import { PageHeader } from '@/components/ui/professional-layout';
import { TenantLicenseMonitoring } from './TenantLicenseMonitoring';
import { TenantsTab } from './SuperAdmin/TenantsTab';
import { UsersTab } from './SuperAdmin/UsersTab';
import { DatabasesTab } from './SuperAdmin/DatabasesTab';
import { AnomaliesTab } from './SuperAdmin/AnomaliesTab';
import { PluginsTab } from './SuperAdmin/PluginsTab';
import type { Tenant, User, DatabaseStatus } from './SuperAdmin/types';

const SuperAdminDashboard: React.FC = () => {
  const { user } = useAuth();
  const { t } = useTranslation();

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

  return <SuperAdminDashboardContent />;
};

const SuperAdminDashboardContent: React.FC = () => {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const isAnomaliesEnabled = isFeatureEnabled('anomaly_detection');

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [databases, setDatabases] = useState<DatabaseStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('tenants');
  const [selectedTenantForUsers, setSelectedTenantForUsers] = useState<Tenant | null>(null);
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

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        await Promise.all([fetchTenants(), fetchUsers(), fetchDatabaseOverview()]);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  useEffect(() => {
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

  const activeTenants = tenants.filter(t => t.is_active && !t.is_archived).length;
  const archivedTenants = tenants.filter(t => t.is_archived).length;
  const healthyDatabases = databases.filter(db => db.status === 'connected').length;
  const superUsers = users.filter(u => u.is_superuser).length;
  const unhealthyDatabases = databases.filter(db => db.status !== 'connected');
  const systemHealthy = unhealthyDatabases.length === 0;

  const tenantEmailsMissingUsers = selectedTenantForUsers
    ? []
    : tenants.filter(t => t.email && !users.some(u => u.email === t.email));

  return (
    <div className="h-full space-y-6 fade-in">
      <PageHeader
        title={t('superAdmin.dashboard_title')}
        description={t('superAdmin.dashboard_description')}
      />

      {tenantEmailsMissingUsers.length > 0 && (
        <Alert className="mb-6" variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <b>{t('superAdmin.warning_tenant_email_missing')}:</b><br />
            <ul className="list-disc ml-6 mt-2">
              {tenantEmailsMissingUsers.map(tenant => (
                <li key={tenant.id}>
                  <b>{tenant.name}</b>: <span className="text-red-600">{tenant.email}</span>
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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          title={t('superAdmin.total_organizations_label')}
          value={tenants.length}
          icon={Building}
          description={`${activeTenants} ${t('superAdmin.active_label')}${archivedTenants ? `, ${archivedTenants} archived` : ''}`}
        />
        <MetricCard
          title={t('superAdmin.total_users_label')}
          value={users.length}
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

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full tabs-professional">
        <TabsList className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 h-auto p-1.5 bg-muted/50 rounded-xl border border-border/50">
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
          <TabsTrigger value="plugins" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.plugins_tab')}</TabsTrigger>
          <TabsTrigger value="licensing" className="text-xs md:text-sm min-w-0 flex-shrink-0 gap-2 rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium justify-center">{t('superAdmin.licensing_tab')}</TabsTrigger>
        </TabsList>

        <TabsContent value="tenants" className="space-y-4">
          <TenantsTab
            tenants={tenants}
            selectedTenantForUsersId={selectedTenantForUsers?.id}
            onTenantsChanged={fetchTenants}
            onUsersChanged={fetchUsers}
            onDatabasesChanged={fetchDatabaseOverview}
          />
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <UsersTab
            users={users}
            tenants={tenants}
            selectedTenantForUsers={selectedTenantForUsers}
            onSelectedTenantChange={setSelectedTenantForUsers}
            onUsersChanged={fetchUsers}
          />
        </TabsContent>

        <TabsContent value="databases" className="space-y-4">
          <DatabasesTab
            databases={databases}
            onDatabasesChanged={fetchDatabaseOverview}
          />
        </TabsContent>

        <TabsContent value="anomalies" className="space-y-4">
          <AnomaliesTab onTotalChange={setTotalAnomalies} />
        </TabsContent>

        <TabsContent value="plugins" className="space-y-4">
          <PluginsTab tenants={tenants} />
        </TabsContent>

        <TabsContent value="licensing" className="space-y-4">
          <TenantLicenseMonitoring />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default function SuperAdminDashboardPage() {
  return <SuperAdminDashboard />;
}
