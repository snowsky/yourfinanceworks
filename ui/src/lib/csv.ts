// Helpers for producing CSV output that is safe against spreadsheet formula injection.
//
// When a CSV cell begins with one of `= + - @ \t \r`, spreadsheet applications (Excel,
// LibreOffice, Google Sheets) may interpret it as a formula. Bank-statement exports embed
// text extracted from arbitrary uploaded documents, so an attacker can smuggle a formula
// (e.g. =HYPERLINK(...) or a DDE payload) into a description and have it run on the machine
// of whoever opens the export. See OWASP "CSV Injection".

const FORMULA_PREFIXES = ['=', '+', '-', '@', '\t', '\r'];

function isNumeric(text: string): boolean {
  return text.trim() !== '' && !Number.isNaN(Number(text));
}

/**
 * Neutralise spreadsheet formula injection by prefixing risky values with a single quote.
 * Plain numbers (including legitimate negatives like "-45.67") are left untouched so
 * numeric columns stay numeric.
 */
export function neutralizeCsvFormula(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = String(value);
  if (text.length === 0) return text;
  if (FORMULA_PREFIXES.includes(text[0]) && !isNumeric(text)) {
    return `'${text}`;
  }
  return text;
}

/**
 * Format a single value as a fully-quoted, formula-safe CSV field. Quoting every field
 * also makes embedded commas, quotes, and newlines safe.
 */
export function csvField(value: unknown): string {
  const safe = neutralizeCsvFormula(value).replace(/"/g, '""');
  return `"${safe}"`;
}

/** Join a row of raw values into a formula-safe, fully-quoted CSV line. */
export function csvRow(values: unknown[]): string {
  return values.map(csvField).join(',');
}
