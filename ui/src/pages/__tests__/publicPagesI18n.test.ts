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
  'pages/portal/PortalDashboard.tsx',
  'pages/EditClient.tsx',
  'components/clients/ClientActivityFeed.tsx',
  'pages/Statements/DuplicateStatementPanel.tsx',
  'pages/Statements/DuplicateTransactionPanel.tsx',
  'pages/Statements/UploadModal.tsx',
];

// Files using `plural('base', n)`, which resolves to `baseOne` / `baseMany`.
const PLURAL_FILES = ['pages/Statements/DuplicateStatementPanel.tsx', 'pages/Statements/DuplicateTransactionPanel.tsx'];

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

  it.each(PLURAL_FILES)('%s has both plural forms for every plural() key', (file) => {
    const source = readFileSync(resolve(__dirname, '../..', file), 'utf8');
    const bases = [...source.matchAll(/\bplural\(\s*['"]([A-Za-z0-9_.]+)['"]/g)].map((m) => m[1]);
    expect(bases.length).toBeGreaterThan(0);
    for (const base of bases) {
      expect(typeof lookup(`${base}One`)).toBe('string');
      expect(typeof lookup(`${base}Many`)).toBe('string');
    }
  });

  it('ExpensesView only uses expenses.view.* keys that exist (older keys rely on inline fallbacks)', () => {
    const source = readFileSync(resolve(__dirname, '../ExpensesView.tsx'), 'utf8');
    const keys = [...source.matchAll(/['"](expenses\.view\.[A-Za-z]+)['"]/g)].map((m) => m[1]);
    expect(keys.length).toBeGreaterThan(8);
    expect(keys.filter((k) => typeof lookup(k) !== 'string')).toEqual([]);
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

describe('edit client option labels', () => {
  it('has a label for every stage, relationship status and tab', () => {
    const source = readFileSync(resolve(__dirname, '../EditClient.tsx'), 'utf8');
    const values = (name: string) => {
      const block = source.match(new RegExp(`const ${name} = \\[([\\s\\S]*?)\\]`))?.[1] ?? '';
      return [...block.matchAll(/value: "([a-z_]+)"/g)].map((m) => m[1]);
    };
    const stages = values('STAGE_OPTIONS');
    const statuses = values('RELATIONSHIP_OPTIONS');
    expect(stages.length).toBeGreaterThan(0);
    expect(statuses.length).toBeGreaterThan(0);
    for (const v of stages) expect(typeof lookup(`editClient.stages.${v}`)).toBe('string');
    for (const v of statuses) expect(typeof lookup(`editClient.relationshipStatuses.${v}`)).toBe('string');
    const priorities = source.match(/TASK_PRIORITY_OPTIONS = \[([^\]]+)\]/)?.[1] ?? '';
    for (const p of [...priorities.matchAll(/"([a-z]+)"/g)].map((m) => m[1])) {
      expect(typeof lookup(`editClient.tasks.priorities.${p}`)).toBe('string');
    }
    for (const f of ['owner', 'stage', 'relationshipStatus', 'source', 'lastContact', 'nextFollowUp']) {
      expect(typeof lookup(`editClient.overview.${f}`)).toBe('string');
    }
    for (const tab of ['overview', 'details', 'activity', 'tasks', 'contacts']) {
      expect(typeof lookup(`editClient.tabs.${tab}`)).toBe('string');
    }
  });
});
