
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
  ListChecks // <-- Add icon for audit log
} from "lucide-react";
import { API_BASE_URL, settingsApi } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { createSettingsQueryOptions } from "@/utils/query";

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const [open, setOpen] = useState(!isMobile);
  const [forceUpdate, setForceUpdate] = useState(0);

  // Get current user data from localStorage
  const user = getCurrentUser();
  const userRole = user?.role || 'user';
  const isAdminUser = userRole === 'admin';
  const isSuperUser = user?.is_superuser || false;

  console.log('Sidebar: User check:', { 
    user, 
    userRole, 
    isAdminUser,
    isSuperUser,
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

  const companyName = settings?.company_info?.name || 'InvoiceApp';

  // Debug logging
  useEffect(() => {
    console.log('Sidebar: Settings data changed:', {
      companyName,
      settings: settings?.company_info,
      settingsFull: settings,
      forceUpdate,
      timestamp: new Date().toISOString()
    });
  }, [settings, companyName, forceUpdate]);

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
    }] : [])
  ];

  const settingsMenuItems = [
    // Only show Settings for admin users
    ...(isAdminUser ? [{ 
      path: '/settings', 
      label: t('navigation.settings'), 
      icon: <Settings className="w-5 h-5" /> 
    }] : []),
    // Only show Super Admin for super users
    ...(isSuperUser ? [{ 
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
          <div className="px-2">
            <LanguageSwitcher />
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
