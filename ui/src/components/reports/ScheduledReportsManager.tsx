import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Plus, Play, Pause, Trash2, Edit, Clock, Mail, Calendar } from 'lucide-react';
import { toast } from 'sonner';
import { reportApi, ScheduledReport } from '@/lib/api';
import { ScheduledReportForm } from './ScheduledReportForm';
import { ScheduledReportDetails } from './ScheduledReportDetails';
import { formatDistanceToNow, format } from 'date-fns';

export function ScheduledReportsManager() {
  const [scheduledReports, setScheduledReports] = useState<ScheduledReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingReport, setEditingReport] = useState<ScheduledReport | null>(null);
  const [selectedReport, setSelectedReport] = useState<ScheduledReport | null>(null);

  useEffect(() => {
    loadScheduledReports();
  }, []);

  const loadScheduledReports = async () => {
    try {
      setLoading(true);
      const response = await reportApi.getScheduledReports();
      setScheduledReports(response.scheduled_reports);
    } catch (error) {
      console.error('Failed to load scheduled reports:', error);
      toast.error('Failed to load scheduled reports');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (report: ScheduledReport) => {
    try {
      await reportApi.updateScheduledReport(report.id, {
        is_active: !report.is_active
      });
      
      setScheduledReports(prev => 
        prev.map(r => 
          r.id === report.id 
            ? { ...r, is_active: !r.is_active }
            : r
        )
      );
      
      toast.success(`Schedule ${report.is_active ? 'paused' : 'resumed'}`);
    } catch (error) {
      console.error('Failed to toggle schedule:', error);
      toast.error('Failed to update schedule');
    }
  };

  const handleDelete = async (report: ScheduledReport) => {
    if (!confirm('Are you sure you want to delete this scheduled report?')) {
      return;
    }

    try {
      await reportApi.deleteScheduledReport(report.id);
      setScheduledReports(prev => prev.filter(r => r.id !== report.id));
      toast.success('Scheduled report deleted');
    } catch (error) {
      console.error('Failed to delete scheduled report:', error);
      toast.error('Failed to delete scheduled report');
    }
  };

  const handleCreateSuccess = (newReport: ScheduledReport) => {
    setScheduledReports(prev => [...prev, newReport]);
    setShowCreateForm(false);
    toast.success('Scheduled report created');
  };

  const handleUpdateSuccess = (updatedReport: ScheduledReport) => {
    setScheduledReports(prev => 
      prev.map(r => r.id === updatedReport.id ? updatedReport : r)
    );
    setEditingReport(null);
    toast.success('Scheduled report updated');
  };

  const getScheduleDescription = (report: ScheduledReport) => {
    const { schedule_config } = report;
    const time = `${schedule_config.hour || 0}:${(schedule_config.minute || 0).toString().padStart(2, '0')}`;
    
    switch (schedule_config.schedule_type) {
      case 'daily':
        return `Daily at ${time}`;
      case 'weekly':
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return `Weekly on ${days[schedule_config.day_of_week || 0]} at ${time}`;
      case 'monthly':
        return `Monthly on day ${schedule_config.day_of_month || 1} at ${time}`;
      case 'yearly':
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `Yearly on ${months[(schedule_config.month || 1) - 1]} ${schedule_config.day_of_month || 1} at ${time}`;
      default:
        return 'Unknown schedule';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading scheduled reports...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Scheduled Reports</h2>
          <p className="text-muted-foreground">
            Manage automated report generation and delivery
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Schedule Report
        </Button>
      </div>

      {scheduledReports.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No scheduled reports</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first scheduled report to automate report generation and delivery.
            </p>
            <Button onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Schedule Report
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {scheduledReports.map((report) => (
            <Card key={report.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div>
                      <CardTitle className="text-lg">
                        {report.template?.name || `Template ${report.template_id}`}
                      </CardTitle>
                      <CardDescription className="flex items-center space-x-4 mt-1">
                        <span className="flex items-center">
                          <Clock className="h-4 w-4 mr-1" />
                          {getScheduleDescription(report)}
                        </span>
                        <span className="flex items-center">
                          <Mail className="h-4 w-4 mr-1" />
                          {report.recipients.length} recipient{report.recipients.length !== 1 ? 's' : ''}
                        </span>
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge variant={report.is_active ? "default" : "secondary"}>
                      {report.is_active ? "Active" : "Paused"}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-muted-foreground space-y-1">
                    {report.last_run && (
                      <div>
                        Last run: {formatDistanceToNow(new Date(report.last_run), { addSuffix: true })}
                      </div>
                    )}
                    {report.next_run && (
                      <div>
                        Next run: {format(new Date(report.next_run), 'MMM d, yyyy h:mm a')}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedReport(report)}
                    >
                      View Details
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditingReport(report)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggleActive(report)}
                    >
                      {report.is_active ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(report)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {showCreateForm && (
        <ScheduledReportForm
          onSuccess={handleCreateSuccess}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {editingReport && (
        <ScheduledReportForm
          scheduledReport={editingReport}
          onSuccess={handleUpdateSuccess}
          onCancel={() => setEditingReport(null)}
        />
      )}

      {selectedReport && (
        <ScheduledReportDetails
          scheduledReport={selectedReport}
          onClose={() => setSelectedReport(null)}
        />
      )}
    </div>
  );
}