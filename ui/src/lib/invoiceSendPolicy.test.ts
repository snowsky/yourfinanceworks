import { describe, it, expect } from 'vitest';
import { isSendBlockedByApproval } from './invoiceSendPolicy';

const settingsOn = { require_approval_before_send: true, approval_threshold_amount: 0 };

describe('isSendBlockedByApproval', () => {
  it('blocks unapproved statuses when policy applies', () => {
    for (const status of ['draft', 'pending_approval', 'rejected']) {
      expect(isSendBlockedByApproval({ status, amount: 100 }, settingsOn)).toBe(true);
    }
  });

  it('allows approved / downstream statuses', () => {
    for (const status of ['approved', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled']) {
      expect(isSendBlockedByApproval({ status, amount: 100 }, settingsOn)).toBe(false);
    }
  });

  it('does not block when policy is off', () => {
    expect(isSendBlockedByApproval({ status: 'draft', amount: 100 },
      { require_approval_before_send: false, approval_threshold_amount: 0 })).toBe(false);
  });

  it('respects the threshold', () => {
    const s = { require_approval_before_send: true, approval_threshold_amount: 500 };
    expect(isSendBlockedByApproval({ status: 'draft', amount: 499 }, s)).toBe(false);
    expect(isSendBlockedByApproval({ status: 'draft', amount: 500 }, s)).toBe(true);
  });

  it('does not block when settings are undefined', () => {
    expect(isSendBlockedByApproval({ status: 'draft', amount: 100 }, undefined)).toBe(false);
  });
});
