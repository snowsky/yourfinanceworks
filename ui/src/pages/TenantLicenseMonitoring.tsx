import React, { useState, useEffect } from 'react';
import { useTranslation } from "react-i18next";
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Shield, Users, Building, AlertTriangle, CheckCircle2, Key, Info, Lock, Globe, Save, Trash2, Loader2 } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from 'sonner';
import { superAdminApi, api } from '@/lib/api';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalTextarea } from '@/components/ui/professional-textarea';
import { useFeatures } from '@/contexts/FeatureContext';

interface TenantLicenseInfo {
  id: number;
  name: string;
  is_active: boolean;
  is_enabled: boolean;
  count_against_license: boolean;
}

interface UserLicenseInfo {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  count_against_license: boolean;
  tenant_name?: string;
  tenant_count_against_license?: boolean;
  effectively_exempt?: boolean;
}

interface GlobalLicenseStatus {
  is_licensed: boolean;
  license_status: string;
  effective_source: string;
  global_license_info?: {
    customer_name: string;
    expires_at: string;
    max_tenants: number;
    license_scope?: string;
  };
  enabled_features: string[];
  user_licensing_info?: {
    max_users: number | null;
    current_users_count: number;
  };
}

export const TenantLicenseMonitoring: React.FC = () => {
  const { t } = useTranslation();
  const { refetch: refetchFeatures } = useFeatures();
  const [tenants, setTenants] = useState<TenantLicenseInfo[]>([]);
  const [users, setUsers] = useState<UserLicenseInfo[]>([]);
  const [status, setStatus] = useState<GlobalLicenseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [globalKey, setGlobalKey] = useState('');
  const [activating, setActivating] = useState(false);
  const [deactivatingGlobal, setDeactivatingGlobal] = useState(false);
  const [showDeactivateGlobalDialog, setShowDeactivateGlobalDialog] = useState(false);
  
  // Signup control states
  const [allowPasswordSignup, setAllowPasswordSignup] = useState(true);
  const [allowSsoSignup, setAllowSsoSignup] = useState(true);
  const [maxTenantsManual, setMaxTenantsManual] = useState<number>(0);
  const [maxUsersManual, setMaxUsersManual] = useState<number>(0);
  const [savingSettings, setSavingSettings] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tenantsData, usersData, statusData, signupSettings] = await Promise.all([
        superAdminApi.getTenantLicenseMonitoring(),
        superAdminApi.getUserLicenseMonitoring(),
        api.get<GlobalLicenseStatus>('/license/status'),
        superAdminApi.getGlobalSignupSettings()
      ]);
      setTenants(tenantsData);
      setUsers(usersData);
      setStatus(statusData);
      setAllowPasswordSignup(signupSettings.allow_password_signup);
      setAllowSsoSignup(signupSettings.allow_sso_signup);
      setMaxTenantsManual(signupSettings.max_tenants || 0);
      setMaxUsersManual(statusData.user_licensing_info?.max_users || 0);
    } catch (err) {
      toast.error(t('superAdmin.license_capacity_monitoring.load_error', 'Failed to load license monitoring data'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpdateTenantExemption = async (tenantId: number, counts: boolean) => {
    try {
      await superAdminApi.updateTenantCapacityControl(tenantId, counts);
      toast.success(counts ? t('superAdmin.license_capacity_monitoring.tenant_counts_license', 'Tenant now counts against license') : t('superAdmin.license_capacity_monitoring.tenant_exempt_license', 'Tenant now exempt from license'));
      setTenants(prev => prev.map(t => t.id === tenantId ? { ...t, count_against_license: counts } : t));
    } catch (err) {
      toast.error(t('superAdmin.license_capacity_monitoring.update_exemption_error', 'Failed to update tenant exemption'));
    }
  };

  const handleUpdateUserExemption = async (userId: number, counts: boolean) => {
    try {
      await superAdminApi.updateUserCapacityControl(userId, counts);
      toast.success(counts ? t('superAdmin.license_capacity_monitoring.user_counts_license', 'User now counts against license') : t('superAdmin.license_capacity_monitoring.user_exempt_license', 'User now exempt from license'));
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, count_against_license: counts } : u));
      // Refresh status to update totals
      const statusData = await api.get<GlobalLicenseStatus>('/license/status');
      setStatus(statusData);
    } catch (err) {
      toast.error(t('superAdmin.license_capacity_monitoring.update_user_exemption_error', 'Failed to update user exemption'));
    }
  };

  const handleActivateGlobal = async () => {
    if (!globalKey.trim()) return;
    setActivating(true);
    try {
      const result = await superAdminApi.activateGlobalLicense(globalKey.trim());
      if (result.success) {
        toast.success(t('superAdmin.license_capacity_monitoring.global_license_activated', 'Global license activated successfully'));
        setGlobalKey('');
        fetchData();
        // Refresh feature context so all tenants see the new global license features
        await refetchFeatures();
      } else {
        toast.error(result.message || t('superAdmin.license_capacity_monitoring.activation_failed', 'Activation failed'));
      }
    } catch (err: any) {
      toast.error(err.message || t('superAdmin.license_capacity_monitoring.activate_global_error', 'Failed to activate global license'));
    } finally {
      setActivating(false);
    }
  };

  const handleDeactivateGlobal = async () => {
    setDeactivatingGlobal(true);
    try {
      const result = await superAdminApi.deactivateGlobalLicense();
      if (result.success) {
        toast.success(t('superAdmin.license_capacity_monitoring.global_license_deactivated', 'Global license deactivated successfully'));
        fetchData();
        // Refresh feature context so all tenants see the updated license status
        await refetchFeatures();
      } else {
        toast.error(result.message || t('superAdmin.license_capacity_monitoring.deactivation_failed', 'Deactivation failed'));
      }
    } catch (err: any) {
      toast.error(err.message || t('superAdmin.license_capacity_monitoring.deactivate_global_error', 'Failed to deactivate global license'));
    } finally {
      setDeactivatingGlobal(false);
      setShowDeactivateGlobalDialog(false);
    }
  };

  const handleUpdateSignupSettings = async (type: 'password' | 'sso' | 'max_tenants' | 'max_users', value: any) => {
    setSavingSettings(true);
    try {
      let settings = {};
      if (type === 'password') settings = { allow_password_signup: value };
      else if (type === 'sso') settings = { allow_sso_signup: value };
      else if (type === 'max_tenants') settings = { max_tenants: parseInt(value) };
      else if (type === 'max_users') settings = { max_users: parseInt(value) };
      
      await superAdminApi.updateGlobalSignupSettings(settings);
      
      if (type === 'password') setAllowPasswordSignup(value);
      else if (type === 'sso') setAllowSsoSignup(value);
      else if (type === 'max_tenants') {
        setMaxTenantsManual(parseInt(value));
        fetchData(); // Refresh to update overview
      }
      else if (type === 'max_users') {
        setMaxUsersManual(parseInt(value));
        fetchData(); // Refresh to update overview
      }
      
      toast.success(t('superAdmin.license_capacity_monitoring.settings_updated', 'Global settings updated'));
    } catch (err) {
      toast.error(t('superAdmin.license_capacity_monitoring.update_settings_error', 'Failed to update global settings'));
    } finally {
      setSavingSettings(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
    </div>
  );

  const countedTenantCount = tenants.filter(t => t.count_against_license).length;
  const maxTenants = status?.global_license_info?.max_tenants || 0;
  const isOverLimit = maxTenants > 0 && countedTenantCount > maxTenants;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('superAdmin.license_capacity_monitoring.title')}
        description={t('superAdmin.license_capacity_monitoring.description')}
      />

      {/* Global License Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ProfessionalCard variant="elevated">
          <ProfessionalCardHeader>
            <ProfessionalCardTitle className="flex items-center">
              <Shield className="h-5 w-5 mr-2 text-primary" />
              {t('superAdmin.license_capacity_monitoring.global_license_status')}
            </ProfessionalCardTitle>
          </ProfessionalCardHeader>
          <ProfessionalCardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                <span className="text-sm font-medium">{t('superAdmin.license_capacity_monitoring.status')}</span>
                <div className="flex items-center gap-2">
                  <Badge variant={status?.global_license_info ? "default" : "secondary"}>
                    {status?.global_license_info ? t('superAdmin.license_capacity_monitoring.active') : t('superAdmin.license_capacity_monitoring.inactive')}
                  </Badge>
                </div>
              </div>
              
              {status?.global_license_info && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">{t('superAdmin.license_capacity_monitoring.customer')}</span>
                    <span className="text-sm font-medium">{status.global_license_info.customer_name}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">{t('superAdmin.license_capacity_monitoring.expires_at')}</span>
                    <span className="text-sm font-medium">
                      {new Date(status.global_license_info.expires_at).toLocaleDateString()}
                    </span>
                  </div>
                  {status.global_license_info.license_scope && (
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">{t('superAdmin.license_capacity_monitoring.license_scope')}</span>
                      <Badge variant="outline" className="text-xs">
                        {status.global_license_info.license_scope === "global" ? t('superAdmin.license_capacity_monitoring.system_wide') : t('superAdmin.license_capacity_monitoring.local')}
                      </Badge>
                    </div>
                  )}
                </>
              )}

              <div className="flex justify-between items-center border-t pt-4">
                <span className="text-sm font-medium">{t('superAdmin.license_capacity_monitoring.capacity_usage')}</span>
                <div className="text-right">
                  <span className={`text-lg font-bold ${isOverLimit ? 'text-destructive' : 'text-primary'}`}>
                    {countedTenantCount}
                  </span>
                  <span className="text-sm text-muted-foreground"> / {maxTenants || 'Unlimited'} {t('superAdmin.license_capacity_monitoring.organizations')}</span>
                </div>
              </div>

              {status?.user_licensing_info && (
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">{t('superAdmin.license_capacity_monitoring.user_capacity_usage', 'User Capacity Usage')}</span>
                  <div className="text-right">
                    <span className={`text-lg font-bold ${status.user_licensing_info.max_users && status.user_licensing_info.current_users_count > status.user_licensing_info.max_users ? 'text-destructive' : 'text-primary'}`}>
                      {status.user_licensing_info.current_users_count}
                    </span>
                    <span className="text-sm text-muted-foreground"> / {status.user_licensing_info.max_users || 'Unlimited'} {t('superAdmin.license_capacity_monitoring.users', 'Users')}</span>
                  </div>
                </div>
              )}

              {isOverLimit && (
                <div className="p-3 bg-destructive/10 text-destructive rounded-lg flex items-start gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  <p>{t('superAdmin.license_capacity_monitoring.capacity_exceeded')}</p>
                </div>
              )}
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>

        {/* Activate Global License */}
        <ProfessionalCard>
          <ProfessionalCardHeader>
            <ProfessionalCardTitle className="flex items-center">
              <Key className="h-5 w-5 mr-2 text-primary" />
              {t('superAdmin.license_capacity_monitoring.system_wide_activation')}
            </ProfessionalCardTitle>
          </ProfessionalCardHeader>
          <ProfessionalCardContent>
            <div className="space-y-4">
              <div className="p-3 bg-blue-50 text-blue-800 rounded-lg flex items-start gap-2 text-xs">
                <Info className="h-4 w-4 shrink-0" />
                <p>{t('superAdmin.license_capacity_monitoring.global_license_info')}</p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="global-key">{t('superAdmin.license_capacity_monitoring.license_key')}</Label>
                <ProfessionalTextarea
                  id="global-key"
                  placeholder={t('superAdmin.license_capacity_monitoring.license_key_placeholder')}
                  value={globalKey}
                  onChange={(e) => setGlobalKey(e.target.value)}
                  className="font-mono text-xs h-24"
                />
              </div>
              
              <div className="flex gap-2">
                <ProfessionalButton 
                  onClick={handleActivateGlobal} 
                  className="flex-1"
                  loading={activating}
                  disabled={!globalKey.trim()}
                >
                  {t('superAdmin.license_capacity_monitoring.activate_system_wide')}
                </ProfessionalButton>

                {status?.global_license_info && (
                  <AlertDialog open={showDeactivateGlobalDialog} onOpenChange={setShowDeactivateGlobalDialog}>
                    <AlertDialogTrigger asChild>
                      <ProfessionalButton 
                        variant="outline"
                        className="text-destructive border-destructive/20 hover:bg-destructive/10 hover:text-destructive shadow-sm"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        {t('superAdmin.license_capacity_monitoring.deactivate')}
                      </ProfessionalButton>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('superAdmin.license_capacity_monitoring.deactivate_system_wide_license')}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t('superAdmin.license_capacity_monitoring.deactivate_system_wide_description')}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                        <AlertDialogAction 
                          onClick={handleDeactivateGlobal} 
                          disabled={deactivatingGlobal}
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                          {deactivatingGlobal ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                          {t('superAdmin.license_capacity_monitoring.confirm_deactivation')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )}
              </div>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      </div>

      {/* Global Signup Controls */}
      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center">
            <Lock className="h-5 w-5 mr-2 text-primary" />
            {t('superAdmin.license_capacity_monitoring.global_signup_controls')}
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="flex items-center justify-between p-4 border rounded-xl bg-muted/10">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" />
                  <span className="font-semibold text-sm">{t('superAdmin.license_capacity_monitoring.password_registration')}</span>
                </div>
                <p className="text-xs text-muted-foreground">{t('superAdmin.license_capacity_monitoring.password_registration_description')}</p>
              </div>
              <Switch 
                checked={allowPasswordSignup} 
                onCheckedChange={(val) => handleUpdateSignupSettings('password', val)}
                disabled={savingSettings}
              />
            </div>
            
            <div className="flex items-center justify-between p-4 border rounded-xl bg-muted/10">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Globe className="h-4 w-4 text-muted-foreground" />
                  <span className="font-semibold text-sm">{t('superAdmin.license_capacity_monitoring.sso_registration')}</span>
                </div>
                <p className="text-xs text-muted-foreground">{t('superAdmin.license_capacity_monitoring.sso_registration_description')}</p>
              </div>
              <Switch 
                checked={allowSsoSignup} 
                onCheckedChange={(val) => handleUpdateSignupSettings('sso', val)}
                disabled={savingSettings}
              />
            </div>
          </div>
          
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8 border-t pt-8">
            <div className="space-y-2">
              <Label htmlFor="max-tenants-manual" className="flex items-center gap-2">
                <Building className="h-4 w-4 text-muted-foreground" />
                {t('superAdmin.license_capacity_monitoring.max_organizations_limit', 'Max Organizations Limit')}
              </Label>
              <div className="flex gap-2">
                <input
                  id="max-tenants-manual"
                  type="number"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  value={maxTenantsManual}
                  onChange={(e) => setMaxTenantsManual(parseInt(e.target.value) || 0)}
                  disabled={savingSettings}
                />
                <ProfessionalButton
                  size="sm"
                  onClick={() => handleUpdateSignupSettings('max_tenants', maxTenantsManual)}
                  disabled={savingSettings}
                >
                  {t('common.save', 'Save')}
                </ProfessionalButton>
              </div>
              <p className="text-xs text-muted-foreground">{t('superAdmin.license_capacity_monitoring.max_tenants_description', 'Manually override the system-wide organization limit.')}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-users-manual" className="flex items-center gap-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                {t('superAdmin.license_capacity_monitoring.max_users_limit', 'Max Users Limit')}
              </Label>
              <div className="flex gap-2">
                <input
                  id="max-users-manual"
                  type="number"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  value={maxUsersManual}
                  onChange={(e) => setMaxUsersManual(parseInt(e.target.value) || 0)}
                  disabled={savingSettings}
                />
                <ProfessionalButton
                  size="sm"
                  onClick={() => handleUpdateSignupSettings('max_users', maxUsersManual)}
                  disabled={savingSettings}
                >
                  {t('common.save', 'Save')}
                </ProfessionalButton>
              </div>
              <p className="text-xs text-muted-foreground">{t('superAdmin.license_capacity_monitoring.max_users_description', 'Manually override the system-wide user limit.')}</p>
            </div>
          </div>

          <div className="mt-8 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-800 space-y-1">
              <p className="font-bold uppercase tracking-tight">{t('superAdmin.license_capacity_monitoring.important_security_note')}</p>
              <p>{t('superAdmin.license_capacity_monitoring.security_note_description')}</p>
              <p>{t('superAdmin.license_capacity_monitoring.initial_admin_note')}</p>
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      {/* User Capacity Control Section */}
      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center">
            <Users className="h-5 w-5 mr-2 text-primary" />
            {t('superAdmin.license_capacity_monitoring.user_capacity_control', 'User Capacity Control')}
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.user', 'User')}</TableHead>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.email', 'Email')}</TableHead>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.organization', 'Organization')}</TableHead>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.status', 'Status')}</TableHead>
                  <TableHead className="w-[300px]">{t('superAdmin.license_capacity_monitoring.capacity_control', 'Capacity Control')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.first_name} {user.last_name}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-sm">{user.tenant_name || '-'}</span>
                        {user.tenant_count_against_license === false && (
                          <span className="text-[10px] text-amber-600 font-medium leading-none mt-1">
                            {t('superAdmin.license_capacity_monitoring.org_exempted', 'Org Exempted')}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant={user.is_active ? "default" : "secondary"}>
                          {user.is_active ? t('superAdmin.license_capacity_monitoring.active', 'Active') : t('common.inactive', 'Inactive')}
                        </Badge>
                        {user.effectively_exempt && user.count_against_license && (
                          <Badge variant="outline" className="text-[9px] h-4 bg-amber-50 text-amber-700 border-amber-200">
                             {t('superAdmin.license_capacity_monitoring.inherited_exempt', 'Inherited Exempt')}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <RadioGroup
                        value={user.count_against_license ? "counts" : "exempt"}
                        onValueChange={(val) => handleUpdateUserExemption(user.id, val === "counts")}
                        className="flex items-center gap-4"
                      >
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="counts" id={`user-counts-${user.id}`} />
                          <Label htmlFor={`user-counts-${user.id}`} className="cursor-pointer">{t('superAdmin.license_capacity_monitoring.counts', 'Counts')}</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="exempt" id={`user-exempt-${user.id}`} />
                          <Label htmlFor={`user-exempt-${user.id}`} className="cursor-pointer font-semibold text-primary">{t('superAdmin.license_capacity_monitoring.exempt', 'Exempt')}</Label>
                        </div>
                      </RadioGroup>
                    </TableCell>
                  </TableRow>
                ))}
                {users.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                      {t('superAdmin.license_capacity_monitoring.no_users_found', 'No users found')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      {/* Organization Capacity Control Section */}
      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center">
            <Building className="h-5 w-5 mr-2 text-primary" />
            {t('superAdmin.license_capacity_monitoring.organization_capacity_control', 'Organization Capacity Control')}
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.organization', 'Organization')}</TableHead>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.status', 'Status')}</TableHead>
                  <TableHead>{t('superAdmin.license_capacity_monitoring.capacity_status', 'Capacity Status')}</TableHead>
                  <TableHead className="w-[300px]">{t('superAdmin.license_capacity_monitoring.capacity_control', 'Capacity Control')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell className="font-medium">{tenant.name}</TableCell>
                    <TableCell>
                      <Badge variant={tenant.is_active ? "default" : "secondary"}>
                        {tenant.is_active ? t('superAdmin.license_capacity_monitoring.active', 'Active') : t('common.inactive', 'Inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={tenant.is_enabled ? "default" : "destructive"}>
                        {tenant.is_enabled ? t('superAdmin.license_capacity_monitoring.active', 'Active') : t('common.inactive', 'Inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 text-sm">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{tenant.count_against_license ? t('superAdmin.license_capacity_monitoring.counts_against_limit', 'Counts against limit') : t('superAdmin.license_capacity_monitoring.exempt', 'Exempt')}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <RadioGroup
                        value={tenant.count_against_license ? "counts" : "exempt"}
                        onValueChange={(val) => handleUpdateTenantExemption(tenant.id, val === "counts")}
                        className="flex items-center gap-4"
                      >
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="counts" id={`counts-${tenant.id}`} />
                          <Label htmlFor={`counts-${tenant.id}`} className="cursor-pointer">{t('superAdmin.license_capacity_monitoring.counts', 'Counts')}</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="exempt" id={`exempt-${tenant.id}`} />
                          <Label htmlFor={`exempt-${tenant.id}`} className="cursor-pointer font-semibold text-primary">{t('superAdmin.license_capacity_monitoring.exempt', 'Exempt')}</Label>
                        </div>
                      </RadioGroup>
                    </TableCell>
                  </TableRow>
                ))}
                {tenants.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center h-24 text-muted-foreground">
                      {t('superAdmin.license_capacity_monitoring.no_organizations_found', 'No organizations found')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    </div>
  );
};
