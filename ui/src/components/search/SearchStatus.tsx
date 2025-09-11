import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Search, AlertCircle, CheckCircle, Database } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';

interface SearchStatus {
  opensearch_enabled: boolean;
  opensearch_connected: boolean;
  opensearch_health?: string;
  opensearch_nodes?: number;
  opensearch_error?: string;
  host: string;
  port: number;
  fallback_available: boolean;
  error?: string;
}

export function SearchStatus() {
  const [status, setStatus] = useState<SearchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);

  const fetchStatus = async () => {
    try {
      const response = await apiClient.get<SearchStatus>('/search/status');
      setStatus(response.data);
    } catch (error) {
      console.error('Error fetching search status:', error);
      toast.error('Failed to fetch search status');
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    try {
      await apiClient.post('/search/reindex');
      toast.success('Search data reindexed successfully');
      await fetchStatus(); // Refresh status
    } catch (error) {
      console.error('Error reindexing:', error);
      toast.error('Failed to reindex search data');
    } finally {
      setReindexing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-6">
          <RefreshCw className="h-4 w-4 animate-spin mr-2" />
          Loading search status...
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-6">
          <AlertCircle className="h-4 w-4 text-red-500 mr-2" />
          Failed to load search status
        </CardContent>
      </Card>
    );
  }

  const getStatusBadge = () => {
    if (status.opensearch_enabled && status.opensearch_connected) {
      return (
        <Badge variant="default" className="bg-green-100 text-green-800">
          <CheckCircle className="h-3 w-3 mr-1" />
          OpenSearch Active
        </Badge>
      );
    } else if (status.fallback_available) {
      return (
        <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
          <Database className="h-3 w-3 mr-1" />
          Database Fallback
        </Badge>
      );
    } else {
      return (
        <Badge variant="destructive">
          <AlertCircle className="h-3 w-3 mr-1" />
          Search Disabled
        </Badge>
      );
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Search Service Status
            </CardTitle>
            <CardDescription>
              Monitor and manage the search indexing system
            </CardDescription>
          </div>
          {getStatusBadge()}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="font-medium">OpenSearch:</span>
            <span className="ml-2">
              {status.opensearch_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          <div>
            <span className="font-medium">Connection:</span>
            <span className="ml-2">
              {status.opensearch_connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div>
            <span className="font-medium">Host:</span>
            <span className="ml-2">{status.host}:{status.port}</span>
          </div>
          <div>
            <span className="font-medium">Fallback:</span>
            <span className="ml-2">
              {status.fallback_available ? 'Available' : 'Unavailable'}
            </span>
          </div>
        </div>

        {status.opensearch_health && (
          <div className="text-sm">
            <span className="font-medium">Cluster Health:</span>
            <Badge 
              variant={status.opensearch_health === 'green' ? 'default' : 'secondary'}
              className="ml-2"
            >
              {status.opensearch_health}
            </Badge>
            {status.opensearch_nodes && (
              <span className="ml-2 text-muted-foreground">
                ({status.opensearch_nodes} nodes)
              </span>
            )}
          </div>
        )}

        {status.opensearch_error && (
          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
            <AlertCircle className="h-4 w-4 inline mr-1" />
            {status.opensearch_error}
          </div>
        )}

        {status.error && (
          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
            <AlertCircle className="h-4 w-4 inline mr-1" />
            {status.error}
          </div>
        )}

        <div className="flex gap-2 pt-4 border-t">
          <Button
            onClick={fetchStatus}
            variant="outline"
            size="sm"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh Status
          </Button>
          
          <Button
            onClick={handleReindex}
            variant="default"
            size="sm"
            disabled={reindexing || (!status.opensearch_enabled && !status.fallback_available)}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${reindexing ? 'animate-spin' : ''}`} />
            {reindexing ? 'Reindexing...' : 'Reindex Data'}
          </Button>
        </div>

        <div className="text-xs text-muted-foreground">
          {status.opensearch_enabled && status.opensearch_connected
            ? 'Search is powered by OpenSearch with full-text search capabilities.'
            : status.fallback_available
            ? 'Search is using database fallback with basic text matching.'
            : 'Search functionality is currently unavailable.'
          }
        </div>
      </CardContent>
    </Card>
  );
}