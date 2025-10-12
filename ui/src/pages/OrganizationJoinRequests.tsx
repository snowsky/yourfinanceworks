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
import { useAuth } from '@/hooks/useAuth';
import { toast } from 'sonner';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { SidebarProvider } from '@/components/ui/sidebar';
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

const OrganizationJoinRequestsContent: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [requests, setRequests] = useState<OrganizationJoinRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<JoinRequestDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [approvalForm, setApprovalForm] = useState({
    status: 'approved' as 'approved' | 'rejected',
    approved_role: '',
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

  const handleViewDetails = (request: OrganizationJoinRequest) => {
    fetchRequestDetails(request.id);
  };

  const handleApproval = async () => {
    if (!selectedRequest) return;

    try {
      setSubmitting(true);
      const response = await apiRequest(
        `/organization-join/${selectedRequest.id}/approve`,
        {
          method: 'POST',
          body: JSON.stringify(approvalForm),
        }
      );

      if (response.success) {
        toast.success(response.message);
        setShowApprovalDialog(false);
        setSelectedRequest(null);
        fetchRequests(); // Refresh the list
        resetApprovalForm();
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
      approved_role: '',
      rejection_reason: '',
      notes: ''
    });
  };

  const openApprovalDialog = (request: JoinRequestDetails, action: 'approved' | 'rejected') => {
    setSelectedRequest(request);
    setApprovalForm({
      ...approvalForm,
      status: action,
      approved_role: action === 'approved' ? request.requested_role : ''
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
      <Badge variant={config.variant} className="flex items-center gap-1">
        {config.icon}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading join requests...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Organization Join Requests</h1>
          <p className="text-gray-600">Manage requests to join your organization</p>
        </div>
      </div>

      {error && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5" />
            Pending Requests ({requests.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {requests.length === 0 ? (
            <div className="text-center py-8">
              <UserPlus className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">No pending join requests</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Applicant</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Requested Role</TableHead>
                  <TableHead>Applied</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
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
                            : 'Unknown Name'
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
                          onClick={() => handleViewDetails(request)}
                          className="flex items-center gap-1"
                        >
                          <Eye className="w-3 h-3" />
                          View
                        </Button>
                        {request.status === 'pending' && (
                          <>
                            <Button
                              size="sm"
                              onClick={() => {
                                fetchRequestDetails(request.id);
                                setTimeout(() => {
                                  if (selectedRequest) {
                                    openApprovalDialog(selectedRequest, 'approved');
                                  }
                                }, 100);
                              }}
                              className="flex items-center gap-1"
                            >
                              <CheckCircle className="w-3 h-3" />
                              Approve
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                fetchRequestDetails(request.id);
                                setTimeout(() => {
                                  if (selectedRequest) {
                                    openApprovalDialog(selectedRequest, 'rejected');
                                  }
                                }, 100);
                              }}
                              className="flex items-center gap-1"
                            >
                              <XCircle className="w-3 h-3" />
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Request Details Modal */}
      <Dialog open={!!selectedRequest && !showApprovalDialog} onOpenChange={() => setSelectedRequest(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Join Request Details</DialogTitle>
          </DialogHeader>
          
          {selectedRequest && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Name</Label>
                  <p className="text-sm">
                    {selectedRequest.first_name && selectedRequest.last_name
                      ? `${selectedRequest.first_name} ${selectedRequest.last_name}`
                      : 'Not provided'
                    }
                  </p>
                </div>
                <div>
                  <Label>Email</Label>
                  <p className="text-sm">{selectedRequest.email}</p>
                </div>
                <div>
                  <Label>Requested Role</Label>
                  <Badge variant="outline">{selectedRequest.requested_role}</Badge>
                </div>
                <div>
                  <Label>Status</Label>
                  {getStatusBadge(selectedRequest.status)}
                </div>
                <div>
                  <Label>Applied Date</Label>
                  <p className="text-sm">{new Date(selectedRequest.created_at).toLocaleString()}</p>
                </div>
                {selectedRequest.expires_at && (
                  <div>
                    <Label>Expires</Label>
                    <p className="text-sm">{new Date(selectedRequest.expires_at).toLocaleString()}</p>
                  </div>
                )}
              </div>

              {selectedRequest.message && (
                <div>
                  <Label>Message from Applicant</Label>
                  <div className="bg-gray-50 p-3 rounded-md">
                    <p className="text-sm">{selectedRequest.message}</p>
                  </div>
                </div>
              )}

              {selectedRequest.reviewed_at && (
                <div className="border-t pt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Reviewed Date</Label>
                      <p className="text-sm">{new Date(selectedRequest.reviewed_at).toLocaleString()}</p>
                    </div>
                    <div>
                      <Label>Reviewed By</Label>
                      <p className="text-sm">{selectedRequest.reviewed_by_name || 'Unknown'}</p>
                    </div>
                  </div>

                  {selectedRequest.rejection_reason && (
                    <div className="mt-4">
                      <Label>Rejection Reason</Label>
                      <div className="bg-red-50 border border-red-200 p-3 rounded-md">
                        <p className="text-sm text-red-700">{selectedRequest.rejection_reason}</p>
                      </div>
                    </div>
                  )}

                  {selectedRequest.notes && (
                    <div className="mt-4">
                      <Label>Admin Notes</Label>
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
                    Approve Request
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => openApprovalDialog(selectedRequest, 'rejected')}
                    className="flex items-center gap-2"
                  >
                    <XCircle className="w-4 h-4" />
                    Reject Request
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
              {approvalForm.status === 'approved' ? 'Approve' : 'Reject'} Join Request
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {selectedRequest && (
              <div>
                <Label>Applicant</Label>
                <p className="text-sm font-medium">{selectedRequest.email}</p>
              </div>
            )}

            {approvalForm.status === 'approved' && (
              <div>
                <Label htmlFor="approved_role">Assign Role</Label>
                <Select
                  value={approvalForm.approved_role}
                  onValueChange={(value) => setApprovalForm({...approvalForm, approved_role: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">User</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="viewer">Viewer</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            {approvalForm.status === 'rejected' && (
              <div>
                <Label htmlFor="rejection_reason">Reason for Rejection</Label>
                <Textarea
                  id="rejection_reason"
                  value={approvalForm.rejection_reason}
                  onChange={(e) => setApprovalForm({...approvalForm, rejection_reason: e.target.value})}
                  placeholder="Explain why this request is being rejected..."
                  rows={3}
                />
              </div>
            )}

            <div>
              <Label htmlFor="notes">Admin Notes (Optional)</Label>
              <Textarea
                id="notes"
                value={approvalForm.notes}
                onChange={(e) => setApprovalForm({...approvalForm, notes: e.target.value})}
                placeholder="Add any internal notes..."
                rows={2}
              />
            </div>

            <div className="flex space-x-2 pt-4">
              <Button
                onClick={handleApproval}
                disabled={submitting}
                className={approvalForm.status === 'approved' ? '' : 'bg-red-600 hover:bg-red-700'}
              >
                {submitting ? 'Processing...' : (approvalForm.status === 'approved' ? 'Approve' : 'Reject')}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowApprovalDialog(false);
                  resetApprovalForm();
                }}
                disabled={submitting}
              >
                Cancel
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const OrganizationJoinRequests: React.FC = () => {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <div className="w-64 flex-shrink-0">
          <AppSidebar />
        </div>
        <div className="flex-1">
          <OrganizationJoinRequestsContent />
        </div>
      </div>
    </SidebarProvider>
  );
};

export default OrganizationJoinRequests;
