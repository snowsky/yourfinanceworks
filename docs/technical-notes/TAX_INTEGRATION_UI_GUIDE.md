# Tax Service UI Integration Guide

This guide explains how to integrate the Tax Service components into your existing Invoice App pages.

## 🎯 Components Overview

### Core Components

1. **`SendToTaxServiceButton`** - Individual send button for expenses/invoices
2. **`TaxIntegrationStatus`** - Shows integration status and connection info
3. **`BulkSendToTaxServiceDialog`** - Bulk send functionality
4. **`TaxIntegrationSettings`** - Settings display component

## 🚀 Quick Integration

### Step 1: Import Components

```tsx
import {
  SendToTaxServiceButton,
  TaxIntegrationStatus,
  BulkSendToTaxServiceDialog,
} from '@/components/tax-integration';
```

### Step 2: Add Status Component

Add the status component to show integration health:

```tsx
function MyPage() {
  return (
    <AppLayout>
      <div className="space-y-4">
        {/* Add this line */}
        <TaxIntegrationStatus />

        {/* Rest of your page content */}
      </div>
    </AppLayout>
  );
}
```

### Step 3: Add Individual Send Buttons

Add send buttons to table rows or detail views:

```tsx
<TableCell>
  <div className="flex items-center space-x-2">
    <SendToTaxServiceButton
      itemId={expense.id}
      itemType="expense"
      onSuccess={() => {
        // Refresh your data
        fetchExpenses();
      }}
      size="sm"
    />
    {/* Other action buttons */}
  </div>
</TableCell>
```

### Step 4: Add Bulk Send Functionality

Add bulk selection and send capabilities:

```tsx
const [selectedIds, setSelectedIds] = useState<number[]>([]);
const [bulkSendDialogOpen, setBulkSendDialogOpen] = useState(false);

function MyPage() {
  const handleBulkSendToTaxService = () => {
    if (selectedIds.length === 0) {
      toast.error(t('taxIntegration.errors.noItemsSelected'));
      return;
    }
    setBulkSendDialogOpen(true);
  };

  const handleTaxServiceSuccess = () => {
    fetchData(); // Refresh your data
    setSelectedIds([]); // Clear selection
  };

  return (
    <>
      {/* Bulk Actions Bar */}
      {selectedIds.length > 0 && (
        <div className="flex items-center justify-between p-4 bg-blue-50 border border-blue-200 rounded-md">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium">
              {selectedIds.length} selected
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleBulkSendToTaxService}
            >
              <Send className="h-4 w-4 mr-2" />
              Send Selected ({selectedIds.length})
            </Button>
          </div>
        </div>
      )}

      {/* Bulk Send Dialog */}
      <BulkSendToTaxServiceDialog
        open={bulkSendDialogOpen}
        onOpenChange={setBulkSendDialogOpen}
        items={items.filter(item => selectedIds.includes(item.id))}
        itemType="expense" // or "invoice"
        onSuccess={handleTaxServiceSuccess}
      />
    </>
  );
}
```

## 📋 Complete Integration Examples

### Expenses Page Integration

