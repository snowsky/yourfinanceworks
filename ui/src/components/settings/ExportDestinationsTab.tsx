import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { FeatureGate } from '@/components/FeatureGate';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader
} from '@/components/ui/professional-card';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalTextarea } from '@/components/ui/professional-textarea'; // Ensure this exists or use Textarea with class
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Plus, Edit, Trash2, CheckCircle, XCircle, AlertCircle, Eye, EyeOff, Globe, Database, Folder, HardDrive, Cloud, Shield, ExternalLink } from 'lucide-react';
import { exportDestinationApi, ExportDestination, ExportDestinationCreate, ExportDestinationUpdate } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';
import { Switch } from '@/components/ui/switch';

interface ExportDestinationsTabProps {
  isAdmin: boolean;
}

export const ExportDestinationsTab: React.FC<ExportDestinationsTabProps> = ({ isAdmin }) => {
  return (
    <FeatureGate
      feature="advanced_export"
      fallback={
        <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
          <ProfessionalCardContent className="p-12 text-center">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
              <ExternalLink className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">Business License Required</h3>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
              Export destinations allow you to automatically send invoices and data to external storage services and cloud platforms.
              Upgrade to a business license to configure automated exports and streamline your data management workflow.
            </p>
            <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
              <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                With Business License, you get:
              </h4>
              <ul className="text-left space-y-3 text-sm text-foreground/80">
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Connect to AWS S3, Azure Blob, and Google Cloud Storage</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Automated batch export and scheduled transfers</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Secure credential management and connection testing</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>Integration with Google Drive and local file systems</span>
                </li>
              </ul>
            </div>
            <div className="flex justify-center gap-4">
              <ProfessionalButton
                variant="gradient"
                onClick={() => window.location.href = '/settings?tab=license'}
                size="lg"
              >
                Activate Business License
              </ProfessionalButton>
              <ProfessionalButton
                variant="outline"
                onClick={() => window.open('https://docs.example.com/export-destinations', '_blank')}
                size="lg"
              >
                Learn More
              </ProfessionalButton>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      }
    >
      <ExportDestinationsContent isAdmin={isAdmin} />
    </FeatureGate>
  );
};

