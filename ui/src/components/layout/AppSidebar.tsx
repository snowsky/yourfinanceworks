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
  FolderKanban,
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
  TrendingUp,
} from "lucide-react";
import { iconRegistry } from '@/plugins/plugin-icons';
import type { PluginNavItem } from '@/types/plugin-routes';
import { API_BASE_URL, settingsApi } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { Building } from 'lucide-react';
import { OrganizationSwitcher } from "./OrganizationSwitcher";
import { useOrganizations } from "@/hooks/useOrganizations";
import { useMe } from "@/hooks/useMe";
import { usePlugins } from '@/contexts/PluginContext';
import { PluginMenuErrorBoundary } from '@/components/plugins/PluginErrorBoundary';

// ---------------------------------------------------------------------------
// Module-level glob — evaluated ONCE at import time, not on every render.
// Calling import.meta.glob inside a component body creates a new object
// reference each render, which breaks useMemo dependency tracking.
// ---------------------------------------------------------------------------
import type { LucideIcon } from 'lucide-react';
import { Puzzle } from 'lucide-react';
import { usePluginModules } from '@/hooks/usePluginModules';

export function AppSidebar() {
  const pluginModules = usePluginModules();
  const _runtimeIconRegistry: Record<string, LucideIcon> = {
    ...iconRegistry,
    ...pluginModules.reduce<Record<string, LucideIcon>>(
      (acc, m) => ({ ...acc, ...(m.pluginIcons ?? {}) }),
      {},
    ),
  };
  const { state, setOpenMobile, isMobile: isMobileContext } = useSidebar();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Use the hook directly or from context, consistency is key, but context one is synced with sidebar state
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
  const [isSuperUser, setIsSuperUser] = useState(false);

  // Force re-reading user data when forceUpdate changes
  const [currentUser, setCurrentUser] = useState(user);
  useEffect(() => {
    setCurrentUser(getCurrentUser());
  }, [forceUpdate]);

  const showAnalytics = (currentUser as any)?.show_analytics !== false;

  const { data: me, isLoading: roleLoading } = useMe();
  const effectiveRole = me?.role || userRole;
  const isAdminEffective = effectiveRole === 'admin';

  // Plugin management
  const { enabledPlugins, isPluginEnabled } = usePlugins();

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

  // Get the current organization's role
  const currentOrgRole = userOrganizations.find(org => org.id.toString() === currentOrgId)?.role || 'user';
  const isAdminInCurrentOrg = currentOrgRole === 'admin';

  // Check super admin status via API
  useEffect(() => {
    const checkSuperAdminStatus = async () => {
      if (!currentUser?.is_superuser) {
        setIsSuperUser(false);
        return;
      }

      const userTenantIdStr = currentUser?.tenant_id != null ? String(currentUser.tenant_id) : '';
      const currentOrgIdStr = localStorage.getItem('selected_tenant_id') || userTenantIdStr;
      const isInPrimaryTenant = currentOrgIdStr === userTenantIdStr;
      setIsSuperUser(currentUser.is_superuser && isInPrimaryTenant);
    };

    checkSuperAdminStatus();
  }, [currentUser?.is_superuser, currentUser?.tenant_id]);

  // Sync currentOrgId with localStorage when it changes
  useEffect(() => {
    const handleStorageChange = () => {
      const stored = localStorage.getItem('selected_tenant_id');
      if (stored && stored !== currentOrgId) {
        setCurrentOrgId(stored);
      }
    };

    const handleOrgSwitch = () => {
      const stored = localStorage.getItem('selected_tenant_id');
      if (stored && stored !== currentOrgId) {
        setCurrentOrgId(stored);
      }
    };

    const handleUserUpdate = () => {
      // Force re-render to pick up new user data
      setForceUpdate(prev => prev + 1);
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('org-switched', handleOrgSwitch);
    window.addEventListener('user-updated', handleUserUpdate);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('org-switched', handleOrgSwitch);
      window.removeEventListener('user-updated', handleUserUpdate);
    };
  }, [currentOrgId]);

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
  // Only fetch settings when sidebar is actually visible (not on every page load)
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
    staleTime: 1000 * 60 * 60, // 1 hour cache
    gcTime: 1000 * 60 * 60 * 2, // Keep in cache for 2 hours
    enabled: (!roleLoading && isAdminEffective && state === 'expanded'), // Only fetch when sidebar is expanded and user is admin
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
  const userTenantIdStr = currentUser?.tenant_id != null ? String(currentUser.tenant_id) : '';
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
      icon: <BarChart className="w-5 h-5" />,
      tourId: 'nav-dashboard'
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
      label: t('navigation.approvals', { defaultValue: 'Approvals' }),
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
    ...((!roleLoading && isAdminInCurrentOrg) ? [{
      path: '/workflows',
      label: t('navigation.workflows', { defaultValue: 'Workflows' }),
      icon: <FolderKanban className="w-5 h-5" />,
      tourId: 'nav-workflows'
    }] : []),
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
    ...((!roleLoading && isAdminInCurrentOrg) ? [{
      path: '/users',
      label: t('navigation.users'),
      icon: <UserCheck className="w-5 h-5" />,
      tourId: 'nav-users'
    }] : []),
    // Only show Audit Log for admin or superuser
    ...((!roleLoading && (isSuperUser || isAdminInCurrentOrg)) ? [{
      path: '/audit-log',
      label: t('navigation.audit_log'),
      icon: <ListChecks className="w-5 h-5" />,
      tourId: 'nav-audit-log'
    }] : []),
    // Only show Analytics for admin or superuser if user has enabled it
    ...((!roleLoading && (isSuperUser || isAdminInCurrentOrg) && showAnalytics) ? [{
      path: '/analytics',
      label: t('navigation.analytics', { defaultValue: 'Analytics' }),
      icon: <BarChart className="w-5 h-5" />,
      tourId: 'nav-analytics'
    }] : []),
    // Only show Super Admin for super users in their primary tenant
    ...((!roleLoading && currentUser?.is_superuser && isPrimaryTenant) ? [{
      path: '/super-admin',
      label: t('navigation.super_admin'),
      icon: <ShieldCheck className="w-5 h-5" />,
      tourId: 'nav-super-admin'
    }] : [])
  ];

  // Plugin menu items — auto-discovered from each plugin's navItems export via import.meta.glob.
  // The glob runs at module level (above) so the reference is stable across renders.
  const pluginMenuItems = useMemo(() => {
    return pluginModules
      .flatMap((m) => m.navItems ?? [])
      .sort((a, b) => (a.priority ?? 999) - (b.priority ?? 999))
      .filter((item) => isPluginEnabled(item.id));
  }, [pluginModules, enabledPlugins, isPluginEnabled]);

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const handleNavigation = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  return (
    <>
      <Sidebar data-tour="sidebar" className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-r border-slate-700/50 shadow-2xl backdrop-blur-xl">
        <SidebarHeader className="py-3 px-4 border-b border-slate-700/30">
          <OrganizationSwitcher />
        </SidebarHeader>

        {/* Wrapper for flexible content with relative positioning for scroll indicators */}
        <div className="flex-1 min-h-0 relative flex flex-col">
          {/* Scroll Up Indicator */}
          <div
            className={`absolute top-0 left-0 right-0 h-10 bg-gradient-to-b from-slate-900 via-slate-900/80 to-transparent z-10 flex items-start justify-center pt-1 transition-opacity duration-300 pointer-events-none ${canScrollUp ? 'opacity-100' : 'opacity-0'}`}
          >
            <button
              onClick={() => scrollToDirection('up')}
              className={`rounded-full p-1.5 shadow-lg border transition-all pointer-events-auto cursor-pointer ${
                canScrollUp
                  ? "bg-blue-600/90 border-blue-400/60 text-white hover:bg-blue-500 ring-2 ring-blue-400/40"
                  : "bg-slate-800/80 border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700"
              }`}
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
                    {t('navigation.section.core', { defaultValue: 'Core' })}
                  </h3>
                </div>
                {mainMenuItems.map((item) => (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      asChild
                      className={`mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden ${isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm"
                        }`}
                      isActive={isActive(item.path)}
                    >
                      <Link
                        to={item.path}
                        className="flex items-center gap-2.5 w-full h-full py-2 px-3"
                        data-tour={item.tourId}
                        onClick={handleNavigation}
                      >
                        <div className={`p-2 rounded-lg transition-all duration-200 ${isActive(item.path)
                          ? "bg-white/20 shadow-sm"
                          : "bg-slate-700/30 group-hover:bg-slate-600/30"
                          }`}>
                          {item.icon}
                        </div>
                        <span className="font-medium text-[13px] leading-5">{item.label}</span>
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
                    {t('navigation.section.administration', { defaultValue: 'Administration' })}
                  </h3>
                </div>
                {settingsMenuItems.map((item) => (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton
                      asChild
                      className={`mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden ${isActive(item.path)
                        ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20"
                        : "text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm"
                        }`}
                      isActive={isActive(item.path)}
                    >
                      <Link
                        to={item.path}
                        className="flex items-center gap-2.5 w-full h-full py-2 px-3"
                        data-tour={item.tourId}
                        onClick={handleNavigation}
                      >
                        <div className={`p-2 rounded-lg transition-all duration-200 ${isActive(item.path)
                          ? "bg-white/20 shadow-sm"
                          : "bg-slate-700/30 group-hover:bg-slate-600/30"
                          }`}>
                          {item.icon}
                        </div>
                        <span className="font-medium text-[13px] leading-5">{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </div>

              {/* Plugins Section - Only show if plugins are enabled */}
              {pluginMenuItems.length > 0 && (
                <>
                  {/* Separator */}
                  <div className="px-3">
                    <div className="border-t border-slate-700/30"></div>
                  </div>

                  <div className="space-y-1">
                    <div className="px-3 mb-3">
                      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        {t('navigation.section.plugins', { defaultValue: 'Plugins' })}
                      </h3>
                    </div>
                    {pluginMenuItems.map((item) => {
                      const IconComponent = _runtimeIconRegistry[item.icon] ?? Puzzle;
                      return (
                        <SidebarMenuItem key={item.path}>
                          <PluginMenuErrorBoundary
                            pluginId={item.id}
                            pluginName={item.label}
                          >
                            <SidebarMenuButton
                              asChild
                              className={`mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden ${isActive(item.path)
                                ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg ring-2 ring-blue-500/20"
                                : "text-slate-300 hover:text-white hover:bg-slate-700/30 hover:shadow-sm"
                                }`}
                              isActive={isActive(item.path)}
                            >
                              <Link
                                to={item.path}
                                className="flex items-center gap-2.5 w-full h-full py-2 px-3"
                                data-tour={item.tourId}
                                onClick={handleNavigation}
                              >
                                <div className={`p-2 rounded-lg transition-all duration-200 ${isActive(item.path)
                                  ? "bg-white/20 shadow-sm"
                                  : "bg-slate-700/30 group-hover:bg-slate-600/30"
                                  }`}>
                                  {IconComponent && <IconComponent className="w-5 h-5" />}
                                </div>
                                <span className="font-medium text-[13px] leading-5">{item.label}</span>
                              </Link>
                            </SidebarMenuButton>
                          </PluginMenuErrorBoundary>
                        </SidebarMenuItem>
                      );
                    })}

                  </div>
                </>
              )}
            </SidebarMenu>
          </SidebarContent>

          {/* Scroll Down Indicator */}
          <div
            className={`absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-slate-900 via-slate-900/80 to-transparent z-10 flex items-end justify-center pb-1 transition-opacity duration-300 pointer-events-none ${canScrollDown ? 'opacity-100' : 'opacity-0'}`}
          >
            <button
              onClick={() => scrollToDirection('down')}
              className={`rounded-full p-1.5 shadow-lg border transition-all pointer-events-auto cursor-pointer ${
                canScrollDown
                  ? "bg-blue-600/90 border-blue-400/60 text-white hover:bg-blue-500 ring-2 ring-blue-400/40"
                  : "bg-slate-800/80 border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700"
              }`}
              tabIndex={canScrollDown ? 0 : -1}
              aria-label="Scroll down"
            >
              <ChevronDown className="w-3 h-3" />
            </button>
          </div>
        </div>


        <SidebarFooter className="py-3 px-4 border-t border-slate-700/30">
          {/* User identity + actions zone */}
          <div className="flex items-center gap-2.5 mb-3">
            <Avatar className="h-8 w-8 shrink-0 ring-2 ring-slate-600/30">
              <AvatarImage src={undefined as any} alt={currentUser?.email || 'User'} />
              <AvatarFallback className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-xs font-bold">
                {(() => {
                  const first = (currentUser?.first_name || '').trim();
                  const last = (currentUser?.last_name || '').trim();
                  const name = `${first} ${last}`.trim() || (currentUser?.email?.split('@')[0] || 'User');
                  const parts = name.split(' ').filter(Boolean);
                  const initials = parts.length >= 2 ? `${parts[0][0]}${parts[1][0]}` : name.slice(0, 2);
                  return initials.toUpperCase();
                })()}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col leading-tight flex-1 min-w-0">
              <span className="text-xs font-semibold text-white truncate">
                {(() => {
                  const first = (currentUser?.first_name || '').trim();
                  const last = (currentUser?.last_name || '').trim();
                  const name = `${first} ${last}`.trim();
                  return name || (currentUser?.email?.split('@')[0] || 'User');
                })()}
              </span>
              <span className="text-[11px] text-slate-400 truncate">
                {currentOrgRole === 'admin'
                  ? t('roles.administrator', { defaultValue: 'Administrator' })
                  : t('roles.user', { defaultValue: 'User' })}
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('auth.logout')}
              title={t('auth.logout')}
              onClick={handleLogout}
              className="h-7 w-7 shrink-0 text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200 rounded-lg"
            >
              <LogOut className="w-3.5 h-3.5" />
            </Button>
          </div>

          {/* Controls row */}
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <LanguageSwitcher />
            </div>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t('navigation.dark_mode')}
              title={t('navigation.dark_mode')}
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="h-8 w-8 border border-slate-600/30 bg-slate-700/20 hover:bg-slate-600/20 text-slate-300 hover:text-white transition-all duration-200 rounded-lg shrink-0"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </Button>
          </div>
        </SidebarFooter>
        {/* Always-available thin rail to toggle when sidebar is hidden */}
        <SidebarRail />
      </Sidebar>
    </>
  );
}
