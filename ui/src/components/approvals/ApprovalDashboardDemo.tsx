import React from 'react';
import { ApprovalDashboard } from './ApprovalDashboard';

// Demo component to verify the approval dashboard works
export function ApprovalDashboardDemo() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Approval Dashboard Demo</h1>
      <ApprovalDashboard />
    </div>
  );
}