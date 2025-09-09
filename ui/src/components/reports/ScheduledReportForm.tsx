import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { X, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { reportApi, ReportTemplate, ScheduledReport, ScheduledReportCreate, ScheduledReportUpdate, ScheduleConfig } from '@/lib/api';

interface ScheduledReportFormProps {
  scheduledReport?: ScheduledReport;
  onSuccess: (report: ScheduledReport) => void;
  onCancel: () => void;
}

export function ScheduledReportForm({ scheduledReport, onSuccess, onCancel }: ScheduledReportFormProps) {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    template_id: scheduledReport?.template_id || 0,
    schedule_config: {
      schedule_type: scheduledReport?.schedule_config.schedule_type || 'weekly' as const,
      day_of_week: scheduledReport?.schedule_config.day_of_week || 1,
      day_of_month: scheduledReport?.schedule_config.day_of_month || 1,
      month: scheduledReport?.schedule_config.month || 1,
      hour: scheduledReport?.schedule_config.hour || 9,
      minute: scheduledReport?.schedule_config.minute || 0,
      timezone: scheduledReport?.schedule_config.timezone || 'UTC',
    },
    recipients: scheduledReport?.recipients || [],
    is_active: scheduledReport?.is_active ?? true,
  });
  const [newRecipient, setNewRecipient] = useState('');

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await reportApi.getTemplates();
      setTemplates(response.templates);
    } catch (error) {
      console.error('Failed to load templates:', error);
      toast.error('Failed to load templates');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.template_id) {
      toast.error('Please select a template');
      return;
    }

    if (formData.recipients.length === 0) {
      toast.error('Please add at least one recipient');
      return;
    }

    try {
      setLoading(true);
      
      if (scheduledReport) {
        // Update existing scheduled report
        const updated = await reportApi.updateScheduledReport(scheduledReport.id, {
          schedule_config: formData.schedule_config,
          recipients: formData.recipients,
          is_active: formData.is_active,
        });
        onSuccess(updated);
      } else {
        // Create new scheduled report
        const created = await reportApi.createScheduledReport({
          template_id: formData.template_id,
          schedule_config: formData.schedule_config,
          recipients: formData.recipients,
          is_active: formData.is_active,
        });
        onSuccess(created);
      }
    } catch (error) {
      console.error('Failed to save scheduled report:', error);
      toast.error('Failed to save scheduled report');
    } finally {
      setLoading(false);
    }
  };

  const addRecipient = () => {
    if (!newRecipient.trim()) return;
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(newRecipient.trim())) {
      toast.error('Please enter a valid email address');
      return;
    }

    if (formData.recipients.includes(newRecipient.trim())) {
      toast.error('This recipient is already added');
      return;
    }

    setFormData(prev => ({
      ...prev,
      recipients: [...prev.recipients, newRecipient.trim()]
    }));
    setNewRecipient('');
  };

  const removeRecipient = (email: string) => {
    setFormData(prev => ({
      ...prev,
      recipients: prev.recipients.filter(r => r !== email)
    }));
  };

  const updateScheduleConfig = (updates: Partial<ScheduleConfig>) => {
    setFormData(prev => ({
      ...prev,
      schedule_config: { ...prev.schedule_config, ...updates }
    }));
  };

  const selectedTemplate = templates.find(t => t.id === formData.template_id);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>
                {scheduledReport ? 'Edit Scheduled Report' : 'Schedule New Report'}
              </CardTitle>
              <CardDescription>
                Configure automated report generation and delivery
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Template Selection */}
            <div className="space-y-2">
              <Label htmlFor="template">Report Template</Label>
              <Select
                value={formData.template_id.toString()}
                onValueChange={(value) => setFormData(prev => ({ ...prev, template_id: parseInt(value) }))}
                disabled={!!scheduledReport} // Can't change template for existing schedules
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a template" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((template) => (
                    <SelectItem key={template.id} value={template.id.toString()}>
                      <div className="flex items-center space-x-2">
                        <span>{template.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {template.report_type}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedTemplate && (
                <p className="text-sm text-muted-foreground">
                  {selectedTemplate.report_type} report template
                </p>
              )}
            </div>

            <Separator />

            {/* Schedule Configuration */}
            <div className="space-y-4">
              <Label className="text-base font-medium">Schedule Configuration</Label>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="schedule_type">Frequency</Label>
                  <Select
                    value={formData.schedule_config.schedule_type}
                    onValueChange={(value: 'daily' | 'weekly' | 'monthly' | 'yearly') => 
                      updateScheduleConfig({ schedule_type: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="monthly">Monthly</SelectItem>
                      <SelectItem value="yearly">Yearly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select
                    value={formData.schedule_config.timezone}
                    onValueChange={(value) => updateScheduleConfig({ timezone: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UTC">UTC</SelectItem>
                      <SelectItem value="America/New_York">Eastern Time</SelectItem>
                      <SelectItem value="America/Chicago">Central Time</SelectItem>
                      <SelectItem value="America/Denver">Mountain Time</SelectItem>
                      <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                      <SelectItem value="Europe/London">London</SelectItem>
                      <SelectItem value="Europe/Paris">Paris</SelectItem>
                      <SelectItem value="Asia/Tokyo">Tokyo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Schedule-specific fields */}
              {formData.schedule_config.schedule_type === 'weekly' && (
                <div className="space-y-2">
                  <Label htmlFor="day_of_week">Day of Week</Label>
                  <Select
                    value={formData.schedule_config.day_of_week?.toString() || '1'}
                    onValueChange={(value) => updateScheduleConfig({ day_of_week: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">Sunday</SelectItem>
                      <SelectItem value="1">Monday</SelectItem>
                      <SelectItem value="2">Tuesday</SelectItem>
                      <SelectItem value="3">Wednesday</SelectItem>
                      <SelectItem value="4">Thursday</SelectItem>
                      <SelectItem value="5">Friday</SelectItem>
                      <SelectItem value="6">Saturday</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {(formData.schedule_config.schedule_type === 'monthly' || formData.schedule_config.schedule_type === 'yearly') && (
                <div className="space-y-2">
                  <Label htmlFor="day_of_month">Day of Month</Label>
                  <Select
                    value={formData.schedule_config.day_of_month?.toString() || '1'}
                    onValueChange={(value) => updateScheduleConfig({ day_of_month: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                        <SelectItem key={day} value={day.toString()}>
                          {day}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {formData.schedule_config.schedule_type === 'yearly' && (
                <div className="space-y-2">
                  <Label htmlFor="month">Month</Label>
                  <Select
                    value={formData.schedule_config.month?.toString() || '1'}
                    onValueChange={(value) => updateScheduleConfig({ month: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">January</SelectItem>
                      <SelectItem value="2">February</SelectItem>
                      <SelectItem value="3">March</SelectItem>
                      <SelectItem value="4">April</SelectItem>
                      <SelectItem value="5">May</SelectItem>
                      <SelectItem value="6">June</SelectItem>
                      <SelectItem value="7">July</SelectItem>
                      <SelectItem value="8">August</SelectItem>
                      <SelectItem value="9">September</SelectItem>
                      <SelectItem value="10">October</SelectItem>
                      <SelectItem value="11">November</SelectItem>
                      <SelectItem value="12">December</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="hour">Hour (24h format)</Label>
                  <Select
                    value={formData.schedule_config.hour?.toString() || '9'}
                    onValueChange={(value) => updateScheduleConfig({ hour: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => i).map(hour => (
                        <SelectItem key={hour} value={hour.toString()}>
                          {hour.toString().padStart(2, '0')}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="minute">Minute</Label>
                  <Select
                    value={formData.schedule_config.minute?.toString() || '0'}
                    onValueChange={(value) => updateScheduleConfig({ minute: parseInt(value) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[0, 15, 30, 45].map(minute => (
                        <SelectItem key={minute} value={minute.toString()}>
                          {minute.toString().padStart(2, '0')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <Separator />

            {/* Recipients */}
            <div className="space-y-4">
              <Label className="text-base font-medium">Email Recipients</Label>
              
              <div className="flex space-x-2">
                <Input
                  type="email"
                  placeholder="Enter email address"
                  value={newRecipient}
                  onChange={(e) => setNewRecipient(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addRecipient())}
                />
                <Button type="button" onClick={addRecipient}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>

              {formData.recipients.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm">Recipients ({formData.recipients.length})</Label>
                  <div className="flex flex-wrap gap-2">
                    {formData.recipients.map((email) => (
                      <Badge key={email} variant="secondary" className="flex items-center space-x-1">
                        <span>{email}</span>
                        <button
                          type="button"
                          onClick={() => removeRecipient(email)}
                          className="ml-1 hover:text-destructive"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <Separator />

            {/* Active Status */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-base">Active Status</Label>
                <p className="text-sm text-muted-foreground">
                  Enable or disable this scheduled report
                </p>
              </div>
              <Switch
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked }))}
              />
            </div>

            {/* Form Actions */}
            <div className="flex justify-end space-x-2 pt-4">
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Saving...' : (scheduledReport ? 'Update Schedule' : 'Create Schedule')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}