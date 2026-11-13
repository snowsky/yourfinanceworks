import { describe, it, expect } from 'vitest';
import i18n, { loadPluginTranslations, unloadPluginTranslations } from './index';

describe('plugin translations on a fresh page load', () => {
  it.each(['en', 'es', 'fr', 'de'])('registers profitability before enabling plugins in %s', (lng) => {
    expect(i18n.t('profitability.title', { lng, ns: 'time_tracking' })).not.toBe('profitability.title');
    expect(i18n.t('profitability.load_error', { lng, ns: 'time_tracking' })).not.toBe('profitability.load_error');
  });
  it('resolves the runtime hyphenated plugin ID to its locale namespace', async () => {
    unloadPluginTranslations('time-tracking');
    await loadPluginTranslations('time-tracking');
    expect(i18n.t('profitability.title', { lng: 'en', ns: 'time_tracking' })).toBe('Profitability');
  });
});
