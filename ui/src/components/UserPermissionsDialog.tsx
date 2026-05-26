import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { toast } from '@/components/ui/sonner';
import {
  ComponentDescriptor,
  EffectivePermission,
  PermissionLevel,
  UserPermissions,
  clearUserPermission,
  getComponentCatalog,
  getUserPermissions,
  setUserPermission,
} from '@/lib/api/permissions';

interface UserPermissionsDialogProps {
  userId: number | null;
  userLabel?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  core_financial: 'Core Financial',
  secondary: 'Financial Views',
  plugins: 'Plugins',
  admin: 'Admin Areas',
};

// Sentinel for the "no grant" Select item — empty strings are invalid in Radix Select.
const NO_GRANT = '__none__';

export function UserPermissionsDialog({
  userId,
  userLabel,
  open,
  onOpenChange,
}: UserPermissionsDialogProps) {
  const queryClient = useQueryClient();

  const catalogQuery = useQuery({
    queryKey: ['permissions', 'components'],
    queryFn: getComponentCatalog,
    enabled: open,
    staleTime: 1000 * 60 * 30,
  });

  const userPermsQuery = useQuery<UserPermissions>({
    queryKey: ['permissions', 'user', userId],
    queryFn: () => getUserPermissions(userId as number),
    enabled: open && userId != null,
  });

  const [pendingChange, setPendingChange] = useState<string | null>(null);

  const setMutation = useMutation({
    mutationFn: ({ component, level }: { component: string; level: PermissionLevel }) =>
      setUserPermission(userId as number, component, level),
    onMutate: ({ component }) => setPendingChange(component),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserPermissions | undefined>(
        ['permissions', 'user', userId],
        (prev) => updateLocal(prev, updated),
      );
      toast.success('Permission updated');
    },
    onError: (err: unknown) =>
      toast.error(`Failed to update permission: ${(err as Error).message}`),
    onSettled: () => setPendingChange(null),
  });

  const clearMutation = useMutation({
    mutationFn: ({ component }: { component: string }) =>
      clearUserPermission(userId as number, component),
    onMutate: ({ component }) => setPendingChange(component),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserPermissions | undefined>(
        ['permissions', 'user', userId],
        (prev) => updateLocal(prev, updated),
      );
      toast.success('Permission reset to role default');
    },
    onError: (err: unknown) =>
      toast.error(`Failed to reset permission: ${(err as Error).message}`),
    onSettled: () => setPendingChange(null),
  });

  const groupedComponents = useMemo(() => {
    const groups: Record<string, ComponentDescriptor[]> = {};
    for (const c of catalogQuery.data?.components ?? []) {
      (groups[c.category] ||= []).push(c);
    }
    return groups;
  }, [catalogQuery.data]);

  const permLookup = useMemo(() => {
    const m = new Map<string, EffectivePermission>();
    for (const p of userPermsQuery.data?.permissions ?? []) m.set(p.component, p);
    return m;
  }, [userPermsQuery.data]);

  const role = userPermsQuery.data?.role ?? 'user';
  const isSuperuser = userPermsQuery.data?.is_superuser ?? false;
  const levels: PermissionLevel[] = catalogQuery.data?.levels ?? ['viewer', 'user', 'admin'];

  const onChange = (component: string, value: string) => {
    if (value === NO_GRANT) {
      clearMutation.mutate({ component });
    } else {
      setMutation.mutate({ component, level: value as PermissionLevel });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Manage permissions{userLabel ? ` — ${userLabel}` : ''}
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            Role <span className="font-medium">{role}</span> is the ceiling. Component grants can
            only restrict access further. {isSuperuser && '(Super admin — bypasses all checks.)'}
          </p>
        </DialogHeader>

        {(catalogQuery.isLoading || userPermsQuery.isLoading) && (
          <p className="text-sm text-muted-foreground py-6">Loading…</p>
        )}

        {catalogQuery.data && userPermsQuery.data && (
          <div className="space-y-6 py-2">
            {Object.entries(groupedComponents).map(([categoryKey, components]) => (
              <section key={categoryKey} className="space-y-2">
                <h4 className="text-sm font-semibold tracking-wide text-foreground">
                  {CATEGORY_LABELS[categoryKey] ?? categoryKey}
                </h4>
                <div className="rounded-md border border-border/60 divide-y">
                  {components.map(
                    (c) => {
                      const p = permLookup.get(c.key);
                      const grant = p?.grant_level;
                      const effective = p?.effective_level ?? 'viewer';
                      const isPending = pendingChange === c.key;
                      return (
                        <div
                          key={c.key}
                          className="flex items-center justify-between gap-4 px-3 py-2"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{c.label}</p>
                            <p className="text-xs text-muted-foreground truncate">
                              {c.description}
                            </p>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-xs text-muted-foreground">
                              Effective: <span className="font-medium">{effective}</span>
                            </span>
                            <Select
                              value={grant ?? NO_GRANT}
                              disabled={isPending || isSuperuser}
                              onValueChange={(v) => onChange(c.key, v)}
                            >
                              <SelectTrigger className="w-36 h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NO_GRANT}>Role default</SelectItem>
                                {levels.map((lvl) => (
                                  <SelectItem key={lvl} value={lvl}>
                                    {lvl}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      );
                    },
                  )}
                </div>
              </section>
            ))}
          </div>
        )}

        <DialogFooter>
          <ProfessionalButton variant="secondary" onClick={() => onOpenChange(false)}>
            Close
          </ProfessionalButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function updateLocal(
  prev: UserPermissions | undefined,
  updated: EffectivePermission,
): UserPermissions | undefined {
  if (!prev) return prev;
  const next = prev.permissions.map((p) =>
    p.component === updated.component ? updated : p,
  );
  return { ...prev, permissions: next };
}
