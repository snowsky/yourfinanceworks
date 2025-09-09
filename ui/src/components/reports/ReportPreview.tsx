import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Loader2, Eye, EyeOff } from 'lucide-react';
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
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            Generating Preview...
          </CardTitle>
          <CardDescription>Please wait while we generate your report preview</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="animate-pulse space-y-2">
              <div className="h-4 bg-gray-200 rounded w-1/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              <div className="h-4 bg-gray-200 rounded w-1/3"></div>
            </div>
            <div className="animate-pulse">
              <div className="h-32 bg-gray-200 rounded"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <EyeOff className="h-5 w-5" />
            Preview Error
          </CardTitle>
          <CardDescription>There was an error generating the preview</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={onRefresh} variant="outline">
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!reportData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Report Preview
          </CardTitle>
          <CardDescription>Configure your filters and click preview to see a sample of your report</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No preview available. Please configure your filters and generate a preview.
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
        return value.join(', ');
      }
      // For other objects, try to extract meaningful data or stringify
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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Eye className="h-5 w-5" />
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