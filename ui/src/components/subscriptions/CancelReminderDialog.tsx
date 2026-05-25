import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { SubscriptionResponse } from '@/lib/api/subscriptions';

interface Props {
  subscription: SubscriptionResponse | null;
  open: boolean;
  onClose: () => void;
  onSubmit: (remindOn: string | null) => Promise<void>;
}

const todayPlusDays = (days: number): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export const CancelReminderDialog: React.FC<Props> = ({
  subscription,
  open,
  onClose,
  onSubmit,
}) => {
  const [date, setDate] = useState<string>(subscription?.cancel_reminder_at ?? todayPlusDays(7));
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (open) {
      setDate(subscription?.cancel_reminder_at ?? todayPlusDays(7));
    }
  }, [open, subscription]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSubmit(date || null);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    try {
      await onSubmit(null);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set cancel reminder</DialogTitle>
          <DialogDescription>
            {subscription
              ? `Get a reminder to cancel "${subscription.label}" on this date.`
              : null}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="cancel-reminder-date">Remind me on</Label>
          <Input
            id="cancel-reminder-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <DialogFooter className="gap-2">
          {subscription?.cancel_reminder_at ? (
            <Button variant="ghost" onClick={handleClear} disabled={saving}>
              Clear reminder
            </Button>
          ) : null}
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!date || saving}>
            Save reminder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
