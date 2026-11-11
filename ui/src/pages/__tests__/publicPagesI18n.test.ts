import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import en from '@/i18n/locales/en.json';

// Page tests mock t() to return the key, so they cannot notice a key that is
// missing from en.json. This checks the literal keys the public pages use.
const FILES = [
  'components/auth/AuthBrandPanel.tsx',
  'components/auth/AuthLayout.tsx',
  'components/sharing/PoweredBy.tsx',
  'pages/Login.tsx',
  'pages/ForgotPassword.tsx',
  'pages/ResetPassword.tsx',
  'pages/NotFound.tsx',
  'pages/OAuthCallback.tsx',
  'pages/SharedRecord.tsx',
  'pages/portal/PortalLogin.tsx',
  'pages/portal/PortalVerify.tsx',
];

const lookup = (key: string) =>
  key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en);

describe('public page translation keys', () => {
  it.each(FILES)('%s only uses keys that exist in en.json', (file) => {
    const source = readFileSync(resolve(__dirname, '../..', file), 'utf8');
    const keys = [...source.matchAll(/\bt\(\s*["']([A-Za-z0-9_.]+)["']/g)].map((m) => m[1]);
    expect(keys.length).toBeGreaterThan(0);
    const missing = keys.filter((k) => typeof lookup(k) !== 'string');
    expect(missing).toEqual([]);
  });

  it('has a label for every shared record type', () => {
    const source = readFileSync(resolve(__dirname, '../SharedRecord.tsx'), 'utf8');
    const list = source.match(/const RECORD_TYPES = \[([^\]]+)\]/)?.[1] ?? '';
    const types = [...list.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
    expect(types.length).toBeGreaterThan(0);
    for (const type of [...types, 'record']) {
      expect(typeof lookup(`sharedRecord.types.${type}`)).toBe('string');
    }
  });
});
