import { describe, it, expect } from 'vitest';
import { neutralizeCsvFormula, csvField, csvRow } from './csv';

describe('neutralizeCsvFormula', () => {
  it('returns empty string for null/undefined', () => {
    expect(neutralizeCsvFormula(null)).toBe('');
    expect(neutralizeCsvFormula(undefined)).toBe('');
  });

  it('leaves plain text unchanged', () => {
    expect(neutralizeCsvFormula('Coffee shop')).toBe('Coffee shop');
  });

  it.each([
    '=HYPERLINK("http://evil","x")',
    '+1+1',
    '@SUM(A1:A9)',
    "=cmd|' /C calc'!A0",
    '\tinjected',
    '\rinjected',
  ])('neutralises formula prefix %s', (payload) => {
    expect(neutralizeCsvFormula(payload)).toBe(`'${payload}`);
  });

  it('does not mangle plain negative numbers', () => {
    expect(neutralizeCsvFormula('-45.67')).toBe('-45.67');
    expect(neutralizeCsvFormula(-45.67)).toBe('-45.67');
  });

  it('escapes a dash-led non-number', () => {
    expect(neutralizeCsvFormula('-1+cmd')).toBe("'-1+cmd");
  });

  it('escapes a +-led phone number (not a valid number)', () => {
    expect(neutralizeCsvFormula('+44 7700 900900')).toBe("'+44 7700 900900");
  });
});

describe('csvField', () => {
  it('wraps values in quotes and escapes inner quotes', () => {
    expect(csvField('a,b')).toBe('"a,b"');
    expect(csvField('say "hi"')).toBe('"say ""hi"""');
  });

  it('quotes a neutralised formula', () => {
    expect(csvField('=1+1')).toBe('"\'=1+1"');
  });

  it('keeps embedded newlines inside one quoted field', () => {
    expect(csvField('line1\nline2')).toBe('"line1\nline2"');
  });
});

describe('csvRow', () => {
  it('joins fields with commas, each quoted', () => {
    expect(csvRow(['2024-01-01', 'Acme, Inc', -45.67])).toBe('"2024-01-01","Acme, Inc","-45.67"');
  });
});
