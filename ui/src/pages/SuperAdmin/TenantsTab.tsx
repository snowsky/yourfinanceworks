import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Building, Edit, Trash2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { apiRequest } from '../../lib/api';
import { toast } from 'sonner';
import type { Tenant } from './types';

interface TenantsTabProps {
  tenants: Tenant[];
  selectedTenantForUsersId?: number;
  onTenantsChanged: () => void;
  onUsersChanged: (tenantId?: number) => void;
  onDatabasesChanged: () => void;
}

export const TenantsTab: React.FC<TenantsTabProps> = ({
  tenants,
  selectedTenantForUsersId,
  onTenantsChanged,
  onUsersChanged,
  onDatabasesChanged,
}) => {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();

  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [createTenantForm, setCreateTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [editTenant, setEditTenant] = useState<Tenant | null>(null);
  const [editTenantForm, setEditTenantForm] = useState({ name: '', email: '', default_currency: 'USD' });
  const [tenantToDelete, setTenantToDelete] = useState<Tenant | null>(null);

  const handleCreateTenant = async () => {
    try {
      await apiRequest('/super-admin/tenants', {
        method: 'POST',
        body: JSON.stringify(createTenantForm),
      }, { skipTenant: true });

      setShowCreateTenant(false);
      setCreateTenantForm({ name: '', email: '', default_currency: 'USD' });
      toast.success('Organization created successfully');
      onTenantsChanged();
      onUsersChanged(selectedTenantForUsersId);
      onDatabasesChanged();
    } catch (err: any) {
      const errorMessage = err?.detail || err?.message || 'Failed to create organization';
      if (errorMessage.includes('email') && errorMessage.includes('valid email address')) {
        toast.error('Please enter a valid email address');
      } else if (errorMessage.includes('email') && errorMessage.includes('already registered')) {
        toast.error('Email is already registered. Please use a different email.');
      } else if (errorMessage.includes('name') && errorMessage.includes('already exists')) {
        toast.error('Organization name already exists. Please choose a different name.');
      } else if (errorMessage.startsWith('Validation error:')) {
        toast.error('Please check your input and try again');
      } else {
        toast.error(errorMessage);
      }
    }
  };

  const handleEditTenant = (tenant: Tenant) => {
    setEditTenant(tenant);
    setEditTenantForm({
      name: tenant.name,
      email: tenant.email,
      default_currency: tenant.default_currency || 'USD',
    });
  };

  const handleUpdateTenant = async () => {
    if (!editTenant) return;
    try {
      await apiRequest(`/super-admin/tenants/${editTenant.id}`, {
        method: 'PUT',
        body: JSON.stringify(editTenantForm),
      }, { skipTenant: true });
      setEditTenant(null);
      toast.success('Tenant updated successfully');
      onTenantsChanged();
    } catch (err) {
      toast.error('Failed to update tenant');
    }
  };

  const confirmDeleteTenant = async () => {
    if (!tenantToDelete) return;
    try {
      await apiRequest(`/super-admin/tenants/${tenantToDelete.id}`, {
        method: 'DELETE',
      }, { skipTenant: true });
      toast.success('Tenant deleted successfully');
      setTenantToDelete(null);
      onTenantsChanged();
      onUsersChanged(selectedTenantForUsersId);
      onDatabasesChanged();
    } catch (err) {
      toast.error('Failed to delete tenant');
      setTenantToDelete(null);
    }
  };

  const handleToggleTenantStatus = async (tenant: Tenant) => {
    try {
      await apiRequest(`/super-admin/tenants/${tenant.id}/toggle-status`, {
        method: 'PATCH',
      }, { skipTenant: true });
      toast.success(`Organization ${tenant.is_active ? 'disabled' : 'enabled'} successfully`);
      onTenantsChanged();
    } catch (err) {
      toast.error('Failed to toggle organization status');
    }
  };

  return (
    <>
      <ProfessionalCard className="slide-in">
        <div className="p-6">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
            <h2 className="text-xl font-semibold">{t('superAdmin.organizations_management_title')}</h2>
            <Dialog open={showCreateTenant} onOpenChange={setShowCreateTenant}>
              <DialogTrigger asChild>
                <Button className="w-full sm:w-auto">
                  <Building className="h-4 w-4 mr-2" />
                  {t('superAdmin.create_organization_button')}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t('superAdmin.create_new_organization_title')}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="tenant-name">{t('superAdmin.organization_name_label')}</Label>
                    <Input
                      id="tenant-name"
                      value={createTenantForm.name}
                      onChange={(e) => setCreateTenantForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder={t('superAdmin.organization_name_placeholder')}
                    />
                  </div>
                  <div>
                    <Label htmlFor="tenant-email">{t('superAdmin.email_label')}</Label>
                    <Input
                      id="tenant-email"
                      type="email"
                      value={createTenantForm.email}
                      onChange={(e) => setCreateTenantForm(prev => ({ ...prev, email: e.target.value }))}
                      placeholder={t('superAdmin.email_placeholder')}
                    />
                  </div>
                  <div>
                    <Label htmlFor="tenant-currency">{t('superAdmin.default_currency_label')}</Label>
                    <CurrencySelector
                      value={createTenantForm.default_currency}
                      onValueChange={(value) => setCreateTenantForm(prev => ({ ...prev, default_currency: value }))}
                      placeholder={t('superAdmin.select_currency')}
                    />
                  </div>
                  <Button onClick={handleCreateTenant} className="w-full">{t('superAdmin.create_organization_button')}</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('superAdmin.name_header')}</TableHead>
                  <TableHead>{t('superAdmin.email_header')}</TableHead>
                  <TableHead>{t('superAdmin.users_header')}</TableHead>
                  <TableHead>{t('superAdmin.currency_header')}</TableHead>
                  <TableHead>{t('superAdmin.status_header')}</TableHead>
                  <TableHead>{t('superAdmin.created_at_header')}</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants
                  .slice()
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map((tenant) => (
                    <TableRow key={tenant.id}>
                      <TableCell className="font-medium">{tenant.name}</TableCell>
                      <TableCell>{tenant.email}</TableCell>
                      <TableCell>{tenant.user_count}</TableCell>
                      <TableCell>{tenant.default_currency}</TableCell>
                      <TableCell>
                        <Badge variant={tenant.is_active ? 'default' : 'secondary'}>
                          {tenant.is_active ? t('superAdmin.active_status') : t('superAdmin.inactive_status')}
                        </Badge>
                      </TableCell>
                      <TableCell>{new Date(tenant.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button size="sm" variant="outline" onClick={() => handleEditTenant(tenant)}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          {currentUser && tenant.id !== currentUser.tenant_id && (
                            <Button
                              size="sm"
                              variant={tenant.is_active ? 'destructive' : 'default'}
                              onClick={() => handleToggleTenantStatus(tenant)}
                            >
                              {tenant.is_active ? t('superAdmin.disable_button') : t('superAdmin.enable_button')}
                            </Button>
                          )}
                          {currentUser && tenant.id !== currentUser.tenant_id && (
                            <Button size="sm" variant="outline" onClick={() => setTenantToDelete(tenant)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </ProfessionalCard>

      {/* Edit Tenant Dialog */}
      <Dialog open={!!editTenant} onOpenChange={open => { if (!open) setEditTenant(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.edit_organization_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="edit-tenant-name">{t('superAdmin.organization_name_label')}</Label>
              <Input id="edit-tenant-name" value={editTenantForm.name} onChange={e => setEditTenantForm(prev => ({ ...prev, name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-email">{t('superAdmin.email_label')}</Label>
              <Input id="edit-tenant-email" type="email" value={editTenantForm.email} onChange={e => setEditTenantForm(prev => ({ ...prev, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="edit-tenant-currency">{t('superAdmin.default_currency_label')}</Label>
              <CurrencySelector
                value={editTenantForm.default_currency}
                onValueChange={value => setEditTenantForm(prev => ({ ...prev, default_currency: value }))}
                placeholder={t('superAdmin.select_currency')}
              />
            </div>
            <Button onClick={handleUpdateTenant} className="w-full">{t('superAdmin.update_tenant_button')}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Tenant Confirmation Dialog */}
      <Dialog open={!!tenantToDelete} onOpenChange={open => { if (!open) setTenantToDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.delete_tenant_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>{String(t('superAdmin.delete_tenant_confirmation_text', { tenantName: tenantToDelete?.name || '' } as any))}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setTenantToDelete(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmDeleteTenant}>{t('superAdmin.delete_button')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
