import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Star, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { crmApi, CrmContact } from '@/lib/api/crm';

interface Props {
  clientId: number;
}

export function CrmContactsPanel({ clientId }: Props) {
  const [contacts, setContacts]     = useState<CrmContact[]>([]);
  const [loading, setLoading]       = useState(true);
  const [showForm, setShowForm]     = useState(false);
  const [saving, setSaving]         = useState(false);
  const [form, setForm]             = useState({ name: '', email: '', phone: '', role: '', is_primary: false });

  const load = async () => {
    setLoading(true);
    try {
      setContacts(await crmApi.contacts.list(clientId));
    } catch {
      toast.error('Failed to load CRM contacts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [clientId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await crmApi.contacts.create({ ...form, client_id: clientId });
      setForm({ name: '', email: '', phone: '', role: '', is_primary: false });
      setShowForm(false);
      await load();
    } catch {
      toast.error('Failed to create contact');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await crmApi.contacts.delete(id);
      setContacts(prev => prev.filter(c => c.id !== id));
    } catch {
      toast.error('Failed to delete contact');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">CRM Contacts</h3>
          <p className="text-sm text-muted-foreground">People at this client linked in the CRM</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setShowForm(v => !v)}>
          <Plus className="w-4 h-4 mr-1" />
          {showForm ? 'Cancel' : 'Add Contact'}
        </Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="rounded-lg border bg-muted/30 p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="crm-name">Name *</Label>
              <Input id="crm-name" required placeholder="Full name"
                value={form.name} onChange={e => setForm(v => ({ ...v, name: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="crm-role">Role</Label>
              <Input id="crm-role" placeholder="e.g. Decision Maker"
                value={form.role} onChange={e => setForm(v => ({ ...v, role: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="crm-email">Email</Label>
              <Input id="crm-email" type="email" placeholder="email@example.com"
                value={form.email} onChange={e => setForm(v => ({ ...v, email: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="crm-phone">Phone</Label>
              <Input id="crm-phone" placeholder="+1 555 000 0000"
                value={form.phone} onChange={e => setForm(v => ({ ...v, phone: e.target.value }))} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" id="crm-primary" checked={form.is_primary}
              onChange={e => setForm(v => ({ ...v, is_primary: e.target.checked }))} />
            <Label htmlFor="crm-primary" className="cursor-pointer">Primary contact</Label>
          </div>
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Save Contact
            </Button>
          </div>
        </form>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      )}

      {!loading && contacts.length === 0 && (
        <p className="text-sm text-muted-foreground py-4">No CRM contacts linked to this client yet.</p>
      )}

      <div className="space-y-2">
        {contacts.map(c => (
          <div key={c.id} className="flex items-start justify-between rounded-lg border bg-card p-3">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{c.name}</span>
                {c.is_primary && (
                  <Badge variant="secondary" className="text-xs gap-1">
                    <Star className="w-3 h-3" /> Primary
                  </Badge>
                )}
                {c.role && <span className="text-xs text-muted-foreground">{c.role}</span>}
              </div>
              <div className="text-xs text-muted-foreground flex gap-3">
                {c.email && <span>{c.email}</span>}
                {c.phone && <span>{c.phone}</span>}
              </div>
            </div>
            <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive h-7 w-7"
              onClick={() => handleDelete(c.id)}>
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
