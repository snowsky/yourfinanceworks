import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '@/components/ui/select';
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { 
  Share2, 
  Copy, 
  Eye, 
  EyeOff, 
  Calendar, 
  Users, 
  Link as LinkIcon,
  Trash2,
  Plus,
  Clock,
  Shield
} from 'lucide-react';
import { ReportHistory as ReportHistoryType } from '@/lib/api';
import { toast } from 'sonner';
import { format, addDays, addWeeks, addMonths } from 'date-fns';

interface ReportSharingProps {
  report: ReportHistoryType;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ShareLink {
  id: string;
  url: string;
  expiresAt: Date | null;
  accessCount: number;
  maxAccess: number | null;
  isActive: boolean;
  createdAt: Date;
  allowDownload: boolean;
  requireAuth: boolean;
}

interface ShareSettings {
  expirationDays: number;
  maxAccess: number | null;
  allowDownload: boolean;
  requireAuth: boolean;
  password: string;
}

const EXPIRATION_OPTIONS = [
  { label: '1 Day', value: 1 },
  { label: '3 Days', value: 3 },
  { label: '1 Week', value: 7 },
  { label: '2 Weeks', value: 14 },
  { label: '1 Month', value: 30 },
  { label: 'Never', value: 0 }
];

export function ReportSharing({ report, open, onOpenChange }: ReportSharingProps) {
  const [shareLinks, setShareLinks] = useState<ShareLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  
  const [shareSettings, setShareSettings] = useState<ShareSettings>({
    expirationDays: 7,
    maxAccess: null,
    allowDownload: true,
    requireAuth: false,
    password: ''
  });

  // Mock data for demonstration
  useEffect(() => {
    if (open) {
      // In a real implementation, this would fetch existing share links
      setShareLinks([
        {
          id: '1',
          url: `${window.location.origin}/shared/reports/${report.id}/abc123`,
          expiresAt: addWeeks(new Date(), 1),
          accessCount: 5,
          maxAccess: null,
          isActive: true,
          createdAt: new Date(),
          allowDownload: true,
          requireAuth: false
        }
      ]);
    }
  }, [open, report.id]);

  const handleCreateShareLink = async () => {
    try {
      setCreating(true);
      
      // Generate a unique share ID (in real implementation, this would be done server-side)
      const shareId = Math.random().toString(36).substring(2, 15);
      const shareUrl = `${window.location.origin}/shared/reports/${report.id}/${shareId}`;
      
      const newLink: ShareLink = {
        id: shareId,
        url: shareUrl,
        expiresAt: shareSettings.expirationDays > 0 ? addDays(new Date(), shareSettings.expirationDays) : null,
        accessCount: 0,
        maxAccess: shareSettings.maxAccess,
        isActive: true,
        createdAt: new Date(),
        allowDownload: shareSettings.allowDownload,
        requireAuth: shareSettings.requireAuth
      };
      
      setShareLinks(prev => [newLink, ...prev]);
      
      // Copy to clipboard
      await navigator.clipboard.writeText(shareUrl);
      toast.success('Share link created and copied to clipboard');
      
      // Reset settings
      setShareSettings({
        expirationDays: 7,
        maxAccess: null,
        allowDownload: true,
        requireAuth: false,
        password: ''
      });
      
    } catch (error) {
      console.error('Failed to create share link:', error);
      toast.error('Failed to create share link');
    } finally {
      setCreating(false);
    }
  };

  const handleCopyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Link copied to clipboard');
    } catch (error) {
      toast.error('Failed to copy link');
    }
  };

  const handleToggleLink = async (linkId: string) => {
    setShareLinks(prev => prev.map(link => 
      link.id === linkId 
        ? { ...link, isActive: !link.isActive }
        : link
    ));
    toast.success('Share link updated');
  };

  const handleDeleteLink = async (linkId: string) => {
    setShareLinks(prev => prev.filter(link => link.id !== linkId));
    toast.success('Share link deleted');
  };

  const getExpirationStatus = (link: ShareLink) => {
    if (!link.expiresAt) return { status: 'never', color: 'bg-gray-100 text-gray-800' };
    
    const now = new Date();
    const timeLeft = link.expiresAt.getTime() - now.getTime();
    const daysLeft = Math.ceil(timeLeft / (1000 * 60 * 60 * 24));
    
    if (timeLeft <= 0) return { status: 'expired', color: 'bg-red-100 text-red-800' };
    if (daysLeft <= 1) return { status: `${Math.ceil(timeLeft / (1000 * 60 * 60))}h left`, color: 'bg-orange-100 text-orange-800' };
    if (daysLeft <= 7) return { status: `${daysLeft}d left`, color: 'bg-yellow-100 text-yellow-800' };
    
    return { status: `${daysLeft}d left`, color: 'bg-green-100 text-green-800' };
  };

  const getAccessStatus = (link: ShareLink) => {
    if (!link.maxAccess) return 'Unlimited';
    return `${link.accessCount}/${link.maxAccess}`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Share2 className="h-5 w-5" />
            Share Report
          </DialogTitle>
          <DialogDescription>
            Create secure links to share this report with others. You can control access permissions and expiration.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Report Info */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">{report.report_type.charAt(0).toUpperCase() + report.report_type.slice(1)} Report</h3>
                  <p className="text-sm text-gray-500">
                    Generated on {format(new Date(report.generated_at), 'MMM dd, yyyy HH:mm')}
                  </p>
                </div>
                <Badge variant="outline">
                  {(report.parameters.export_format || 'pdf').toUpperCase()}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Create New Share Link */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Create Share Link</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Expiration</Label>
                  <Select
                    value={shareSettings.expirationDays.toString()}
                    onValueChange={(value) => setShareSettings(prev => ({ 
                      ...prev, 
                      expirationDays: parseInt(value) 
                    }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {EXPIRATION_OPTIONS.map(option => (
                        <SelectItem key={option.value} value={option.value.toString()}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Max Access Count</Label>
                  <Input
                    type="number"
                    placeholder="Unlimited"
                    value={shareSettings.maxAccess || ''}
                    onChange={(e) => setShareSettings(prev => ({ 
                      ...prev, 
                      maxAccess: e.target.value ? parseInt(e.target.value) : null 
                    }))}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Allow Download</Label>
                    <p className="text-sm text-gray-500">
                      Allow users to download the report file
                    </p>
                  </div>
                  <Switch
                    checked={shareSettings.allowDownload}
                    onCheckedChange={(checked) => setShareSettings(prev => ({ 
                      ...prev, 
                      allowDownload: checked 
                    }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Require Authentication</Label>
                    <p className="text-sm text-gray-500">
                      Users must be logged in to access the report
                    </p>
                  </div>
                  <Switch
                    checked={shareSettings.requireAuth}
                    onCheckedChange={(checked) => setShareSettings(prev => ({ 
                      ...prev, 
                      requireAuth: checked 
                    }))}
                  />
                </div>
              </div>

              <Button 
                onClick={handleCreateShareLink} 
                disabled={creating}
                className="w-full"
              >
                <Plus className="h-4 w-4 mr-2" />
                {creating ? 'Creating...' : 'Create Share Link'}
              </Button>
            </CardContent>
          </Card>

          {/* Existing Share Links */}
          {shareLinks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Active Share Links</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Link</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Expiration</TableHead>
                      <TableHead>Access</TableHead>
                      <TableHead>Permissions</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shareLinks.map((link) => {
                      const expiration = getExpirationStatus(link);
                      return (
                        <TableRow key={link.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <LinkIcon className="h-4 w-4 text-gray-400" />
                              <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                                ...{link.id}
                              </code>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge className={link.isActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}>
                              {link.isActive ? 'Active' : 'Disabled'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={expiration.color}>
                              {expiration.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Users className="h-4 w-4 text-gray-400" />
                              {getAccessStatus(link)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {link.allowDownload && (
                                <Badge variant="outline" className="text-xs">
                                  Download
                                </Badge>
                              )}
                              {link.requireAuth && (
                                <Badge variant="outline" className="text-xs">
                                  <Shield className="h-3 w-3 mr-1" />
                                  Auth
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleCopyLink(link.url)}
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleToggleLink(link.id)}
                              >
                                {link.isActive ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteLink(link.id)}
                                className="text-red-600 hover:text-red-700"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}