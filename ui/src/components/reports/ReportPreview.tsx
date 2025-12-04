import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Loader2, Eye, EyeOff, RefreshCw } from 'lucide-react';
import { ReportData } from '@/lib/api';
import { format } from 'date-fns';

interface ReportPreviewProps {
  reportData: ReportData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const ReportPreview: React.FC<ReportPreviewProps> = ({
  reportData,
  loading,
  error,
  onRefresh,
}) => {
  if (loading) {
    return (
      <Card className="slide-in">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </div>
            Generating Preview...
          </CardTitle>
          <CardDescription>Please wait while we generate your report preview</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-muted/50 rounded w-1/4"></div>
              <div className="h-4 bg-muted/50 rounded w-1/2"></div>
              <div className="h-4 bg-muted/50 rounded w-1/3"></div>
            </div>
            <div className="animate-pulse">
              <div className="h-40 bg-muted/50 rounded-lg"></div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-20 bg-muted/50 rounded-lg"></div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="slide-in border-destructive/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-3 text-destructive">
            <div className="p-2 bg-destructive/10 rounded-lg">
              <EyeOff className="h-5 w-5" />
            </div>
            Preview Error
          </CardTitle>
          <CardDescription>There was an error generating the preview</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="p-4 bg-destructive/5 border border-destructive/20 rounded-lg">
              <p className="text-sm text-destructive/80">{error}</p>
            </div>
            <Button onClick={onRefresh} variant="outline" className="w-full">
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!reportData) {
    return (
      <Card className="slide-in">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="p-2 bg-muted/50 rounded-lg">
              <Eye className="h-5 w-5 text-muted-foreground" />
            </div>
            Report Preview
          </CardTitle>
          <CardDescription>Configure your filters and click preview to see a sample of your report</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-16 text-muted-foreground">
            <div className="mx-auto w-16 h-16 bg-muted/30 rounded-full flex items-center justify-center mb-4">
              <Eye className="h-8 w-8" />
            </div>
            <p className="font-medium mb-2">No preview available</p>
            <p className="text-sm">Configure your filters and generate a preview to see your data</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formatValue = (value: any, key: string): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span className="text-muted-foreground">-</span>;
    }

    // Handle objects - convert to string representation
    if (typeof value === 'object' && value !== null) {
      if (Array.isArray(value)) {
        if (value.length === 0) {
          return <span className="text-muted-foreground">-</span>;
        }
        return value.join(', ');
      }
      // For other objects, check if empty first
      const keys = Object.keys(value);
      if (keys.length === 0) {
        return <span className="text-muted-foreground">-</span>;
      }
      // Try to extract meaningful data or stringify
      // If it has a 'value' property, use that
      if ('value' in value) {
        return formatValue(value.value, key);
      }
      // For dictionary-style objects (like breakdowns), format as key-value pairs
      // Check if all values are numbers or simple types
      const isSimpleDict = keys.every(k => {
        const v = value[k];
        return typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean';
      });

      if (isSimpleDict && keys.length <= 5) {
        // Display as readable list for small dictionaries
        return (
          <div className="space-y-1">
            {keys.map(k => (
              <div key={k} className="text-sm">
                <span className="font-medium">{k}:</span> {value[k]}
              </div>
            ))}
          </div>
        );
      } else if (isSimpleDict) {
        // For larger dictionaries, show count
        return `${keys.length} items`;
      }

      // Otherwise, create a readable string representation
      return JSON.stringify(value);
    }

    // Format dates
    if (key.includes('date') || key.includes('_at')) {
      try {
        return format(new Date(value), 'MMM dd, yyyy');
      } catch {
        return String(value);
      }
    }

    // Format amounts
    if (key.includes('amount') || key.includes('balance') || key.includes('total') || key.includes('paid')) {
      if (typeof value === 'number') {
        try {
          const currency = reportData.summary.currency || 'USD';
          if (currency === 'Mixed' || currency === 'mixed') {
            return `${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (Mixed)`;
          }
          return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
          }).format(value);
        } catch (error) {
          // Fallback for invalid currency codes
          return `${reportData.summary.currency || 'USD'} ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
      }
    }

    // Format status
    if (key === 'status' && typeof value === 'string') {
      return (
        <Badge variant={
          value === 'paid' || value === 'completed' ? 'default' :
            value === 'pending' || value === 'draft' ? 'secondary' :
              value === 'overdue' || value === 'failed' ? 'destructive' :
                'outline'
        }>
          {value.replace('_', ' ').toUpperCase()}
        </Badge>
      );
    }

    // Ensure we always return a string or React element, never an object
    return String(value);
  };

  const getColumnHeaders = () => {
    if (reportData.data.length === 0) return [];

    const firstRow = reportData.data[0];
    return Object.keys(firstRow).filter(key =>
      !key.startsWith('_') && // Filter out internal fields
      key !== 'id' // Hide ID column for cleaner preview
    );
  };

  const formatColumnHeader = (header: string) => {
    return header
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <Card className="slide-in">
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Eye className="h-5 w-5 text-primary" />
          </div>
          Report Preview
        </CardTitle>
        <CardDescription>
          Preview of your {reportData.report_type} report
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Summary Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-muted/50 p-4 rounded-lg">
            <div className="text-2xl font-bold">{reportData.summary.total_records}</div>
            <div className="text-sm text-muted-foreground">Total Records</div>
          </div>
          {reportData.summary.total_amount !== undefined && (
            <div className="bg-muted/50 p-4 rounded-lg">
              <div className="text-2xl font-bold">
                {(() => {
                  const currency = reportData.summary.currency || 'USD';
                  // Handle mixed currencies or invalid currency codes
                  if (currency === 'Mixed' || currency === 'mixed') {
                    return `${reportData.summary.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (Mixed)`;
                  }
                  try {
                    return new Intl.NumberFormat('en-US', {
                      style: 'currency',
                      currency: currency,
                    }).format(reportData.summary.total_amount);
                  } catch (error) {
                    // Fallback for invalid currency codes
                    return `${currency} ${reportData.summary.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                  }
                })()}
              </div>
              <div className="text-sm text-muted-foreground">Total Amount</div>
            </div>
          )}
          {reportData.summary.date_range && (
            <div className="bg-muted/50 p-4 rounded-lg">
              <div className="text-sm font-medium">
                {reportData.summary.date_range.date_from &&
                  format(new Date(reportData.summary.date_range.date_from), 'MMM dd, yyyy')
                }
                {reportData.summary.date_range.date_from && reportData.summary.date_range.date_to && ' - '}
                {reportData.summary.date_range.date_to &&
                  format(new Date(reportData.summary.date_range.date_to), 'MMM dd, yyyy')
                }
              </div>
              <div className="text-sm text-muted-foreground">Date Range</div>
            </div>
          )}
        </div>

        {/* Key Metrics */}
        {Object.keys(reportData.summary.key_metrics).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-medium mb-3">Key Metrics</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(reportData.summary.key_metrics).map(([key, value]) => (
                <div key={key} className="bg-muted/30 p-3 rounded">
                  <div className="text-lg font-semibold">{formatValue(value, key)}</div>
                  <div className="text-xs text-muted-foreground">{formatColumnHeader(key)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Data Table */}
        {reportData.data.length > 0 ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">Sample Data</h4>
              <Badge variant="outline">
                Showing {Math.min(reportData.data.length, 10)} of {reportData.summary.total_records} records
              </Badge>
            </div>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    {getColumnHeaders().map((header) => (
                      <TableHead key={header} className="font-medium">
                        {formatColumnHeader(header)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reportData.data.slice(0, 10).map((row, index) => (
                    <TableRow key={index}>
                      {getColumnHeaders().map((header) => (
                        <TableCell key={header}>
                          {formatValue(row[header], header)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {reportData.data.length > 10 && (
              <p className="text-sm text-muted-foreground text-center">
                ... and {reportData.data.length - 10} more records
              </p>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No data found matching your filters.
          </div>
        )}
      </CardContent>
    </Card>
  );
};