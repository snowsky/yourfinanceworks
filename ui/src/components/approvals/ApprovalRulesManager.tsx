import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Settings, Info } from 'lucide-react';
import { toast } from 'sonner';
import { ApprovalRuleForm } from './ApprovalRuleForm';
import { ApprovalRulesList } from './ApprovalRulesList';
import { approvalApi } from '@/lib/api';
import { ApprovalRule } from '@/types';
import { Alert, AlertDescription } from '@/components/ui/alert';

export function ApprovalRulesManager() {
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<ApprovalRule | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleCreateRule = () => {
    setEditingRule(null);
    setShowForm(true);
  };

  const handleEditRule = (rule: ApprovalRule) => {
    setEditingRule(rule);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingRule(null);
  };

  const handleSubmitRule = async (data: any) => {
    try {
      setLoading(true);
      
      if (editingRule) {
        await approvalApi.updateApprovalRule(editingRule.id, data);
        toast.success('Approval rule updated successfully');
      } else {
        await approvalApi.createApprovalRule(data);
        toast.success('Approval rule created successfully');
      }
      
      setRefreshKey(prev => prev + 1);
      handleCloseForm();
    } catch (error) {
      console.error('Failed to save approval rule:', error);
      toast.error('Failed to save approval rule');
      throw error; // Re-throw to prevent form from closing
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="h-6 w-6" />
              <CardTitle>Approval Rules Management</CardTitle>
            </div>
            <Button onClick={handleCreateRule}>
              <Plus className="mr-2 h-4 w-4" />
              Create Rule
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              Approval rules determine which expenses require approval and who should approve them. 
              Rules are evaluated in priority order (highest first). The first matching rule will be applied.
              Configure amount thresholds, categories, and approval levels to match your organization's policies.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Rules List */}
      <ApprovalRulesList 
        onEdit={handleEditRule}
        onRefresh={handleRefresh}
        refreshKey={refreshKey}
      />

      {/* Rule Form Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingRule ? 'Edit Approval Rule' : 'Create Approval Rule'}
            </DialogTitle>
          </DialogHeader>
          <ApprovalRuleForm
            rule={editingRule || undefined}
            onSubmit={handleSubmitRule}
            onCancel={handleCloseForm}
            loading={loading}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}