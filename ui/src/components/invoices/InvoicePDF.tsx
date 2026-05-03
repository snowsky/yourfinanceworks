import { Document, Page, Text, View, StyleSheet } from '@react-pdf/renderer';
import { Invoice } from '@/lib/api';

// Custom currency names for cryptocurrencies and other custom currencies
const customCurrencyNames: { [key: string]: { name: string; decimals: number } } = {
  'BTC': { name: 'Bitcoin', decimals: 8 },
  'ETH': { name: 'Ethereum', decimals: 18 },
  'XRP': { name: 'Ripple', decimals: 6 },
  'SOL': { name: 'Solana', decimals: 9 },
};

// Traditional currency names
const traditionalCurrencyNames: { [key: string]: { name: string; decimals: number } } = {
  'USD': { name: 'US Dollar', decimals: 2 },
  'EUR': { name: 'Euro', decimals: 2 },
  'GBP': { name: 'British Pound', decimals: 2 },
  'CAD': { name: 'Canadian Dollar', decimals: 2 },
  'AUD': { name: 'Australian Dollar', decimals: 2 },
  'JPY': { name: 'Japanese Yen', decimals: 0 },
  'CHF': { name: 'Swiss Franc', decimals: 2 },
  'CNY': { name: 'Chinese Yuan', decimals: 2 },
  'INR': { name: 'Indian Rupee', decimals: 2 },
  'BRL': { name: 'Brazilian Real', decimals: 2 },
};

const formatCurrency = (amount: number, currency: string = 'USD'): string => {
  const upperCurrency = currency.toUpperCase();
  
  // Check custom currencies first
  if (customCurrencyNames[upperCurrency]) {
    const info = customCurrencyNames[upperCurrency];
    const formattedAmount = amount.toFixed(info.decimals);
    return `${formattedAmount} ${upperCurrency}`;
  }
  
  // Check traditional currencies
  if (traditionalCurrencyNames[upperCurrency]) {
    const info = traditionalCurrencyNames[upperCurrency];
    const formattedAmount = amount.toFixed(info.decimals);
    return `${formattedAmount} ${upperCurrency}`;
  }
  
  // Fallback
  return `${amount.toFixed(2)} ${upperCurrency}`;
};

const formatInvoiceDate = (value?: string | Date | null): string => {
  if (!value) return 'N/A';

  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return 'N/A';

  return date.toLocaleDateString('en-US', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  });
};

// Create styles
const styles = StyleSheet.create({
  page: {
    flexDirection: 'column',
    backgroundColor: '#ffffff',
    padding: 40,
    fontFamily: 'Helvetica',
  },
  header: {
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  companyInfo: {
    fontSize: 12,
    color: '#666',
    marginBottom: 20,
  },
  section: {
    marginBottom: 20,
  },
  row: {
    flexDirection: 'row',
    marginBottom: 5,
  },
  label: {
    width: 100,
    fontSize: 10,
    color: '#666',
  },
  value: {
    flex: 1,
    fontSize: 10,
  },
  table: {
    marginTop: 20,
  },
  tableHeader: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#000',
    paddingBottom: 5,
    marginBottom: 5,
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 5,
  },
  tableCell: {
    fontSize: 10,
  },
  col1: {
    width: '40%',
  },
  col2: {
    width: '15%',
    textAlign: 'right',
  },
  col3: {
    width: '15%',
    textAlign: 'right',
  },
  col4: {
    width: '30%',
    textAlign: 'right',
  },
  total: {
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#000',
    paddingTop: 10,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginBottom: 5,
  },
  totalLabel: {
    width: 100,
    fontSize: 10,
    textAlign: 'right',
  },
  totalValue: {
    width: 100,
    fontSize: 10,
    textAlign: 'right',
    fontWeight: 'bold',
  },
  notes: {
    marginTop: 30,
    fontSize: 10,
    color: '#666',
  },
});

interface InvoicePDFProps {
  invoice: Invoice;
  companyName: string;
  clientCompany?: string;
  showDiscount: boolean;
  template?: string;
}

