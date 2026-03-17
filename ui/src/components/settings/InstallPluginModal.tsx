import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, GitBranch, Download, CheckCircle, XCircle, Clock, AlertTriangle, RotateCcw } from 'lucide-react';
import { pluginApi, InstallJob } from '@/lib/api/plugins';
import { toast } from 'sonner';

interface InstallPluginModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInstalled?: (pluginId: string) => void;
}

type ModalState = 'form' | 'installing' | 'done' | 'failed';

const StepIcon: React.FC<{ status: InstallJob['steps'][0]['status'] }> = ({ status }) => {
  switch (status) {
    case 'done':
      return <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />;
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-500 shrink-0" />;
    case 'running':
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />;
    default:
      return <Clock className="w-4 h-4 text-gray-300 shrink-0" />;
  }
};

export const InstallPluginModal: React.FC<InstallPluginModalProps> = ({ open, onOpenChange, onInstalled }) => {
  const [gitUrl, setGitUrl] = useState('');
  const [ref, setRef] = useState('main');
  const [modalState, setModalState] = useState<ModalState>('form');
  const [job, setJob] = useState<InstallJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    if (!open) {
      stopPolling();
    }
    return () => stopPolling();
  }, [open]);

  const startPolling = (jobId: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const updated = await pluginApi.getInstallStatus(jobId);
        setJob(updated);
        if (updated.status === 'done') {
          stopPolling();
          setModalState('done');
          if (updated.plugin_id) {
            onInstalled?.(updated.plugin_id);
          }
        } else if (updated.status === 'failed') {
          stopPolling();
          setModalState('failed');
        }
      } catch {
        // silently retry
      }
    }, 2000);
  };

  const handleInstall = async () => {
    if (!gitUrl.trim()) return;
    setSubmitting(true);
    try {
      const { job_id } = await pluginApi.installFromGit(gitUrl.trim(), ref.trim() || 'main');
      setModalState('installing');
      // Fetch initial state immediately
      const initial = await pluginApi.getInstallStatus(job_id);
      setJob(initial);
      startPolling(job_id);
    } catch (err: any) {
      toast.error(err?.message ?? 'Failed to start installation');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    stopPolling();
    setModalState('form');
    setJob(null);
    setGitUrl('');
    setRef('main');
    onOpenChange(false);
  };

  const handleReset = () => {
    stopPolling();
    setModalState('form');
    setJob(null);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="w-5 h-5 text-blue-600" />
            Install Plugin from Git
          </DialogTitle>
          <DialogDescription>
            Clone a plugin repository and install it into this instance.
            A server restart is required after installation.
          </DialogDescription>
        </DialogHeader>

        {/* ── FORM ─────────────────────────────────────────────────── */}
        {modalState === 'form' && (
          <>
            <div className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label htmlFor="git-url">Repository URL</Label>
                <Input
                  id="git-url"
                  placeholder="https://github.com/org/my-plugin"
                  value={gitUrl}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setGitUrl(e.target.value)}
                  onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && handleInstall()}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="git-ref" className="flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5" />
                  Branch / Tag
                </Label>
                <Input
                  id="git-ref"
                  placeholder="main"
                  value={ref}
                  onChange={e => setRef(e.target.value)}
                />
              </div>

              <Alert className="border-amber-200 bg-amber-50">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-800 text-sm">
                  <strong>Restart required.</strong> After installation the server must be
                  restarted and the frontend rebuilt before the plugin becomes active.
                  Only install plugins from sources you trust.
                </AlertDescription>
              </Alert>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>Cancel</Button>
              <Button
                onClick={handleInstall}
                disabled={submitting || !gitUrl.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Install Plugin
              </Button>
            </DialogFooter>
          </>
        )}

        {/* ── INSTALLING ───────────────────────────────────────────── */}
        {(modalState === 'installing' || modalState === 'done' || modalState === 'failed') && job && (
          <>
            <div className="py-2 space-y-3">
              {/* Status badge */}
              <div className="flex items-center gap-2">
                {modalState === 'installing' && (
                  <Badge className="bg-blue-100 text-blue-700 border-blue-200">
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" /> Installing…
                  </Badge>
                )}
                {modalState === 'done' && (
                  <Badge className="bg-green-100 text-green-700 border-green-200">
                    <CheckCircle className="w-3 h-3 mr-1" /> Installed
                  </Badge>
                )}
                {modalState === 'failed' && (
                  <Badge className="bg-red-100 text-red-700 border-red-200">
                    <XCircle className="w-3 h-3 mr-1" /> Failed
                  </Badge>
                )}
                {job.plugin_id && (
                  <span className="text-sm text-muted-foreground font-mono">{job.plugin_id}</span>
                )}
              </div>

              {/* Steps */}
              <div className="rounded-md border bg-gray-50 p-3 space-y-2">
                {job.steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <StepIcon status={step.status} />
                    <div className="flex-1">
                      <span className={step.status === 'pending' ? 'text-gray-400' : 'text-gray-800'}>
                        {step.label}
                      </span>
                      {step.detail && (
                        <p className="text-xs text-muted-foreground mt-0.5">{step.detail}</p>
                      )}
                    </div>
                  </div>
                ))}
                {modalState === 'installing' && job.steps.length === 0 && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Starting…
                  </div>
                )}
              </div>

              {/* Error detail */}
              {modalState === 'failed' && job.error && (
                <Alert className="border-red-200 bg-red-50">
                  <XCircle className="h-4 w-4 text-red-600" />
                  <AlertDescription className="text-red-800 text-sm">{job.error}</AlertDescription>
                </Alert>
              )}

              {/* Success note */}
              {modalState === 'done' && (
                <Alert className="border-blue-200 bg-blue-50">
                  <AlertTriangle className="h-4 w-4 text-blue-600" />
                  <AlertDescription className="text-blue-800 text-sm">
                    <strong>Restart required.</strong> Run{' '}
                    <code className="bg-blue-100 px-1 rounded">docker-compose restart</code> and
                    rebuild the frontend to activate the plugin.
                  </AlertDescription>
                </Alert>
              )}
            </div>

            <DialogFooter>
              {modalState === 'failed' && (
                <Button variant="outline" onClick={handleReset} className="mr-auto">
                  <RotateCcw className="w-4 h-4 mr-1" /> Try Again
                </Button>
              )}
              <Button variant={modalState === 'done' ? 'default' : 'outline'} onClick={handleClose}>
                {modalState === 'done' ? 'Done' : 'Close'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
