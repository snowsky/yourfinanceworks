import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Alert, AlertDescription } from '../ui/alert';
import { Switch } from '../ui/switch';
import { Textarea } from '../ui/textarea';
import { Copy, Key, Trash2, RotateCcw, Shield } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../../lib/api';

interface APIClient {
  id: number;
  client_id: string;
  client_name: string;
  client_description?: string;
  user_id: number;
  api_key_prefix: string;
  allowed_document_types: string[];
  max_transaction_amount?: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  allowed_ip_addresses?: string[];
  webhook_url?: string;
  is_active: boolean;
  is_sandbox: boolean;
  total_requests: number;
  total_transactions_submitted: number;
  last_used_at?: string;
  created_at: string;
  updated_at: string;
}

interface APIKeyCreateRequest {
  client_name: string;
  client_description?: string;
  allowed_document_types: string[];
  max_transaction_amount?: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  allowed_ip_addresses?: string[];
  webhook_url?: string;
  is_sandbox: boolean;
  expires_in_days?: number;
}

interface APIKeyResponse {
  client_id: string;
  api_key: string;
  api_key_prefix: string;
  client_name: string;
  allowed_document_types: string[];
  rate_limits: {
    per_minute: number;
    per_hour: number;
    per_day: number;
  };
  expires_at?: string;
  created_at: string;
}

interface OAuthClientCreateRequest {
  client_name: string;
  client_description?: string;
  redirect_uris: string[];
  scopes: string[];
  allowed_document_types: string[];
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
}

const DOCUMENT_TYPES = [
  { value: 'invoice', label: 'Invoices' },
  { value: 'expense', label: 'Expenses' },
  { value: 'statement', label: 'Statements' }
];

const OAUTH_SCOPES = [
  { value: 'read', label: 'Read Access' },
  { value: 'write', label: 'Write Access' },
  { value: 'invoices:read', label: 'Read Invoices' },
  { value: 'invoices:write', label: 'Write Invoices' },
  { value: 'expenses:read', label: 'Read Expenses' },
  { value: 'expenses:write', label: 'Write Expenses' },
  { value: 'transactions:read', label: 'Read Transactions' },
  { value: 'transactions:write', label: 'Write Transactions' }
];

