import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useTracking, useBusinessTracking } from '@/hooks/useTracking';
import { Badge } from '@/components/ui/badge';
import { BarChart3, Target, ShoppingCart, UserPlus, FileText, AlertCircle } from 'lucide-react';

const TrackingExample = () => {
  const tracking = useTracking();
  const businessTracking = useBusinessTracking();

  const handleAnalyticsEvent = () => {
    tracking.trackEvent('button_click', {
      button_name: 'analytics_example',
      page: 'tracking_demo',
      timestamp: Date.now()
    });
  };

  const handleMarketingEvent = () => {
    tracking.trackConversion('demo_conversion', {
      conversion_type: 'demo',
      value: 1,
      currency: 'USD'
    });
  };

  const handleBusinessEvent = () => {
    businessTracking.trackInvoiceCreated('INV-001', 1500.00, 'USD');
  };

  const handleUserEngagement = () => {
    tracking.trackUserEngagement('demo_interaction', 'engagement', 1);
  };

  const handleError = () => {
    businessTracking.trackError('Demo error for testing', 'tracking_example');
  };

  const handleFeatureUsage = () => {
    businessTracking.trackFeatureUsed('tracking_demo', 'example_page');
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Cookie Consent Tracking Demo
          </CardTitle>
          <CardDescription>
            This demo shows how analytics and marketing tracking respects user cookie preferences.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h3 className="font-semibold">Current Status</h3>
              <div className="flex gap-2">
                <Badge variant={tracking.analyticsEnabled ? "default" : "secondary"}>
                  Analytics: {tracking.analyticsEnabled ? 'Enabled' : 'Disabled'}
                </Badge>
                <Badge variant={tracking.marketingEnabled ? "default" : "secondary"}>
                  Marketing: {tracking.marketingEnabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold">Behavior</h3>
              <p className="text-sm text-muted-foreground">
                {tracking.analyticsEnabled || tracking.marketingEnabled 
                  ? 'Events will be tracked based on your cookie preferences'
                  : 'Events will be queued until you give consent'
                }
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Analytics Events */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Analytics Events
            </CardTitle>
            <CardDescription>
              Requires Analytics Cookies consent
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button 
              onClick={handleAnalyticsEvent}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled}
            >
              Track Button Click
            </Button>
            <Button 
              onClick={handleFeatureUsage}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled}
            >
              Track Feature Usage
            </Button>
            <Button 
              onClick={handleUserEngagement}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled}
            >
              Track User Engagement
            </Button>
          </CardContent>
        </Card>

        {/* Marketing Events */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Target className="w-4 h-4" />
              Marketing Events
            </CardTitle>
            <CardDescription>
              Requires Marketing Cookies consent
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button 
              onClick={handleMarketingEvent}
              variant="outline" 
              className="w-full"
              disabled={!tracking.marketingEnabled}
            >
              Track Conversion
            </Button>
            <Button 
              onClick={() => tracking.trackSignup('demo')}
              variant="outline" 
              className="w-full"
              disabled={!tracking.marketingEnabled}
            >
              <UserPlus className="w-4 h-4 mr-2" />
              Track Signup
            </Button>
            <Button 
              onClick={() => tracking.trackAddToCart('demo-item', 99.99)}
              variant="outline" 
              className="w-full"
              disabled={!tracking.marketingEnabled}
            >
              <ShoppingCart className="w-4 h-4 mr-2" />
              Track Add to Cart
            </Button>
          </CardContent>
        </Card>

        {/* Business Events */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileText className="w-4 h-4" />
              Business Events
            </CardTitle>
            <CardDescription>
              Tracks to both Analytics & Marketing
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button 
              onClick={handleBusinessEvent}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled && !tracking.marketingEnabled}
            >
              Track Invoice Created
            </Button>
            <Button 
              onClick={() => businessTracking.trackInvoicePaid('INV-001', 1500.00, 'USD')}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled && !tracking.marketingEnabled}
            >
              Track Invoice Paid
            </Button>
            <Button 
              onClick={() => businessTracking.trackClientAdded('CLIENT-001')}
              variant="outline" 
              className="w-full"
              disabled={!tracking.analyticsEnabled && !tracking.marketingEnabled}
            >
              Track Client Added
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Error Tracking */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            Error & Performance Tracking
          </CardTitle>
          <CardDescription>
            Always works (essential for debugging)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-3">
            <Button 
              onClick={handleError}
              variant="destructive" 
              size="sm"
            >
              Track Error
            </Button>
            <Button 
              onClick={() => businessTracking.trackPerformance('demo_load_time', 1250)}
              variant="outline" 
              size="sm"
            >
              Track Performance
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>How It Works</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="font-semibold mb-2">With Consent</h4>
              <ul className="space-y-1 text-muted-foreground">
                <li>• Events are tracked immediately</li>
                <li>• Analytics scripts are loaded</li>
                <li>• Marketing pixels fire</li>
                <li>• Data is sent to providers</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-2">Without Consent</h4>
              <ul className="space-y-1 text-muted-foreground">
                <li>• Events are queued in memory</li>
                <li>• No scripts are loaded</li>
                <li>• No data is sent externally</li>
                <li>• Queued events fire when consent is given</li>
              </ul>
            </div>
          </div>
          
          <div className="bg-blue-50 p-4 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>Try it:</strong> Change your cookie preferences in the Cookie Settings tab, 
              then test the buttons above to see how tracking behavior changes based on your consent.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TrackingExample;