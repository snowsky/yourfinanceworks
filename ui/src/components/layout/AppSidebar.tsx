
import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useIsMobile } from "@/hooks/use-mobile";

import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { HelpCenter } from "@/components/onboarding/HelpCenter";
import {
  BarChart,
  ChevronLeft,
  DollarSign,
  FileText,
  LogOut,
  Settings,
  Users,
  UserCheck,
  ShieldCheck,
  ListChecks,
  Moon,
  Sun,
  Trash2,
  Bot
} from "lucide-react";
import { API_BASE_URL, settingsApi, apiRequest } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { createSettingsQueryOptions } from "@/utils/query";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Building } from 'lucide-react';
import { toast } from 'sonner';

export function AppSidebar() {
  const { state } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const [open, setOpen] = useState(!isMobile);
  const [forceUpdate, setForceUpdate] = useState(0);
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') || 'system';
    }
    return 'system';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (theme === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
    localStorage.setItem('theme', theme);
    // Optionally: update user profile theme in backend here
  }, [theme]);

  // Get current user data from localStorage
  const user = getCurrentUser();
  const userRole = user?.role || 'user';
  const [effectiveRole, setEffectiveRole] = useState<string>(userRole);
  const [roleLoading, setRoleLoading] = useState(true);
  const isAdminEffective = effectiveRole === 'admin';
  const showAnalytics = (user as any)?.show_analytics !== false;
  const [isSuperUser, setIsSuperUser] = useState(false);

  // Organization switching state
  const [userOrganizations, setUserOrganizations] = useState([]);
  const initialOrgId = (() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('selected_tenant_id');
      if (stored) return stored;
    }
    return user?.tenant_id?.toString() || '';
  })();
  const [currentOrgId, setCurrentOrgId] = useState(initialOrgId);
  const [isSwitchingOrg, setIsSwitchingOrg] = useState(false);
  
  // Check super admin status via API
  useEffect(() => {
    const checkSuperAdminStatus = async () => {
      if (!user?.is_superuser) {
        setIsSuperUser(false);
        return;
      }

      const isInPrimaryTenant = currentOrgId === user?.tenant_id?.toString();
      setIsSuperUser(user.is_superuser && isInPrimaryTenant);
    };

    checkSuperAdminStatus();
  }, [currentOrgId, user?.is_superuser, user?.tenant_id]);
  
  console.log('Sidebar: User check:', { 
    user, 
    userRole, 
    effectiveRole,
    isAdminEffective,
    isSuperUser,
    currentOrgId,
    primaryTenant: user?.tenant_id?.toString(),
    shouldFetchSettings: isAdminEffective 
  });

  // Get company name from settings with moderate refetching (only for admin users)
  // Note: We conditionally define the query to prevent API calls for non-admin users
  const { data: settings, isLoading: settingsLoading, refetch } = useQuery({
    queryKey: ['settings', forceUpdate], // Include forceUpdate in query key to force refetch
    queryFn: () => {
      console.log('Sidebar: Refetching settings data, forceUpdate:', forceUpdate);
      return settingsApi.getSettings();
    },
    refetchInterval: 30000, // 30 seconds
    refetchOnWindowFocus: true,
    refetchOnMount: true,
    refetchOnReconnect: true,
    refetchIntervalInBackground: false,
    staleTime: 0,
    enabled: (!roleLoading && isAdminEffective), // Only fetch settings after role is known and admin in current org
    retry: (failureCount, error: any) => {
      // Don't retry on authentication/authorization errors
      if (error?.message?.includes('403') || error?.message?.includes('401')) {
        return false;
      }
      return failureCount < 3;
    },
  });

  // Fetch effective role for current organization (uses X-Tenant-ID header automatically)
  useEffect(() => {
    const fetchEffectiveRole = async () => {
      setRoleLoading(true);
      try {
        // Ensure X-Tenant-ID header reflects currentOrgId by stashing it before the call
        if (typeof window !== 'undefined' && currentOrgId) {
          localStorage.setItem('selected_tenant_id', currentOrgId);
        }
        const me: any = await apiRequest('/auth/me');
        if (me && me.role) {
          setEffectiveRole(me.role);
          
          // Update localStorage with the effective role for this organization
          // so that auth utility functions use the correct role
          const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
          if (currentUser && currentUser.role !== me.role) {
            console.log(`🔄 Role updated: ${currentUser.role} → ${me.role} for org ${currentOrgId}`);
            const updatedUser = { ...currentUser, role: me.role };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            
            // Trigger auth refresh for other components
            window.dispatchEvent(new CustomEvent('auth-updated'));
          }
        } else {
          setEffectiveRole(userRole);
        }
      } catch {
        setEffectiveRole(userRole);
      } finally {
        setRoleLoading(false);
      }
    };
    fetchEffectiveRole();
  }, [currentOrgId, userRole]);

  // Get company name from current organization or settings
  const companyName = (() => {
    if (userOrganizations.length > 0) {
      const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);
      if (currentOrg) {
        return currentOrg.name;
      }
    }
    return settings?.company_info?.name || 'InvoiceApp';
  })();
  const companyLogoUrl = settings?.company_info?.logo;
  // Normalize tenant id types for safe comparisons
  const userTenantIdStr = user?.tenant_id != null ? String(user.tenant_id) : '';
  const isPrimaryTenant = currentOrgId === userTenantIdStr;

  // Debug logging
  useEffect(() => {
    console.log('Sidebar: Settings data changed:', {
      companyName,
      settings: settings?.company_info,
      settingsFull: settings,
      forceUpdate,
      userOrganizations: userOrganizations.length,
      currentOrgId,
      selectedTenantId: localStorage.getItem('selected_tenant_id'),
      timestamp: new Date().toISOString()
    });
  }, [settings, companyName, forceUpdate, userOrganizations, currentOrgId]);

  // Fetch user's organizations
  useEffect(() => {
    const fetchUserOrganizations = async () => {
      if (!user?.id) {
        console.log('No user ID available, skipping organization fetch');
        return;
      }

      console.log('🏢 Fetching organizations for user:', user.email);

      try {
        type Org = { id: number; name: string };
        type MeResponse = { organizations?: Org[] };
        const response = await apiRequest('/auth/me', {}, { skipTenant: true });
        const me = response as MeResponse;
        const orgs = me.organizations ?? [];
        console.log('📋 User organizations response:', me);

        if (orgs.length > 0) {
          console.log(`✅ User has access to ${orgs.length} organizations:`, orgs);
          setUserOrganizations(orgs);

          // Use selected tenant from localStorage or default to user's primary tenant
          let selectedTenantId = localStorage.getItem('selected_tenant_id');
          console.log('🔍 Selected tenant from localStorage:', selectedTenantId);

          // If no selected tenant, default to user's primary tenant
          if (!selectedTenantId) {
            selectedTenantId = user.tenant_id?.toString();
            console.log('🏠 Using user primary tenant:', selectedTenantId);
          } else {
            // Verify user has access to the selected tenant
            const hasAccess = orgs.some(org => org.id.toString() === selectedTenantId);
            if (!hasAccess) {
              console.warn(`⚠️ User doesn't have access to tenant ${selectedTenantId}, resetting to primary tenant`);
              localStorage.removeItem('selected_tenant_id');
              selectedTenantId = user.tenant_id?.toString();
            } else {
              console.log('✅ User has access to selected tenant:', selectedTenantId);
            }
          }

          console.log(`🎯 Setting current org ID to: ${selectedTenantId}`);
          setCurrentOrgId(selectedTenantId || user.tenant_id?.toString() || '');

          // Store the selected tenant if not already stored
          if (selectedTenantId && !localStorage.getItem('selected_tenant_id')) {
            localStorage.setItem('selected_tenant_id', selectedTenantId);
            console.log('💾 Stored selected tenant ID:', selectedTenantId);
          }
        } else {
          console.log('⚠️ No organizations found in response, using fallback');
          // Fallback to single organization and clear invalid tenant ID
          localStorage.removeItem('selected_tenant_id');
          const currentOrg = {
            id: user.tenant_id,
            name: settings?.company_info?.name || 'Current Organization'
          };
          setUserOrganizations([currentOrg]);
          setCurrentOrgId(user.tenant_id?.toString() || '');
          console.log('🔄 Set fallback organization:', currentOrg);
        }
      } catch (err) {
        console.error('❌ Failed to fetch user organizations:', err);
        // Fallback to single organization and clear invalid tenant ID
        localStorage.removeItem('selected_tenant_id');
        const currentOrg = {
          id: user.tenant_id,
          name: settings?.company_info?.name || 'Current Organization'
        };
        setUserOrganizations([currentOrg]);
        setCurrentOrgId(user.tenant_id?.toString() || '');
        console.log('🔄 Set error fallback organization:', currentOrg);
      }
    };
    
    fetchUserOrganizations();
  }, [user?.id, user?.tenant_id, settings?.company_info?.name]);
  
  const handleOrganizationSwitch = async (orgId: string) => {
    if (orgId === currentOrgId) return;
    
    const selectedOrg = userOrganizations.find(org => org.id.toString() === orgId);
    const orgName = selectedOrg?.name || `Organization ${orgId}`;
    
    console.log(`🔄 Switching organization from ${currentOrgId} to ${orgId} (${orgName})`);
    setIsSwitchingOrg(true);
    
    try {
      // Show loading toast
      toast.loading(`Switching to ${orgName}...`, { id: 'org-switch' });
      
      // Store the selected organization
      localStorage.setItem('selected_tenant_id', orgId);
      console.log(`✅ Stored selected_tenant_id: ${orgId}`);
      
      // Store the selected organization
      localStorage.setItem('selected_tenant_id', orgId);
      localStorage.removeItem('react-query-offline-cache');
      console.log(`✅ Stored selected_tenant_id: ${orgId}`);
      
      // Clear all cached data and force reload
      queryClient.clear();
      queryClient.invalidateQueries();
      sessionStorage.clear();
      console.log('🗑️ Cleared all caches');
      
      // Show success toast
      toast.success(`Switched to ${orgName}`, { id: 'org-switch' });
      
      // Reload page
      setTimeout(() => {
        window.location.reload();
      }, 100);
    } catch (error) {
      console.error('❌ Error during organization switch:', error);
      toast.error('Failed to switch organization', { id: 'org-switch' });
      setIsSwitchingOrg(false);
    }
  };


  // Also try a direct approach - listen for localStorage changes
  useEffect(() => {
    const checkForUpdates = () => {
      const lastUpdate = localStorage.getItem('settings_updated');
      if (lastUpdate) {
        console.log('Sidebar: Detected settings update via localStorage');
        setForceUpdate(prev => prev + 1);
      }
    };

    // Check immediately
    checkForUpdates();
    
    // Set up interval to check for updates
    const interval = setInterval(checkForUpdates, 5000); // Check every 5 seconds
    
    return () => clearInterval(interval);
  }, []);

  // Listen for settings updates and force refetch
  useEffect(() => {
    const handleSettingsUpdate = () => {
      console.log('Sidebar: Settings update event received');
      // Force refetch settings when they're updated
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      queryClient.refetchQueries({ queryKey: ['settings'] });
      // Force component re-render
      setForceUpdate(prev => prev + 1);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'settings_updated') {
        console.log('Sidebar: Storage event received for settings update');
        handleSettingsUpdate();
      }
    };

    // Listen for both custom events and storage events
    window.addEventListener('settings-updated', handleSettingsUpdate);
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('settings-updated', handleSettingsUpdate);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [queryClient]);

  const handleLogout = () => {
    // Clear authentication data
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    
    // Clear React Query cache to prevent 403 errors
    queryClient.clear();
    
    // Redirect to login page
    navigate('/login');
  };

  const mainMenuItems = [
    { 
      path: '/', 
      label: t('navigation.dashboard'),
      icon: <BarChart className="w-5 h-5" /> 
    },
    { 
      path: '/clients', 
      label: t('navigation.clients'),
      icon: <Users className="w-5 h-5" />,
      tourId: 'nav-clients'
    },
    { 
      path: '/invoices', 
      label: t('navigation.invoices'),
      icon: <FileText className="w-5 h-5" />,
      tourId: 'nav-invoices'
    },
    { 
      path: '/payments', 
      label: t('navigation.payments'),
      icon: <DollarSign className="w-5 h-5" />,
      tourId: 'nav-payments'
    },
    { 
      path: '/expenses', 
      label: t('navigation.expenses'),
      icon: <DollarSign className="w-5 h-5" />,
      tourId: 'nav-expenses'
    },
    { 
      path: '/bank-statements', 
      label: t('navigation.bank_statements'),
      icon: <FileText className="w-5 h-5" />,
      tourId: 'nav-bank-statements'
    },

    // Users, Audit Log, and Analytics moved under Settings; remove from main nav
  ];

  const settingsMenuItems = [
    // Only show Settings for admin users in their owned organization
    ...((!roleLoading && isAdminEffective && isPrimaryTenant) ? [{ 
      path: '/settings',
      label: t('navigation.settings'),
      icon: <Settings className="w-5 h-5" />,
      tourId: 'nav-settings'
    }] : []),
    // Users is now a sub-entry under Settings for admins
    ...((!roleLoading && isAdminEffective) ? [{
      path: '/users',
      label: t('navigation.users'),
      icon: <UserCheck className="w-5 h-5" />
    }] : []),
    // Only show Audit Log for admin or superuser
    ...((!roleLoading && (isAdminEffective || isSuperUser)) ? [{
      path: '/audit-log',
      label: t('navigation.audit_log'),
      icon: <ListChecks className="w-5 h-5" />
    }] : []),
    // Only show Analytics for admin or superuser if user has enabled it
    ...((!roleLoading && (isAdminEffective || isSuperUser) && showAnalytics) ? [{
      path: '/analytics',
      label: 'Analytics',
      icon: <BarChart className="w-5 h-5" />
    }] : []),
    // Only show Super Admin for super users in their primary tenant
    ...((user?.is_superuser && isPrimaryTenant) ? [{ 
      path: '/super-admin', 
      label: t('navigation.super_admin'), 
      icon: <ShieldCheck className="w-5 h-5" /> 
    }] : [])
  ];

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <>
      <Sidebar data-tour="sidebar" className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 shadow-2xl">
        <SidebarHeader className="py-8 px-6 border-b border-slate-700/50 bg-gradient-to-r from-slate-800/50 to-slate-700/50">
          {/* Professional Company Logo Section */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              {companyLogoUrl ? (
                <img
                  src={companyLogoUrl.startsWith('http') ? companyLogoUrl : `${API_BASE_URL}${companyLogoUrl}`}
                  alt={`${companyName} Logo`}
                  className="h-12 w-12 object-contain rounded-xl shadow-lg ring-2 ring-blue-500/20"
                  onError={(e) => {
                    console.error('Failed to load company logo:', e);
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ) : (
                <div className="h-12 w-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg ring-2 ring-blue-500/20">
                  <Building className="h-6 w-6 text-white" />
                </div>
              )}
              <div className="flex flex-col leading-tight">
                <span className="text-lg font-bold text-white truncate max-w-[140px] tracking-tight">
                  {companyName}
                </span>
                <span className="text-sm text-slate-300 font-medium">
                  Invoice Management
                </span>
              </div>
            </div>
            <SidebarTrigger>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Toggle sidebar"
                className="text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-lg transition-all duration-200"
              >
                <ChevronLeft className="h-5 w-5" />
              </Button>
            </SidebarTrigger>
          </div>
          
          {/* Professional User Profile Section */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
            <div className="flex items-center gap-3">
              <Avatar className="h-10 w-10 ring-2 ring-slate-600/50">
                <AvatarImage src={undefined as any} alt={user?.email || 'User'} />
                <AvatarFallback className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-sm font-bold">
                  {(() => {
                    const first = (user?.first_name || '').trim();
                    const last = (user?.last_name || '').trim();
                    const name = `${first} ${last}`.trim() || (user?.email?.split('@')[0] || 'User');
                    const parts = name.split(' ').filter(Boolean);
                    const initials = parts.length >= 2 ? `${parts[0][0]}${parts[1][0]}` : name.slice(0, 2);
                    return initials.toUpperCase();
                  })()}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col leading-tight flex-1 min-w-0">
                <span className="text-sm font-bold text-white truncate">
                  {(() => {
                    const first = (user?.first_name || '').trim();
                    const last = (user?.last_name || '').trim();
                    const name = `${first} ${last}`.trim();
                    return name || (user?.email?.split('@')[0] || 'User');
                  })()}
                </span>
                <span className="text-xs text-slate-300 truncate">
                  {user?.email}
                </span>
              </div>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent className="pt-8 px-4">
          {/* Organization Selector */}
          {userOrganizations.length > 0 && (
            <div className="mb-6">
              <div className="px-3 mb-3">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Organization {userOrganizations.length > 1 ? `(${userOrganizations.length} available)` : ''}
                </h3>
              </div>
              <div className="px-3">
                <Select value={currentOrgId} onValueChange={handleOrganizationSwitch} disabled={isSwitchingOrg}>
                  <SelectTrigger className="w-full bg-slate-800/50 border-slate-700/50 text-white hover:bg-slate-700/50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <Building className="w-4 h-4 text-slate-300" />
                      {isSwitchingOrg ? (
                        <span className="text-sm">Switching...</span>
                      ) : (
                        <SelectValue placeholder="Select organization" />
                      )}
                    </div>
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700/50">
                    {userOrganizations.sort((a, b) => a.name.localeCompare(b.name)).map((org) => (
                      <SelectItem key={org.id} value={org.id.toString()} className="text-white hover:bg-slate-700/50">
                        <div className="flex items-center justify-between w-full">
                          <span>
                            {org.name}
                            {org.id === user?.tenant_id && (
                              <span className="text-xs text-blue-500 ml-1">(Home)</span>
                            )}
                          </span>
                          {org.id.toString() === currentOrgId && (
                            <span className="text-xs text-green-500 ml-2">✓</span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          
          <SidebarMenu className="space-y-2">
            {/* Main Navigation Section */}
            <div className="mb-6">
              <div className="px-3 mb-3">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Main Navigation
                </h3>
              </div>
              {mainMenuItems.map((item) => (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    className={`mx-2 rounded-xl transition-all duration-200 ${
                      isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20 transform scale-105"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/50 hover:transform hover:scale-105"
                    }`}
                    isActive={isActive(item.path)}
                  >
                    <Link
                      to={item.path}
                      className="flex items-center gap-4 w-full h-full py-3 px-4"
                      data-tour={item.tourId}
                    >
                      <div className={`p-2 rounded-lg ${
                        isActive(item.path)
                          ? "bg-white/20"
                          : "bg-slate-700/50 group-hover:bg-slate-600/50"
                      }`}>
                        {item.icon}
                      </div>
                      <span className="font-medium">{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </div>

            {/* Professional Separator */}
            <div className="my-6 px-3">
              <div className="border-t border-slate-700/50"></div>
            </div>
            
            {/* Settings Section */}
            <div>
              <div className="px-3 mb-3">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  System
                </h3>
              </div>
              {settingsMenuItems.map((item) => (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    className={`mx-2 rounded-xl transition-all duration-200 ${
                      isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20 transform scale-105"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/50 hover:transform hover:scale-105"
                    }`}
                    isActive={isActive(item.path)}
                  >
                    <Link
                      to={item.path}
                      className="flex items-center gap-4 w-full h-full py-3 px-4"
                      data-tour={item.tourId}
                    >
                      <div className={`p-2 rounded-lg ${
                        isActive(item.path)
                          ? "bg-white/20"
                          : "bg-slate-700/50 group-hover:bg-slate-600/50"
                      }`}>
                        {item.icon}
                      </div>
                      <span className="font-medium">{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </div>
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter className="py-6 px-6 border-t border-slate-700/50 bg-gradient-to-r from-slate-800/50 to-slate-700/50">
          {/* Professional Controls Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex-1">
                <LanguageSwitcher />
              </div>
              <Button
                variant="outline"
                size="icon"
                aria-label={t('navigation.dark_mode')}
                title={t('navigation.dark_mode')}
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="border-slate-600/50 bg-slate-700/50 hover:bg-slate-600/50 text-slate-300 hover:text-white transition-all duration-200 rounded-lg"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </Button>
            </div>

            {/* Professional Logout Button */}
            <Button
              variant="destructive"
              size="sm"
              className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-medium py-3 rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              <span>{t('auth.logout')}</span>
            </Button>
          </div>
        </SidebarFooter>
        {/* Always-available thin rail to toggle when sidebar is hidden */}
        <SidebarRail />
      </Sidebar>
      {/* Floating toggle shown when sidebar is hidden (desktop) */}
      {state === 'collapsed' && (
        <div className="fixed top-4 left-2 z-50 hidden md:block">
          <SidebarTrigger className="rounded-full bg-white shadow-md hover:bg-gray-100" />
        </div>
      )}
    </>
  );
}
