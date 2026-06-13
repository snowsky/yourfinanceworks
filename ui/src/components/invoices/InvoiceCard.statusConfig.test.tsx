import { describe, it, expect } from 'vitest';
import { getStatusConfig } from './InvoiceCard';

describe('getStatusConfig approval statuses', () => {
  it('maps pending_approval', () => {
    expect(getStatusConfig('pending_approval')).toEqual({
      variant: 'secondary',
      className: 'status-pending-approval',
      icon: '🕓',
    });
  });

  it('maps approved', () => {
    expect(getStatusConfig('approved')).toEqual({
      variant: 'default',
      className: 'status-approved',
      icon: '☑',
    });
  });

  it('maps rejected', () => {
    expect(getStatusConfig('rejected')).toEqual({
      variant: 'destructive',
      className: 'status-rejected',
      icon: '✕',
    });
  });

  it('keeps the generic default for unknown statuses', () => {
    expect(getStatusConfig('whatever').icon).toBe('📄');
  });
});
