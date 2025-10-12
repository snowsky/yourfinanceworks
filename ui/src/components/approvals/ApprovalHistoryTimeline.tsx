import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { approvalApi } from '@/lib/api';
import { ApprovalHistoryEntry } from '@/types';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  Send,
  UserCheck,
  History
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow, format } from 'date-fns';

interface ApprovalHistoryTimelineProps {
  expenseId: number;
}

export function ApprovalHistoryTimeline({ expenseId }: ApprovalHistoryTimelineProps) {
  const [history, setHistory] = useState<ApprovalHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const data = await approvalApi.getApprovalHistory(expenseId);
        setHistory(data.history);
      } catch (error) {
        console.error('Failed to fetch approval history:', error);
        toast.error('Failed to load approval history');
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [expenseId]);

  const getActionIcon = (action: string, status: string) => {
    switch (action) {
      case 'submitted':
        return <Send className="h-4 w-4 text-blue-500" />;
      case 'approved':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'rejected':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'delegated':
        return <UserCheck className="h-4 w-4 text-purple-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getActionColor = (action: string, status: string) => {
    switch (action) {
      case 'submitted':
        return 'bg-blue-100 text-blue-800';
      case 'approved':
        return 'bg-green-100 text-green-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      case 'delegated':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getActionText = (entry: ApprovalHistoryEntry) => {
    switch (entry.action) {
      case 'submitted':
        return 'Submitted for approval';
      case 'approved':
        return 'Approved';
      case 'rejected':
        return 'Rejected';
      case 'delegated':
        return 'Delegated approval';
      default:
        return entry.action;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Approval History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (history.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Approval History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No approval history available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Approval History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />
          
          <div className="space-y-6">
            {history.map((entry, index) => (
              <div key={entry.id} className="relative flex gap-4">
                {/* Timeline dot */}
                <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-background border-2 border-border">
                  {getActionIcon(entry.action, entry.status)}
                </div>
                
                {/* Content */}
                <div className="flex-1 min-w-0 pb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className={getActionColor(entry.action, entry.status)}>
                      {getActionText(entry)}
                    </Badge>
                    
                    {entry.approval_level && (
                      <Badge variant="outline">
                        Level {entry.approval_level}
                      </Badge>
                    )}
                  </div>
                  
                  <div className="text-sm space-y-1">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <span>
                        {entry.approver?.name || 'System'}
                      </span>
                      <span>•</span>
                      <span>
                        {format(new Date(entry.timestamp), 'MMM d, yyyy h:mm a')}
                      </span>
                      <span>•</span>
                      <span>
                        {formatDistanceToNow(new Date(entry.timestamp))} ago
                      </span>
                    </div>
                    
                    {entry.rejection_reason && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-800 text-sm">
                        <strong>Reason:</strong> {entry.rejection_reason}
                      </div>
                    )}
                    
                    {entry.notes && (
                      <div className="mt-2 p-2 bg-muted rounded text-sm">
                        <strong>Notes:</strong> {entry.notes}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}