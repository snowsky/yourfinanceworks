import { describe, it, expect } from 'vitest';
import { roundMoney, sumMoney, formatMoney } from './money';

describe('sumMoney', () => {
  it('eliminates classic float drift', () => {
    expect(sumMoney([0.1, 0.2])).toBe(0.3);
    expect(sumMoney([0.99, 0.99, 0.99])).toBe(2.97);
  });

  it('sums 100 cents to exactly 1.00', () => {
    expect(sumMoney(Array(100).fill(0.01))).toBe(1.0);
  });

  it('treats null/undefined as 0', () => {
    expect(sumMoney([1.5, null, 2.5, undefined])).toBe(4.0);
  });

  it('returns 0 for empty', () => {
    expect(sumMoney([])).toBe(0);
  });
});

describe('roundMoney', () => {
  it('rounds to two decimals', () => {
    expect(roundMoney(1.234)).toBe(1.23);
    expect(roundMoney(0.1 + 0.2)).toBe(0.3);
  });
});

describe('formatMoney', () => {
  it('always shows two decimal places', () => {
    expect(formatMoney(2.97)).toMatch(/2[.,]97$/);
    expect(formatMoney(5)).toMatch(/5[.,]00$/);
  });
});