```tsx
import React, { useState } from 'react';
import { SendToTaxServiceButton, TaxIntegrationStatus, BulkSendToTaxServiceDialog } from '@/components/tax-integration';

function ExpensesPage() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkSendDialogOpen, setBulkSendDialogOpen] = useState(false);

  const handleTaxServiceSuccess = () => {
    fetchExpenses();
    setSelectedIds([]);
  };

  return (
    <AppLayout>
      <div className="space-y-4">
        {/* Integration Status */}
        <TaxIntegrationStatus />

        {/* Bulk Actions */}
        {selectedIds.length > 0 && (
          <Button onClick={() => setBulkSendDialogOpen(true)}>
            Send {selectedIds.length} to Tax Service
          </Button>
        )}

        {/* Table with checkboxes and send buttons */}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Checkbox
                  checked={selectedIds.length === expenses.length}
                  onCheckedChange={(checked) => {
                    setSelectedIds(checked ? expenses.map(e => e.id) : []);
                  }}
                />
              </TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {expenses.map((expense) => (
              <TableRow key={expense.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(expense.id)}
                    onCheckedChange={(checked) => {
                      setSelectedIds(prev =>
                        checked
                          ? [...prev, expense.id]
                          : prev.filter(id => id !== expense.id)
                      );
                    }}
                  />
                </TableCell>
                <TableCell>{expense.expense_date}</TableCell>
                <TableCell>{expense.vendor}</TableCell>
                <TableCell>${expense.amount}</TableCell>
                <TableCell>
                  <SendToTaxServiceButton
                    itemId={expense.id}
                    itemType="expense"
                    onSuccess={handleTaxServiceSuccess}
                    size="sm"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Bulk Send Dialog */}
        <BulkSendToTaxServiceDialog
          open={bulkSendDialogOpen}
          onOpenChange={setBulkSendDialogOpen}
          items={expenses.filter(e => selectedIds.includes(e.id))}
          itemType="expense"
          onSuccess={handleTaxServiceSuccess}
        />
      </div>
    </AppLayout>
  );
}
```

### Invoices Page Integration

```tsx
import React, { useState } from 'react';
import { SendToTaxServiceButton, TaxIntegrationStatus, BulkSendToTaxServiceDialog } from '@/components/tax-integration';

function InvoicesPage() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkSendDialogOpen, setBulkSendDialogOpen] = useState(false);

  const handleTaxServiceSuccess = () => {
    fetchInvoices();
    setSelectedIds([]);
  };

  return (
    <AppLayout>
      <div className="space-y-4">
        {/* Integration Status */}
        <TaxIntegrationStatus />

        {/* Bulk Actions */}
        {selectedIds.length > 0 && (
          <Button onClick={() => setBulkSendDialogOpen(true)}>
            Send {selectedIds.length} to Tax Service
          </Button>
        )}

        {/* Table with checkboxes and send buttons */}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Checkbox
                  checked={selectedIds.length === invoices.length}
                  onCheckedChange={(checked) => {
                    setSelectedIds(checked ? invoices.map(i => i.id) : []);
                  }}
                />
              </TableHead>
              <TableHead>Number</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(invoice.id)}
                    onCheckedChange={(checked) => {
                      setSelectedIds(prev =>
                        checked
                          ? [...prev, invoice.id]
                          : prev.filter(id => id !== invoice.id)
                      );
                    }}
                  />
                </TableCell>
                <TableCell>{invoice.number}</TableCell>
                <TableCell>{invoice.client_name}</TableCell>
                <TableCell>${invoice.amount}</TableCell>
                <TableCell>
                  <Badge variant={invoice.status === 'paid' ? 'default' : 'secondary'}>
                    {invoice.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <SendToTaxServiceButton
                    itemId={invoice.id}
                    itemType="invoice"
                    onSuccess={handleTaxServiceSuccess}
                    size="sm"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Bulk Send Dialog */}
        <BulkSendToTaxServiceDialog
          open={bulkSendDialogOpen}
          onOpenChange={setBulkSendDialogOpen}
          items={invoices.filter(i => selectedIds.includes(i.id))}
          itemType="invoice"
          onSuccess={handleTaxServiceSuccess}
        />
      </div>
    </AppLayout>
  );
}
```

## 🎨 Customization Options

### Button Variants

```tsx
<SendToTaxServiceButton
  variant="default" // default, outline, ghost, link
  size="sm"        // sm, default, lg
  disabled={false}
/>
```

### Custom Styling

```tsx
<SendToTaxServiceButton
  className="bg-green-600 hover:bg-green-700"
  itemId={item.id}
  itemType="expense"
/>
```

### Custom Success Handler

