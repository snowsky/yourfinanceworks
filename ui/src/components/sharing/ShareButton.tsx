import { useState } from 'react';
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
}

export function ShareButton({ recordType, recordId, variant = 'outline', size = 'sm' }: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  const handleOpen = async () => {
    setOpen(true);
    if (token) return; // already loaded

    setLoading(true);
    try {
      // Check for existing token first (idempotent on backend, but avoids regenerating)
      const res = await shareTokenApi.createToken(recordType, recordId);
      setToken(res.token);
      // Use frontend origin so the URL matches the actual deployment
      setShareUrl(`${window.location.origin}/shared/${res.token}`);
    } catch {
      toast.error('Failed to generate share link');
      setOpen(false);
    } finally {
      setLoading(false);
    }
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
      setOpen(false);
      toast.success('Share link revoked');
    } catch {
      toast.error('Failed to revoke link');
    }
  };

  return (
    <>
      <Button variant={variant} size={size} onClick={handleOpen}>
        <Share2 className="h-4 w-4 mr-1" />
        Share
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link className="h-4 w-4" />
              Share link
            </DialogTitle>
          </DialogHeader>

          {loading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Generating link…</span>
            </div>
          ) : shareUrl ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Anyone with this link can view this record without logging in.
              </p>
              <div className="flex gap-2">
                <Input readOnly value={shareUrl} className="font-mono text-xs" />
                <Button size="icon" variant="outline" onClick={handleCopy} title="Copy link">
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={handleRevoke}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Revoke link
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
