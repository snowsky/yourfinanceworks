export const formatCurrency = (amount: number, currency: string = 'USD'): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount);
};

export const formatCurrencyCompact = (amount: number, currency: string = 'USD'): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(amount);
};

export const getCurrencySymbol = (currency: string = 'USD'): string => {
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  });
  
  // Extract the currency symbol from a formatted number
  const parts = formatter.formatToParts(1234.56);
  const symbolPart = parts.find(part => part.type === 'currency');
  return symbolPart ? symbolPart.value : currency;
}; 