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
import { Badge } from "@/components/ui/badge";
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
  Bot,
  Package,
  Clock,
  Building,
  Zap,
  TrendingUp,
  Activity,
} from "lucide-react";
import { API_BASE_URL, settingsApi, apiRequest } from "@/lib/api";
import { isAdmin, getCurrentUserRole, getCurrentUser } from "@/utils/auth";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { toast } from 'sonner';
import { cn } from "@/lib/utils";

interface NavigationItem {
  id: string;
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
  category: 'primary' | 'secondary' | 'admin';
  tourId?: string;
  requiresPermission?: boolean;
}

export function ProfessionalSidebar() {
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
      const stored = localStorage.getItem('theme');
      if (stored === 'dark' || stored === 'light') return stored;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  });

  // User and organization state
  const user = getCurrentUser();
  const userRole = user?.role || 'user';
  const [effectiveRole, setEffectiveRole] = useState<string>(userRole);
  const [roleLoading, setRoleLoading] = useState(true);
  const isAdminEffective = effectiveRole === 'admin';
  const showAnalytics = (user as any)?.show_analytics !== false;
  const [isSuperUser, setIsSuperUser] = useState(false);
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

  // Theme handling
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
  }, [theme]);

  // Get company settings
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings', forceUpdate],
    queryFn: () => settingsApi.getSettings(),
    refetchInterval: 30000,
    enabled: (!roleLoading && isAdminEffective),
    retry: (failureCount, error: any) => {
      if (error?.message?.includes('403') || error?.message?.includes('401')) {
        return false;
      }
      return failureCount < 3;
    },
  });

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
  const userTenantIdStr = user?.tenant_id != null ? String(user.tenant_id) : '';
  const isPrimaryTenant = currentOrgId === userTenantIdStr;

  // Navigation items configuration
  const navigationItems: NavigationItem[] = [
    // Primary Navigation
    {
      id: 'dashboard',
      label: t('navigation.dashboard'),
      path: '/',
      icon: Activity,
      category: 'primary',
    },
    {
      id: 'expenses',
      label: t('navigation.expenses'),
      path: '/expenses',
      icon: DollarSign,
      category: 'primary',
      tourId: 'nav-expenses'
    },
    {
      id: 'invoices',
      label: t('navigation.invoices'),
      path: '/invoices',
      icon: FileText,
      category: 'primary',
      tourId: 'nav-invoices'
    },
    {
      id: 'clients',
      label: t('navigation.clients'),
      path: '/clients',
      icon: Users,
      category: 'primary',
      tourId: 'nav-clients'
    },
    {
      id: 'payments',
      label: t('navigation.payments'),
      path: '/payments',
      icon: DollarSign,
      category: 'primary',
      tourId: 'nav-payments'
    },
    
    // Secondary Navigation
    {
      id: 'approvals',
      label: 'Approvals',
      path: '/approvals',
      icon: ListChecks,
      category: 'secondary',
      tourId: 'nav-approvals'
    },
    {
      id: 'inventory',
      label: t('navigation.inventory', 'Inventory'),
      path: '/inventory',
      icon: Package,
      category: 'secondary',
      tourId: 'nav-inventory'
    },
    {
      id: 'reminders',
      label: t('navigation.reminders'),
      path: '/reminders',
      icon: Clock,
      category: 'secondary',
      tourId: 'nav-reminders',
      requiresPermission: true
    },
    {
      id: 'reports',
      label: t('navigation.reports'),
      path: '/reports',
      icon: BarChart,
      category: 'secondary',
      tourId: 'nav-reports'
    },
    {
      id: 'statements',
      label: t('navigation.bank_statements'),
      path: '/statements',
      icon: FileText,
      category: 'secondary',
      tourId: 'nav-statements'
    },

    // Admin Navigation
    {
      id: 'settings',
      label: t('navigation.settings'),
      path: '/settings',
      icon: Settings,
      category: 'admin',
      tourId: 'nav-settings'
    },
    {
      id: 'users',
      label: t('navigation.users'),
      path: '/users',
      icon: UserCheck,
      category: 'admin'
    },
    {
      id: 'audit-log',
      label: t('navigation.audit_log'),
      path: '/audit-log',
      icon: ListChecks,
      category: 'admin'
    },
    {
      id: 'analytics',
      label: 'Analytics',
      path: '/analytics',
      icon: TrendingUp,
      category: 'admin'
    },
    {
      id: 'super-admin',
      label: t('navigation.super_admin'),
      path: '/super-admin',
      icon: ShieldCheck,
      category: 'admin'
    }
  ];

  // Filter navigation items based on permissions
  const getFilteredItems = (category: 'primary' | 'secondary' | 'admin') => {
    return navigationItems.filter(item => {
      if (item.category !== category) return false;
      
      // Admin items
      if (category === 'admin') {
        if (item.id === 'settings' && (!isAdminEffective || !isPrimaryTenant)) return false;
        if (item.id === 'users' && !isAdminEffective) return false;
        if (item.id === 'audit-log' && !(isAdminEffective || isSuperUser)) return false;
        if (item.id === 'analytics' && !(isAdminEffective || isSuperUser) || !showAnalytics) return false;
        if (item.id === 'super-admin' && !(user?.is_superuser && isPrimaryTenant)) return false;
      }
      
      return true;
    });
  };

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    // Dispatch custom event to notify FeatureContext
    window.dispatchEvent(new Event('auth-changed'));
    queryClient.clear();
    navigate('/login');
  };

  const renderNavigationSection = (title: string, items: NavigationItem[]) => {
    if (items.length === 0) return null;

    return (
      <div className="space-y-1">
        <div className="px-3 mb-3">
          <h3 className="text-xs font-semibold text-sidebar-foreground/60 uppercase tracking-wider">
            {title}
          </h3>
        </div>
        {items.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          
          return (
            <SidebarMenuItem key={item.id}>
              <SidebarMenuButton
                className={cn(
                  "mx-2 rounded-xl transition-all duration-200 group relative overflow-hidden",
                  active
                    ? "bg-gradient-to-r from-sidebar-primary to-sidebar-primary/80 text-sidebar-primary-foreground shadow-lg ring-2 ring-sidebar-primary/20"
                    : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                )}
                isActive={active}
              >
                <Link
                  to={item.path}
                  className="flex items-center gap-3 w-full h-full py-3 px-4"
                  data-tour={item.tourId}
                >
                  <div className={cn(
                    "p-2 rounded-lg transition-all duration-200",
                    active
                      ? "bg-white/20 shadow-sm"
                      : "bg-sidebar-accent/30 group-hover:bg-sidebar-accent/50"
                  )}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="font-medium text-sm">{item.label}</span>
                  {item.badge && (
                    <Badge 
                      variant="secondary" 
                      className="ml-auto h-5 w-5 p-0 flex items-center justify-center text-xs bg-sidebar-primary text-sidebar-primary-foreground"
                    >
                      {item.badge}
                    </Badge>
                  )}
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        })}
      </div>
    );
  };

  return (
    <>
      <Sidebar 
        data-tour="sidebar" 
        className="bg-gradient-to-br from-sidebar-background via-sidebar-background to-sidebar-accent/20 border-r border-sidebar-border/50 shadow-2xl backdrop-blur-xl"
      >
        <SidebarHeader className="py-4 px-4 border-b border-sidebar-border/30 bg-gradient-to-r from-sidebar-accent/20 to-transparent">
          {/* Company Branding */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {companyLogoUrl ? (
                <img
                  src={companyLogoUrl.startsWith('http') ? companyLogoUrl : `${API_BASE_URL}${companyLogoUrl}`}
                  alt={`${companyName} Logo`}
                  className="h-10 w-10 object-contain rounded-xl shadow-lg ring-2 ring-sidebar-primary/20 bg-white/10 p-1"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ) : (
                <div className="h-10 w-10 bg-gradient-to-br from-sidebar-primary to-sidebar-primary/80 rounded-xl flex items-center justify-center shadow-lg ring-2 ring-sidebar-primary/20">
                  <Building className="h-5 w-5 text-sidebar-primary-foreground" />
                </div>
              )}
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold text-sidebar-foreground truncate max-w-[140px] tracking-tight">
                  {companyName}
                </span>
                <span className="text-xs text-sidebar-foreground/60 font-medium">
                  Financial Management
                </span>
              </div>
            </div>
            <SidebarTrigger>
              <Button
                variant="ghost"
                size="icon"
                className="text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 rounded-lg h-8 w-8"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </SidebarTrigger>
          </div>
          
          {/* User Profile */}
          <div className="bg-sidebar-accent/30 rounded-xl p-3 border border-sidebar-border/20 backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8 ring-2 ring-sidebar-primary/30">
                <AvatarImage src={undefined as any} alt={user?.email || 'User'} />
                <AvatarFallback className="bg-gradient-to-br from-sidebar-primary to-sidebar-primary/80 text-sidebar-primary-foreground text-xs font-bold">
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
                <span className="text-xs font-semibold text-sidebar-foreground truncate">
                  {(() => {
                    const first = (user?.first_name || '').trim();
                    const last = (user?.last_name || '').trim();
                    const name = `${first} ${last}`.trim();
                    return name || (user?.email?.split('@')[0] || 'User');
                  })()}
                </span>
                <span className="text-xs text-sidebar-foreground/60 truncate">
                  {effectiveRole === 'admin' ? 'Administrator' : 'User'}
                </span>
              </div>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent className="pt-4 px-3 space-y-6">
          <SidebarMenu className="space-y-6">
            {/* Primary Navigation */}
            {renderNavigationSection("Core", getFilteredItems('primary'))}
            
            {/* Secondary Navigation */}
            {renderNavigationSection("Tools", getFilteredItems('secondary'))}
            
            {/* Admin Navigation */}
            {getFilteredItems('admin').length > 0 && (
              <>
                <div className="border-t border-sidebar-border/30 my-4"></div>
                {renderNavigationSection("Administration", getFilteredItems('admin'))}
              </>
            )}
          </SidebarMenu>
        </SidebarContent>

        <SidebarFooter className="py-4 px-4 border-t border-sidebar-border/30 bg-gradient-to-r from-sidebar-accent/10 to-transparent">
          <div className="space-y-4">
            {/* Controls */}
            <div className="flex items-center justify-between gap-2">
              <HelpCenter />
              <div className="flex-1">
                <LanguageSwitcher />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="h-8 w-8 border border-sidebar-border/30 bg-sidebar-accent/20 hover:bg-sidebar-accent/40 text-sidebar-foreground/60 hover:text-sidebar-foreground rounded-lg"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </Button>
            </div>

            {/* Logout Button */}
            <Button
              variant="destructive"
              size="sm"
              className="w-full bg-gradient-to-r from-red-600/90 to-red-700/90 hover:from-red-700 hover:to-red-800 text-white font-medium py-2.5 rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 border border-red-500/20"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4 mr-2" />
              <span className="text-sm">{t('auth.logout')}</span>
            </Button>
          </div>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      {/* Floating toggle for collapsed state */}
      {state === 'collapsed' && (
        <div className="fixed top-4 left-2 z-50 hidden md:block">
          <SidebarTrigger className="rounded-full bg-background/80 backdrop-blur-sm shadow-lg hover:bg-background border border-border/50" />
        </div>
      )}
    </>
  );
}