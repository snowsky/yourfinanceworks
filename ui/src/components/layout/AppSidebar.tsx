import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
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
import {
  BarChart,
  ChevronLeft,
  ChevronUp,
  ChevronDown,
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
  Package,
  Clock,
} from "lucide-react";
import { API_BASE_URL, settingsApi } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { Building } from 'lucide-react';
import { OrganizationSwitcher } from "./OrganizationSwitcher";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useMe } from "@/hooks/useMe";

export function AppSidebar() {
  const { state } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const { t } = useTranslation();
  const [forceUpdate, setForceUpdate] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('theme');
      if (stored === 'dark' || stored === 'light') return stored;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
    // Optionally: update user profile theme in backend here
  }, [theme]);

  // Get current user data from localStorage
  const user = getCurrentUser();
  const userRole = user?.role || 'user';
  const showAnalytics = (user as any)?.show_analytics !== false;
  const [isSuperUser, setIsSuperUser] = useState(false);

  const { data: me, isLoading: roleLoading } = useMe();
  const effectiveRole = me?.role || userRole;
  const isAdminEffective = effectiveRole === 'admin';

  // Organization switching state - REMOVED, now handled by OrganizationSwitcher component
  const { data: userOrganizations = [] } = useOrganizations();
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

      const userTenantIdStr = user?.tenant_id != null ? String(user.tenant_id) : '';
      const currentOrgIdStr = localStorage.getItem('selected_tenant_id') || userTenantIdStr;
      const isInPrimaryTenant = currentOrgIdStr === userTenantIdStr;
      setIsSuperUser(user.is_superuser && isInPrimaryTenant);
    };

    checkSuperAdminStatus();
  }, [user?.is_superuser, user?.tenant_id]);

  const [canScrollUp, setCanScrollUp] = useState(false);
  const [canScrollDown, setCanScrollDown] = useState(false);

  // Optimized scroll handler using requestAnimationFrame
  const handleScroll = useCallback(() => {
    if (!contentRef.current) return;

    // Use requestAnimationFrame to throttle updates and prevent flashing
    requestAnimationFrame(() => {
      if (!contentRef.current) return;
      const { scrollTop, scrollHeight, clientHeight } = contentRef.current;

      // Add a small buffer (e.g., 2px) to prevent flickering at boundaries
      const hasScrollUp = scrollTop > 2;
      const hasScrollDown = scrollTop + clientHeight < scrollHeight - 2;

      setCanScrollUp(hasScrollUp);
      setCanScrollDown(hasScrollDown);
    });
  }, []);

  const scrollToDirection = useCallback((direction: 'up' | 'down') => {
    if (!contentRef.current) return;
    const scrollAmount = 200;
    contentRef.current.scrollBy({
      top: direction === 'down' ? scrollAmount : -scrollAmount,
      behavior: 'smooth'
    });
  }, []);

  useEffect(() => {
    const element = contentRef.current;
    if (!element) return;

    // Initial check
    handleScroll();

    element.addEventListener('scroll', handleScroll);
    window.addEventListener('resize', handleScroll);

    // Also check when content size might change (e.g. expansion panels)
    const observer = new ResizeObserver(handleScroll);
    observer.observe(element);

    return () => {
      element.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
      observer.disconnect();
    };
  }, [handleScroll]);


  // Get company name from settings with reduced refetching frequency (only for admin users)
  // Note: We conditionally define the query to prevent API calls for non-admin users
  const { data: settings } = useQuery({
    queryKey: ['settings'], // Removed forceUpdate to prevent unnecessary refetches
    queryFn: () => {
      return settingsApi.getSettings();
    },
    refetchInterval: false, // Disable automatic refetching
    refetchOnWindowFocus: false, // Disable window focus refetching
    refetchOnMount: false, // Don't refetch on mount
    refetchOnReconnect: false, // Disable reconnect refetching
    refetchIntervalInBackground: false,
    staleTime: Infinity, // Never consider data stale
    gcTime: 1000 * 60 * 60, // Keep in cache for 1 hour
    enabled: (!roleLoading && isAdminEffective), // Only fetch settings after role is known and admin in current org
    retry: (failureCount, error: any) => {
      // Don't retry on authentication/authorization errors
      if (error?.message?.includes('403') || error?.message?.includes('401')) {
        return false;
      }
      return failureCount < 3;
    },
  });

  // Sync me data to localStorage role
  useEffect(() => {
    if (me?.role) {
      const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
      if (currentUser && currentUser.role !== me.role) {
        console.log(`🔄 Role updated: ${currentUser.role} → ${me.role}`);
        const updatedUser = { ...currentUser, role: me.role };
        localStorage.setItem('user', JSON.stringify(updatedUser));
        window.dispatchEvent(new CustomEvent('auth-updated'));
      }
    }
  }, [me]);

  // Memoize company name to prevent unnecessary recalculations
  const companyName = useMemo(() => {
    if (userOrganizations.length > 0) {
      const currentOrg = userOrganizations.find(org => org.id.toString() === currentOrgId);
      if (currentOrg) {
        return currentOrg.name;
      }
    }
    return settings?.company_info?.name || 'InvoiceApp';
  }, [userOrganizations, currentOrgId, settings?.company_info?.name]);
  // Normalize tenant id types for safe comparisons
  const companyLogoUrl = settings?.company_info?.logo;
  const userTenantIdStr = user?.tenant_id != null ? String(user.tenant_id) : '';
  const isPrimaryTenant = currentOrgId === userTenantIdStr;




  // Listen for settings updates and force refetch
  useEffect(() => {
    const handleSettingsUpdate = () => {
      // Invalidate settings cache when updated
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'settings_updated') {
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

    // Dispatch custom event to notify FeatureContext
    window.dispatchEvent(new Event('auth-changed'));

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
      path: '/approvals',
      label: 'Approvals',
      icon: <ListChecks className="w-5 h-5" />,
      tourId: 'nav-approvals'
    },
    {
      path: '/inventory',
      label: t('navigation.inventory', 'Inventory'),
      icon: <Package className="w-5 h-5" />,
      tourId: 'nav-inventory'
    },
    {
      path: '/statements',
      label: t('navigation.bank_statements'),
      icon: <FileText className="w-5 h-5" />,
      tourId: 'nav-statements'
    },
    {
      path: '/reminders',
      label: t('navigation.reminders'),
      icon: <Clock className="w-5 h-5" />,
      tourId: 'nav-reminders'
    },
    {
      path: '/reports',
      label: t('navigation.reports'),
      icon: <BarChart className="w-5 h-5" />,
      tourId: 'nav-reports'
    },

    // Users, Audit Log, and Analytics moved under Settings; remove from main nav
  ];

  const settingsMenuItems = [
    // Show Settings for all users
    ...((!roleLoading) ? [{
      path: '/settings',
      label: t('navigation.settings'),
      icon: <Settings className="w-5 h-5" />,
      tourId: 'nav-settings'
    }] : []),
    // User Management section for admins
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
    ...((!roleLoading && user?.is_superuser && isPrimaryTenant) ? [{
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
      <Sidebar data-tour="sidebar" className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 shadow-2xl backdrop-blur-xl">
        <SidebarHeader className="py-4 px-4 border-b border-slate-700/30 bg-gradient-to-r from-slate-800/30 to-slate-700/30 backdrop-blur-sm">
          {/* Enhanced Company Branding Section */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {companyLogoUrl ? (
                <img
                  src={companyLogoUrl.startsWith('http') ? companyLogoUrl : `${API_BASE_URL}${companyLogoUrl}`}
                  alt={`${companyName} Logo`}
                  className="h-10 w-10 object-contain rounded-xl shadow-lg ring-2 ring-blue-500/20 bg-white/10 p-1 backdrop-blur-sm"
                  onError={(e) => {
                    console.error('Failed to load company logo:', e);
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ) : (
                <div className="h-10 w-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg ring-2 ring-blue-500/20">
                  <Building className="h-5 w-5 text-white" />
                </div>
              )}
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold text-white truncate max-w-[140px] tracking-tight">
                  {companyName}
                </span>
                <span className="text-xs text-slate-300 font-medium">
                  YourFinanceWORKS
                </span>
              </div>
            </div>
            <SidebarTrigger>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Toggle sidebar"
                className="text-slate-300 hover:text-white hover:bg-slate-700/50 rounded-lg h-8 w-8 transition-all duration-200"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </SidebarTrigger>
          </div>

          {/* Enhanced User Profile Section */}
          <div className="bg-slate-800/30 rounded-xl p-3 border border-slate-700/20 backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8 ring-2 ring-slate-600/30">
                <AvatarImage src={undefined as any} alt={user?.email || 'User'} />
                <AvatarFallback className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-xs font-bold">
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
                <span className="text-xs font-semibold text-white truncate">
                  {(() => {
                    const first = (user?.first_name || '').trim();
                    const last = (user?.last_name || '').trim();
                    const name = `${first} ${last}`.trim();
                    return name || (user?.email?.split('@')[0] || 'User');
                  })()}
                </span>
                <span className="text-xs text-slate-300 truncate">
                  {effectiveRole === 'admin' ? 'Administrator' : 'User'}
                </span>
              </div>
            </div>
          </div>
        </SidebarHeader>
        {/* Organization Switcher - Fixed, doesn't scroll */}
        <div className="px-3 py-3 border-b border-slate-700/30">
          <OrganizationSwitcher />
        </div>



        {/* Wrapper for flexible content with relative positioning for scroll indicators */}
        <div className="flex-1 min-h-0 relative flex flex-col">
          {/* Scroll Up Indicator */}
          <div
            className={`absolute top-0 left-0 right-0 h-10 bg-gradient-to-b from-slate-900 via-slate-900/80 to-transparent z-10 flex items-start justify-center pt-1 transition-opacity duration-300 pointer-events-none ${canScrollUp ? 'opacity-100' : 'opacity-0'}`}
          >
            <button
              onClick={() => scrollToDirection('up')}
              className="bg-slate-800/80 rounded-full p-1 shadow-lg border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700 transition-all pointer-events-auto cursor-pointer"
              tabIndex={canScrollUp ? 0 : -1}
              aria-label="Scroll up"
            >
              <ChevronUp className="w-3 h-3" />
            </button>
          </div>

          {/* Scrollable Content */}
          <SidebarContent className="px-3 pt-4 pb-20 space-y-6 scrollbar-hide overflow-y-auto" ref={contentRef}>
            {/* Menu items only - org picker moved above */}

            <SidebarMenu className="space-y-6">
              {/* Core Navigation Section */}
              <div className="space-y-1">
                <div className="px-3 mb-3">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Core
                  </h3>
                </div>
                {mainMenuItems.map((item) => (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      className={`mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden ${isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm"
                        }`}
                      isActive={isActive(item.path)}
                    >
                      <Link
                        to={item.path}
                        className="flex items-center gap-3 w-full h-full py-3 px-4"
                        data-tour={item.tourId}
                      >
                        <div className={`p-2 rounded-lg transition-all duration-200 ${isActive(item.path)
                          ? "bg-white/20 shadow-sm"
                          : "bg-slate-700/30 group-hover:bg-slate-600/30"
                          }`}>
                          {item.icon}
                        </div>
                        <span className="font-medium text-sm">{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </div>

              {/* Separator */}
              <div className="px-3">
                <div className="border-t border-slate-700/30"></div>
              </div>

              {/* Administration Section */}
              <div className="space-y-1">
                <div className="px-3 mb-3">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Administration
                  </h3>
                </div>
                {settingsMenuItems.map((item) => (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      className={`mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden ${isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm"
                        }`}
                      isActive={isActive(item.path)}
                    >
                      <Link
                        to={item.path}
                        className="flex items-center gap-3 w-full h-full py-3 px-4"
                        data-tour={item.tourId}
                      >
                        <div className={`p-2 rounded-lg transition-all duration-200 ${isActive(item.path)
                          ? "bg-white/20 shadow-sm"
                          : "bg-slate-700/30 group-hover:bg-slate-600/30"
                          }`}>
                          {item.icon}
                        </div>
                        <span className="font-medium text-sm">{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </div>
            </SidebarMenu>
          </SidebarContent>

          {/* Scroll Down Indicator */}
          <div
            className={`absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-slate-900 via-slate-900/80 to-transparent z-10 flex items-end justify-center pb-1 transition-opacity duration-300 pointer-events-none ${canScrollDown ? 'opacity-100' : 'opacity-0'}`}
          >
            <button
              onClick={() => scrollToDirection('down')}
              className="bg-slate-800/80 rounded-full p-1 shadow-lg border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700 transition-all pointer-events-auto cursor-pointer"
              tabIndex={canScrollDown ? 0 : -1}
              aria-label="Scroll down"
            >
              <ChevronDown className="w-3 h-3" />
            </button>
          </div>
        </div>


        <SidebarFooter className="py-4 px-4 border-t border-slate-700/30 bg-gradient-to-r from-slate-800/30 to-slate-700/30 backdrop-blur-sm">
          <div className="space-y-4">
            {/* Controls */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex-1">
                <LanguageSwitcher />
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('navigation.dark_mode')}
                title={t('navigation.dark_mode')}
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="h-8 w-8 border border-slate-600/30 bg-slate-700/20 hover:bg-slate-600/20 text-slate-300 hover:text-white transition-all duration-200 rounded-lg"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </Button>
            </div>

            {/* Softened Logout Button */}
            <Button
              variant="outline"
              size="sm"
              className="w-full border-slate-700/50 bg-slate-800/20 text-slate-400 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/30 font-medium py-2.5 rounded-xl transition-all duration-200"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              <span className="text-sm">{t('auth.logout')}</span>
            </Button>
          </div>
        </SidebarFooter>
        {/* Always-available thin rail to toggle when sidebar is hidden */}
        <SidebarRail />
      </Sidebar>
      {/* Floating toggle shown when sidebar is hidden (desktop) */}
      {state === 'collapsed' && (
        <div className="fixed top-4 left-2 z-50 hidden md:block">
          <SidebarTrigger className="rounded-full bg-background/80 backdrop-blur-sm shadow-lg hover:bg-background border border-border/50" />
        </div>
      )}
    </>
  );
}