const APIClientManagement: React.FC = () => {
  const [clients, setClients] = useState<APIClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showOAuthDialog, setShowOAuthDialog] = useState(false);
  const [showApiKey, setShowApiKey] = useState<APIKeyResponse | null>(null);
  const [showOAuthCredentials, setShowOAuthCredentials] = useState<any>(null);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState<{clientId: string, clientName: string} | null>(null);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState<{clientId: string, clientName: string} | null>(null);
  
  // Create API key form state
  const [createForm, setCreateForm] = useState<APIKeyCreateRequest>({
    client_name: '',
    client_description: '',
    allowed_document_types: [],
    max_transaction_amount: undefined,
    rate_limit_per_minute: 60,
    rate_limit_per_hour: 1000,
    rate_limit_per_day: 10000,
    allowed_ip_addresses: [],
    webhook_url: '',
    is_sandbox: false,
    expires_in_days: undefined
  });

  // Create OAuth client form state
  const [oauthForm, setOAuthForm] = useState<OAuthClientCreateRequest>({
    client_name: '',
    client_description: '',
    redirect_uris: [''],
    scopes: [],
    allowed_document_types: [],
    rate_limit_per_minute: 100,
    rate_limit_per_hour: 2000,
    rate_limit_per_day: 20000
  });

  // Form helpers
  const [ipAddressInput, setIpAddressInput] = useState('');
  const [redirectUriInput, setRedirectUriInput] = useState('');

  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    try {
      setLoading(true);
      const clients: APIClient[] = await api.get('/external-auth/api-keys');
      setClients(clients || []);
    } catch (error) {
      console.error('Failed to load API clients:', error);
      toast.error('Failed to load API clients');
      setClients([]); // Ensure clients is always an array
    } finally {
      setLoading(false);
    }
  };

  const createApiKey = async () => {
    try {
      // Check API key limit
      if (clients.length >= 2) {
        toast.error('Maximum of 2 API keys allowed per user');
        return;
      }

      if (!createForm.client_name.trim()) {
        toast.error('Client name is required');
        return;
      }
      
      if (createForm.allowed_document_types.length === 0) {
        toast.error('At least one document type is required');
        return;
      }

      const apiKeyResponse: APIKeyResponse = await api.post('/external-auth/api-keys', createForm);
      
      setShowCreateDialog(false);
      setShowApiKey(apiKeyResponse);
      
      // Reset form
      setCreateForm({
        client_name: '',
        client_description: '',
        allowed_document_types: [],
        max_transaction_amount: undefined,
        rate_limit_per_minute: 60,
        rate_limit_per_hour: 1000,
        rate_limit_per_day: 10000,
        allowed_ip_addresses: [],
        webhook_url: '',
        is_sandbox: false,
        expires_in_days: undefined
      });
      
      // Reload clients list
      await loadClients();

      toast.success('API key created successfully');
    } catch (error) {
      console.error('Failed to create API key:', error);
      toast.error('Failed to create API key');
    }
  };

  const createOAuthClient = async () => {
    try {
      if (!oauthForm.client_name.trim()) {
        toast.error('Client name is required');
        return;
      }
      
      if (oauthForm.allowed_document_types.length === 0) {
        toast.error('At least one document type is required');
        return;
      }

      if (oauthForm.redirect_uris.filter(uri => uri.trim()).length === 0) {
        toast.error('At least one redirect URI is required');
        return;
      }

      if (oauthForm.scopes.length === 0) {
        toast.error('At least one scope is required');
        return;
      }

      const cleanedForm = {
        ...oauthForm,
        redirect_uris: oauthForm.redirect_uris.filter(uri => uri.trim())
      };

      const response: any = await api.post('/external-auth/oauth/clients', cleanedForm);

      setShowOAuthDialog(false);
      setShowOAuthCredentials(response);
      
      // Reset form
      setOAuthForm({
        client_name: '',
        client_description: '',
        redirect_uris: [''],
        scopes: [],
        allowed_document_types: [],
        rate_limit_per_minute: 100,
        rate_limit_per_hour: 2000,
        rate_limit_per_day: 20000
      });
      
      toast.success('OAuth client created successfully');
    } catch (error) {
      console.error('Failed to create OAuth client:', error);
      toast.error('Failed to create OAuth client');
    }
  };

  const handleRevokeClick = (clientId: string, clientName: string) => {
    setShowRevokeConfirm({ clientId, clientName });
  };

  const confirmRevokeApiKey = async () => {
    if (!showRevokeConfirm) return;
    
    try {
      await api.delete(`/external-auth/api-keys/${showRevokeConfirm.clientId}`);
      loadClients();
      toast.success('API key revoked successfully');
      setShowRevokeConfirm(null);
    } catch (error) {
      console.error('Failed to revoke API key:', error);
      toast.error('Failed to revoke API key');
    }
  };

  const handleRegenerateClick = (clientId: string, clientName: string) => {
    setShowRegenerateConfirm({ clientId, clientName });
  };

  const confirmRegenerateApiKey = async () => {
    if (!showRegenerateConfirm) return;
    
    try {
      const apiKeyResponse: APIKeyResponse = await api.post(`/external-auth/api-keys/${showRegenerateConfirm.clientId}/regenerate`);
      setShowApiKey(apiKeyResponse);
      loadClients();
      toast.success('API key regenerated successfully');
      setShowRegenerateConfirm(null);
    } catch (error) {
      console.error('Failed to regenerate API key:', error);
      toast.error('Failed to regenerate API key');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch (error) {
      toast.error('Failed to copy to clipboard');
    }
  };

  const addIpAddress = () => {
    if (ipAddressInput.trim() && !createForm.allowed_ip_addresses?.includes(ipAddressInput.trim())) {
      setCreateForm({
        ...createForm,
        allowed_ip_addresses: [...(createForm.allowed_ip_addresses || []), ipAddressInput.trim()]
      });
      setIpAddressInput('');
    }
  };

  const removeIpAddress = (ip: string) => {
    setCreateForm({
      ...createForm,
      allowed_ip_addresses: createForm.allowed_ip_addresses?.filter(addr => addr !== ip)
    });
  };

  const addRedirectUri = () => {
    if (redirectUriInput.trim()) {
      setOAuthForm({
        ...oauthForm,
        redirect_uris: [...oauthForm.redirect_uris, redirectUriInput.trim()]
      });
      setRedirectUriInput('');
    }
  };

  const removeRedirectUri = (index: number) => {
    setOAuthForm({
      ...oauthForm,
      redirect_uris: oauthForm.redirect_uris.filter((_, i) => i !== index)
    });
  };

  const handleDocumentTypeToggle = (type: string, checked: boolean) => {
    if (checked) {
      setCreateForm({
        ...createForm,
        allowed_document_types: [...createForm.allowed_document_types, type]
      });
    } else {
      setCreateForm({
        ...createForm,
        allowed_document_types: createForm.allowed_document_types.filter(t => t !== type)
      });
    }
  };

  const handleOAuthScopeToggle = (scope: string, checked: boolean) => {
    if (checked) {
      setOAuthForm({
        ...oauthForm,
        scopes: [...oauthForm.scopes, scope]
      });
    } else {
      setOAuthForm({
        ...oauthForm,
        scopes: oauthForm.scopes.filter(s => s !== scope)
      });
    }
  };

  const handleOAuthDocumentTypeToggle = (type: string, checked: boolean) => {
    if (checked) {
      setOAuthForm({
        ...oauthForm,
        allowed_document_types: [...oauthForm.allowed_document_types, type]
      });
    } else {
      setOAuthForm({
        ...oauthForm,
        allowed_document_types: oauthForm.allowed_document_types.filter(t => t !== type)
      });
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl p-12 shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Loading API Clients</h3>
          <p className="text-gray-600">Please wait while we load your API clients...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Professional Header Section */}
      <div className="bg-white dark:bg-gray-700 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-600">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
              <Key className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">API Clients</h2>
              <p className="text-gray-600">
                Manage your API keys and OAuth clients 
                <span className={`ml-2 px-2 py-1 rounded-full text-xs font-medium ${
                  clients.length >= 2 
                    ? 'bg-red-100 text-red-800' 
                    : clients.length === 1 
                    ? 'bg-yellow-100 text-yellow-800' 
                    : 'bg-green-100 text-green-800'
                }`}>
                  {clients.length}/2 API keys used
                </span>
              </p>
            </div>
          </div>
          <div className="flex space-x-3">
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <button 
                  disabled={clients.length >= 2}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors duration-200 flex items-center space-x-2 ${
                    clients.length >= 2 
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }`}
                  title={clients.length >= 2 ? 'Maximum of 2 API keys allowed per user' : 'Create a new API key'}
                >
                  <Key className="w-4 h-4" />
                  <span>Create API Key {clients.length >= 2 ? `(${clients.length}/2)` : ''}</span>
                </button>
              </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New API Key</DialogTitle>
              </DialogHeader>
              
              {clients.length === 1 && (
                <Alert>
                  <AlertDescription>
                    <strong>Note:</strong> You can create one more API key. Maximum limit is 2 API keys per account.
                  </AlertDescription>
                </Alert>
              )}
              
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="client_name">Client Name *</Label>
                    <Input
                      id="client_name"
                      value={createForm.client_name}
                      onChange={(e) => setCreateForm({ ...createForm, client_name: e.target.value })}
                      placeholder="My Accounting System"
                    />
                  </div>
                  
                  <div>
                    <Label>
                      <Switch
                        checked={createForm.is_sandbox}
                        onCheckedChange={(checked) => setCreateForm({ ...createForm, is_sandbox: checked })}
                      />
                      <span className="ml-2">Sandbox Mode</span>
                    </Label>
                  </div>
                </div>
                
                <div>
                  <Label htmlFor="client_description">Description</Label>
                  <Textarea
                    id="client_description"
                    value={createForm.client_description}
                    onChange={(e) => setCreateForm({ ...createForm, client_description: e.target.value })}
                    placeholder="Integration with accounting software"
                    rows={2}
                  />
                </div>
                
                <div>
                  <Label>Document Types *</Label>
                  <div className="grid grid-cols-1 gap-2 mt-2">
                    {DOCUMENT_TYPES.map((type) => (
                      <div key={type.value} className="flex items-center space-x-2">
                        <Switch
                          id={type.value}
                          checked={createForm.allowed_document_types.includes(type.value)}
                          onCheckedChange={(checked) => handleDocumentTypeToggle(type.value, checked)}
                        />
                        <Label htmlFor={type.value} className="text-sm">
                          {type.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label htmlFor="rate_limit_per_minute">Per Minute</Label>
                    <Input
                      id="rate_limit_per_minute"
                      type="number"
                      value={createForm.rate_limit_per_minute}
                      onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_minute: parseInt(e.target.value) })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="rate_limit_per_hour">Per Hour</Label>
                    <Input
                      id="rate_limit_per_hour"
                      type="number"
                      value={createForm.rate_limit_per_hour}
                      onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_hour: parseInt(e.target.value) })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="rate_limit_per_day">Per Day</Label>
                    <Input
                      id="rate_limit_per_day"
                      type="number"
                      value={createForm.rate_limit_per_day}
                      onChange={(e) => setCreateForm({ ...createForm, rate_limit_per_day: parseInt(e.target.value) })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="max_transaction_amount">Max Transaction Amount</Label>
                    <Input
                      id="max_transaction_amount"
                      type="number"
                      step="0.01"
                      value={createForm.max_transaction_amount || ''}
                      onChange={(e) => setCreateForm({ 
                        ...createForm, 
                        max_transaction_amount: e.target.value ? parseFloat(e.target.value) : undefined 
                      })}
                      placeholder="No limit"
                    />
                  </div>
                  <div>
                    <Label htmlFor="expires_in_days">Expires in Days</Label>
                    <Input
                      id="expires_in_days"
                      type="number"
                      value={createForm.expires_in_days || ''}
                      onChange={(e) => setCreateForm({ 
                        ...createForm, 
                        expires_in_days: e.target.value ? parseInt(e.target.value) : undefined 
                      })}
                      placeholder="Never expires"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="webhook_url">Webhook URL</Label>
                  <Input
                    id="webhook_url"
                    value={createForm.webhook_url}
                    onChange={(e) => setCreateForm({ ...createForm, webhook_url: e.target.value })}
                    placeholder="https://your-app.com/webhooks/invoice-system"
                  />
                </div>

                <div>
                  <Label>Allowed IP Addresses</Label>
                  <div className="flex space-x-2 mt-2">
                    <Input
                      value={ipAddressInput}
                      onChange={(e) => setIpAddressInput(e.target.value)}
                      placeholder="192.168.1.100 or 10.0.0.0/24"
                    />
                    <Button type="button" onClick={addIpAddress} variant="outline">
                      Add
                    </Button>
                  </div>
                  {createForm.allowed_ip_addresses && createForm.allowed_ip_addresses.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {createForm.allowed_ip_addresses.map((ip) => (
                        <Badge key={ip} variant="secondary" className="cursor-pointer" onClick={() => removeIpAddress(ip)}>
                          {ip} ✕
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={createApiKey}>
                    Create API Key
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          <Dialog open={showOAuthDialog} onOpenChange={setShowOAuthDialog}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Shield className="w-4 h-4 mr-2" />
                Create OAuth Client
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create OAuth 2.0 Client</DialogTitle>
              </DialogHeader>
              <div className="space-y-6">
                <Alert>
                  <AlertDescription>
                    OAuth clients are for enterprise integrations and require admin approval.
                  </AlertDescription>
                </Alert>

                <div>
                  <Label htmlFor="oauth_client_name">Client Name *</Label>
                  <Input
                    id="oauth_client_name"
                    value={oauthForm.client_name}
                    onChange={(e) => setOAuthForm({ ...oauthForm, client_name: e.target.value })}
                    placeholder="Enterprise Integration"
                  />
                </div>
                
                <div>
                  <Label htmlFor="oauth_client_description">Description</Label>
                  <Textarea
                    id="oauth_client_description"
                    value={oauthForm.client_description}
                    onChange={(e) => setOAuthForm({ ...oauthForm, client_description: e.target.value })}
                    placeholder="OAuth client for enterprise system"
                    rows={2}
                  />
                </div>

                <div>
                  <Label>OAuth Scopes *</Label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {OAUTH_SCOPES.map((scope) => (
                      <div key={scope.value} className="flex items-center space-x-2">
                        <Switch
                          id={scope.value}
                          checked={oauthForm.scopes.includes(scope.value)}
                          onCheckedChange={(checked) => handleOAuthScopeToggle(scope.value, checked)}
                        />
                        <Label htmlFor={scope.value} className="text-sm">
                          {scope.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label>Document Types *</Label>
                  <div className="grid grid-cols-1 gap-2 mt-2">
                    {DOCUMENT_TYPES.map((type) => (
                      <div key={type.value} className="flex items-center space-x-2">
                        <Switch
                          id={`oauth_${type.value}`}
                          checked={oauthForm.allowed_document_types.includes(type.value)}
                          onCheckedChange={(checked) => handleOAuthDocumentTypeToggle(type.value, checked)}
                        />
                        <Label htmlFor={`oauth_${type.value}`} className="text-sm">
                          {type.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label>Redirect URIs *</Label>
                  <div className="flex space-x-2 mt-2">
                    <Input
                      value={redirectUriInput}
                      onChange={(e) => setRedirectUriInput(e.target.value)}
                      placeholder="https://your-app.com/oauth/callback"
                    />
                    <Button type="button" onClick={addRedirectUri} variant="outline">
                      Add
                    </Button>
                  </div>
                  {oauthForm.redirect_uris.filter(uri => uri.trim()).length > 0 && (
                    <div className="space-y-2 mt-2">
                      {oauthForm.redirect_uris.map((uri, index) => (
                        uri.trim() && (
                          <div key={index} className="flex items-center space-x-2">
                            <Input value={uri} readOnly />
                            <Button 
                              type="button" 
                              onClick={() => removeRedirectUri(index)} 
                              variant="outline" 
                              size="sm"
                            >
                              Remove
                            </Button>
                          </div>
                        )
                      ))}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label htmlFor="oauth_rate_limit_per_minute">Per Minute</Label>
                    <Input
                      id="oauth_rate_limit_per_minute"
                      type="number"
                      value={oauthForm.rate_limit_per_minute}
                      onChange={(e) => setOAuthForm({ ...oauthForm, rate_limit_per_minute: parseInt(e.target.value) })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="oauth_rate_limit_per_hour">Per Hour</Label>
                    <Input
                      id="oauth_rate_limit_per_hour"
                      type="number"
                      value={oauthForm.rate_limit_per_hour}
                      onChange={(e) => setOAuthForm({ ...oauthForm, rate_limit_per_hour: parseInt(e.target.value) })}
                    />
                  </div>
                  <div>
                    <Label htmlFor="oauth_rate_limit_per_day">Per Day</Label>
                    <Input
                      id="oauth_rate_limit_per_day"
                      type="number"
                      value={oauthForm.rate_limit_per_day}
                      onChange={(e) => setOAuthForm({ ...oauthForm, rate_limit_per_day: parseInt(e.target.value) })}
                    />
                  </div>
                </div>
                
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setShowOAuthDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={createOAuthClient}>
                    Create OAuth Client
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          </div>
        </div>
      </div>

      {/* API Key Display Dialog */}
      {showApiKey && (
        <Dialog open={!!showApiKey} onOpenChange={() => setShowApiKey(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>API Key Generated Successfully</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Alert>
                <AlertDescription>
                  Please copy and save this API key securely. It will not be shown again for security reasons.
                </AlertDescription>
              </Alert>
              
              <div className="space-y-3">
                <div>
                  <Label>Client ID</Label>
                  <div className="flex items-center space-x-2">
                    <Input value={showApiKey.client_id} readOnly />
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => copyToClipboard(showApiKey.client_id)}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                
                <div>
                  <Label>API Key</Label>
                  <div className="flex items-center space-x-2">
                    <Input value={showApiKey.api_key} readOnly className="font-mono" />
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => copyToClipboard(showApiKey.api_key)}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Rate Limits:</span>
                    <ul className="mt-1 space-y-1">
                      <li>Per minute: {showApiKey.rate_limits.per_minute}</li>
                      <li>Per hour: {showApiKey.rate_limits.per_hour}</li>
                      <li>Per day: {showApiKey.rate_limits.per_day}</li>
                    </ul>
                  </div>
                  <div>
                    <span className="font-medium">Document Types:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {showApiKey.allowed_document_types.map((type) => (
                        <Badge key={type} variant="outline" className="text-xs">
                          {type}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                {showApiKey.expires_at && (
                  <div className="text-sm">
                    <span className="font-medium">Expires:</span> {new Date(showApiKey.expires_at).toLocaleDateString()}
                  </div>
                )}
              </div>
              
              <div className="flex justify-end space-x-2">
                <Button onClick={() => copyToClipboard(showApiKey.api_key)} variant="outline">
                  Copy API Key
                </Button>
                <Button onClick={() => setShowApiKey(null)}>
                  I've Saved the Key
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* OAuth Credentials Display Dialog */}
      {showOAuthCredentials && (
        <Dialog open={!!showOAuthCredentials} onOpenChange={() => setShowOAuthCredentials(null)}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>OAuth Client Created Successfully</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Alert>
                <AlertDescription>
                  Please copy and save these OAuth credentials securely. The client secret will not be shown again.
                </AlertDescription>
              </Alert>
              
              <div className="space-y-3">
                <div>
                  <Label>Client ID</Label>
                  <div className="flex items-center space-x-2">
                    <Input value={showOAuthCredentials.oauth_client_id} readOnly />
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => copyToClipboard(showOAuthCredentials.oauth_client_id)}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                
                <div>
                  <Label>Client Secret</Label>
                  <div className="flex items-center space-x-2">
                    <Input value={showOAuthCredentials.oauth_client_secret} readOnly className="font-mono" />
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => copyToClipboard(showOAuthCredentials.oauth_client_secret)}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Scopes:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {showOAuthCredentials.scopes.map((scope: string) => (
                        <Badge key={scope} variant="outline" className="text-xs">
                          {scope}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="font-medium">Redirect URIs:</span>
                    <ul className="mt-1 space-y-1 text-xs">
                      {showOAuthCredentials.redirect_uris.map((uri: string, index: number) => (
                        <li key={index} className="break-all">{uri}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end space-x-2">
                <Button onClick={() => copyToClipboard(showOAuthCredentials.oauth_client_secret)} variant="outline">
                  Copy Client Secret
                </Button>
                <Button onClick={() => setShowOAuthCredentials(null)}>
                  I've Saved the Credentials
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Revoke API Key Confirmation Dialog */}
      {showRevokeConfirm && (
        <Dialog open={!!showRevokeConfirm} onOpenChange={() => setShowRevokeConfirm(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <Trash2 className="w-5 h-5" />
                Revoke API Key
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Alert className="border-red-200 bg-red-50">
                <Trash2 className="w-4 h-4 text-red-600" />
                <AlertDescription className="text-red-800">
                  <strong>Warning:</strong> This action cannot be undone. The API key will be permanently revoked and any applications using it will lose access immediately.
                </AlertDescription>
              </Alert>
              
              <div className="space-y-2">
                <p className="text-sm text-gray-600">
                  You are about to revoke the API key for:
                </p>
                <div className="bg-gray-50 rounded-lg p-3 border">
                  <p className="font-medium text-gray-900">{showRevokeConfirm.clientName}</p>
                  <p className="text-sm text-gray-500">Client ID: {showRevokeConfirm.clientId}</p>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowRevokeConfirm(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={confirmRevokeApiKey}
                  className="bg-red-600 hover:bg-red-700"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Yes, Revoke API Key
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Regenerate API Key Confirmation Dialog */}
      {showRegenerateConfirm && (
        <Dialog open={!!showRegenerateConfirm} onOpenChange={() => setShowRegenerateConfirm(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-orange-600">
                <RotateCcw className="w-5 h-5" />
                Regenerate API Key
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Alert className="border-orange-200 bg-orange-50">
                <RotateCcw className="w-4 h-4 text-orange-600" />
                <AlertDescription className="text-orange-800">
                  <strong>Warning:</strong> This will generate a new API key and invalidate the current one. Any applications using the current key will lose access immediately.
                </AlertDescription>
              </Alert>
              
              <div className="space-y-2">
                <p className="text-sm text-gray-600">
                  You are about to regenerate the API key for:
                </p>
                <div className="bg-gray-50 rounded-lg p-3 border">
                  <p className="font-medium text-gray-900">{showRegenerateConfirm.clientName}</p>
                  <p className="text-sm text-gray-500">Client ID: {showRegenerateConfirm.clientId}</p>
                </div>
                <p className="text-sm text-gray-600">
                  Make sure to update all applications with the new API key after regeneration.
                </p>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowRegenerateConfirm(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="default"
                  onClick={confirmRegenerateApiKey}
                  className="bg-orange-600 hover:bg-orange-700 text-white"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Yes, Regenerate Key
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* API Key Limit Warning */}
      {clients.length >= 2 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-amber-900">API Key Limit Reached</h3>
              <p className="text-amber-800 text-sm mt-1">
                You have reached the maximum limit of 2 API keys per account. To create a new API key, you must first revoke an existing one.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Professional API Clients List */}
      <div className="space-y-6">
        {(!clients || clients.length === 0) ? (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-12 shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="text-center">
              <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Key className="w-10 h-10 text-gray-400" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">No API Clients Found</h3>
              <p className="text-gray-600 mb-8 max-w-md mx-auto">
                Get started by creating your first API key to enable external integrations. You can create up to 2 API keys per account.
              </p>
              <button
                onClick={() => setShowCreateDialog(true)}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 flex items-center space-x-2 mx-auto font-medium transform hover:scale-105"
              >
                <Key className="w-5 h-5" />
                <span>Create Your First API Key</span>
              </button>
            </div>
          </div>
        ) : (
          (clients || []).map((client) => (
            <div key={client.client_id} className="bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-lg transition-shadow duration-200">
              <div className="p-6 border-b border-gray-200">
                <div className="flex justify-between items-start">
                  <div className="flex items-center space-x-3">
                    <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                      <Key className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2 mb-1">
                        <h3 className="text-xl font-bold text-gray-900">{client.client_name}</h3>
                        {client.is_sandbox && (
                          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-medium rounded-full">
                            Sandbox
                          </span>
                        )}
                      </div>
                      {client.client_description && (
                        <p className="text-gray-600 mb-2">{client.client_description}</p>
                      )}
                      <p className="text-sm text-gray-500 font-mono">
                        Client ID: {client.client_id}
                      </p>
                    </div>
                  </div>
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                    client.is_active
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {client.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-6">
                  {/* Client Statistics */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">{client.api_key_prefix}</div>
                      <div className="text-sm text-gray-600">API Key</div>
                    </div>
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">{client.total_requests.toLocaleString()}</div>
                      <div className="text-sm text-gray-600">Total Requests</div>
                    </div>
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">
                        {client.last_used_at
                          ? new Date(client.last_used_at).toLocaleDateString()
                          : 'Never'}
                      </div>
                      <div className="text-sm text-gray-600">Last Used</div>
                    </div>
                    <div className="text-center p-4 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-bold text-gray-900">{new Date(client.created_at).toLocaleDateString()}</div>
                      <div className="text-sm text-gray-600">Created</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Rate Limits:</span>
                      <ul className="mt-1 space-y-1 text-xs">
                        <li>{client.rate_limit_per_minute}/min</li>
                        <li>{client.rate_limit_per_hour}/hour</li>
                        <li>{client.rate_limit_per_day}/day</li>
                      </ul>
                    </div>
                    <div>
                      <span className="font-medium">Document Types:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {client.allowed_document_types.map((type) => (
                          <Badge key={type} variant="outline" className="text-xs">
                            {type}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="font-medium">Max Amount:</span>
                      <div className="mt-1">
                        {client.max_transaction_amount
                          ? `$${client.max_transaction_amount.toLocaleString()}`
                          : 'No limit'}
                      </div>
                    </div>
                  </div>

                  {(client.max_transaction_amount || client.allowed_ip_addresses?.length || client.webhook_url) && (
                    <div className="grid grid-cols-1 gap-2 text-sm">
                      {client.max_transaction_amount && (
                        <div>
                          <span className="font-medium">Max Amount:</span> ${client.max_transaction_amount.toLocaleString()}
                        </div>
                      )}
                      {client.allowed_ip_addresses && client.allowed_ip_addresses.length > 0 && (
                        <div>
                          <span className="font-medium">Allowed IPs:</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {client.allowed_ip_addresses.map((ip) => (
                              <Badge key={ip} variant="outline" className="text-xs font-mono">
                                {ip}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                      {client.webhook_url && (
                        <div>
                          <span className="font-medium">Webhook:</span>
                          <span className="text-xs font-mono ml-2">{client.webhook_url}</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="flex space-x-2">
                    {client.is_active && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRegenerateClick(client.client_id, client.client_name)}
                      >
                        <RotateCcw className="w-4 h-4 mr-1" />
                        Regenerate Key
                      </Button>
                    )}
                    
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleRevokeClick(client.client_id, client.client_name)}
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                      Revoke
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default APIClientManagement;
