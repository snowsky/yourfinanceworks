import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { X, Clock, Mail, Calendar, Settings, User } from 'lucide-react';
import { ScheduledReport } from '@/lib/api';
import { format, formatDistanceToNow } from 'date-fns';

interface ScheduledReportDetailsProps {
  scheduledReport: ScheduledReport;
  onClose: () => void;
}

export function ScheduledReportDetails({ scheduledReport, onClose }: ScheduledReportDetailsProps) {
  const getScheduleDescription = () => {
    const { schedule_config } = scheduledReport;
    const time = `${schedule_config.hour || 0}:${(schedule_config.minute || 0).toString().padStart(2, '0')}`;
    
    switch (schedule_config.schedule_type) {
      case 'daily':
        return `Every day at ${time}`;
      case 'weekly':
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return `Every ${days[schedule_config.day_of_week || 0]} at ${time}`;
      case 'monthly':
        return `Every month on day ${schedule_config.day_of_month || 1} at ${time}`;
      case 'yearly':
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        return `Every year on ${months[(schedule_config.month || 1) - 1]} ${schedule_config.day_of_month || 1} at ${time}`;
      default:
        return 'Unknown schedule';
    }
  };

  const getTimezoneDisplay = () => {
    const timezone = scheduledReport.schedule_config.timezone || 'UTC';
    const timezoneNames: Record<string, string> = {
      'UTC': 'UTC',
      'America/New_York': 'Eastern Time',
      'America/Chicago': 'Central Time',
      'America/Denver': 'Mountain Time',
      'America/Los_Angeles': 'Pacific Time',
      'Europe/London': 'London',
      'Europe/Paris': 'Paris',
      'Asia/Tokyo': 'Tokyo',
    };
    return timezoneNames[timezone] || timezone;
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Calendar className="h-5 w-5" />
                <span>Scheduled Report Details</span>
              </CardTitle>
              <CardDescription>
                View configuration and status of this scheduled report
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Status and Basic Info */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">
                {scheduledReport.template?.name || `Template ${scheduledReport.template_id}`}
              </h3>
              <p className="text-sm text-muted-foreground">
                {scheduledReport.template?.report_type} report
              </p>
            </div>
            <Badge variant={scheduledReport.is_active ? "default" : "secondary"} className="text-sm">
              {scheduledReport.is_active ? "Active" : "Paused"}
            </Badge>
          </div>

          <Separator />

          {/* Schedule Configuration */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Settings className="h-5 w-5 text-muted-foreground" />
              <h4 className="font-medium">Schedule Configuration</h4>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-7">
              <div>
                <Label className="text-sm font-medium text-muted-foreground">Frequency</Label>
                <p className="text-sm">{getScheduleDescription()}</p>
              </div>
              <div>
                <Label className="text-sm font-medium text-muted-foreground">Timezone</Label>
                <p className="text-sm">{getTimezoneDisplay()}</p>
              </div>
            </div>

            {/* Execution Times */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-7">
              {scheduledReport.last_run && (
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Last Execution</Label>
                  <p className="text-sm">
                    {format(new Date(scheduledReport.last_run), 'MMM d, yyyy h:mm a')}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(scheduledReport.last_run), { addSuffix: true })}
                  </p>
                </div>
              )}
              {scheduledReport.next_run && (
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Next Execution</Label>
                  <p className="text-sm">
                    {format(new Date(scheduledReport.next_run), 'MMM d, yyyy h:mm a')}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(scheduledReport.next_run), { addSuffix: true })}
                  </p>
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Recipients */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Mail className="h-5 w-5 text-muted-foreground" />
              <h4 className="font-medium">Email Recipients</h4>
              <Badge variant="outline" className="text-xs">
                {scheduledReport.recipients.length} recipient{scheduledReport.recipients.length !== 1 ? 's' : ''}
              </Badge>
            </div>
            
            <div className="pl-7">
              <div className="space-y-2">
                {scheduledReport.recipients.map((email, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{email}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <Separator />

          {/* Template Information */}
          {scheduledReport.template && (
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <h4 className="font-medium">Template Information</h4>
              </div>
              
              <div className="pl-7 space-y-3">
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Template Name</Label>
                  <p className="text-sm">{scheduledReport.template.name}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Report Type</Label>
                  <p className="text-sm capitalize">{scheduledReport.template.report_type}</p>
                </div>
                {scheduledReport.template.filters && Object.keys(scheduledReport.template.filters).length > 0 && (
                  <div>
                    <Label className="text-sm font-medium text-muted-foreground">Applied Filters</Label>
                    <div className="text-sm space-y-1">
                      {Object.entries(scheduledReport.template.filters).map(([key, value]) => (
                        <div key={key} className="flex items-center space-x-2">
                          <span className="text-muted-foreground">{key}:</span>
                          <span>{Array.isArray(value) ? value.join(', ') : String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <Separator />

          {/* Metadata */}
          <div className="space-y-2">
            <h4 className="font-medium text-sm text-muted-foreground">Metadata</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Created</Label>
                <p>{format(new Date(scheduledReport.created_at), 'MMM d, yyyy h:mm a')}</p>
              </div>
              <div>
                <Label className="text-xs font-medium text-muted-foreground">Last Updated</Label>
                <p>{format(new Date(scheduledReport.updated_at), 'MMM d, yyyy h:mm a')}</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end pt-4">
            <Button onClick={onClose}>
              Close
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Helper component for labels
function Label({ className, children, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 ${className || ''}`} {...props}>
      {children}
    </label>
  );
}