import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, it, expect, beforeEach } from 'vitest';
const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }));
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate, useLocation: () => ({ pathname: '/' }), Link: ({ children, to }: React.PropsWithChildren<{ to: string }>) => <a href={to}>{children}</a> }));
import { toast } from 'sonner';
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }));
vi.mock('@/hooks/useThemePreference', () => ({ useThemePreference: () => ({ resolvedTheme: 'light', setTheme: vi.fn() }) }));
vi.mock('@/hooks/usePluginModules', () => ({ usePluginModules: () => [] }));
vi.mock('@/contexts/PluginContext', () => ({ usePlugins: () => ({ enabledPlugins: [], isPluginEnabled: () => false, getPlugin: vi.fn() }), PluginProvider: ({ children }: React.PropsWithChildren) => children }));
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppSidebar } from '../AppSidebar';
import { PluginProvider } from '@/contexts/PluginContext';

// Mock the hooks and components
vi.mock('@/hooks/use-mobile', () => ({
  useIsMobile: () => false
}));

vi.mock('@/hooks/useOrganizations', () => ({
  useOrganizations: () => ({ data: [] })
}));

vi.mock('@/hooks/useMe', () => ({
  useMe: () => ({ data: { role: 'user' }, isLoading: false })
}));

vi.mock('@/lib/api', () => ({
  API_BASE_URL: 'http://localhost:8000',
  settingsApi: {
    getSettings: vi.fn().mockResolvedValue({
      company_info: { name: 'Test Company' }
    })
  }
}));

vi.mock('../OrganizationSwitcher', () => ({
  OrganizationSwitcher: () => <div data-testid="org-switcher">Organization Switcher</div>
}));

vi.mock('@/components/ui/language-switcher', () => ({
  LanguageSwitcher: () => <div data-testid="language-switcher">Language Switcher</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    // Mirror i18next: return the provided defaultValue when present, else the key —
    // the component renders section/nav labels via t(key, { defaultValue: 'Label' }).
    t: (key: string, opts?: { defaultValue?: string }) =>
      opts && typeof opts === 'object' && opts.defaultValue ? opts.defaultValue : key
  }),
  // i18n/index.ts (pulled in transitively) calls `.use(initReactI18next)` at import;
  // the mock must provide it or collection fails before any test runs.
  initReactI18next: { type: '3rdParty', init: () => {} }
}));

// AppSidebar reads useFeatures() to gate nav items; provide a stub that enables all.
vi.mock('@/contexts/FeatureContext', () => ({
  useFeatures: () => ({ isFeatureEnabled: () => true })
}));

// Mock sidebar components
vi.mock('@/components/ui/sidebar', () => ({
  Sidebar: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar" {...props}>{children}</div>,
  SidebarContent: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-content" {...props}>{children}</div>,
  SidebarFooter: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-footer" {...props}>{children}</div>,
  SidebarHeader: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-header" {...props}>{children}</div>,
  SidebarMenu: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-menu" {...props}>{children}</div>,
  SidebarMenuButton: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-menu-button" {...props}>{children}</div>,
  SidebarMenuItem: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-menu-item" {...props}>{children}</div>,
  SidebarTrigger: (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button data-testid="sidebar-trigger" {...props}>Toggle</button>,
  SidebarRail: (props: React.HTMLAttributes<HTMLDivElement>) => <div data-testid="sidebar-rail" {...props}></div>,
  useSidebar: () => ({
    state: 'expanded',
    setOpenMobile: vi.fn(),
    isMobile: false
  })
}));

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return (
    <QueryClientProvider client={queryClient}>

        <PluginProvider>
          {children}
        </PluginProvider>

    </QueryClientProvider>
  );
};


beforeEach(() => {
 vi.clearAllMocks();
 vi.mocked(localStorage.getItem).mockImplementation(key => key === 'user' ? JSON.stringify({ id: 1, email: 'test@example.com', role: 'user', tenant_id: 1 }) : null);
});
it('sidebar waits for cookie clearance before local cleanup and navigation', async () => {
 let finish!: (value: Response) => void;
 vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }));
 render(<TestWrapper><AppSidebar /></TestWrapper>);
 await userEvent.click(screen.getByRole('button', { name: 'auth.logout' }));
 expect(fetch).toHaveBeenCalledWith('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
 expect(localStorage.removeItem).not.toHaveBeenCalled();
 expect(navigate).not.toHaveBeenCalled();
 finish({ ok: true } as Response);
 await waitFor(() => expect(navigate).toHaveBeenCalledWith('/login'));
 for (const key of ['user', 'token', 'selected_tenant_id']) expect(localStorage.removeItem).toHaveBeenCalledWith(key);
});
it.each(['server', 'network'])('sidebar preserves session and allows retry on %s failure', async kind => {
 if (kind === 'server') vi.mocked(fetch).mockResolvedValueOnce({ ok: false } as Response);
 else vi.mocked(fetch).mockRejectedValueOnce(new Error('offline'));
 render(<TestWrapper><AppSidebar /></TestWrapper>);
 await userEvent.click(screen.getByRole('button', { name: 'auth.logout' }));
 await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Unable to log out. Please try again.'));
 expect(localStorage.removeItem).not.toHaveBeenCalled();
 expect(navigate).not.toHaveBeenCalled();
 vi.mocked(fetch).mockResolvedValueOnce({ ok: true } as Response);
 await userEvent.click(screen.getByRole('button', { name: 'auth.logout' }));
 await waitFor(() => expect(navigate).toHaveBeenCalledWith('/login'));
});
