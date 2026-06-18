import { describe, it, expect } from 'vitest';
import { isOnboardingIntent } from './onboardingShortcut';

describe('isOnboardingIntent', () => {
  const label = 'Help me get set up';
  it('matches the exact quick-action label', () => {
    expect(isOnboardingIntent('Help me get set up', label)).toBe(true);
  });
  it('matches case-insensitively', () => {
    expect(isOnboardingIntent('help me get set up', label)).toBe(true);
  });
  it('does not match unrelated text', () => {
    expect(isOnboardingIntent('show my invoices', label)).toBe(false);
  });
});
