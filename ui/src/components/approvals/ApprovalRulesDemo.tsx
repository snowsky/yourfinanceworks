import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Settings, Plus, Edit, Trash2, ArrowUp, ArrowDown } from 'lucide-react';

export function ApprovalRulesDemo() {
  const mockRules = [
    {
      id: 1,
      name: 'Manager Approval',
      min_amount: 100,
      max_amount: 1000,
      category_filter: '["Travel", "Meals"]',
      currency: 'USD',
      approval_level: 1,
      approver_id: 1,
      approver_name: 'John Doe',
      is_active: true,
      priority: 10,
      auto_approve_below: 50,
    },
    {
      id: 2,
      name: 'Director Approval',
      min_amount: 1000,
      max_amount: undefined,
      category_filter: undefined,
      currency: 'USD',
      approval_level: 2,
      approver_id: 2,
      approver_name: 'Jane Smith',
      is_active: true,
      priority: 5,
    },
    {
      id: 3,
      name: 'Small Expense Auto-Approval',
      min_amount: 0,
      max_amount: 50,
      category_filter: '["Office Supplies"]',
      currency: 'USD',
      approval_level: 1,
      approver_id: 1,
      approver_name: 'System',
      is_active: true,
      priority: 15,
      auto_approve_below: 50,
    },
  ];

  const formatAmount = (amount?: number) => {
    return amount !== undefined ? `$${amount.toFixed(2)}` : 'No limit';
  };

  const formatCategories = (categoryFilter?: string) => {
    if (!categoryFilter) return 'All categories';
    try {
      const categories = JSON.parse(categoryFilter);
      return categories.length > 0 ? categories.join(', ') : 'All categories';
    } catch {
      return 'All categories';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="h-6 w-6" />
              <CardTitle>Approval Rules Management Demo</CardTitle>
            </div>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Create Rule
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            This demo shows the approval rule management interface. Rules determine which expenses require approval 
            and who should approve them based on amount thresholds, categories, and approval levels.
          </p>
        </CardContent>
      </Card>

      {/* Rules List */}
      <Card>
        <CardHeader>
          <CardTitle>Approval Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {mockRules.map((rule, index) => (
              <div key={rule.id} className="border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{rule.name}</h3>
                      <Badge variant={rule.is_active ? 'default' : 'secondary'}>
                        {rule.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      <Badge variant="outline">Level {rule.approval_level}</Badge>
                      <Badge variant="secondary">Priority: {rule.priority}</Badge>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="font-medium">Approver:</span> {rule.approver_name}
                      </div>
                      <div>
                        <span className="font-medium">Amount Range:</span> {formatAmount(rule.min_amount)} - {formatAmount(rule.max_amount)} {rule.currency}
                      </div>
                      <div>
                        <span className="font-medium">Categories:</span> {formatCategories(rule.category_filter)}
                      </div>
                    </div>

                    {rule.auto_approve_below && (
                      <div className="text-sm text-muted-foreground">
                        Auto-approve expenses below ${rule.auto_approve_below}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Priority Controls */}
                    <div className="flex flex-col gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        disabled={index === 0}
                      >
                        <ArrowUp className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        disabled={index === mockRules.length - 1}
                      >
                        <ArrowDown className="h-3 w-3" />
                      </Button>
                    </div>

                    {/* Action Buttons */}
                    <Button variant="ghost" size="sm">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Features Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Key Features</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h4 className="font-semibold">Rule Configuration</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Amount thresholds (min/max)</li>
                <li>• Category-based filtering</li>
                <li>• Multi-level approval workflows</li>
                <li>• Auto-approval for small amounts</li>
                <li>• Currency support</li>
              </ul>
            </div>
            <div className="space-y-2">
              <h4 className="font-semibold">Management Features</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Drag-and-drop priority ordering</li>
                <li>• Search and filter capabilities</li>
                <li>• Active/inactive status toggle</li>
                <li>• Real-time rule validation</li>
                <li>• Comprehensive audit trail</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}