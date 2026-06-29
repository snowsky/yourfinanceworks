import { describe, it, expect } from 'vitest';
import { normalizeSectionOrder, DEFAULT_SECTION_ORDER } from './invoice-branding';

describe('normalizeSectionOrder', () => {
  it('returns the default order for a non-array', () => {
    expect(normalizeSectionOrder(undefined)).toEqual(DEFAULT_SECTION_ORDER);
    expect(normalizeSectionOrder('items,billto')).toEqual(DEFAULT_SECTION_ORDER);
  });

  it('keeps a valid full order as-is', () => {
    const order = ['notes', 'totals', 'items', 'custom', 'billto'];
    expect(normalizeSectionOrder(order)).toEqual(order);
  });

  it('drops unknown ids then appends missing in canonical order', () => {
    expect(normalizeSectionOrder(['notes', 'bogus', 'items'])).toEqual([
      'notes', 'items', 'billto', 'custom', 'totals',
    ]);
  });

  it('de-dupes keeping first occurrence', () => {
    expect(normalizeSectionOrder(['items', 'items', 'billto'])).toEqual([
      'items', 'billto', 'custom', 'totals', 'notes',
    ]);
  });
});
