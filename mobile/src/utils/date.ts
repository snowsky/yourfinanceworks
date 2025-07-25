import { parseISO, format, isValid } from 'date-fns';

export const formatDate = (date: string | Date): string => {
  if (!date) return new Date().toLocaleDateString();
  
  try {
    let dateObj: Date;
    
    if (typeof date === 'string') {
      // Handle YYYY-MM-DD format
      if (date.match(/^\d{4}-\d{2}-\d{2}$/)) {
        const [year, month, day] = date.split('-').map(Number);
        dateObj = new Date(year, month - 1, day);
      } else {
        dateObj = new Date(date);
      }
    } else {
      dateObj = date;
    }

    if (!isValid(dateObj)) {
      return new Date().toLocaleDateString();
    }

    return dateObj.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch (error) {
    return new Date().toLocaleDateString();
  }
};

export const formatDateTime = (date: string | Date): string => {
  let dateObj: Date;
  
  if (typeof date === 'string') {
    // Append 'Z' if no timezone information is present to ensure it's parsed as UTC
    const utcDateString = date.endsWith('Z') || date.includes('+') || date.includes('-') 
                          ? date 
                          : date + 'Z';
    dateObj = parseISO(utcDateString);
  } else {
    dateObj = date;
  }

  if (!isValid(dateObj)) return "Invalid Date";

  // Format to UTC time string, e.g., Jul 11, 2025, 2:07 PM UTC
  const utcString = dateObj.toLocaleString('en-US', { 
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });
  
  return `${utcString} UTC`;
};

export const formatDateFull = (date: string | Date): string => {
  let dateObj: Date;
  
  if (typeof date === 'string') {
    const utcDateString = date.endsWith('Z') || date.includes('+') || date.includes('-') 
                          ? date 
                          : date + 'Z';
    dateObj = parseISO(utcDateString);
  } else {
    dateObj = date;
  }

  if (!isValid(dateObj)) return "Invalid Date";

  return dateObj.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

export const formatDateShort = (date: string | Date): string => {
  let dateObj: Date;
  
  if (typeof date === 'string') {
    const utcDateString = date.endsWith('Z') || date.includes('+') || date.includes('-') 
                          ? date 
                          : date + 'Z';
    dateObj = parseISO(utcDateString);
  } else {
    dateObj = date;
  }

  if (!isValid(dateObj)) return "Invalid Date";

  return dateObj.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    month: 'numeric',
    day: 'numeric',
    year: 'numeric',
  });
};

export const formatToLocal = (utcString: string, dateFormat = 'yyyy-MM-dd HH:mm'): string => {
  if (!utcString) return '';
  // Ensure the string ends with 'Z' for UTC if not already present
  const safeUtc = utcString.endsWith('Z') ? utcString : utcString + 'Z';
  const utcDate = parseISO(safeUtc);
  // Format in UTC instead of local time
  return format(utcDate, dateFormat) + ' UTC';
};

export const isOverdue = (dueDate: string | Date): boolean => {
  let due: Date;
  
  if (typeof dueDate === 'string') {
    const utcDateString = dueDate.endsWith('Z') || dueDate.includes('+') || dueDate.includes('-') 
                          ? dueDate 
                          : dueDate + 'Z';
    due = parseISO(utcDateString);
  } else {
    due = dueDate;
  }

  if (!isValid(due)) return false;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  return due < today;
};

export const getDaysUntilDue = (dueDate: string | Date): number => {
  let due: Date;
  
  if (typeof dueDate === 'string') {
    const utcDateString = dueDate.endsWith('Z') || dueDate.includes('+') || dueDate.includes('-') 
                          ? dueDate 
                          : dueDate + 'Z';
    due = parseISO(utcDateString);
  } else {
    due = dueDate;
  }

  if (!isValid(due)) return 0;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  const diffTime = due.getTime() - today.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

export const safeParseDateString = (dateString?: string): Date => {
  if (!dateString) return new Date();
  
  // Append 'Z' if no timezone information is present
  const utcDateString = dateString.endsWith('Z') || dateString.includes('+') || dateString.includes('-') 
                        ? dateString 
                        : dateString + 'Z';
  
  const parsedDate = parseISO(utcDateString);
  return isValid(parsedDate) ? parsedDate : new Date();
}; 