const ExportDestinationsContent: React.FC<ExportDestinationsTabProps> = ({ isAdmin }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showDialog, setShowDialog] = useState(false);
  const [editingDestination, setEditingDestination] = useState<ExportDestination | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState<ExportDestinationCreate>({
    name: '',
    destination_type: 's3',
    credentials: {},
    config: {},
    is_default: false,
  });

  // Credential form states for different providers
  const [s3Credentials, setS3Credentials] = useState({
    access_key_id: '',
    secret_access_key: '',
    region: 'us-east-1',
    bucket_name: '',
    path_prefix: '',
  });

  const [azureCredentials, setAzureCredentials] = useState({
    auth_type: 'connection_string' as 'connection_string' | 'account_key',
    connection_string: '',
    account_name: '',
    account_key: '',
    container_name: '',
    path_prefix: '',
  });

  const [gcsCredentials, setGcsCredentials] = useState({
    auth_type: 'service_account' as 'service_account' | 'project_id',
    service_account_json: '',
    project_id: '',
    credentials: '',
    bucket_name: '',
    path_prefix: '',
  });

  const [googleDriveCredentials, setGoogleDriveCredentials] = useState({
    oauth_token: '',
    refresh_token: '',
    folder_id: '',
  });

  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});

  // Queries
  const { data: destinationsData, isLoading: loading } = useQuery<ExportDestination[]>({
    queryKey: ['export-destinations'],
    queryFn: async () => {
      const data = await exportDestinationApi.getDestinations();
      return Array.isArray(data) ? data : (data as any).destinations || [];
    },
    enabled: isAdmin,
  });

  const destinations = destinationsData || [];

  // Mutations
  const saveMutation = useMutation({
    mutationFn: async (vars: { id?: number, data: ExportDestinationCreate | ExportDestinationUpdate }) => {
      if (vars.id) {
        return exportDestinationApi.updateDestination(vars.id, vars.data as ExportDestinationUpdate);
      } else {
        return exportDestinationApi.createDestination(vars.data as ExportDestinationCreate);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['export-destinations'] });
      toast.success(editingDestination ? t('settings.export_destination_updated') : t('settings.export_destination_created'));
      setShowDialog(false);
    },
    onError: (error) => {
      console.error('Failed to save export destination:', error);
      toast.error(getErrorMessage(error, t));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => exportDestinationApi.deleteDestination(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['export-destinations'] });
      toast.success(t('settings.export_destination_deleted'));
    },
    onError: (error) => {
      console.error('Failed to delete export destination:', error);
      toast.error(getErrorMessage(error, t));
    }
  });

  const testConnectionMutation = useMutation({
    mutationFn: (id: number) => exportDestinationApi.testConnection(id),
    onSuccess: (result) => {
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
      queryClient.invalidateQueries({ queryKey: ['export-destinations'] });
    },
    onSettled: () => {
      setTestingId(null);
    },
    onError: (error) => {
      console.error('Failed to test connection:', error);
      toast.error(getErrorMessage(error, t));
    }
  });

  const handleCreate = () => {
    setEditingDestination(null);
    setFormData({
      name: '',
      destination_type: 's3',
      credentials: {},
      config: {},
      is_default: false,
    });
    resetCredentialForms();
    setShowDialog(true);
  };

  const handleEdit = (destination: ExportDestination) => {
    setEditingDestination(destination);
    setFormData({
      name: destination.name,
      destination_type: destination.destination_type,
      credentials: {},
      config: destination.config || {},
      is_default: destination.is_default,
    });

    // Populate form fields with masked credentials
    if (destination.masked_credentials) {
      const masked = destination.masked_credentials;

      if (destination.destination_type === 's3') {
        setS3Credentials({
          access_key_id: masked.access_key_id || '',
          secret_access_key: masked.secret_access_key || '',
          region: masked.region || 'us-east-1',
          bucket_name: masked.bucket_name || '',
          path_prefix: masked.path_prefix || '',
        });
      } else if (destination.destination_type === 'azure') {
        setAzureCredentials({
          auth_type: masked.connection_string ? 'connection_string' : 'account_key',
          connection_string: masked.connection_string || '',
          account_name: masked.account_name || '',
          account_key: masked.account_key || '',
          container_name: masked.container_name || '',
          path_prefix: masked.path_prefix || '',
        });
      } else if (destination.destination_type === 'gcs') {
        setGcsCredentials({
          auth_type: masked.service_account_json ? 'service_account' : 'project_id',
          service_account_json: masked.service_account_json || '',
          project_id: masked.project_id || '',
          credentials: masked.credentials || '',
          bucket_name: masked.bucket_name || '',
          path_prefix: masked.path_prefix || '',
        });
      } else if (destination.destination_type === 'google_drive') {
        setGoogleDriveCredentials({
          oauth_token: masked.oauth_token || '',
          refresh_token: masked.refresh_token || '',
          folder_id: masked.folder_id || '',
        });
      }
    } else {
      resetCredentialForms();
    }

    setShowDialog(true);
  };

  const resetCredentialForms = () => {
    setS3Credentials({
      access_key_id: '',
      secret_access_key: '',
      region: 'us-east-1',
      bucket_name: '',
      path_prefix: '',
    });
    setAzureCredentials({
      auth_type: 'connection_string',
      connection_string: '',
      account_name: '',
      account_key: '',
      container_name: '',
      path_prefix: '',
    });
    setGcsCredentials({
      auth_type: 'service_account',
      service_account_json: '',
      project_id: '',
      credentials: '',
      bucket_name: '',
      path_prefix: '',
    });
    setGoogleDriveCredentials({
      oauth_token: '',
      refresh_token: '',
      folder_id: '',
    });
  };

  const handleSave = async () => {
    if (!isAdmin) return;

    // Build credentials based on destination type
    let credentials: Record<string, any> = {};

    switch (formData.destination_type) {
      case 's3':
        credentials = {
          access_key_id: s3Credentials.access_key_id.trim(),
          secret_access_key: s3Credentials.secret_access_key.trim(),
          region: s3Credentials.region.trim(),
          bucket_name: s3Credentials.bucket_name.trim(),
          path_prefix: s3Credentials.path_prefix?.trim() || undefined,
        };
        break;
      case 'azure':
        if (azureCredentials.auth_type === 'connection_string') {
          credentials = {
            connection_string: azureCredentials.connection_string.trim(),
            container_name: azureCredentials.container_name.trim(),
            path_prefix: azureCredentials.path_prefix?.trim() || undefined,
          };
        } else {
          credentials = {
            account_name: azureCredentials.account_name.trim(),
            account_key: azureCredentials.account_key.trim(),
            container_name: azureCredentials.container_name.trim(),
            path_prefix: azureCredentials.path_prefix?.trim() || undefined,
          };
        }
        break;
      case 'gcs':
        if (gcsCredentials.auth_type === 'service_account') {
          credentials = {
            service_account_json: gcsCredentials.service_account_json.trim(),
            bucket_name: gcsCredentials.bucket_name.trim(),
            path_prefix: gcsCredentials.path_prefix?.trim() || undefined,
          };
        } else {
          credentials = {
            project_id: gcsCredentials.project_id.trim(),
            credentials: gcsCredentials.credentials.trim(),
            bucket_name: gcsCredentials.bucket_name.trim(),
            path_prefix: gcsCredentials.path_prefix?.trim() || undefined,
          };
        }
        break;
      case 'google_drive':
        credentials = {
          oauth_token: googleDriveCredentials.oauth_token.trim(),
          refresh_token: googleDriveCredentials.refresh_token?.trim() || undefined,
          folder_id: googleDriveCredentials.folder_id.trim(),
        };
        break;
      case 'local':
        // Local might not need credentials or handled differently
        break;
    }

    if (editingDestination) {
      const updateData: ExportDestinationUpdate = {
        name: formData.name,
        config: formData.config,
        is_default: formData.is_default,
      };
      if (Object.values(credentials).some(v => v)) {
        updateData.credentials = credentials;
      }
      saveMutation.mutate({ id: editingDestination.id, data: updateData });
    } else {
      saveMutation.mutate({ data: { ...formData, credentials } });
    }
  };

  const handleDelete = (id: number) => {
    if (!isAdmin) return;
    if (!confirm(t('settings.confirm_delete_export_destination'))) return;
    deleteMutation.mutate(id);
  };

  const handleTestConnection = (id: number) => {
    if (!isAdmin) return;
    setTestingId(id);
    testConnectionMutation.mutate(id);
  };

  const getDestinationTypeLabel = (type: string) => {
    switch (type) {
      case 's3': return 'AWS S3';
      case 'azure': return 'Azure Blob Storage';
      case 'gcs': return 'Google Cloud Storage';
      case 'google_drive': return 'Google Drive';
      case 'local': return 'Local File System';
      default: return type;
    }
  };

  const getDestinationIcon = (type: string) => {
    switch (type) {
      case 's3': return <Cloud className="h-5 w-5 text-orange-500" />;
      case 'azure': return <Database className="h-5 w-5 text-blue-500" />;
      case 'gcs': return <Globe className="h-5 w-5 text-green-500" />;
      case 'google_drive': return <HardDrive className="h-5 w-5 text-yellow-500" />;
      case 'local': return <Folder className="h-5 w-5 text-gray-500" />;
      default: return <Database className="h-5 w-5" />;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
    {/* Gradient Banner */}
    <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
          <ExternalLink className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{t('settings.export_destinations', 'Export Destinations')}</h2>
          <p className="text-muted-foreground mt-0.5">{t('settings.export_destinations_banner_description', 'Configure cloud storage destinations for exports')}</p>
        </div>
      </div>
    </div>

    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t('settings.export_destinations_description')}
          </p>
          <ProfessionalButton onClick={handleCreate} size="sm" variant="gradient">
            <Plus className="h-4 w-4 mr-2" />
            {t('settings.add_destination')}
          </ProfessionalButton>
        </div>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-6">
        {/* Destinations list */}
        {destinations.length > 0 ? (
          <div className="grid gap-4">
            {destinations.map((destination) => (
              <div key={destination.id} className="flex flex-col md:flex-row items-start md:items-center justify-between p-5 border border-border/50 rounded-xl bg-card/50 hover:bg-card hover:shadow-md transition-all duration-200 gap-4">
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-muted/30 rounded-lg">
                      {getDestinationIcon(destination.destination_type)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold text-base">{destination.name}</h4>
                        {destination.is_default && (
                          <Badge variant="outline" className="bg-primary/5 border-primary/20 text-primary text-[10px] uppercase tracking-wider">
                            {t('settings.default')}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground mt-0.5">
                        <span className="font-medium">{getDestinationTypeLabel(destination.destination_type)}</span>
                        {destination.last_test_at && (
                          <>
                            <span className="text-muted-foreground/30">•</span>
                            <span>{new Date(destination.last_test_at).toLocaleDateString()}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 pl-[52px]">
                    <Badge variant={destination.is_active ? 'default' : 'secondary'} className={destination.is_active ? "bg-green-100 text-green-700 hover:bg-green-200 border-transparent shadow-none" : ""}>
                      {destination.is_active ? t('settings.active') : t('settings.inactive')}
                    </Badge>

                    {destination.last_test_success !== null && (
                      <div className={`flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${destination.last_test_success
                        ? 'bg-green-50 text-green-700'
                        : 'bg-red-50 text-red-700'
                        }`}>
                        {destination.last_test_success ? (
                          <CheckCircle className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        {destination.last_test_success ? t('settings.test_passed') : t('settings.test_failed')}
                      </div>
                    )}
                  </div>

                  {destination.last_test_error && (
                    <div className="ml-[52px] mt-2 p-2 bg-red-50 border border-red-100 rounded-md text-xs text-red-700">
                      <span className="font-medium">{t('settings.error')}:</span> {destination.last_test_error}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 w-full md:w-auto pl-[52px] md:pl-0">
                  {destination.testable && (
                    <ProfessionalButton
                      variant="outline"
                      size="sm"
                      onClick={() => handleTestConnection(destination.id)}
                      disabled={testingId === destination.id}
                      className="flex-1 md:flex-none"
                    >
                      {testingId === destination.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        t('settings.test')
                      )}
                    </ProfessionalButton>
                  )}
                  <ProfessionalButton
                    variant="ghost"
                    size="icon"
                    onClick={() => handleEdit(destination)}
                    className="shrink-0"
                  >
                    <Edit className="h-4 w-4 text-muted-foreground" />
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(destination.id)}
                    className="shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </ProfessionalButton>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Empty state hero */}
            <div className="rounded-2xl border-2 border-dashed border-border/50 bg-muted/20 px-8 py-12 flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
                <ExternalLink className="w-8 h-8 text-primary/60" />
              </div>
              <h3 className="text-xl font-semibold mb-2">{t('settings.no_export_destinations_configured')}</h3>
              <p className="text-sm text-muted-foreground mb-6 max-w-sm leading-relaxed">
                {t('settings.add_destination_to_get_started')}
              </p>
              <ProfessionalButton onClick={handleCreate} variant="gradient" size="lg">
                <Plus className="h-4 w-4 mr-2" />
                {t('settings.add_destination')}
              </ProfessionalButton>

              {/* Supported provider tiles */}
              <div className="mt-10 w-full max-w-md">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/60 mb-4">
                  Supported Destinations
                </p>
                <div className="grid grid-cols-5 gap-3">
                  {[
                    { icon: <Cloud className="w-5 h-5 text-orange-500" />, label: 'AWS S3', bg: 'bg-orange-50 border-orange-200/60' },
                    { icon: <Database className="w-5 h-5 text-blue-500" />, label: 'Azure', bg: 'bg-blue-50 border-blue-200/60' },
                    { icon: <Globe className="w-5 h-5 text-green-500" />, label: 'GCS', bg: 'bg-green-50 border-green-200/60' },
                    { icon: <HardDrive className="w-5 h-5 text-yellow-500" />, label: 'Drive', bg: 'bg-yellow-50 border-yellow-200/60' },
                    { icon: <Folder className="w-5 h-5 text-gray-500" />, label: 'Local', bg: 'bg-gray-50 border-gray-200/60' },
                  ].map(({ icon, label, bg }) => (
                    <div key={label} className={`flex flex-col items-center gap-2 p-3 rounded-xl border ${bg}`}>
                      {icon}
                      <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Env vars info */}
            <div className="flex gap-3 p-4 rounded-xl bg-blue-50/60 border border-blue-200/50">
              <AlertCircle className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
              <div className="space-y-1 text-sm">
                <p className="font-medium text-blue-900">{t('settings.no_destinations_configured')}</p>
                <p className="text-blue-700">{t('settings.environment_variables_will_be_used')}</p>
                <p className="text-blue-700 font-medium mt-2">{t('settings.supported_env_vars')}:</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 mt-1">
                  {['AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY', 'AZURE_STORAGE_CONNECTION_STRING', 'GOOGLE_APPLICATION_CREDENTIALS'].map(v => (
                    <code key={v} className="text-xs bg-blue-100/80 text-blue-800 px-2 py-1 rounded font-mono leading-tight">{v}</code>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </ProfessionalCardContent>

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingDestination
                ? t('settings.edit_export_destination')
                : t('settings.add_export_destination')}
            </DialogTitle>
            <DialogDescription>
              {t('settings.configure_export_destination_description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Name */}
            <ProfessionalInput
              id="destination-name"
              label={t('settings.destination_name')}
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder={t('settings.destination_name_placeholder')}
            />

            {/* Destination Type */}
            <div className="space-y-2">
              <Label htmlFor="destination-type">{t('settings.destination_type')}</Label>
              <Select
                value={formData.destination_type}
                onValueChange={(value: any) => setFormData({ ...formData, destination_type: value })}
                disabled={!!editingDestination}
              >
                <SelectTrigger className="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="s3">AWS S3</SelectItem>
                  <SelectItem value="azure">Azure Blob Storage</SelectItem>
                  <SelectItem value="gcs">Google Cloud Storage</SelectItem>
                  <SelectItem value="google_drive">Google Drive</SelectItem>
                  <SelectItem value="local">Local File System</SelectItem>
                </SelectContent>
              </Select>
              {editingDestination && (
                <p className="text-sm text-muted-foreground">
                  {t('settings.destination_type_cannot_be_changed')}
                </p>
              )}
            </div>

            {/* S3 Credentials */}
            {formData.destination_type === 's3' && (
              <div className="space-y-4 p-5 border border-border/50 rounded-xl bg-muted/20">
                <h4 className="font-medium flex items-center gap-2">
                  <Cloud className="h-4 w-4" />
                  AWS S3 {t('settings.credentials')}
                </h4>
                {editingDestination && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 flex items-center gap-2">
                    <EyeOff className="h-4 w-4" />
                    <p>{t('settings.secret_fields_are_masked')}</p>
                  </div>
                )}
                <div className="space-y-4">
                  <ProfessionalInput
                    id="s3-access-key"
                    label={`${t('settings.access_key_id')} (optional)`}
                    value={s3Credentials.access_key_id}
                    onChange={(e) => setS3Credentials({ ...s3Credentials, access_key_id: e.target.value })}
                    placeholder="Leave empty to use AWS_S3_ACCESS_KEY_ID"
                  />

                  <div>
                    <Label htmlFor="s3-secret-key" className="mb-2 block">{t('settings.secret_access_key')} <span className="text-muted-foreground text-xs">(optional)</span></Label>
                    <div className="relative">
                      <ProfessionalInput
                        id="s3-secret-key"
                        type={showPassword['s3-secret'] ? 'text' : 'password'}
                        value={s3Credentials.secret_access_key}
                        onChange={(e) => setS3Credentials({ ...s3Credentials, secret_access_key: e.target.value })}
                        placeholder="Leave empty to use AWS_S3_SECRET_ACCESS_KEY"
                        rightIcon={
                          <button
                            type="button"
                            onClick={() => setShowPassword({ ...showPassword, 's3-secret': !showPassword['s3-secret'] })}
                            className="text-muted-foreground hover:text-foreground transition-colors outline-none"
                          >
                            {showPassword['s3-secret'] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        }
                      />
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="s3-region" className="mb-2 block">{t('settings.region')}</Label>
                    <Select
                      value={s3Credentials.region}
                      onValueChange={(value) => setS3Credentials({ ...s3Credentials, region: value })}
                    >
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="us-east-1">US East (N. Virginia)</SelectItem>
                        <SelectItem value="us-east-2">US East (Ohio)</SelectItem>
                        <SelectItem value="us-west-1">US West (N. California)</SelectItem>
                        <SelectItem value="us-west-2">US West (Oregon)</SelectItem>
                        <SelectItem value="eu-west-1">EU (Ireland)</SelectItem>
                        <SelectItem value="eu-central-1">EU (Frankfurt)</SelectItem>
                        <SelectItem value="ap-southeast-1">Asia Pacific (Singapore)</SelectItem>
                        <SelectItem value="ap-northeast-1">Asia Pacific (Tokyo)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <ProfessionalInput
                    id="s3-bucket"
                    label={`${t('settings.bucket_name')} (optional)`}
                    value={s3Credentials.bucket_name}
                    onChange={(e) => setS3Credentials({ ...s3Credentials, bucket_name: e.target.value })}
                    placeholder="Leave empty to use AWS_S3_BUCKET_NAME"
                  />

                  <ProfessionalInput
                    id="s3-prefix"
                    label={t('settings.path_prefix')}
                    value={s3Credentials.path_prefix}
                    onChange={(e) => setS3Credentials({ ...s3Credentials, path_prefix: e.target.value })}
                    placeholder="exported"
                    helperText='Path prefix for organizing batch files in S3 (e.g., "exported" or a UUID)'
                  />
                </div>
              </div>
            )}

            {/* Azure Credentials */}
            {formData.destination_type === 'azure' && (
              <div className="space-y-4 p-5 border border-border/50 rounded-xl bg-muted/20">
                <h4 className="font-medium flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Azure Blob Storage {t('settings.credentials')}
                </h4>
                {editingDestination && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 flex items-center gap-2">
                    <EyeOff className="h-4 w-4" />
                    <p>{t('settings.secret_fields_are_masked')}</p>
                  </div>
                )}
                <div className="space-y-4">
                  <div>
                    <Label className="mb-2 block">{t('settings.authentication_method')}</Label>
                    <Select
                      value={azureCredentials.auth_type}
                      onValueChange={(value: any) => setAzureCredentials({ ...azureCredentials, auth_type: value })}
                    >
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="connection_string">{t('settings.connection_string')}</SelectItem>
                        <SelectItem value="account_key">{t('settings.account_name_and_key')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {azureCredentials.auth_type === 'connection_string' ? (
                    <div>
                      <Label htmlFor="azure-connection-string" className="mb-2 block">{t('settings.connection_string')}</Label>
                      <ProfessionalTextarea
                        id="azure-connection-string"
                        value={azureCredentials.connection_string}
                        onChange={(e) => setAzureCredentials({ ...azureCredentials, connection_string: e.target.value })}
                        placeholder="DefaultEndpointsProtocol=https;AccountName=..."
                        rows={3}
                      />
                    </div>
                  ) : (
                    <>
                      <ProfessionalInput
                        id="azure-account-name"
                        label={t('settings.account_name')}
                        value={azureCredentials.account_name}
                        onChange={(e) => setAzureCredentials({ ...azureCredentials, account_name: e.target.value })}
                        placeholder="mystorageaccount"
                      />

                      <div>
                        <Label htmlFor="azure-account-key" className="mb-2 block">{t('settings.account_key')}</Label>
                        <ProfessionalInput
                          id="azure-account-key"
                          type={showPassword['azure-key'] ? 'text' : 'password'}
                          value={azureCredentials.account_key}
                          onChange={(e) => setAzureCredentials({ ...azureCredentials, account_key: e.target.value })}
                          placeholder="••••••••"
                          rightIcon={
                            <button
                              type="button"
                              onClick={() => setShowPassword({ ...showPassword, 'azure-key': !showPassword['azure-key'] })}
                              className="text-muted-foreground hover:text-foreground transition-colors outline-none"
                            >
                              {showPassword['azure-key'] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </button>
                          }
                        />
                      </div>
                    </>
                  )}

                  <ProfessionalInput
                    id="azure-container"
                    label={t('settings.container_name')}
                    value={azureCredentials.container_name}
                    onChange={(e) => setAzureCredentials({ ...azureCredentials, container_name: e.target.value })}
                    placeholder="exports"
                  />

                  <ProfessionalInput
                    id="azure-prefix"
                    label={`${t('settings.path_prefix')} (${t('common.optional')})`}
                    value={azureCredentials.path_prefix}
                    onChange={(e) => setAzureCredentials({ ...azureCredentials, path_prefix: e.target.value })}
                    placeholder="batch-results/"
                  />
                </div>
              </div>
            )}

            {/* GCS Credentials */}
            {formData.destination_type === 'gcs' && (
              <div className="space-y-4 p-5 border border-border/50 rounded-xl bg-muted/20">
                <h4 className="font-medium flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Google Cloud Storage {t('settings.credentials')}
                </h4>
                {editingDestination && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 flex items-center gap-2">
                    <EyeOff className="h-4 w-4" />
                    <p>{t('settings.secret_fields_are_masked')}</p>
                  </div>
                )}
                <div className="space-y-4">
                  <div>
                    <Label className="mb-2 block">{t('settings.authentication_method')}</Label>
                    <Select
                      value={gcsCredentials.auth_type}
                      onValueChange={(value: any) => setGcsCredentials({ ...gcsCredentials, auth_type: value })}
                    >
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="service_account">{t('settings.service_account_json')}</SelectItem>
                        <SelectItem value="project_id">{t('settings.project_id_and_credentials')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {gcsCredentials.auth_type === 'service_account' ? (
                    <div>
                      <Label htmlFor="gcs-service-account" className="mb-2 block">{t('settings.service_account_json')}</Label>
                      <ProfessionalTextarea
                        id="gcs-service-account"
                        value={gcsCredentials.service_account_json}
                        onChange={(e) => setGcsCredentials({ ...gcsCredentials, service_account_json: e.target.value })}
                        placeholder='{"type": "service_account", "project_id": "...", ...}'
                        rows={5}
                      />
                      <p className="text-sm text-muted-foreground mt-1">
                        {t('settings.paste_service_account_json_content')}
                      </p>
                    </div>
                  ) : (
                    <>
                      <ProfessionalInput
                        id="gcs-project-id"
                        label={t('settings.project_id')}
                        value={gcsCredentials.project_id}
                        onChange={(e) => setGcsCredentials({ ...gcsCredentials, project_id: e.target.value })}
                        placeholder="my-project-id"
                      />
                      <div>
                        <Label htmlFor="gcs-credentials" className="mb-2 block">{t('settings.credentials_json')}</Label>
                        <ProfessionalTextarea
                          id="gcs-credentials"
                          value={gcsCredentials.credentials}
                          onChange={(e) => setGcsCredentials({ ...gcsCredentials, credentials: e.target.value })}
                          placeholder='{"client_id": "...", "client_secret": "...", ...}'
                          rows={3}
                        />
                      </div>
                    </>
                  )}

                  <ProfessionalInput
                    id="gcs-bucket"
                    label={t('settings.bucket_name')}
                    value={gcsCredentials.bucket_name}
                    onChange={(e) => setGcsCredentials({ ...gcsCredentials, bucket_name: e.target.value })}
                    placeholder="my-export-bucket"
                  />

                  <ProfessionalInput
                    id="gcs-prefix"
                    label={`${t('settings.path_prefix')} (${t('common.optional')})`}
                    value={gcsCredentials.path_prefix}
                    onChange={(e) => setGcsCredentials({ ...gcsCredentials, path_prefix: e.target.value })}
                    placeholder="exports/"
                  />
                </div>
              </div>
            )}

            {/* Google Drive Credentials */}
            {formData.destination_type === 'google_drive' && (
              <div className="space-y-4 p-5 border border-border/50 rounded-xl bg-muted/20">
                <h4 className="font-medium flex items-center gap-2">
                  <HardDrive className="h-4 w-4" />
                  Google Drive {t('settings.credentials')}
                </h4>
                {editingDestination && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 flex items-center gap-2">
                    <EyeOff className="h-4 w-4" />
                    <p>{t('settings.secret_fields_are_masked')}</p>
                  </div>
                )}
                <div className="space-y-4">
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                    <p className="text-sm text-yellow-800">
                      {t('settings.google_drive_oauth_note')}
                    </p>
                  </div>

                  <ProfessionalInput
                    id="gdrive-oauth-token"
                    label={t('settings.oauth_access_token')}
                    type={showPassword['gdrive-oauth'] ? 'text' : 'password'}
                    value={googleDriveCredentials.oauth_token}
                    onChange={(e) => setGoogleDriveCredentials({ ...googleDriveCredentials, oauth_token: e.target.value })}
                    placeholder="ya29...."
                    rightIcon={
                      <button
                        type="button"
                        onClick={() => setShowPassword({ ...showPassword, 'gdrive-oauth': !showPassword['gdrive-oauth'] })}
                        className="text-muted-foreground hover:text-foreground transition-colors outline-none"
                      >
                        {showPassword['gdrive-oauth'] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    }
                  />

                  <ProfessionalInput
                    id="gdrive-refresh-token"
                    label={t('settings.oauth_refresh_token')}
                    type={showPassword['gdrive-refresh'] ? 'text' : 'password'}
                    value={googleDriveCredentials.refresh_token}
                    onChange={(e) => setGoogleDriveCredentials({ ...googleDriveCredentials, refresh_token: e.target.value })}
                    placeholder="1//..."
                    rightIcon={
                      <button
                        type="button"
                        onClick={() => setShowPassword({ ...showPassword, 'gdrive-refresh': !showPassword['gdrive-refresh'] })}
                        className="text-muted-foreground hover:text-foreground transition-colors outline-none"
                      >
                        {showPassword['gdrive-refresh'] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    }
                  />

                  <ProfessionalInput
                    id="gdrive-folder-id"
                    label={t('settings.folder_id')}
                    value={googleDriveCredentials.folder_id}
                    onChange={(e) => setGoogleDriveCredentials({ ...googleDriveCredentials, folder_id: e.target.value })}
                    placeholder="1a2b3c4d5e6f7g8h9i0j"
                    helperText={t('settings.folder_id_from_url')}
                  />
                </div>
              </div>
            )}

            {/* Default toggle */}
            <div className="flex items-center justify-between p-4 border border-border/50 rounded-xl bg-muted/10">
              <Label htmlFor="is-default" className="flex-1 cursor-pointer font-medium">{t('settings.set_as_default_destination')}</Label>
              <Switch
                id="is-default"
                checked={formData.is_default}
                onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <ProfessionalButton variant="outline" onClick={() => setShowDialog(false)}>
              {t('common.cancel')}
            </ProfessionalButton>
            <ProfessionalButton onClick={handleSave} variant="gradient">
              {editingDestination ? t('common.update') : t('common.create')}
            </ProfessionalButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ProfessionalCard>
    </div>
  );
};

export default ExportDestinationsTab;

