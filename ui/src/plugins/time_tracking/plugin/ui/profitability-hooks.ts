import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest, expenseApi, type Expense } from '@/lib/api';
import { getCurrentUser } from '@/utils/auth';
import { projectApi, timeEntryApi, type TimeEntry } from './api';
import { getProjectProfitability, profitabilityApi, type TenantContributor, type BackfillPreview, type CostRateWrite, type Replacement } from './profitability-api';

const events = ['storage', 'org-switched', 'user-updated', 'auth-updated', 'auth-changed'];
let authorizationEpoch = 0;
const listeners = new Set<() => void>();
const authorizationChanged = () => { authorizationEpoch += 1; listeners.forEach(notify => notify()); };
const scopeSnapshot = () => { const user = getCurrentUser(); return `${localStorage.getItem('selected_tenant_id') || user?.tenant_id || ''}:${user?.id || ''}:${user?.role || ''}:${authorizationEpoch}`; };
const subscribe = (notify: () => void) => {
  if (!listeners.size) events.forEach(e => window.addEventListener(e, authorizationChanged));
  listeners.add(notify);
  return () => { listeners.delete(notify); if (!listeners.size) events.forEach(e => window.removeEventListener(e, authorizationChanged)); };
};
export function useCostAccess() {
  const scope = useSyncExternalStore(subscribe, scopeSnapshot);
  const [tenant, user] = scope.split(':');
  const me = useQuery({ queryKey: ['cost-access', scope], queryFn: () => apiRequest<{ id: number; tenant_id: number; role: string; is_active?: boolean; organizations?: { id: number; role: string; is_active?: boolean }[] }>('/auth/me', {}, { skipTenant: true }), enabled: !!tenant && !!user, staleTime: 0, retry: false, refetchOnWindowFocus: 'always' });
  const membership = me.data?.organizations?.find(o => String(o.id) === tenant);
  const allowed = !!me.data && !me.isError && me.data.is_active !== false && (membership ? membership.role === 'admin' && membership.is_active !== false : String(me.data.tenant_id) === tenant && me.data.role === 'admin');
  return { scope, tenant, user, allowed };
}
export function useProjectProfitability(projectId: number) {
  const access = useCostAccess();
  const qc = useQueryClient();
  useEffect(() => qc.getMutationCache().subscribe(event => {
    if (event.type === 'updated' && event.mutation.state.status === 'success') {
      void qc.invalidateQueries({ queryKey: ['project-profitability', access.scope] });
    }
  }), [qc, access.scope]);
  const query = useQuery({ queryKey: ['project-profitability', access.scope, projectId], queryFn: async ({ signal }) => {
    const value = await getProjectProfitability(projectId, signal);
    if (scopeSnapshot() !== access.scope) throw new Error('Scope changed');
    return value;
  }, enabled: access.allowed && !!projectId, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: 'always' });
  return { ...query, data: access.allowed && !query.isError ? query.data : undefined, access };
}
export function useCostSetup(projectId: number, currency: string, contributor: number) {
  const access = useCostAccess();
  const qc = useQueryClient();
  const currentAccess = useRef(access);
  currentAccess.current = access;
  const guard = () => { if (!currentAccess.current.allowed || scopeSnapshot() !== access.scope) throw new Error('Authorization changed'); };
  const details = useQuery({ queryKey: ['cost-details', access.scope, projectId], enabled: access.allowed, gcTime: 0, queryFn: async () => {
    guard();
    const loadEntries = async () => {
      const entries: TimeEntry[] = [];
      for (let skip = 0; ; skip += 500) {
        guard();
        const page = await timeEntryApi.list({ project_id: projectId, skip, limit: 500 });
        entries.push(...page);
        if (page.length < 500) return entries;
      }
    };
    const loadExpenses = async () => {
      const expenses: Expense[] = [];
      for (let skip = 0; ; skip += 100) {
        guard();
        const page = await expenseApi.getExpensesPaginated({ skip, limit: 100 });
        expenses.push(...page.expenses);
        if (!page.expenses.length || expenses.length >= page.total) return expenses;
      }
    };
    const [users, entries, expenses, tasks] = await Promise.all([apiRequest<TenantContributor[]>('/auth/users'), loadEntries(), loadExpenses(), projectApi.listTasks(projectId)]);
    guard(); return { users, entries, expenses, tasks };
  } });
  const rates = useQuery({ queryKey: ['cost-rates', access.scope, contributor, currency], enabled: access.allowed && !!contributor && !!currency, gcTime: 0, queryFn: async () => { guard(); const result = await profitabilityApi.rates(contributor, currency); guard(); return result; } });
  const changed = () => { void qc.invalidateQueries({ queryKey: ['project-profitability', access.scope] }); void qc.invalidateQueries({ queryKey: ['cost-rates', access.scope] }); };
  const saveRate = useMutation({ mutationFn: (data: CostRateWrite) => { guard(); return profitabilityApi.saveRate(data); }, onSuccess: changed });
  const preview = useMutation({ mutationFn: async (ids: number[]) => { guard(); const result = await profitabilityApi.preview(projectId, ids); guard(); return result; } });
  const apply = useMutation({ mutationFn: (data: BackfillPreview) => { guard(); return profitabilityApi.apply(projectId, data); }, onSuccess: changed });
  const replace = useMutation({ mutationFn: ({ entry, data }: { entry: number; data: Replacement }) => { guard(); return profitabilityApi.replace(projectId, entry, data); }, onSuccess: changed });
  return { access, details: { ...details, data: access.allowed && !details.isError ? details.data : undefined }, rates: { ...rates, data: access.allowed && !rates.isError ? rates.data : undefined }, saveRate, preview, apply, replace };
}
