import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle, XCircle, Clock, Eye, UserPlus, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from "react-i18next";
import { apiRequest } from '../lib/api';

interface OrganizationJoinRequest {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  organization_name: string;
  requested_role: string;
  message?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  created_at: string;
  reviewed_at?: string;
  reviewed_by_name?: string;
  rejection_reason?: string;
  notes?: string;
}

interface JoinRequestDetails extends OrganizationJoinRequest {
  tenant_id: number;
  reviewed_by_id?: number;
  expires_at?: string;
}

interface JoinRequestsTableProps {
  showAsCard?: boolean;
  onRequestProcessed?: () => void;
}

interface JoinRequestActionResponse {
  success: boolean;
  message: string;
}

export const JoinRequestsTable: React.FC<JoinRequestsTableProps> = ({
  showAsCard = true,
  onRequestProcessed
}) => {
  const { t } = useTranslation();
  const [requests, setRequests] = useState<OrganizationJoinRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<JoinRequestDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [approvalForm, setApprovalForm] = useState({
    status: 'approved' as 'approved' | 'rejected',
    approved_role: null as string | null,
    rejection_reason: '',
    notes: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchRequests = async () => {
    try {
      setLoading(true);
      const response = await apiRequest<OrganizationJoinRequest[]>('/organization-join/pending');
      setRequests(response);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching join requests:', err);
      setError(err.message || 'Failed to fetch join requests');
    } finally {
      setLoading(false);
    }
  };

  const fetchRequestDetails = async (requestId: number) => {
    try {
      const response = await apiRequest<JoinRequestDetails>(`/organization-join/${requestId}`);
      setSelectedRequest(response);
    } catch (err: any) {
      console.error('Error fetching request details:', err);
      toast.error('Failed to fetch request details');
    }
  };

  const handleApproval = async () => {
    if (!selectedRequest) return;

    try {
      setSubmitting(true);
      
      // Prepare the approval form data
      const formData = {
        status: approvalForm.status,
        approved_role: approvalForm.status === 'approved' ? approvalForm.approved_role : null,
        rejection_reason: approvalForm.status === 'rejected' ? approvalForm.rejection_reason : null,
        notes: approvalForm.notes || null
      };

      const response = await apiRequest<JoinRequestActionResponse>(
        `/organization-join/${selectedRequest.id}/approve`,
        {
          method: 'POST',
          body: JSON.stringify(formData),
        }
      );

      if (response.success) {
        toast.success(response.message);
        setShowApprovalDialog(false);
        setSelectedRequest(null);
        fetchRequests();
        resetApprovalForm();
        onRequestProcessed?.();
      } else {
        toast.error(response.message || 'Failed to process request');
      }
    } catch (err: any) {
      console.error('Error processing approval:', err);
      toast.error(err.message || 'Failed to process request');
    } finally {
      setSubmitting(false);
    }
  };

  const resetApprovalForm = () => {
    setApprovalForm({
      status: 'approved',
      approved_role: null,
      rejection_reason: '',
      notes: ''
    });
  };

  const openApprovalDialog = (request: JoinRequestDetails, action: 'approved' | 'rejected') => {
    setSelectedRequest(request);
    setApprovalForm({
      status: action,
      approved_role: action === 'approved' ? request.requested_role : null,
      rejection_reason: '',
      notes: ''
    });
    setShowApprovalDialog(true);
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: 'default' | 'destructive' | 'outline' | 'secondary', icon: React.ReactNode }> = {
      pending: { variant: 'outline', icon: <Clock className="w-3 h-3" /> },
      approved: { variant: 'default', icon: <CheckCircle className="w-3 h-3" /> },
      rejected: { variant: 'destructive', icon: <XCircle className="w-3 h-3" /> },
      expired: { variant: 'secondary', icon: <AlertTriangle className="w-3 h-3" /> }
    };

    const config = variants[status] || variants.pending;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1 whitespace-nowrap py-1 px-2 w-fit">
        {config.icon}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const content = (
    <>
      {error && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">{t('organizationJoinRequests.loading_requests')}</p>
        </div>
      ) : requests.length === 0 ? (
        <div className="text-center py-8">
          <UserPlus className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">{t('organizationJoinRequests.no_pending_requests')}</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('organizationJoinRequests.applicant')}</TableHead>
              <TableHead>{t('organizationJoinRequests.email')}</TableHead>
              <TableHead>{t('organizationJoinRequests.requested_role')}</TableHead>
              <TableHead>{t('organizationJoinRequests.applied')}</TableHead>
              <TableHead>{t('organizationJoinRequests.status')}</TableHead>
              <TableHead>{t('organizationJoinRequests.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {requests.map((request) => (
              <TableRow key={request.id}>
                <TableCell>
                  <div>
                    <p className="font-medium">
                      {request.first_name && request.last_name
                        ? `${request.first_name} ${request.last_name}`
                        : t('organizationJoinRequests.unknown')
                      }
                    </p>
                    {request.message && (
                      <p className="text-sm text-gray-500 truncate max-w-xs">
                        {request.message}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell>{request.email}</TableCell>
                <TableCell>
                  <Badge variant="outline">{request.requested_role}</Badge>
                </TableCell>
                <TableCell>
                  {new Date(request.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>{getStatusBadge(request.status)}</TableCell>
                <TableCell>
                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => fetchRequestDetails(request.id)}
                      className="flex items-center gap-1 border-primary text-primary hover:bg-primary hover:text-primary-foreground"
                    >
                      <Eye className="w-3 h-3" />
                      {t('organizationJoinRequests.view')}
                    </Button>

                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Request Details Modal */}
      <Dialog open={!!selectedRequest && !showApprovalDialog} onOpenChange={() => setSelectedRequest(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('organizationJoinRequests.join_request_details')}</DialogTitle>
          </DialogHeader>

          {selectedRequest && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{t('organizationJoinRequests.name')}</Label>
                  <p className="text-sm">
                    {selectedRequest.first_name && selectedRequest.last_name
                      ? `${selectedRequest.first_name} ${selectedRequest.last_name}`
                      : t('organizationJoinRequests.not_provided')
                    }
                  </p>
                </div>
                <div>
                  <Label>{t('organizationJoinRequests.email')}</Label>
                  <p className="text-sm">{selectedRequest.email}</p>
                </div>
                <div>
                  <Label>{t('organizationJoinRequests.requested_role')}</Label>
                  <Badge variant="outline">{selectedRequest.requested_role}</Badge>
                </div>
                <div>
                  <Label>{t('organizationJoinRequests.status')}</Label>
                  {getStatusBadge(selectedRequest.status)}
                </div>
                <div>
                  <Label>{t('organizationJoinRequests.applied_date')}</Label>
                  <p className="text-sm">{new Date(selectedRequest.created_at).toLocaleString()}</p>
                </div>
                {selectedRequest.expires_at && (
                  <div>
                    <Label>{t('organizationJoinRequests.expires')}</Label>
                    <p className="text-sm">{new Date(selectedRequest.expires_at).toLocaleString()}</p>
                  </div>
                )}
              </div>

              {selectedRequest.message && (
                <div>
                  <Label>{t('organizationJoinRequests.message_from_applicant')}</Label>
                  <div className="bg-gray-50 p-3 rounded-md">
                    <p className="text-sm">{selectedRequest.message}</p>
                  </div>
                </div>
              )}

              {selectedRequest.reviewed_at && (
                <div className="border-t pt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{t('organizationJoinRequests.reviewed_date')}</Label>
                      <p className="text-sm">{new Date(selectedRequest.reviewed_at).toLocaleString()}</p>
                    </div>
                    <div>
                      <Label>{t('organizationJoinRequests.reviewed_by')}</Label>
                      <p className="text-sm">{selectedRequest.reviewed_by_name || t('organizationJoinRequests.unknown')}</p>
                    </div>
                  </div>

                  {selectedRequest.rejection_reason && (
                    <div className="mt-4">
                      <Label>{t('organizationJoinRequests.rejection_reason')}</Label>
                      <div className="bg-red-50 border border-red-200 p-3 rounded-md">
                        <p className="text-sm text-red-700">{selectedRequest.rejection_reason}</p>
                      </div>
                    </div>
                  )}

                  {selectedRequest.notes && (
                    <div className="mt-4">
                      <Label>{t('organizationJoinRequests.admin_notes')}</Label>
                      <div className="bg-gray-50 p-3 rounded-md">
                        <p className="text-sm">{selectedRequest.notes}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {selectedRequest.status === 'pending' && (
                <div className="flex space-x-2 pt-4 border-t">
                  <Button
                    onClick={() => openApprovalDialog(selectedRequest, 'approved')}
                    className="flex items-center gap-2"
                  >
                    <CheckCircle className="w-4 h-4" />
                    {t('organizationJoinRequests.approve_request')}
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => openApprovalDialog(selectedRequest, 'rejected')}
                    className="flex items-center gap-2"
                  >
                    <XCircle className="w-4 h-4" />
                    {t('organizationJoinRequests.reject_request')}
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Approval/Rejection Dialog */}
      <Dialog open={showApprovalDialog} onOpenChange={setShowApprovalDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {approvalForm.status === 'approved' ? t('organizationJoinRequests.approve') : t('organizationJoinRequests.reject')} {t('organizationJoinRequests.title')}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {selectedRequest && (
              <div>
                <Label>{t('organizationJoinRequests.applicant')}</Label>
                <p className="text-sm font-medium">{selectedRequest.email}</p>
              </div>
            )}

            {approvalForm.status === 'approved' && (
              <div>
                <Label htmlFor="approved_role">{t('organizationJoinRequests.assign_role')}</Label>
                <Select
                  value={approvalForm.approved_role || ''}
                  onValueChange={(value) => setApprovalForm({ ...approvalForm, approved_role: value || null })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('organizationJoinRequests.select_role')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">{t('organizationJoinRequests.user')}</SelectItem>
                    <SelectItem value="admin">{t('organizationJoinRequests.admin')}</SelectItem>
                    <SelectItem value="viewer">{t('organizationJoinRequests.viewer')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            {approvalForm.status === 'rejected' && (
              <div>
                <Label htmlFor="rejection_reason">{t('organizationJoinRequests.reason_for_rejection')}</Label>
                <Textarea
                  id="rejection_reason"
                  value={approvalForm.rejection_reason}
                  onChange={(e) => setApprovalForm({ ...approvalForm, rejection_reason: e.target.value })}
                  placeholder={t('organizationJoinRequests.explain_rejection')}
                  rows={3}
                />
              </div>
            )}

            <div>
              <Label htmlFor="notes">{t('organizationJoinRequests.admin_notes')}</Label>
              <Textarea
                id="notes"
                value={approvalForm.notes}
                onChange={(e) => setApprovalForm({ ...approvalForm, notes: e.target.value })}
                placeholder={t('organizationJoinRequests.add_internal_notes')}
                rows={2}
              />
            </div>

            <div className="flex space-x-2 pt-4">
              <Button
                onClick={handleApproval}
                disabled={submitting}
                className={approvalForm.status === 'approved' ? '' : 'bg-red-600 hover:bg-red-700'}
              >
                {submitting ? t('organizationJoinRequests.processing') : (approvalForm.status === 'approved' ? t('organizationJoinRequests.approve') : t('organizationJoinRequests.reject'))}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowApprovalDialog(false);
                  resetApprovalForm();
                }}
                disabled={submitting}
              >
                {t('organizationJoinRequests.cancel')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );

  if (showAsCard) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5" />
            {t('organizationJoinRequests.title')} ({requests.filter(r => r.status === 'pending').length})
          </CardTitle>
        </CardHeader>
        <CardContent>{content}</CardContent>
      </Card>
    );
  }

  return <div className="space-y-6">{content}</div>;
};