```tsx
<SendToTaxServiceButton
  itemId={item.id}
  itemType="expense"
  onSuccess={() => {
    toast.success('Custom success message!');
    // Additional logic here
  }}
/>
```

## 🔧 Configuration

### Environment Variables

Make sure these are set in your `.env` file:

```bash
TAX_SERVICE_ENABLED=true
TAX_SERVICE_BASE_URL=http://localhost:8000
TAX_SERVICE_API_KEY=your-api-key-here
TAX_SERVICE_TIMEOUT=30
TAX_SERVICE_RETRY_ATTEMPTS=3
```

### Setup Script

Use the provided setup script:

```bash
cd scripts
./setup_tax_integration.sh
```

## 🌐 Internationalization

The components automatically use your existing i18n setup. Translation keys are available for:

- Button labels
- Success/error messages
- Dialog titles
- Status messages

## 🚨 Error Handling

The components include comprehensive error handling:

- Network failures with retry logic
- Authentication errors
- Validation errors
- User-friendly error messages via toast notifications

## 📊 Monitoring

Monitor integration health with:

```tsx
// Add to any page for integration monitoring
<TaxIntegrationStatus />
```

This component shows:
- Connection status
- Configuration status
- Last test results
- Quick test connection button

## 🔄 Best Practices

### 1. Refresh Data After Send

Always refresh your data after successful sends:

```tsx
const handleTaxServiceSuccess = () => {
  fetchExpenses(); // or fetchInvoices()
  setSelectedIds([]); // Clear selections
};
```

### 2. Handle Loading States

The components handle their own loading states, but you can add additional UI feedback:

```tsx
const [isSending, setIsSending] = useState(false);

<SendToTaxServiceButton
  itemId={item.id}
  itemType="expense"
  onSuccess={() => {
    setIsSending(false);
    fetchData();
  }}
/>
```

### 3. Bulk Operations

For large datasets, consider pagination:

```tsx
// Only show bulk actions when reasonable number of items
{selectedIds.length > 0 && selectedIds.length <= 50 && (
  <BulkSendToTaxServiceDialog ... />
)}
```

### 4. User Feedback

Provide clear feedback for user actions:

```tsx
import { toast } from 'sonner';

const handleTaxServiceSuccess = () => {
  toast.success('Expense sent to tax service successfully!');
  fetchExpenses();
};
```

## 🧪 Testing

Test your integration with the provided test scripts:

```bash
# Test API endpoints
python scripts/test_tax_integration.py --token YOUR_JWT_TOKEN

# Or use the bash script
./scripts/test_tax_integration.sh
```

## 📁 File Structure

Your integrated components should be organized as:

```
src/
├── components/
│   └── tax-integration/
│       ├── SendToTaxServiceButton.tsx
│       ├── TaxIntegrationStatus.tsx
│       ├── BulkSendToTaxServiceDialog.tsx
│       ├── TaxIntegrationSettings.tsx
│       └── index.ts
├── pages/
│   ├── Expenses.tsx (with integration)
│   └── Invoices.tsx (with integration)
└── i18n/
    └── locales/
        ├── en.json (with tax integration keys)
        └── ...other locales
```

## 🎯 Next Steps

1. **Test the Integration**: Use the provided test scripts
2. **Customize Styling**: Adjust colors and layouts to match your design
3. **Add Analytics**: Track usage of the integration features
4. **Handle Edge Cases**: Consider offline scenarios and error recovery
5. **User Training**: Document the new features for your users

---

## 🆘 Troubleshooting

### Common Issues

**"Integration not configured"**
- Check your environment variables
- Run the setup script: `./setup_tax_integration.sh`

**"Connection failed"**
- Verify tax service is running
- Check TAX_SERVICE_BASE_URL
- Test connection manually

**"Authentication failed"**
- Verify TAX_SERVICE_API_KEY
- Check API key permissions in tax service

**Components not rendering**
- Ensure imports are correct
- Check component props
- Verify TypeScript types

For more help, check the console logs and API responses for detailed error information.
