import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Search, Download, Eye, FileText, Receipt, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { FeatureGate } from '@/components/FeatureGate';

interface AttachmentResult {
  id: number;
  entity_type: 'invoice' | 'expense' | 'statement';
  entity_number: string;
  entity_name: string;
  client_name: string;
  filename: string;
  file_path: string;
  file_exists: boolean;
  created_at: string | null;
  preview_url: string;
  download_url: string;
}

interface SearchResponse {
  query: string;
  entity_type: string | null;
  total_results: number;
  results: AttachmentResult[];
}

const AttachmentSearch = () => {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [entityType, setEntityType] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AttachmentResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        query: query.trim(),
        ...(entityType !== 'all' && { entity_type: entityType })
      });

      const response = await api.get<SearchResponse>(`/attachments/search?${params}`);
      setResults(response.results);
      setTotalResults(response.total_results);

      if (response.total_results === 0) {
        toast.info('No attachments found matching your search');
      }
    } catch (error: any) {
      toast.error(error?.message || 'Failed to search attachments');
      setResults([]);
      setTotalResults(0);
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = (result: AttachmentResult) => {
    window.open(result.preview_url, '_blank');
  };

  const handleDownload = async (result: AttachmentResult) => {
    try {
      const response = await fetch(result.download_url, { credentials: 'include' });

      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const getEntityIcon = (entityType: string) => {
    switch (entityType) {
      case 'invoice': return <FileText className="w-4 h-4" />;
      case 'expense': return <Receipt className="w-4 h-4" />;
      case 'statement': return <CreditCard className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const getEntityColor = (entityType: string) => {
    switch (entityType) {
      case 'invoice': return 'bg-blue-100 text-blue-800';
      case 'expense': return 'bg-green-100 text-green-800';
      case 'statement': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Attachment Search</h1>
            <p className="text-muted-foreground">Search for files across invoices, expenses, and statements</p>
          </div>
        </div>

        <FeatureGate
          feature="advanced_search"
          showUpgradePrompt={true}
          upgradeMessage="Attachment Search requires a commercial license. Upgrade to search across all your files and documents."
        >
          <Card className="slide-in">
            <CardHeader>
              <CardTitle>Search Attachments</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-4 mb-4">
                <div className="flex-1">
                  <Input
                    placeholder="Search by filename..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  />
                </div>
                <Select value={entityType} onValueChange={setEntityType}>
                  <SelectTrigger className="w-full sm:w-[180px]">
                    <SelectValue placeholder="All types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="invoice">Invoices</SelectItem>
                    <SelectItem value="expense">Expenses</SelectItem>
                    <SelectItem value="statement">Statements</SelectItem>
                  </SelectContent>
                </Select>
                <Button onClick={handleSearch} disabled={loading}>
                  <Search className="w-4 h-4 mr-2" />
                  {loading ? 'Searching...' : 'Search'}
                </Button>
              </div>

              {totalResults > 0 && (
                <div className="mb-4">
                  <p className="text-sm text-muted-foreground">
                    Found {totalResults} attachment{totalResults !== 1 ? 's' : ''} matching "{query}"
                  </p>
                </div>
              )}

              <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                      <TableHead>Type</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Client/Vendor</TableHead>
                      <TableHead>Filename</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.length > 0 ? (
                      results.map((result) => (
                        <TableRow key={`${result.entity_type}-${result.id}`} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                          <TableCell>
                            <Badge className={getEntityColor(result.entity_type)}>
                              {getEntityIcon(result.entity_type)}
                              <span className="ml-1 capitalize">{result.entity_type}</span>
                            </Badge>
                          </TableCell>
                          <TableCell className="font-medium">
                            {result.entity_name}
                          </TableCell>
                          <TableCell>{result.client_name}</TableCell>
                          <TableCell className="max-w-[200px] truncate" title={result.filename}>
                            {result.filename}
                          </TableCell>
                          <TableCell>
                            {result.created_at ? new Date(result.created_at).toLocaleDateString() : 'N/A'}
                          </TableCell>
                          <TableCell>
                            <Badge variant={result.file_exists ? 'default' : 'destructive'}>
                              {result.file_exists ? 'Available' : 'Missing'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePreview(result)}
                                disabled={!result.file_exists}
                              >
                                <Eye className="w-4 h-4 mr-1" />
                                Preview
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleDownload(result)}
                                disabled={!result.file_exists}
                              >
                                <Download className="w-4 h-4 mr-1" />
                                Download
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                          {loading ? 'Searching...' : 'No attachments found. Try searching for a filename.'}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </FeatureGate>
      </div>
    </>
  );
};

export default AttachmentSearch;