import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight, Calendar, DollarSign, FileText, Percent, User, CreditCard } from "lucide-react";
import { formatDate } from '@/lib/utils';

interface InvoiceHistoryDetailsModalProps {
  open: boolean;
  onClose: () => void;
  historyEntry: {
    id: number | string;
    action: string;
    details?: string;
    previous_values?: Record<string, any>;
    current_values?: Record<string, any>;
    created_at: string;
    user_name?: string;
  };
}

const formatValue = (key: string, value: any): string => {
  if (value === null || value === undefined || value === '') {
    return 'Not set';
  }
  
  switch (key) {
    case 'amount':
    case 'subtotal':
    case 'discount_value':
      return typeof value === 'number' ? `$${value.toFixed(2)}` : `$${parseFloat(value || 0).toFixed(2)}`;
    case 'due_date':
      return formatDate(value);
    case 'currency':
      return value.toUpperCase();
    case 'discount_type':
      return value === 'percentage' ? 'Percentage' : 'Fixed Amount';
    case 'notes':
      return value || 'No notes';
    default:
      return String(value);
  }
};

const getFieldIcon = (key: string) => {
  switch (key) {
    case 'amount':
    case 'subtotal':
      return <DollarSign className="w-4 h-4" />;
    case 'due_date':
      return <Calendar className="w-4 h-4" />;
    case 'currency':
      return <CreditCard className="w-4 h-4" />;
    case 'discount_type':
    case 'discount_value':
      return <Percent className="w-4 h-4" />;
    case 'notes':
      return <FileText className="w-4 h-4" />;
    default:
      return null;
  }
};

const getFieldLabel = (key: string): string => {
  switch (key) {
    case 'amount':
      return 'Total Amount';
    case 'subtotal':
      return 'Subtotal';
    case 'due_date':
      return 'Due Date';
    case 'currency':
      return 'Currency';
    case 'discount_type':
      return 'Discount Type';
    case 'discount_value':
      return 'Discount Value';
    case 'notes':
      return 'Notes';
    default:
      return key.charAt(0).toUpperCase() + key.slice(1).replace('_', ' ');
  }
};

export function InvoiceHistoryDetailsModal({ open, onClose, historyEntry }: InvoiceHistoryDetailsModalProps) {
  const { previous_values, current_values, action, details, created_at, user_name } = historyEntry;
  
  // Get all changed fields
  const changedFields = new Set([
    ...(previous_values ? Object.keys(previous_values) : []),
    ...(current_values ? Object.keys(current_values) : [])
  ]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Change Details
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4">
          {/* Header Information */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Badge variant="outline">{action}</Badge>
                <span className="text-sm text-muted-foreground">
                  {formatDate(created_at)}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {user_name && (
                  <div className="flex items-center gap-2 text-sm">
                    <User className="w-4 h-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Changed by:</span>
                    <span className="font-medium">{user_name}</span>
                  </div>
                )}
                {details && (
                  <div className="text-sm text-muted-foreground">
                    <span className="font-medium">Summary:</span> {details}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Changes Details */}
          {changedFields.size > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Field Changes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Array.from(changedFields).map((field) => {
                    const previousValue = previous_values?.[field];
                    const currentValue = current_values?.[field];
                    
                    // Skip if both values are the same
                    if (previousValue === currentValue) {
                      return null;
                    }
                    
                    return (
                      <div key={field} className="border rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          {getFieldIcon(field)}
                          <span className="font-medium">{getFieldLabel(field)}</span>
                        </div>
                        
                        <div className="flex items-center gap-3 text-sm">
                          <div className="flex-1">
                            <div className="text-muted-foreground mb-1">Previous:</div>
                            <div className="bg-red-50 border border-red-200 rounded px-2 py-1 text-red-800">
                              {formatValue(field, previousValue)}
                            </div>
                          </div>
                          
                          <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
                          
                          <div className="flex-1">
                            <div className="text-muted-foreground mb-1">Current:</div>
                            <div className="bg-green-50 border border-green-200 rounded px-2 py-1 text-green-800">
                              {formatValue(field, currentValue)}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* No changes message */}
          {changedFields.size === 0 && (
            <Card>
              <CardContent className="text-center py-8">
                <div className="text-muted-foreground">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No detailed change information available for this entry.</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
} 