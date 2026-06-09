import type { InvoiceBranding } from '@/lib/api/settings';

export const DEFAULT_BRANDING: InvoiceBranding = {
  brand_color: '#1e3a8a',
  accent_color: '#3b82f6',
  show_logo: true,
  footer_text: '',
};

/** Whether a hex string is a valid 6-digit colour (with or without leading #). */
export function isHexColor(value: string): boolean {
  return /^#?[0-9a-fA-F]{6}$/.test(value.trim());
}

/** Pick black or white text for legibility on top of a given background colour. */
export function readableTextColor(hex: string): string {
  const m = /^#?([0-9a-fA-F]{6})$/.exec((hex || '').trim());
  if (!m) return '#ffffff';
  const int = parseInt(m[1], 16);
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? '#111827' : '#ffffff';
}
