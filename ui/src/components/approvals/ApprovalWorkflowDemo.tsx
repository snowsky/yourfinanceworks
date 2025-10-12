import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ApprovalDashboard } from './ApprovalDashboard';
import { ApprovalHistoryTimeline } from './ApprovalHistoryTimeline';
import { Badge } from '@/components/ui/badge';

// Demo component showcasing all approval workflow components
export function ApprovalWorkflowDemo() {
  const [selectedExpenseId, setSelectedExpenseId] = useState<number>(101);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Expense Approval Workflow</h1>
        <Badge variant="outline" className="text-sm">
          Demo Mode
        </Badge>
      </div>

      <Tabs defaultValue="dashboard" className="space-y-4">
        <TabsList>
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="history">Approval History</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="space-y-4">
          <ApprovalDashboard />
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Select Expense to View History</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 mb-4">
                <Button
                  variant={selectedExpenseId === 101 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedExpenseId(101)}
                >
                  Expense #101
                </Button>
                <Button
                  variant={selectedExpenseId === 102 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedExpenseId(102)}
                >
                  Expense #102
                </Button>
                <Button
                  variant={selectedExpenseId === 103 ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSelectedExpenseId(103)}
                >
                  Expense #103
                </Button>
              </div>
            </CardContent>
          </Card>

          <ApprovalHistoryTimeline expenseId={selectedExpenseId} />
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Component Features</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold mb-2">ApprovalDashboard</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Shows pending approvals count</li>
                <li>• Displays approval statistics</li>
                <li>• Integrates with PendingApprovalsList</li>
                <li>• Real-time updates on actions</li>
              </ul>
            </div>
            
            <div>
              <h3 className="font-semibold mb-2">PendingApprovalsList</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Filtering and sorting capabilities</li>
                <li>• Search by vendor, category, notes</li>
                <li>• Pagination support</li>
                <li>• Integrates with ApprovalActionButtons</li>
              </ul>
            </div>
            
            <div>
              <h3 className="font-semibold mb-2">ApprovalActionButtons</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Approve/reject expense actions</li>
                <li>• Modal dialogs for confirmation</li>
                <li>• Notes and rejection reasons</li>
                <li>• Loading states and error handling</li>
              </ul>
            </div>
            
            <div>
              <h3 className="font-semibold mb-2">ApprovalHistoryTimeline</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Visual timeline of approval actions</li>
                <li>• Shows approver details and timestamps</li>
                <li>• Displays rejection reasons and notes</li>
                <li>• Multi-level approval support</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}