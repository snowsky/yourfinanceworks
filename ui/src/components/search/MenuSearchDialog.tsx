import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  BarChart,
  DollarSign,
  FileText,
  FolderKanban,
  ListChecks,
  Package,
  Clock,
  Users,
  UserCheck,
  ShieldCheck,
  Settings,
  Search,
} from 'lucide-react';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import { usePlugins } from '@/contexts/PluginContext';
import { iconRegistry } from '@/plugins/plugin-icons';
import type { PluginNavItem } from '@/types/plugin-routes';
import { useMe } from '@/hooks/useMe';
import { useOrganizations } from '@/hooks/useOrganizations';
import { getCurrentUser } from '@/utils/auth';

import type { LucideIcon } from 'lucide-react';
import { Puzzle } from 'lucide-react';
import { usePluginModules } from '@/hooks/usePluginModules';

export function MenuSearchDialog() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  // ── Role / org awareness (mirrors AppSidebar) ────────────────────────────
  const { data: me } = useMe();
  const { data: userOrganizations = [] } = useOrganizations();
  const currentUser = getCurrentUser();
  const userTenantIdStr = currentUser?.tenant_id != null ? String(currentUser.tenant_id) : '';
  const currentOrgId =
    (typeof window !== 'undefined' && localStorage.getItem('selected_tenant_id')) ||
    userTenantIdStr;
  const currentOrgRole =
    userOrganizations.find((org) => org.id.toString() === currentOrgId)?.role || 'user';
  const isAdminInCurrentOrg = currentOrgRole === 'admin';
  const isPrimaryTenant = currentOrgId === userTenantIdStr;
  const isSuperUserInPrimary = !!(currentUser?.is_superuser && isPrimaryTenant);
  const showAnalytics = (currentUser as any)?.show_analytics !== false;

  // ── Plugin items ──────────────────────────────────────────────────────────
  const pluginModules = usePluginModules();
  const _runtimeIconRegistry: Record<string, LucideIcon> = {
    ...iconRegistry,
    ...pluginModules.reduce<Record<string, LucideIcon>>(
      (acc, m) => ({ ...acc, ...(m.pluginIcons ?? {}) }),
      {},
    ),
  };
  const { enabledPlugins, isPluginEnabled } = usePlugins();
  const pluginMenuItems = useMemo(() => {
    return pluginModules
      .flatMap((m) => m.navItems ?? [])
      .sort((a, b) => (a.priority ?? 999) - (b.priority ?? 999))
      .filter((item) => isPluginEnabled(item.id));
  }, [pluginModules, enabledPlugins, isPluginEnabled]);

  // ── Keyboard shortcut: ⌘G / Ctrl+G ───────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'g' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  const handleSelect = (path: string) => {
    navigate(path);
    setOpen(false);
  };

  // ── Core nav items (mirrors AppSidebar mainMenuItems) ────────────────────
  const coreItems = [
    { path: '/', label: t('navigation.dashboard'), icon: <BarChart className="h-4 w-4" /> },
    { path: '/clients', label: t('navigation.clients'), icon: <Users className="h-4 w-4" /> },
    {
      path: '/invoices',
      label: t('navigation.invoices'),
      icon: <FileText className="h-4 w-4" />,
    },
    {
      path: '/payments',
      label: t('navigation.payments'),
      icon: <DollarSign className="h-4 w-4" />,
    },
    {
      path: '/expenses',
      label: t('navigation.expenses'),
      icon: <DollarSign className="h-4 w-4" />,
    },
    { path: '/approvals', label: 'Approvals', icon: <ListChecks className="h-4 w-4" /> },
    {
      path: '/inventory',
      label: t('navigation.inventory', 'Inventory'),
      icon: <Package className="h-4 w-4" />,
    },
    {
      path: '/statements',
      label: t('navigation.bank_statements'),
      icon: <FileText className="h-4 w-4" />,
    },
    {
      path: '/reminders',
      label: t('navigation.reminders'),
      icon: <Clock className="h-4 w-4" />,
    },
    {
      path: '/reports',
      label: t('navigation.reports'),
      icon: <BarChart className="h-4 w-4" />,
    },
    {
      path: '/reports/accounting-tax-export',
      label: t('reports.accounting_tax_export.title', 'Accounting & Tax Export'),
      icon: <FileText className="h-4 w-4" />,
    },
  ];

  // ── Admin / settings items (mirrors AppSidebar settingsMenuItems) ─────────
  const adminItems = [
    { path: '/settings', label: t('navigation.settings'), icon: <Settings className="h-4 w-4" /> },
    ...(isAdminInCurrentOrg
      ? [
          {
            path: '/users',
            label: t('navigation.users'),
            icon: <UserCheck className="h-4 w-4" />,
          },
        ]
      : []),
    ...(isAdminInCurrentOrg || isSuperUserInPrimary
      ? [
          {
            path: '/audit-log',
            label: t('navigation.audit_log'),
            icon: <ListChecks className="h-4 w-4" />,
          },
        ]
      : []),
    ...(isAdminInCurrentOrg || (isSuperUserInPrimary && showAnalytics)
      ? [
          {
            path: '/analytics',
            label: 'Analytics',
            icon: <BarChart className="h-4 w-4" />,
          },
        ]
      : []),
    ...(isSuperUserInPrimary
      ? [
          {
            path: '/super-admin',
            label: t('navigation.super_admin'),
            icon: <ShieldCheck className="h-4 w-4" />,
          },
        ]
      : []),
  ];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Go to menu…" />
      <CommandList>
        <CommandEmpty>
          <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
            <Search className="h-6 w-6 opacity-40" />
            <span className="text-sm">No menu found.</span>
          </div>
        </CommandEmpty>

        {/* ── Core ── */}
        <CommandGroup heading="Core">
          {coreItems.map((item) => (
            <CommandItem
              key={item.path}
              value={item.label}
              onSelect={() => handleSelect(item.path)}
              className="flex items-center gap-2 cursor-pointer"
            >
              <span className="text-muted-foreground">{item.icon}</span>
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        {/* ── Administration ── */}
        {adminItems.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Administration">
              {adminItems.map((item) => (
                <CommandItem
                  key={item.path}
                  value={item.label}
                  onSelect={() => handleSelect(item.path)}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <span className="text-muted-foreground">{item.icon}</span>
                  <span>{item.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {/* ── Plugins ── */}
        {pluginMenuItems.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Plugins">
              {pluginMenuItems.map((item) => {
                const IconComponent = _runtimeIconRegistry[item.icon] ?? Puzzle;
                return (
                  <CommandItem
                    key={item.path}
                    value={item.label}
                    onSelect={() => handleSelect(item.path)}
                    className="flex items-center gap-2 cursor-pointer"
                  >
                    <span className="text-muted-foreground">
                      {IconComponent ? (
                        <IconComponent className="h-4 w-4" />
                      ) : (
                        <FolderKanban className="h-4 w-4" />
                      )}
                    </span>
                    <span>{item.label}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </>
        )}
      </CommandList>

      {/* Footer hint */}
      <div className="border-t px-3 py-2 text-xs text-muted-foreground flex items-center gap-4">
        <span>
          <CommandShortcut>↵</CommandShortcut> to navigate
        </span>
        <span>
          <CommandShortcut>↑↓</CommandShortcut> to move
        </span>
        <span>
          <CommandShortcut>Esc</CommandShortcut> to close
        </span>
        <span className="ml-auto">
          <CommandShortcut>⌘G</CommandShortcut>
        </span>
      </div>
    </CommandDialog>
  );
}
