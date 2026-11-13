import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useCostSetup, useProjectProfitability } from './profitability-hooks';
const mock = vi.hoisted(() => ({ request: vi.fn(), read: vi.fn(), preview: vi.fn(), expenses: vi.fn(), identity: 8, tenant: '1', role: 'admin' }));
vi.mock('@/lib/api', () => ({ apiRequest: mock.request, userApi: { getUsers: async () => [] }, expenseApi: { getExpenses: async () => [], getExpensesPaginated: mock.expenses } }));
vi.mock('@/utils/auth', () => ({ getCurrentUser: () => ({ id: mock.identity, tenant_id: 1, role: mock.role }) }));
vi.mock('./api', () => ({ projectApi: { listTasks: async () => [] }, timeEntryApi: { list: async () => [] } }));
vi.mock('./profitability-api', () => ({ getProjectProfitability: mock.read, profitabilityApi: { preview: mock.preview } }));
let client: QueryClient;
beforeEach(() => { mock.tenant = '1'; mock.role = 'admin'; mock.identity = 8; mock.expenses.mockReset(); mock.expenses.mockResolvedValue({ expenses: [], total: 0 }); mock.request.mockImplementation(async () => ({ id: mock.identity, tenant_id: 1, role: mock.role, organizations: [{ id: 1, role: mock.role }, { id: 2, role: mock.role }] })); mock.read.mockReset(); vi.mocked(localStorage.getItem).mockImplementation(key => key === 'selected_tenant_id' ? mock.tenant : null); client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); });
afterEach(() => { cleanup(); client.clear(); });
const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
it('never displays previous tenant costs while switching and rejects an old response', async () => {
  let finishOld: (value: unknown) => void = () => {};
  mock.read.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; })).mockResolvedValueOnce({ known_cost: '20' });
  const { result } = renderHook(() => useProjectProfitability(4), { wrapper });
  await waitFor(() => expect(mock.read).toHaveBeenCalledTimes(1));
  act(() => { mock.tenant = '2'; window.dispatchEvent(new Event('org-switched')); });
  expect(result.current.data).toBeUndefined();
  await waitFor(() => expect(result.current.data?.known_cost).toBe('20'));
  await act(async () => finishOld({ known_cost: '99999' }));
  expect(result.current.data?.known_cost).toBe('20');
});
it('removes displayed costs on membership revocation and disables private queries', async () => {
  mock.read.mockResolvedValue({ known_cost: '580' });
  const { result } = renderHook(() => useProjectProfitability(4), { wrapper });
  await waitFor(() => expect(result.current.data?.known_cost).toBe('580'));
  act(() => { mock.role = 'user'; window.dispatchEvent(new Event('user-updated')); });
  expect(result.current.data).toBeUndefined();
  await waitFor(() => expect(result.current.access.allowed).toBe(false));
  expect(mock.read).toHaveBeenCalledTimes(1);
});
it('rejects an in-flight preview after a tenant switch', async () => {
  let finish: (value: unknown) => void = () => {};
  mock.preview.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { result } = renderHook(() => useCostSetup(4, 'USD', 0), { wrapper });
  await waitFor(() => expect(result.current.access.allowed).toBe(true));
  let pending: Promise<unknown>;
  act(() => { pending = result.current.preview.mutateAsync([1]).catch(error => error); });
  await waitFor(() => expect(mock.preview).toHaveBeenCalled());
  act(() => { mock.tenant = '2'; window.dispatchEvent(new Event('org-switched')); });
  await act(async () => finish({ project_id: 4 }));
  expect(await pending!).toBeInstanceOf(Error);
});
it('does not call private profitability for an ordinary tenant member', async () => {
  mock.role = 'user';
  const { result } = renderHook(() => useProjectProfitability(4), { wrapper });
  await waitFor(() => expect(mock.request).toHaveBeenCalled());
  expect(result.current.access.allowed).toBe(false);
  expect(mock.read).not.toHaveBeenCalled();
});

it('loads eligible project expenses beyond the first tenant expense page', async () => {
  const firstPage = Array.from({ length: 100 }, (_, index) => ({ id: index + 1, vendor: 'Other project' }));
  mock.expenses.mockResolvedValueOnce({ expenses: firstPage, total: 101 }).mockResolvedValueOnce({ expenses: [{ id: 999, vendor: 'Older eligible supplier' }], total: 101 });
  const { result } = renderHook(() => useCostSetup(4, 'USD', 0), { wrapper });
  await waitFor(() => expect(result.current.details.data?.expenses).toContainEqual({ id: 999, vendor: 'Older eligible supplier' }));
  expect(mock.expenses).toHaveBeenNthCalledWith(1, { skip: 0, limit: 100 });
  expect(mock.expenses).toHaveBeenNthCalledWith(2, { skip: 100, limit: 100 });
});
it('immediately hides mounted session costs on same-document auth identity replacement', async () => {
  mock.read.mockResolvedValue({ known_cost: '580' });
  const { result } = renderHook(() => useProjectProfitability(4), { wrapper });
  await waitFor(() => expect(result.current.data?.known_cost).toBe('580'));
  mock.request.mockImplementation(() => new Promise(() => {}));
  act(() => { mock.identity = 19; window.dispatchEvent(new Event('auth-changed')); });
  expect(result.current.data).toBeUndefined();
  expect(result.current.access.allowed).toBe(false);
});
