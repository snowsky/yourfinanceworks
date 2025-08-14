import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, parseISO, isValid } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDateTime(dateString: string | Date | undefined): string {
  if (!dateString) return "N/A";

  let date: Date;
  if (typeof dateString === 'string') {
    // Handle date-only strings (YYYY-MM-DD) explicitly as UTC midnight to avoid TZ shifts
    const dateOnlyMatch = dateString.match(/^\d{4}-(\d{2})-(\d{2})$/);
    if (dateOnlyMatch) {
      const [y, m, d] = dateString.split('-').map((n) => parseInt(n, 10));
      date = new Date(Date.UTC(y, m - 1, d));
    } else {
      // If no explicit timezone in ISO string (no 'Z' and no +/- offset), treat it as UTC
      const hasExplicitTz = /[zZ]|[+\-]\d{2}:?\d{2}$/.test(dateString);
      const normalized = hasExplicitTz ? dateString : `${dateString}Z`;
      date = parseISO(normalized);
    }
  } else {
    date = dateString;
  }

  if (!isValid(date)) return "Invalid Date";

  // Format to UTC time string, e.g., Jul 11, 2025, 2:07 PM UTC
  const utcString = date.toLocaleString('en-US', { 
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
  
  return `${utcString} UTC`;
}

export function formatDate(dateString: string | Date | undefined): string {
  if (!dateString) return "N/A";

  let date: Date;
  if (typeof dateString === 'string') {
    // Handle date-only strings (YYYY-MM-DD) explicitly as UTC midnight to avoid TZ shifts
    const dateOnlyMatch = dateString.match(/^\d{4}-(\d{2})-(\d{2})$/);
    if (dateOnlyMatch) {
      const [y, m, d] = dateString.split('-').map((n) => parseInt(n, 10));
      date = new Date(Date.UTC(y, m - 1, d));
    } else {
      // If no explicit timezone in ISO string (no 'Z' and no +/- offset), treat it as UTC
      const hasExplicitTz = /[zZ]|[+\-]\d{2}:?\d{2}$/.test(dateString);
      const normalized = hasExplicitTz ? dateString : `${dateString}Z`;
      date = parseISO(normalized);
    }
  } else {
    date = dateString;
  }

  if (!isValid(date)) return "Invalid Date";

  // Format to UTC date string, e.g., Jul 11, 2025 UTC
  const utcString = date.toLocaleDateString('en-US', { 
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: '2-digit'
  });
  
  return `${utcString} UTC`;
}