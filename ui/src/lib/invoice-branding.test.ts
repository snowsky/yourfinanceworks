import { describe, it, expect } from 'vitest';
import { normalizeSectionOrder, DEFAULT_SECTION_ORDER, normalizeCustomFieldsLayout, DEFAULT_CUSTOM_FIELDS_LAYOUT } from './invoice-branding';

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

describe('normalizeCustomFieldsLayout', () => {
  it('keeps a valid layout', () => {
    expect(normalizeCustomFieldsLayout('grid')).toBe('grid');
    expect(normalizeCustomFieldsLayout('list')).toBe('list');
  });

  it('falls back to list for anything else', () => {
    expect(normalizeCustomFieldsLayout('fancy')).toBe('list');
    expect(normalizeCustomFieldsLayout(undefined)).toBe('list');
    expect(normalizeCustomFieldsLayout(42)).toBe('list');
  });

  it('default constant is list', () => {
    expect(DEFAULT_CUSTOM_FIELDS_LAYOUT).toBe('list');
  });
});
