import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import en from './locales/en.json';

// Every t('key', { defaultValue: '...' }) call must have its key in en.json,
// so a missing translation never hides behind an inline fallback.
const SRC = resolve(__dirname, '..');
const CALL = /\bt\(\s*(['"])([A-Za-z0-9_.]+)\1\s*,\s*\{[^{}]*?defaultValue\s*:/gs;

const lookup = (key: string) =>
  key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en);

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return name === '__tests__' || name === 'node_modules' ? [] : files(full);
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [full] : [];
  });
}

describe('inline defaultValue fallbacks', () => {
  it('only reference keys that exist in en.json', () => {
    const missing: string[] = [];
    for (const file of files(SRC)) {
      const source = readFileSync(file, 'utf8');
      for (const m of source.matchAll(CALL)) {
        if (typeof lookup(m[2]) !== 'string') missing.push(`${file.slice(SRC.length + 1)}: ${m[2]}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
