import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';
import React from 'react';

import { usePermissionChecker } from '../usePermissions';
import * as permApi from '@/lib/api/permissions';

vi.mock('@/utils/auth', () => ({
  getCurrentUser: vi.fn(() => ({ id: 42 })),
}));

vi.mock('@/lib/api/permissions', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/permissions')>(
    '@/lib/api/permissions',
  );
  return {
    ...actual,
    getMyPermissions: vi.fn(),
    getComponentCatalog: vi.fn(),
  };
});

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('usePermissionChecker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns true while loading to avoid flashing disabled UI', () => {
    (permApi.getMyPermissions as any).mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => usePermissionChecker(), { wrapper });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.hasPermission('invoices', 'user')).toBe(false);
  });

  it('grants access when effective level meets requirement', async () => {
    (permApi.getMyPermissions as any).mockResolvedValue({
      user_id: 42,
      role: 'admin',
      is_superuser: false,
      permissions: [
        {
          component: 'invoices',
          role_level: 'admin',
          grant_level: null,
          effective_level: 'admin',
        },
      ],
    });
    const { result } = renderHook(() => usePermissionChecker(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission('invoices', 'admin')).toBe(true);
    expect(result.current.hasPermission('invoices', 'user')).toBe(true);
    expect(result.current.hasPermission('invoices', 'viewer')).toBe(true);
  });

  it('denies access when effective level is below requirement', async () => {
    (permApi.getMyPermissions as any).mockResolvedValue({
      user_id: 42,
      role: 'user',
      is_superuser: false,
      permissions: [
        {
          component: 'invoices',
          role_level: 'user',
          grant_level: 'viewer',
          effective_level: 'viewer',
        },
      ],
    });
    const { result } = renderHook(() => usePermissionChecker(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission('invoices', 'user')).toBe(false);
    expect(result.current.hasPermission('invoices', 'viewer')).toBe(true);
  });

  it('always grants superusers regardless of grant data', async () => {
    (permApi.getMyPermissions as any).mockResolvedValue({
      user_id: 42,
      role: 'viewer',
      is_superuser: true,
      permissions: [],
    });
    const { result } = renderHook(() => usePermissionChecker(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isSuperuser).toBe(true);
    expect(result.current.hasPermission('settings', 'admin')).toBe(true);
  });

  it('denies unknown components', async () => {
    (permApi.getMyPermissions as any).mockResolvedValue({
      user_id: 42,
      role: 'admin',
      is_superuser: false,
      permissions: [],
    });
    const { result } = renderHook(() => usePermissionChecker(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasPermission('not_a_component', 'viewer')).toBe(false);
  });
});
