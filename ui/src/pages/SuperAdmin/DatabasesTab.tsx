import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Database } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { apiRequest } from '../../lib/api';
import { toast } from 'sonner';
import type { DatabaseStatus } from './types';

interface DatabasesTabProps {
  databases: DatabaseStatus[];
  onDatabasesChanged: () => void;
}

export const DatabasesTab: React.FC<DatabasesTabProps> = ({ databases, onDatabasesChanged }) => {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();
  const [dbToRecreate, setDbToRecreate] = useState<DatabaseStatus | null>(null);

  const confirmRecreateDatabase = async () => {
    if (!dbToRecreate) return;
    try {
      await apiRequest(`/super-admin/tenants/${dbToRecreate.tenant_id}/database/recreate`, {
        method: 'POST',
      }, { skipTenant: true });
      toast.success('Database recreated successfully');
      setDbToRecreate(null);
      onDatabasesChanged();
    } catch (err) {
      toast.error('Failed to recreate database');
      setDbToRecreate(null);
    }
  };

  return (
    <>
      <ProfessionalCard className="slide-in">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-6">{t('superAdmin.database_management_title')}</h2>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('superAdmin.tenant_header')}</TableHead>
                  <TableHead>{t('superAdmin.database_header')}</TableHead>
                  <TableHead>{t('superAdmin.status_header')}</TableHead>
                  <TableHead>{t('superAdmin.message_header')}</TableHead>
                  <TableHead>{t('superAdmin.actions_header')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {databases.map((db) => (
                  <TableRow key={db.tenant_id}>
                    <TableCell className="font-medium">{db.tenant_name}</TableCell>
                    <TableCell>{db.database_name}</TableCell>
                    <TableCell>
                      <Badge variant={db.status === 'connected' ? 'default' : 'destructive'}>
                        {db.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{db.message || db.error || '-'}</TableCell>
                    <TableCell>
                      {currentUser && db.tenant_id !== currentUser.tenant_id ? (
                        <Button size="sm" variant="outline" onClick={() => setDbToRecreate(db)}>
                          <Database className="h-4 w-4 mr-2" />
                          {t('superAdmin.recreate_database_button')}
                        </Button>
                      ) : (
                        <div className="text-sm text-muted-foreground italic">
                          {t('superAdmin.own_database')}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </ProfessionalCard>

      {/* Recreate Database Confirmation Dialog */}
      <Dialog open={!!dbToRecreate} onOpenChange={open => { if (!open) setDbToRecreate(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('superAdmin.recreate_database_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>{String(t('superAdmin.recreate_database_confirmation_text', { tenantName: dbToRecreate?.tenant_name || '' } as any))}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setDbToRecreate(null)}>{t('superAdmin.cancel_button')}</Button>
              <Button variant="destructive" onClick={confirmRecreateDatabase}>{t('superAdmin.recreate_button')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
