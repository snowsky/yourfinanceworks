import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CircleHelp, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { usePlugins } from '@/contexts/PluginContext';
import { pluginAccessApi, PluginAccessRequestRecord } from '@/lib/plugin-access';

interface ApprovalRequiredEventDetail {
  error_code?: string;
  message?: string;
  request?: PluginAccessRequestRecord;
}

type NotificationKind = 'success' | 'error' | 'processing' | 'join_request';
type NotificationFn = (type: NotificationKind, title: string, message: string, actionUrl?: string) => string;
type NotificationWindow = Window & { addAINotification?: NotificationFn };
const PLUGIN_ACCESS_USER_GUIDE_PATH = '/docs/user-guide/PLUGIN_DATA_ACCESS_APPROVALS_USER_GUIDE.md';

function describeAccessType(accessType: string): string {
  return accessType === 'write' ? 'modify' : 'read';
}

export const PluginAccessApprovalPrompt: React.FC = () => {
  const { getPlugin } = usePlugins();
  const [queue, setQueue] = useState<PluginAccessRequestRecord[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const current = queue[0];

  const sourceName = useMemo(() => {
    if (!current) return '';
    return getPlugin(current.source_plugin)?.name || current.source_plugin;
  }, [current, getPlugin]);

  const targetName = useMemo(() => {
    if (!current) return '';
    return getPlugin(current.target_plugin)?.name || current.target_plugin;
  }, [current, getPlugin]);

  const notifyBell = useCallback((type: 'success' | 'error' | 'processing', title: string, message: string) => {
    const addNotification = (window as NotificationWindow).addAINotification;
    if (typeof addNotification === 'function') {
      addNotification(type, title, message);
    }
  }, []);

  const enqueueRequest = useCallback((request: PluginAccessRequestRecord, notify = true) => {
    setQueue(prev => {
      if (prev.some(item => item.id === request.id)) {
        return prev;
      }
      return [...prev, request];
    });

    if (notify) {
      const message = `${request.source_plugin} requested ${describeAccessType(request.access_type)} access to ${request.target_plugin}.`;
      notifyBell('processing', 'Plugin Access Approval Needed', message);
      toast.info(message);
    }
  }, [notifyBell]);

  useEffect(() => {
    let mounted = true;

    const loadPending = async () => {
      // Only load pending requests if user is authenticated
      const token = localStorage.getItem('token');
      if (!token) {
        return;
      }

      try {
        const result = await pluginAccessApi.listPendingMine();
        if (!mounted) return;
        (result.requests || []).forEach(req => enqueueRequest(req, false));
      } catch {
        // Ignore silently: prompt also works from live events.
      }
    };

    loadPending();
    return () => {
      mounted = false;
    };
  }, [enqueueRequest]);

  useEffect(() => {
    const onApprovalRequired = (event: Event) => {
      const customEvent = event as CustomEvent<ApprovalRequiredEventDetail>;
      const request = customEvent.detail?.request;
      if (!request?.id) {
        return;
      }
      enqueueRequest(request, true);
    };

    window.addEventListener('plugin-access-approval-required', onApprovalRequired as EventListener);
    return () => {
      window.removeEventListener('plugin-access-approval-required', onApprovalRequired as EventListener);
    };
  }, [enqueueRequest]);

  const removeCurrent = useCallback(() => {
    setQueue(prev => prev.slice(1));
  }, []);

  const handleResolve = useCallback(async (action: 'approve' | 'deny') => {
    if (!current || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    try {
      if (action === 'approve') {
        await pluginAccessApi.approve(current.id);
        notifyBell(
          'success',
          'Plugin Access Approved',
          `${sourceName} can now ${describeAccessType(current.access_type)} ${targetName} data.`
        );
        toast.success(`${sourceName} can now ${describeAccessType(current.access_type)} ${targetName} data.`);
      } else {
        await pluginAccessApi.deny(current.id);
        notifyBell(
          'error',
          'Plugin Access Denied',
          `${sourceName} was denied access to ${targetName} data.`
        );
        toast.error(`${sourceName} was denied access to ${targetName} data.`);
      }

      window.dispatchEvent(new CustomEvent('plugin-access-approval-resolved', {
        detail: { requestId: current.id, action },
      }));
      removeCurrent();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to resolve plugin access request';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [current, isSubmitting, notifyBell, sourceName, targetName, removeCurrent]);

  return (
    <Dialog open={!!current}>
      <DialogContent
        onInteractOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-500" />
            Plugin Data Access Request
          </DialogTitle>
          <DialogDescription>
            {current ? (
              <>
                <strong>{sourceName}</strong> wants to {describeAccessType(current.access_type)} data from{' '}
                <strong>{targetName}</strong>.
              </>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        {current?.reason && (
          <div className="rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
            Reason: {current.reason}
          </div>
        )}

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>Need help deciding?</span>
          <span>
            Read the user guide at {PLUGIN_ACCESS_USER_GUIDE_PATH}
          </span>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                aria-label="About plugin access approvals"
              >
                <CircleHelp className="w-3.5 h-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent>
              Learn when to allow or deny plugin data access requests.
            </TooltipContent>
          </Tooltip>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleResolve('deny')}
            disabled={isSubmitting}
          >
            Deny
          </Button>
          <Button
            type="button"
            onClick={() => handleResolve('approve')}
            disabled={isSubmitting}
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
            Allow Access
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
