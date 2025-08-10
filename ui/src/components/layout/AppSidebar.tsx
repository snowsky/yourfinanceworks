
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
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { UserProfile } from "./UserProfile";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
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
  Trash2
} from "lucide-react";
import { API_BASE_URL, settingsApi, apiRequest } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { createSettingsQueryOptions } from "@/utils/query";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Building } from 'lucide-react';
import { toast } from 'sonner';

export function AppSidebar() {
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
  const isAdminUser = userRole === 'admin';
  const [isSuperUser, setIsSuperUser] = useState(false);
  
  // Organization switching state
  const [userOrganizations, setUserOrganizations] = useState([]);
  const [currentOrgId, setCurrentOrgId] = useState(user?.tenant_id?.toString() || '');
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
    isAdminUser,
    isSuperUser,
    currentOrgId,
    primaryTenant: user?.tenant_id?.toString(),
    shouldFetchSettings: isAdminUser 
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
    enabled: isAdminUser, // Only fetch settings for admin users
    retry: (failureCount, error: any) => {
      // Don't retry on authentication/authorization errors
      if (error?.message?.includes('403') || error?.message?.includes('401')) {
        return false;
      }
      return failureCount < 3;
    },
  });

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
        const response = await apiRequest('/auth/me', {}, { skipTenant: true });
        console.log('📋 User organizations response:', response);
        
        if (response.organizations && response.organizations.length > 0) {
          console.log(`✅ User has access to ${response.organizations.length} organizations:`, response.organizations);
          setUserOrganizations(response.organizations);
          
          // Use selected tenant from localStorage or default to user's primary tenant
          let selectedTenantId = localStorage.getItem('selected_tenant_id');
          console.log('🔍 Selected tenant from localStorage:', selectedTenantId);
          
          // If no selected tenant, default to user's primary tenant
          if (!selectedTenantId) {
            selectedTenantId = user.tenant_id?.toString();
            console.log('🏠 Using user primary tenant:', selectedTenantId);
          } else {
            // Verify user has access to the selected tenant
            const hasAccess = response.organizations.some(org => org.id.toString() === selectedTenantId);
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
      icon: <Users className="w-5 h-5" /> 
    },
    { 
      path: '/invoices', 
      label: t('navigation.invoices'), 
      icon: <FileText className="w-5 h-5" /> 
    },
    { 
      path: '/payments', 
      label: t('navigation.payments'), 
      icon: <DollarSign className="w-5 h-5" /> 
    },
    { 
      path: '/expenses', 
      label: 'Expenses', 
      icon: <DollarSign className="w-5 h-5" /> 
    },

    // Only show Users menu item for admin users
    ...(isAdminUser ? [{ 
      path: '/users', 
      label: t('navigation.users'), 
      icon: <UserCheck className="w-5 h-5" /> 
    }] : []),
    // Only show Audit Log for admin or superuser
    ...((isAdminUser || isSuperUser) ? [{
      path: '/audit-log',
      label: t('navigation.audit_log'),
      icon: <ListChecks className="w-5 h-5" />
    }] : []),
    // Only show Analytics for admin or superuser if user has enabled it
    ...((isAdminUser || isSuperUser) && user?.show_analytics !== false ? [{
      path: '/analytics',
      label: 'Analytics',
      icon: <BarChart className="w-5 h-5" />
    }] : [])
  ];

  const settingsMenuItems = [
    // Only show Settings for admin users in their owned organization
    ...(isAdminUser && (currentOrgId === user?.tenant_id?.toString() || currentOrgId === user?.tenant_id) ? [{ 
      path: '/settings', 
      label: t('navigation.settings'), 
      icon: <Settings className="w-5 h-5" /> 
    }] : []),
    // Only show Super Admin for super users in their primary tenant
    ...(user?.is_superuser && (currentOrgId === user?.tenant_id?.toString() || currentOrgId === user?.tenant_id) ? [{ 
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
      <Sidebar>
        <SidebarHeader className="py-6 px-2 border-b border-sidebar-border">
          <div className="flex flex-col items-center text-center">
            <span className="text-xl font-bold text-white">InvoiceApp</span>
          </div>
        </SidebarHeader>
        <SidebarContent className="pt-6">
          {/* Organization Selector */}
          {userOrganizations.length > 0 && (
            <div className="px-3 mb-4">
              <div className="text-xs text-sidebar-foreground/60 mb-2">
                Organization {userOrganizations.length > 1 ? `(${userOrganizations.length} available)` : ''}
              </div>
              <Select value={currentOrgId} onValueChange={handleOrganizationSwitch} disabled={isSwitchingOrg}>
                <SelectTrigger className="w-full bg-sidebar border-sidebar-border text-sidebar-foreground">
                  <div className="flex items-center gap-2">
                    <Building className="w-4 h-4" />
                    {isSwitchingOrg ? (
                      <span className="text-sm">Switching...</span>
                    ) : (
                      <SelectValue placeholder="Select organization" />
                    )}
                  </div>
                </SelectTrigger>
                <SelectContent>
                  {userOrganizations.sort((a, b) => a.name.localeCompare(b.name)).map((org) => (
                    <SelectItem key={org.id} value={org.id.toString()}>
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
          )}
          
          <SidebarMenu>
            {mainMenuItems.map((item) => (
              <SidebarMenuItem key={item.path}>
                <SidebarMenuButton asChild 
                  className={isActive(item.path) ? "bg-sidebar-accent text-white" : "text-sidebar-foreground/80 hover:text-white"}
                >
                  <Link to={item.path} className="flex items-center gap-3 px-3 py-2">
                    {item.icon}
                    <span>{item.label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
            
            {/* Separator */}
            <div className="my-4 px-3">
              <div className="border-t border-sidebar-border"></div>
            </div>
            
            {settingsMenuItems.map((item) => (
              <SidebarMenuItem key={item.path}>
                <SidebarMenuButton asChild 
                  className={isActive(item.path) ? "bg-sidebar-accent text-white" : "text-sidebar-foreground/80 hover:text-white"}
                >
                  <Link to={item.path} className="flex items-center gap-3 px-3 py-2">
                    {item.icon}
                    <span>{item.label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
        <SidebarFooter className="py-4 px-2 border-t border-sidebar-border space-y-4">
          <div className="px-2">
            <UserProfile 
              companyName={companyName} 
              companyAddress={settings?.company_info?.address}
              companyLogo={settings?.company_info?.logo}
            />
          </div>
          <div className="px-2 flex items-center gap-2">
            <LanguageSwitcher />
            {/* Dark mode toggle button */}
            <Button
              variant="outline"
              size="icon"
              aria-label={t('navigation.dark_mode')}
              title={t('navigation.dark_mode')}
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="ml-2 border-sidebar-border bg-sidebar hover:bg-sidebar-accent text-sidebar-foreground hover:text-white"
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5" />
              ) : (
                <Moon className="w-5 h-5" />
              )}
            </Button>
          </div>
          <div className="flex justify-center">
            <Button 
              variant="destructive" 
              size="sm" 
              className="w-full"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              {t('auth.logout')}
            </Button>
          </div>
        </SidebarFooter>
      </Sidebar>
      <div className="fixed top-4 left-4 z-50">
        <SidebarTrigger>
          <Button 
            variant="outline" 
            size="icon" 
            className={`rounded-full ${!open ? 'bg-white shadow-md' : 'bg-transparent border-none'}`}
          >
            <ChevronLeft className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
          </Button>
        </SidebarTrigger>
      </div>
    </>
  );
}
