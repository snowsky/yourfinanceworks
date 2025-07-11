import { parseISO, format } from 'date-fns';

export function formatToLocal(utcString: string, dateFormat = 'yyyy-MM-dd HH:mm') {
  if (!utcString) return '';
  // Ensure the string ends with 'Z' for UTC if not already present
  const safeUtc = utcString.endsWith('Z') ? utcString : utcString + 'Z';
  const utcDate = parseISO(safeUtc);
  // Format in UTC instead of local time
  return format(utcDate, dateFormat) + ' UTC';
} 