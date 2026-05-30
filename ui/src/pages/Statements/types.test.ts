import { describe, it, expect } from 'vitest';
import { safeParseDateString, formatRowDate, formatDateToISO } from './types';

describe('safeParseDateString', () => {
  it('returns null for missing/empty input (not today)', () => {
    expect(safeParseDateString(undefined)).toBeNull();
    expect(safeParseDateString('')).toBeNull();
  });

  it('returns null for an unparseable date (not today)', () => {
    expect(safeParseDateString('N/A')).toBeNull();
    expect(safeParseDateString('not-a-date')).toBeNull();
  });

  it('parses a valid ISO date', () => {
    const d = safeParseDateString('2024-01-15');
    expect(d).toBeInstanceOf(Date);
    expect(formatDateToISO(d as Date)).toBe('2024-01-15');
  });
});

describe('formatRowDate', () => {
  it('uses the fallback for missing/invalid dates', () => {
    expect(formatRowDate(undefined, 'PP', 'Pick a date')).toBe('Pick a date');
    expect(formatRowDate('garbage', 'PP', '-')).toBe('-');
  });

  it('formats a valid date', () => {
    // date-fns 'yyyy-MM-dd' round-trips regardless of locale
    expect(formatRowDate('2024-01-15', 'yyyy-MM-dd', '-')).toBe('2024-01-15');
  });
});
