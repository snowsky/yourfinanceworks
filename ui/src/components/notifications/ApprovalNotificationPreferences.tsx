import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Bell, Mail, Smartphone, Clock, Settings } from 'lucide-react';
import { api } from '@/lib/api';

interface ApprovalNotificationPreferences {
  approval_notification_frequency: string;
  approval_reminder_frequency: string;
  approval_notification_channels: string[];
  approval_events: {
    expense_submitted_for_approval: boolean;
    expense_approved: boolean;
    expense_rejected: boolean;
    expense_level_approved: boolean;
    expense_fully_approved: boolean;
    expense_auto_approved: boolean;
    approval_reminder: boolean;
    approval_escalation: boolean;
  };
}

const ApprovalNotificationPreferences: React.FC = () => {
  const [preferences, setPreferences] = useState<ApprovalNotificationPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      const response = await api.get('/notifications/approval-preferences');
      setPreferences(response.data);
    } catch (error) {
      console.error('Error fetching approval notification preferences:', error);
      setError('Failed to load notification preferences');
    } finally {
      setLoading(false);
    }
  };

  const savePreferences = async () => {
    if (!preferences) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      await api.put('/notifications/approval-preferences', preferences);
      setSuccess('Notification preferences updated successfully');
    } catch (error) {
      console.error('Error saving approval notification preferences:', error);
      setError('Failed to save notification preferences');
    } finally {
      setSaving(false);
    }
  };

  const sendTestDigest = async () => {
    try {
      setError(null);
      setSuccess(null);
      
      await api.post('/notifications/send-digest');
      setSuccess('Test digest sent successfully! Check your email.');
    } catch (error) {
      console.error('Error sending test digest:', error);
      setError('Failed to send test digest');
    }
  };

  const updateFrequency = (field: 'approval_notification_frequency' | 'approval_reminder_frequency', value: string) => {
    if (!preferences) return;
    setPreferences({
      ...preferences,
      [field]: value
    });
  };

  const updateChannels = (channel: string, checked: boolean) => {
    if (!preferences) return;
    
    let newChannels = [...preferences.approval_notification_channels];
    if (checked) {
      if (!newChannels.includes(channel)) {
        newChannels.push(channel);
      }
    } else {
      newChannels = newChannels.filter(c => c !== channel);
    }
    
    // Ensure at least one channel is selected
    if (newChannels.length === 0) {
      return;
    }
    
    setPreferences({
      ...preferences,
      approval_notification_channels: newChannels
    });
  };

  const updateEventPreference = (event: keyof ApprovalNotificationPreferences['approval_events'], enabled: boolean) => {
    if (!preferences) return;
    setPreferences({
      ...preferences,
      approval_events: {
        ...preferences.approval_events,
        [event]: enabled
      }
    });
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-6">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading notification preferences...
        </CardContent>
      </Card>
    );
  }

  if (!preferences) {
    return (
      <Card>
        <CardContent className="p-6">
          <Alert>
            <AlertDescription>
              Failed to load notification preferences. Please try refreshing the page.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Approval Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          
          {success && (
            <Alert>
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}

          {/* Notification Frequency */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <Label className="text-base font-medium">Notification Frequency</Label>
            </div>
            
            <div className="space-y-3 ml-6">
              <div>
                <Label htmlFor="notification-frequency" className="text-sm font-medium">
                  Approval Notifications
                </Label>
                <Select
                  value={preferences.approval_notification_frequency}
                  onValueChange={(value) => updateFrequency('approval_notification_frequency', value)}
                >
                  <SelectTrigger className="w-full mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="immediate">Immediate - Send notifications as events occur</SelectItem>
                    <SelectItem value="daily_digest">Daily Digest - Send a summary once per day</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="reminder-frequency" className="text-sm font-medium">
                  Approval Reminders
                </Label>
                <Select
                  value={preferences.approval_reminder_frequency}
                  onValueChange={(value) => updateFrequency('approval_reminder_frequency', value)}
                >
                  <SelectTrigger className="w-full mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily - Send reminders daily</SelectItem>
                    <SelectItem value="weekly">Weekly - Send reminders weekly</SelectItem>
                    <SelectItem value="disabled">Disabled - No reminder notifications</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Notification Channels */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Smartphone className="h-4 w-4" />
              <Label className="text-base font-medium">Notification Channels</Label>
            </div>
            
            <div className="space-y-3 ml-6">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="email-channel"
                  checked={preferences.approval_notification_channels.includes('email')}
                  onCheckedChange={(checked) => updateChannels('email', checked as boolean)}
                />
                <Label htmlFor="email-channel" className="flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  Email notifications
                </Label>
              </div>
              
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="inapp-channel"
                  checked={preferences.approval_notification_channels.includes('in_app')}
                  onCheckedChange={(checked) => updateChannels('in_app', checked as boolean)}
                />
                <Label htmlFor="inapp-channel" className="flex items-center gap-2">
                  <Bell className="h-4 w-4" />
                  In-app notifications
                </Label>
              </div>
              
              <p className="text-sm text-muted-foreground">
                At least one notification channel must be selected.
              </p>
            </div>
          </div>

          {/* Event Preferences */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              <Label className="text-base font-medium">Event Notifications</Label>
            </div>
            
            <div className="space-y-3 ml-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <h4 className="font-medium text-sm">Expense Events</h4>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-submitted" className="text-sm">
                      Expense submitted for approval
                    </Label>
                    <Switch
                      id="expense-submitted"
                      checked={preferences.approval_events.expense_submitted_for_approval}
                      onCheckedChange={(checked) => updateEventPreference('expense_submitted_for_approval', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-approved" className="text-sm">
                      Expense approved
                    </Label>
                    <Switch
                      id="expense-approved"
                      checked={preferences.approval_events.expense_approved}
                      onCheckedChange={(checked) => updateEventPreference('expense_approved', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-rejected" className="text-sm">
                      Expense rejected
                    </Label>
                    <Switch
                      id="expense-rejected"
                      checked={preferences.approval_events.expense_rejected}
                      onCheckedChange={(checked) => updateEventPreference('expense_rejected', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-level-approved" className="text-sm">
                      Expense level approved
                    </Label>
                    <Switch
                      id="expense-level-approved"
                      checked={preferences.approval_events.expense_level_approved}
                      onCheckedChange={(checked) => updateEventPreference('expense_level_approved', checked)}
                    />
                  </div>
                </div>
                
                <div className="space-y-3">
                  <h4 className="font-medium text-sm">System Events</h4>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-fully-approved" className="text-sm">
                      Expense fully approved
                    </Label>
                    <Switch
                      id="expense-fully-approved"
                      checked={preferences.approval_events.expense_fully_approved}
                      onCheckedChange={(checked) => updateEventPreference('expense_fully_approved', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="expense-auto-approved" className="text-sm">
                      Expense auto-approved
                    </Label>
                    <Switch
                      id="expense-auto-approved"
                      checked={preferences.approval_events.expense_auto_approved}
                      onCheckedChange={(checked) => updateEventPreference('expense_auto_approved', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="approval-reminder" className="text-sm">
                      Approval reminders
                    </Label>
                    <Switch
                      id="approval-reminder"
                      checked={preferences.approval_events.approval_reminder}
                      onCheckedChange={(checked) => updateEventPreference('approval_reminder', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label htmlFor="approval-escalation" className="text-sm">
                      Approval escalations
                    </Label>
                    <Switch
                      id="approval-escalation"
                      checked={preferences.approval_events.approval_escalation}
                      onCheckedChange={(checked) => updateEventPreference('approval_escalation', checked)}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4 border-t">
            <Button onClick={savePreferences} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Save Preferences
            </Button>
            
            <Button variant="outline" onClick={sendTestDigest}>
              Send Test Digest
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ApprovalNotificationPreferences;