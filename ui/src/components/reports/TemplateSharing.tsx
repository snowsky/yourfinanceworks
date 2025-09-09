import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { 
  Share2, 
  Users, 
  Lock, 
  Globe,
  Shield,
  Info
} from 'lucide-react';
import { reportApi, ReportTemplate } from '@/lib/api';

interface TemplateSharingProps {
  template: ReportTemplate;
  trigger?: React.ReactNode;
}

export const TemplateSharing: React.FC<TemplateSharingProps> = ({
  template,
  trigger,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isShared, setIsShared] = useState(template.is_shared);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingSharedState, setPendingSharedState] = useState<boolean | null>(null);
  
  const queryClient = useQueryClient();

  // Update sharing mutation
  const updateSharingMutation = useMutation({
    mutationFn: (shared: boolean) => 
      reportApi.updateTemplate(template.id, { is_shared: shared }),
    onSuccess: (updatedTemplate) => {
      setIsShared(updatedTemplate.is_shared);
      queryClient.invalidateQueries({ queryKey: ['reportTemplates'] });
      toast.success(
        updatedTemplate.is_shared 
          ? 'Template is now shared with your organization' 
          : 'Template is now private'
      );
      setShowConfirmDialog(false);
      setPendingSharedState(null);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update sharing settings');
      setShowConfirmDialog(false);
      setPendingSharedState(null);
    },
  });

  const handleSharingToggle = (checked: boolean) => {
    if (checked !== isShared) {
      setPendingSharedState(checked);
      setShowConfirmDialog(true);
    }
  };

  const confirmSharingChange = () => {
    if (pendingSharedState !== null) {
      updateSharingMutation.mutate(pendingSharedState);
    }
  };

  const cancelSharingChange = () => {
    setShowConfirmDialog(false);
    setPendingSharedState(null);
  };

  const defaultTrigger = (
    <Button variant="outline" size="sm">
      <Share2 className="mr-2 h-4 w-4" />
      Sharing
    </Button>
  );

  return (
    <>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          {trigger || defaultTrigger}
        </DialogTrigger>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Share2 className="h-5 w-5" />
              Template Sharing
            </DialogTitle>
            <DialogDescription>
              Manage who can access and use this template
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Current Status */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {isShared ? (
                      <>
                        <Users className="h-4 w-4 text-green-600" />
                        <span className="font-medium">Shared</span>
                      </>
                    ) : (
                      <>
                        <Lock className="h-4 w-4 text-gray-600" />
                        <span className="font-medium">Private</span>
                      </>
                    )}
                  </div>
                  <Badge variant={isShared ? "default" : "secondary"}>
                    {isShared ? "Organization" : "Personal"}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {isShared 
                    ? "All users in your organization can view and use this template"
                    : "Only you can view and use this template"
                  }
                </p>
              </CardContent>
            </Card>

            {/* Sharing Toggle */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Sharing Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Label htmlFor="share-toggle">Share with organization</Label>
                    <p className="text-sm text-muted-foreground">
                      Allow other users to view and use this template
                    </p>
                  </div>
                  <Switch
                    id="share-toggle"
                    checked={isShared}
                    onCheckedChange={handleSharingToggle}
                    disabled={updateSharingMutation.isPending}
                  />
                </div>

                <Separator />

                {/* Sharing Information */}
                <div className="space-y-3">
                  <div className="flex items-start gap-2">
                    <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    <div className="text-sm space-y-1">
                      <p className="font-medium">What happens when you share:</p>
                      <ul className="text-muted-foreground space-y-1 ml-2">
                        <li>• Other users can view the template</li>
                        <li>• They can generate reports using this template</li>
                        <li>• They can duplicate the template to create their own version</li>
                        <li>• Only you can edit or delete the original template</li>
                      </ul>
                    </div>
                  </div>

                  <div className="flex items-start gap-2">
                    <Shield className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium">Privacy & Security:</p>
                      <p className="text-muted-foreground">
                        Shared templates respect user permissions. Users can only see data they have access to.
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Template Details */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Template Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Name:</span>
                    <span className="font-medium">{template.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Type:</span>
                    <span className="font-medium">
                      {template.report_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Created:</span>
                    <span className="font-medium">
                      {new Date(template.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Filters:</span>
                    <span className="font-medium">
                      {Object.keys(template.filters).length} active
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-end">
            <Button onClick={() => setIsOpen(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Confirmation Dialog */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingSharedState ? 'Share Template' : 'Make Template Private'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingSharedState ? (
                <>
                  Are you sure you want to share "{template.name}" with your organization? 
                  All users will be able to view and use this template.
                </>
              ) : (
                <>
                  Are you sure you want to make "{template.name}" private? 
                  Other users will no longer be able to access this template.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={cancelSharingChange}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction 
              onClick={confirmSharingChange}
              disabled={updateSharingMutation.isPending}
            >
              {updateSharingMutation.isPending ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Updating...
                </>
              ) : (
                pendingSharedState ? 'Share Template' : 'Make Private'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};