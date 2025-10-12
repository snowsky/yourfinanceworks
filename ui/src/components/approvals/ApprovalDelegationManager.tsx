import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Settings, Info, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { DelegationForm } from './DelegationForm';
import { ActiveDelegationsList } from './ActiveDelegationsList';
import { approvalApi } from '@/lib/api';
import { ApprovalDelegate } from '@/types';
import { Alert, AlertDescription } from '@/components/ui/alert';

export function ApprovalDelegationManager() {
  const [showForm, setShowForm] = useState(false);
  const [editingDelegation, setEditingDelegation] = useState<ApprovalDelegate | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleCreateDelegation = () => {
    setEditingDelegation(null);
    setShowForm(true);
  };

  const handleEditDelegation = (delegation: ApprovalDelegate) => {
    setEditingDelegation(delegation);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingDelegation(null);
  };

  const handleSubmitDelegation = async (data: any) => {
    try {
      setLoading(true);
      
      if (editingDelegation) {
        await approvalApi.updateDelegation(editingDelegation.id, data);
        toast.success('Approval delegation updated successfully');
      } else {
        await approvalApi.createDelegation(data);
        toast.success('Approval delegation created successfully');
      }
      
      setRefreshKey(prev => prev + 1);
      handleCloseForm();
    } catch (error) {
      console.error('Failed to save approval delegation:', error);
      toast.error('Failed to save approval delegation');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDelegation = async (delegationId: number) => {
    try {
      setLoading(true);
      await approvalApi.deleteDelegation(delegationId);
      toast.success('Approval delegation deleted successfully');
      setRefreshKey(prev => prev + 1);
    } catch (error) {
      console.error('Failed to delete approval delegation:', error);
      toast.error('Failed to delete approval delegation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Approval Delegation Management</h2>
          <p className="text-muted-foreground">
            Set up temporary delegation of approval responsibilities to other users
          </p>
        </div>
        <Button onClick={handleCreateDelegation} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          New Delegation
        </Button>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          Delegations allow you to temporarily assign your approval responsibilities to another user. 
          This is useful when you're out of office or unavailable. Delegations are time-bounded and 
          can be activated or deactivated as needed.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Active Delegations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ActiveDelegationsList
            key={refreshKey}
            onEdit={handleEditDelegation}
            onDelete={handleDeleteDelegation}
            loading={loading}
          />
        </CardContent>
      </Card>

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingDelegation ? 'Edit Delegation' : 'Create New Delegation'}
            </DialogTitle>
          </DialogHeader>
          <DelegationForm
            delegation={editingDelegation}
            onSubmit={handleSubmitDelegation}
            onCancel={handleCloseForm}
            loading={loading}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}