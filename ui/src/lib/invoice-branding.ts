import type { InvoiceBranding, InvoiceFont, LogoPlacement, LogoSize, SectionId } from '@/lib/api/settings';

export type { SectionId } from '@/lib/api/settings';

export const SECTION_IDS: SectionId[] = ['billto', 'custom', 'items', 'totals', 'notes'];
export const DEFAULT_SECTION_ORDER: SectionId[] = [...SECTION_IDS];

/** Mirror of the backend clamp: drop unknown ids, de-dupe (first wins),
 *  append missing sections in canonical order; non-array → default order. */
export function normalizeSectionOrder(order: unknown): SectionId[] {
  if (!Array.isArray(order)) return [...DEFAULT_SECTION_ORDER];
  const allowed = new Set<string>(SECTION_IDS);
  const seen: SectionId[] = [];
  for (const id of order) {
    if (typeof id === 'string' && allowed.has(id) && !seen.includes(id as SectionId)) {
      seen.push(id as SectionId);
    }
  }
  for (const id of SECTION_IDS) {
    if (!seen.includes(id)) seen.push(id);
  }
  return seen;
}

export const DEFAULT_BRANDING: InvoiceBranding = {
  brand_color: '#1e3a8a',
  accent_color: '#3b82f6',
  show_logo: true,
  footer_text: '',
  font_family: 'sans',
  logo_placement: 'left',
  logo_size: 'medium',
  show_notes: true,
  show_custom_fields: true,
  show_footer: true,
  section_order: [...DEFAULT_SECTION_ORDER],
};

export const FONT_OPTIONS: InvoiceFont[] = ['sans', 'serif', 'mono'];
export const LOGO_PLACEMENTS: LogoPlacement[] = ['left', 'center', 'right'];
export const LOGO_SIZES: LogoSize[] = ['small', 'medium', 'large'];

/** Whether a hex string is a valid 6-digit colour (with or without leading #). */
export function isHexColor(value: string): boolean {
  return /^#?[0-9a-fA-F]{6}$/.test(value.trim());
}

/**
 * Fetch an image URL and return it as a data URL, or null on any failure
 * (network, CORS, 404, decode). Lets callers embed a logo in a generated PDF
 * without a bad URL ever throwing during render.
 */
export async function loadImageAsDataUrl(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(typeof reader.result === 'string' ? reader.result : null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
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
