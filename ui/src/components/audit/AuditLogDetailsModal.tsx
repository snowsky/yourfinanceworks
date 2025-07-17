import React from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Copy, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

interface AuditLogDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  auditLog: any;
}

export function AuditLogDetailsModal({ isOpen, onClose, auditLog }: AuditLogDetailsModalProps) {
  const { t } = useTranslation();

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-green-100 text-green-800';
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'CREATE':
        return '➕';
      case 'UPDATE':
        return '✏️';
      case 'DELETE':
        return '🗑️';
      case 'LOGIN':
        return '🔑';
      case 'LOGOUT':
        return '🚪';
      default:
        return '📝';
    }
  };

  if (!auditLog) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>{getActionIcon(auditLog.action)}</span>
            {t('auditLog.details.title') || 'Audit Log Details'}
          </DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-6">
            {/* Basic Information */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.user') || 'User'}
                </label>
                <p className="text-sm">{auditLog.user_email}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.action') || 'Action'}
                </label>
                <p className="text-sm">{auditLog.action}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.resource_type') || 'Resource Type'}
                </label>
                <p className="text-sm">{auditLog.resource_type}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.status') || 'Status'}
                </label>
                <Badge className={getStatusColor(auditLog.status)}>
                  {auditLog.status}
                </Badge>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.resource_id') || 'Resource ID'}
                </label>
                <p className="text-sm">{auditLog.resource_id || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.resource_name') || 'Resource Name'}
                </label>
                <p className="text-sm">{auditLog.resource_name || 'N/A'}</p>
              </div>
            </div>

            {/* Timestamp */}
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                {t('auditLog.details.timestamp') || 'Timestamp'}
              </label>
              <p className="text-sm">{new Date(auditLog.created_at).toLocaleString()}</p>
            </div>

            {/* IP Address and User Agent */}
            {(auditLog.ip_address || auditLog.user_agent) && (
              <div className="space-y-2">
                {auditLog.ip_address && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">
                      {t('auditLog.details.ip_address') || 'IP Address'}
                    </label>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-mono">{auditLog.ip_address}</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(auditLog.ip_address)}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
                {auditLog.user_agent && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">
                      {t('auditLog.details.user_agent') || 'User Agent'}
                    </label>
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-muted-foreground truncate">
                        {auditLog.user_agent}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(auditLog.user_agent)}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Error Message */}
            {auditLog.error_message && (
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.error_message') || 'Error Message'}
                </label>
                <div className="mt-1 p-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-800">{auditLog.error_message}</p>
                </div>
              </div>
            )}

            {/* Details JSON */}
            {auditLog.details && (
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  {t('auditLog.details.details') || 'Details'}
                </label>
                <div className="mt-1 p-3 bg-gray-50 border rounded-md">
                  <pre className="text-xs overflow-auto">
                    {JSON.stringify(auditLog.details, null, 2)}
                  </pre>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2"
                    onClick={() => copyToClipboard(JSON.stringify(auditLog.details, null, 2))}
                  >
                    <Copy className="h-3 w-3 mr-1" />
                    {t('auditLog.details.copy_json') || 'Copy JSON'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
} 