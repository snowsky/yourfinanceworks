import { useState, useEffect } from 'react';
import { Share2, Copy, Link, Trash2, Loader2, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { settingsApi, type SharingSettings } from '@/lib/api';
import { shareTokenApi, type RecordType, type ShareAccessType } from '@/lib/api/share-tokens';

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
  const [sharingSettings, setSharingSettings] = useState<SharingSettings | null>(null);
  const [accessType, setAccessType] = useState<ShareAccessType>('public');
  const [expiresInHours, setExpiresInHours] = useState(24);
  const [oneTime, setOneTime] = useState(false);
  const [password, setPassword] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');

  useEffect(() => {
    if (!open) return;
    settingsApi.getSharingSettings()
      .then((sharing) => {
        setSharingSettings(sharing);
        setAccessType(sharing.default_access_type);
        setExpiresInHours(sharing.default_expiration_hours);
        setOneTime(sharing.default_one_time);
      })
      .catch(() => {
        setSharingSettings(null);
      });
  }, [open]);

  const fetchToken = async () => {
    setLoading(true);
    try {
      const res = await shareTokenApi.createToken(recordType, recordId, {
        access_type: accessType,
        expires_in_hours: expiresInHours,
        one_time: oneTime,
        password: accessType === 'password' ? password : undefined,
        security_question: accessType === 'question' ? securityQuestion : undefined,
        security_answer: accessType === 'question' ? securityAnswer : undefined,
      });
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
      setPassword('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    }
  }, [open]);

  const handleOpen = () => {
    setOpen(true);
  };

  const handleConfirm = async () => {
    if (accessType === 'password' && !password.trim()) {
      toast.error('Enter a password for this share link');
      return;
    }
    if (accessType === 'question' && (!securityQuestion.trim() || !securityAnswer.trim())) {
      toast.error('Enter a question and answer for this share link');
      return;
    }
    setConfirmed(true);
    await fetchToken();
  };

  const accessOptions = [
    { value: 'public' as const, label: 'Anyone with link', enabled: sharingSettings?.allow_public_links ?? true },
    { value: 'password' as const, label: 'Password', enabled: sharingSettings?.allow_password_links ?? true },
    { value: 'question' as const, label: 'Question and answer', enabled: sharingSettings?.allow_question_links ?? true },
  ].filter((option) => option.enabled);

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
              <div className="space-y-2">
                <Label>Access</Label>
                <Select value={accessType} onValueChange={(value) => setAccessType(value as ShareAccessType)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {accessOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {accessType === 'password' && (
                <div className="space-y-2">
                  <Label htmlFor="share-password">Password</Label>
                  <Input
                    id="share-password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                  />
                </div>
              )}

              {accessType === 'question' && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="share-question">Question</Label>
                    <Input
                      id="share-question"
                      value={securityQuestion}
                      onChange={(event) => setSecurityQuestion(event.target.value)}
                      placeholder="What is the project code?"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="share-answer">Answer</Label>
                    <Input
                      id="share-answer"
                      type="password"
                      value={securityAnswer}
                      onChange={(event) => setSecurityAnswer(event.target.value)}
                      autoComplete="new-password"
                    />
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="share-expiration">Expiration hours</Label>
                  <Input
                    id="share-expiration"
                    type="number"
                    min={sharingSettings?.require_expiration ? 1 : 0}
                    max={8760}
                    value={expiresInHours}
                    onChange={(event) => setExpiresInHours(Number(event.target.value))}
                  />
                  {!sharingSettings?.require_expiration && (
                    <p className="text-xs text-muted-foreground">Use 0 for no expiration.</p>
                  )}
                </div>
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div className="space-y-0.5">
                    <Label htmlFor="share-one-time">One-time link</Label>
                    <p className="text-xs text-muted-foreground">Deactivate after first view.</p>
                  </div>
                  <Switch id="share-one-time" checked={oneTime} onCheckedChange={setOneTime} />
                </div>
              </div>

              <p className="flex items-start gap-2 text-sm text-muted-foreground">
                <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0" />
                Shared records use a sanitized public view and do not require an app login.
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
                This link can view a sanitized copy of this record without an app login.
                {expiresAt && (
                  <span className="block mt-1 text-xs">
                    Expires {new Date(expiresAt).toLocaleString()}
                  </span>
                )}
                {oneTime && <span className="block mt-1 text-xs">This link can be used once.</span>}
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
