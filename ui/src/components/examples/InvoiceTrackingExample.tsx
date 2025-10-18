import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useBusinessTracking } from '@/hooks/useTracking';
import { Badge } from '@/components/ui/badge';
import { FileText, DollarSign, Users, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const InvoiceTrackingExample = () => {
  const businessTracking = useBusinessTracking();
  const [invoiceData, setInvoiceData] = useState({
    clientName: '',
    amount: '',
    currency: 'USD'
  });

  const handleCreateInvoice = async () => {
    if (!invoiceData.clientName || !invoiceData.amount) {
      toast.error('Please fill in all fields');
      return;
    }

    const invoiceId = `INV-${Date.now()}`;
    const amount = parseFloat(invoiceData.amount);

    try {
      // Simulate invoice creation
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Track the business event (respects cookie consent)
      businessTracking.trackInvoiceCreated(invoiceId, amount, invoiceData.currency);

      // Track feature usage
      businessTracking.trackFeatureUsed('invoice_creation', 'demo');

      toast.success(`Invoice ${invoiceId} created successfully!`);

      // Reset form
      setInvoiceData({ clientName: '', amount: '', currency: 'USD' });

    } catch (error) {
      // Track errors
      businessTracking.trackError('Invoice creation failed', 'invoice_form');
      toast.error('Failed to create invoice');
    }
  };

  const handleAddClient = () => {
    const clientId = `CLIENT-${Date.now()}`;

    // Track client addition
    businessTracking.trackClientAdded(clientId);
    businessTracking.trackFeatureUsed('client_management', 'demo');

    toast.success(`Client ${clientId} added!`);
  };

  const handlePaymentReceived = () => {
    const invoiceId = `INV-${Date.now()}`;
    const amount = parseFloat(invoiceData.amount) || 100;

    // Track payment (this is a conversion event for marketing)
    businessTracking.trackInvoicePaid(invoiceId, amount, invoiceData.currency);

    toast.success(`Payment of ${invoiceData.currency} ${amount} received!`);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Business Event Tracking Demo
          </CardTitle>
          <CardDescription>
            This demo shows how business events are tracked based on cookie consent preferences.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="client-name">Client Name</Label>
              <Input
                id="client-name"
                value={invoiceData.clientName}
                onChange={(e) => setInvoiceData(prev => ({ ...prev, clientName: e.target.value }))}
                placeholder="Enter client name"
              />
            </div>
            <div>
              <Label htmlFor="amount">Amount</Label>
              <Input
                id="amount"
                type="number"
                value={invoiceData.amount}
                onChange={(e) => setInvoiceData(prev => ({ ...prev, amount: e.target.value }))}
                placeholder="0.00"
              />
            </div>
            <div>
              <Label htmlFor="currency">Currency</Label>
              <select
                id="currency"
                className="w-full p-2 border rounded-md"
                value={invoiceData.currency}
                onChange={(e) => setInvoiceData(prev => ({ ...prev, currency: e.target.value }))}
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
          </div>

          <div className="flex gap-3">
            <Button onClick={handleCreateInvoice} className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Create Invoice
            </Button>
            <Button onClick={handleAddClient} variant="outline" className="flex items-center gap-2">
              <Users className="w-4 h-4" />
              Add Client
            </Button>
            <Button onClick={handlePaymentReceived} variant="outline" className="flex items-center gap-2">
              <DollarSign className="w-4 h-4" />
              Record Payment
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What Gets Tracked</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Badge variant="outline">Analytics Cookies</Badge>
              </h3>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  Page views and navigation
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  Feature usage and interactions
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  Performance metrics
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  Error tracking and debugging
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  User engagement patterns
                </li>
              </ul>
            </div>

            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Badge variant="outline">Marketing Cookies</Badge>
              </h3>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-purple-500" />
                  Conversion tracking
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-purple-500" />
                  Purchase and revenue events
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-purple-500" />
                  Remarketing audience building
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-purple-500" />
                  Ad campaign optimization
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-purple-500" />
                  Cross-platform attribution
                </li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integration Code Examples</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="font-semibold mb-2">Invoice Creation Tracking</h3>
            <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto">
              {`const handleCreateInvoice = async (invoiceData) => {
  try {
    // Create invoice
    const invoice = await createInvoice(invoiceData);
    
    // Track the event (respects cookie consent)
    businessTracking.trackInvoiceCreated(
      invoice.id, 
      invoice.amount, 
      invoice.currency
    );
    
    // Track feature usage
    businessTracking.trackFeatureUsed('invoice_creation');
    
  } catch (error) {
    // Track errors for debugging
    businessTracking.trackError(error.message, 'invoice_creation');
  }
};`}
            </pre>
          </div>

          <div>
            <h3 className="font-semibold mb-2">Payment Tracking</h3>
            <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto">
              {`const handlePaymentReceived = (payment) => {
  // Track payment as both analytics and marketing event
  businessTracking.trackInvoicePaid(
    payment.invoiceId,
    payment.amount,
    payment.currency
  );
  
  // Add to high-value customer audience for remarketing
  if (payment.amount > 1000) {
    tracking.addToRemarketingAudience('high_value_customers', {
      lifetime_value: payment.amount
    });
  }
};`}
            </pre>
          </div>

          <div>
            <h3 className="font-semibold mb-2">User Engagement Tracking</h3>
            <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto">
              {`const handleFeatureClick = (featureName) => {
  // Track user engagement
  tracking.trackUserEngagement('feature_click', featureName);
  
  // Track specific event
  tracking.trackEvent('feature_interaction', {
    feature: featureName,
    timestamp: Date.now(),
    user_type: 'premium'
  });
};`}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default InvoiceTrackingExample;
