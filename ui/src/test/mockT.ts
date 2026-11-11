import en from '@/i18n/locales/en.json';

// A stand-in for i18next's `t` in unit tests: resolves the key from the real
// en.json (with {{interpolation}}), then `defaultValue`, then the key itself.
export function mockT(key: string, opts?: Record<string, unknown>): string {
  const found = key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en);
  let s = typeof found === 'string' ? found : typeof opts?.defaultValue === 'string' ? opts.defaultValue : key;
  if (opts) {
    for (const [k, v] of Object.entries(opts)) {
      if (k !== 'defaultValue') s = s.split(`{{${k}}}`).join(String(v));
    }
  }
  return s;
}
