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
    // Append 'Z' if no timezone information is present to ensure it's parsed as UTC
    const utcDateString = dateString.endsWith('Z') || dateString.includes('+') || dateString.includes('-') 
                          ? dateString 
                          : dateString + 'Z';
    date = parseISO(utcDateString);
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
    // Append 'Z' if no timezone information is present to ensure it's parsed as UTC
    const utcDateString = dateString.endsWith('Z') || dateString.includes('+') || dateString.includes('-') 
                          ? dateString 
                          : dateString + 'Z';
    date = parseISO(utcDateString);
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