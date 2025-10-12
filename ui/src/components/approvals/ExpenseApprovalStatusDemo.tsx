import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ExpenseApprovalStatus } from './ExpenseApprovalStatus';
import type { ExpenseApproval } from '@/types';

export function ExpenseApprovalStatusDemo() {
  const mockApprovals: ExpenseApproval[] = [
    {
      id: 1,
      expense_id: 1,
      approver_id: 1,
      status: 'pending',
      submitted_at: '2024-01-15T10:30:00Z',
      approval_level: 1,
      is_current_level: true,
      approver: {
        id: 1,
        name: 'John Manager',
        email: 'john@example.com',
      },
    },
  ];

  const multiLevelApprovals: ExpenseApproval[] = [
    {
      id: 1,
      expense_id: 2,
      approver_id: 1,
      status: 'approved',
      submitted_at: '2024-01-15T10:30:00Z',
      decided_at: '2024-01-15T11:00:00Z',
      approval_level: 1,
      is_current_level: false,
      approver: { id: 1, name: 'John Manager', email: 'john@example.com' },
    },
    {
      id: 2,
      expense_id: 2,
      approver_id: 2,
      status: 'pending',
      submitted_at: '2024-01-15T11:00:00Z',
      approval_level: 2,
      is_current_level: true,
      approver: { id: 2, name: 'Jane Director', email: 'jane@example.com' },
    },
  ];

  const rejectedApprovals: ExpenseApproval[] = [
    {
      id: 3,
      expense_id: 3,
      approver_id: 1,
      status: 'rejected',
      rejection_reason: 'Missing receipt - please provide documentation',
      submitted_at: '2024-01-15T10:30:00Z',
      decided_at: '2024-01-15T11:00:00Z',
      approval_level: 1,
      is_current_level: false,
      approver: { id: 1, name: 'John Manager', email: 'john@example.com' },
    },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Expense Approval Status Indicators</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <h3 className="font-medium">Pending Approval</h3>
              <ExpenseApprovalStatus 
                expense={{
                  id: 1,
                  status: 'pending_approval',
                  amount: 150,
                  currency: 'USD'
                }}
                approvals={mockApprovals}
              />
              <p className="text-sm text-muted-foreground">
                Single level approval waiting for review
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-medium">Multi-Level Approval</h3>
              <ExpenseApprovalStatus 
                expense={{
                  id: 2,
                  status: 'pending_approval',
                  amount: 2500,
                  currency: 'USD'
                }}
                approvals={multiLevelApprovals}
              />
              <p className="text-sm text-muted-foreground">
                Level 1 approved, waiting for level 2
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-medium">Approved</h3>
              <ExpenseApprovalStatus 
                expense={{
                  id: 4,
                  status: 'approved',
                  amount: 75,
                  currency: 'USD'
                }}
                approvals={[]}
              />
              <p className="text-sm text-muted-foreground">
                Fully approved and ready for reimbursement
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-medium">Rejected</h3>
              <ExpenseApprovalStatus 
                expense={{
                  id: 3,
                  status: 'rejected',
                  amount: 200,
                  currency: 'USD'
                }}
                approvals={rejectedApprovals}
              />
              <p className="text-sm text-muted-foreground">
                Rejected with reason (hover for details)
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="font-medium">Resubmitted</h3>
            <ExpenseApprovalStatus 
              expense={{
                id: 5,
                status: 'resubmitted',
                amount: 200,
                currency: 'USD'
              }}
              approvals={[]}
            />
            <p className="text-sm text-muted-foreground">
              Expense has been resubmitted after rejection
            </p>
          </div>

          <div className="space-y-2">
            <h3 className="font-medium">Non-Approval Expense</h3>
            <ExpenseApprovalStatus 
              expense={{
                id: 6,
                status: 'recorded',
                amount: 50,
                currency: 'USD'
              }}
              approvals={[]}
            />
            <p className="text-sm text-muted-foreground">
              Regular expense not requiring approval (no indicator shown)
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}