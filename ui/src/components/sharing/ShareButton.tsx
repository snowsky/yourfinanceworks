import { useState, useEffect } from 'react';
import { Share2, Copy, Link, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { shareTokenApi, type RecordType } from '@/lib/api/share-tokens';

interface ShareButtonProps {
  recordType: RecordType;
  recordId: number;
  variant?: 'default' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  /** Controlled mode: when provided, the trigger button is not rendered */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function ShareButton({ recordType, recordId, variant = 'outline', size = 'sm', open: controlledOpen, onOpenChange }: ShareButtonProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? (onOpenChange ?? (() => {})) : setInternalOpen;
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);

  const fetchToken = async () => {
    setLoading(true);
    try {
      const res = await shareTokenApi.createToken(recordType, recordId);
      setToken(res.token);
      setExpiresAt(res.expires_at);
      setShareUrl(`${window.location.origin}/shared/${res.token}`);
    } catch {
      toast.error('Failed to generate share link');
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  // Reset confirmation state when modal closes
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!open) {
      setConfirmed(false);
      setToken(null);
      setShareUrl(null);
      setExpiresAt(null);
    }
  }, [open]);

  const handleOpen = () => {
    setOpen(true);
  };

  const handleConfirm = async () => {
    setConfirmed(true);
    await fetchToken();
  };

  const handleCopy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      toast.success('Link copied to clipboard');
    } catch {
      toast.error('Failed to copy link');
    }
  };

  const handleRevoke = async () => {
    if (!token) return;
    try {
      await shareTokenApi.revokeToken(token);
      setToken(null);
      setShareUrl(null);
      setExpiresAt(null);
      setOpen(false);
      toast.success('Share link revoked');
    } catch {
      toast.error('Failed to revoke link');
    }
  };

  return (
    <>
      {!isControlled && (
        <Button variant={variant} size={size} onClick={handleOpen}>
          <Share2 className="h-4 w-4 mr-1" />
          Share
        </Button>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link className="h-4 w-4" />
              Share link
            </DialogTitle>
          </DialogHeader>

          {!confirmed ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                This will generate a public link. Anyone with the link can view this record without logging in.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleConfirm}>
                  Generate link
                </Button>
              </div>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Generating link…</span>
            </div>
          ) : shareUrl ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Anyone with this link can view this record without logging in.
                {expiresAt && (
                  <span className="block mt-1 text-xs">
                    Expires {new Date(expiresAt).toLocaleString()}
                  </span>
                )}
              </p>
              <div className="flex gap-2">
                <Input readOnly value={shareUrl} className="font-mono text-xs" />
                <Button size="icon" variant="outline" onClick={handleCopy} title="Copy link">
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex justify-between items-center">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={handleRevoke}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Revoke link
                </Button>
                <Button size="sm" onClick={() => setOpen(false)}>
                  Done
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