export const InvoicePDF = ({ invoice, companyName, clientCompany, showDiscount, template = 'modern' }: InvoicePDFProps) => {
  const getTemplateColors = () => {
    switch (template) {
      case 'classic':
        return { title: '#000000', header: '#000000', accent: '#666666' };
      case 'modern':
      default:
        return { title: '#1e40af', header: '#1e40af', accent: '#3b82f6' };
    }
  };
  
  const templateColors = getTemplateColors();
  
  const templateStyles = StyleSheet.create({
    ...styles,
    title: {
      ...styles.title,
      color: templateColors.title,
    },
    companyInfo: {
      ...styles.companyInfo,
      color: templateColors.header,
    },
  });
  
  return (
    <Document>
      <Page size="A4" style={templateStyles.page}>
      <View style={styles.header}>
        <Text style={templateStyles.title}>INVOICE</Text>
        <Text style={templateStyles.companyInfo}>{companyName}</Text>
      </View>

      <View style={styles.section}>
        <View style={styles.row}>
          <Text style={styles.label}>Invoice Number:</Text>
          <Text style={styles.value}>{invoice.number}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Date:</Text>
          <Text style={styles.value}>{formatInvoiceDate(invoice.date)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Due Date:</Text>
          <Text style={styles.value}>{formatInvoiceDate(invoice.due_date)}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={[styles.label, { marginBottom: 8 }]}>Bill To:</Text>
        {clientCompany && clientCompany !== invoice.client_name && (
          <View style={styles.row}>
            <Text style={styles.label}></Text>
            <Text style={styles.value}>{clientCompany}</Text>
          </View>
        )}
        <View style={styles.row}>
          <Text style={styles.label}></Text>
          <Text style={styles.value}>{invoice.client_name}</Text>
        </View>
        {invoice.client_email && (
          <View style={styles.row}>
            <Text style={styles.label}></Text>
            <Text style={styles.value}>{invoice.client_email}</Text>
          </View>
        )}
      </View>

      {invoice.custom_fields && Object.keys(invoice.custom_fields).length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.label, { marginBottom: 5 }]}>Custom Fields:</Text>
          {Object.entries(invoice.custom_fields).map(([key, value]) => (
            <View key={key} style={styles.row}>
              <Text style={styles.label}>{key}:</Text>
              <Text style={styles.value}>{String(value)}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.table}>
        <View style={styles.tableHeader}>
          <Text style={[styles.tableCell, styles.col1]}>Description</Text>
          <Text style={[styles.tableCell, styles.col2]}>Quantity</Text>
          <Text style={[styles.tableCell, styles.col3]}>Price</Text>
          <Text style={[styles.tableCell, styles.col4]}>Amount</Text>
        </View>
        {invoice.items.map((item, index) => {
          let displayPrice = item.price;
          let displayAmount = item.amount;

          if (!showDiscount && invoice.discount_value > 0 && invoice.subtotal > 0) {
            const actualDiscountAmount = invoice.discount_type === "percentage"
              ? (invoice.subtotal * invoice.discount_value) / 100
              : Math.min(invoice.discount_value, invoice.subtotal);
            
            const discountFactor = (invoice.subtotal - actualDiscountAmount) / invoice.subtotal;
            
            displayPrice = item.price * discountFactor;
            displayAmount = item.amount * discountFactor;
          }

          return (
            <View key={index} style={styles.tableRow}>
              <Text style={[styles.tableCell, styles.col1]}>{item.description}</Text>
              <Text style={[styles.tableCell, styles.col2]}>{item.quantity}</Text>
              <Text style={[styles.tableCell, styles.col3]}>{formatCurrency(displayPrice, invoice.currency)}</Text>
              <Text style={[styles.tableCell, styles.col4]}>{formatCurrency(displayAmount, invoice.currency)}</Text>
            </View>
          );
        })}
      </View>

      <View style={styles.total}>
        {showDiscount && invoice.discount_value > 0 ? (
          <>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Subtotal:</Text>
              <Text style={styles.totalValue}>{formatCurrency(invoice.subtotal || 0, invoice.currency)}</Text>
            </View>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Discount ({invoice.discount_type === 'percentage' ? `${invoice.discount_value}%` : formatCurrency(invoice.discount_value || 0, invoice.currency)}):</Text>
              <Text style={styles.totalValue}>- {formatCurrency((invoice.subtotal || 0) - invoice.amount, invoice.currency)}</Text>
            </View>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Total:</Text>
              <Text style={styles.totalValue}>{formatCurrency(invoice.amount, invoice.currency)}</Text>
            </View>
          </>
        ) : (
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Subtotal:</Text>
            <Text style={styles.totalValue}>{formatCurrency(invoice.amount, invoice.currency)}</Text>
          </View>
        )}
        {invoice.paid_amount > 0 && (
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Paid Amount:</Text>
            <Text style={styles.totalValue}>{formatCurrency(invoice.paid_amount, invoice.currency)}</Text>
          </View>
        )}
        <View style={styles.totalRow}>
          <Text style={styles.totalLabel}>Balance Due:</Text>
          <Text style={styles.totalValue}>{formatCurrency(invoice.amount - (invoice.paid_amount || 0), invoice.currency)}</Text>
        </View>
      </View>

      {invoice.notes && (
        <View style={styles.notes}>
          <Text style={[styles.label, { marginBottom: 5 }]}>Notes:</Text>
          <Text>{invoice.notes}</Text>
        </View>
      )}
      </Page>
    </Document>
  );
}; 
