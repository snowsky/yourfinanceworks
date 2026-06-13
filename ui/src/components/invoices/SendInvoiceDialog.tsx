import { useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Mail } from 'lucide-react';
import { apiRequest } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from '@/components/ui/dialog';
import { isSendBlockedByApproval } from '@/lib/invoiceSendPolicy';
import type { InvoiceSettings } from '@/lib/api/settings';

interface SendInvoiceDialogProps {
  invoice: { id: number; number: string; status: string; amount: number; client_name?: string; client_email?: string };
  settings?: { invoice_settings?: Partial<InvoiceSettings> } | null;
  onSent?: () => void;
}

export function SendInvoiceDialog({ invoice, settings, onSent }: SendInvoiceDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendCopy, setSendCopy] = useState<boolean>(settings?.invoice_settings?.send_copy ?? true);

  const blocked = isSendBlockedByApproval(
    { status: invoice.status, amount: Number(invoice.amount) },
    settings?.invoice_settings,
  );
  const recipient = invoice.client_email || invoice.client_name || '';

  const handleSend = async () => {
    setSending(true);
    try {
      await apiRequest('/email/send-invoice', {
        method: 'POST',
        body: JSON.stringify({ invoice_id: invoice.id, include_pdf: true, send_copy: sendCopy }),
      });
      toast.success(t('viewInvoice.send_success', { defaultValue: 'Invoice sent.' }));
      setOpen(false);
      onSent?.();
    } catch (error: any) {
      toast.error(error?.message || t('viewInvoice.send_failed', { defaultValue: 'Failed to send invoice.' }));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Mail className="h-4 w-4" />
          {t('viewInvoice.send', { defaultValue: 'Send' })}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('viewInvoice.send_title', { defaultValue: 'Send invoice' })}</DialogTitle>
          <DialogDescription>
            {t('viewInvoice.send_body', {
              defaultValue: 'Email invoice {{number}} to {{recipient}}?',
              number: invoice.number,
              recipient,
            })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          {blocked && (
            <p className="text-warning">
              {t('invoices.send_blocked_pending_approval', {
                defaultValue: 'This invoice must be approved before it can be sent.',
              })}
            </p>
          )}
          <label className="flex items-center gap-2">
            <Checkbox checked={sendCopy} onCheckedChange={(v) => setSendCopy(!!v)} />
            {t('viewInvoice.send_copy', { defaultValue: 'Send me a copy' })}
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={sending}>
            {t('common.cancel', { defaultValue: 'Cancel' })}
          </Button>
          <Button onClick={handleSend} disabled={blocked || sending}>
            {t('viewInvoice.send_confirm', { defaultValue: 'Send invoice' })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
