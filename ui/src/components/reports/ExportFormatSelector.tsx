import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { FileText, Download, Loader2, FileSpreadsheet, File } from 'lucide-react';

interface ExportFormatSelectorProps {
  selectedFormat: 'pdf' | 'csv' | 'excel' | 'json';
  onFormatChange: (format: 'pdf' | 'csv' | 'excel' | 'json') => void;
  onExport: () => void;
  loading: boolean;
  disabled?: boolean;
}

const formatOptions = [
  {
    value: 'pdf' as const,
    label: 'PDF',
    description: 'Professional formatted report with branding',
    icon: <FileText className="h-4 w-4" />,
    recommended: true,
  },
  {
    value: 'excel' as const,
    label: 'Excel',
    description: 'Spreadsheet format with multiple sheets and formatting',
    icon: <FileSpreadsheet className="h-4 w-4" />,
    recommended: false,
  },
  {
    value: 'csv' as const,
    label: 'CSV',
    description: 'Simple comma-separated values for data analysis',
    icon: <File className="h-4 w-4" />,
    recommended: false,
  },
  {
    value: 'json' as const,
    label: 'JSON',
    description: 'Raw data format for API consumption',
    icon: <File className="h-4 w-4" />,
    recommended: false,
  },
];

export const ExportFormatSelector: React.FC<ExportFormatSelectorProps> = ({
  selectedFormat,
  onFormatChange,
  onExport,
  loading,
  disabled = false,
}) => {
  const selectedOption = formatOptions.find(option => option.value === selectedFormat);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export Format</CardTitle>
        <CardDescription>Choose how you want to export your report</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Format Selection */}
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {formatOptions.map((option) => (
              <Button
                key={option.value}
                variant={selectedFormat === option.value ? "default" : "outline"}
                className="h-auto p-4 flex flex-col items-start space-y-2"
                onClick={() => onFormatChange(option.value)}
                disabled={disabled}
              >
                <div className="flex items-center gap-2 w-full">
                  {option.icon}
                  <span className="font-medium">{option.label}</span>
                  {option.recommended && (
                    <Badge variant="secondary" className="ml-auto text-xs">
                      Recommended
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground text-left">
                  {option.description}
                </p>
              </Button>
            ))}
          </div>
        </div>

        {/* Selected Format Details */}
        {selectedOption && (
          <div className="bg-muted/50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              {selectedOption.icon}
              <span className="font-medium">{selectedOption.label} Format</span>
            </div>
            <p className="text-sm text-muted-foreground">
              {selectedOption.description}
            </p>
            
            {/* Format-specific information */}
            {selectedFormat === 'pdf' && (
              <div className="mt-3 space-y-1">
                <p className="text-xs text-muted-foreground">✓ Professional formatting</p>
                <p className="text-xs text-muted-foreground">✓ Company branding</p>
                <p className="text-xs text-muted-foreground">✓ Print-ready layout</p>
              </div>
            )}
            {selectedFormat === 'excel' && (
              <div className="mt-3 space-y-1">
                <p className="text-xs text-muted-foreground">✓ Multiple worksheets</p>
                <p className="text-xs text-muted-foreground">✓ Formatted cells</p>
                <p className="text-xs text-muted-foreground">✓ Charts and graphs</p>
              </div>
            )}
            {selectedFormat === 'csv' && (
              <div className="mt-3 space-y-1">
                <p className="text-xs text-muted-foreground">✓ Universal compatibility</p>
                <p className="text-xs text-muted-foreground">✓ Easy data import</p>
                <p className="text-xs text-muted-foreground">✓ Lightweight format</p>
              </div>
            )}
            {selectedFormat === 'json' && (
              <div className="mt-3 space-y-1">
                <p className="text-xs text-muted-foreground">✓ Structured data</p>
                <p className="text-xs text-muted-foreground">✓ API integration</p>
                <p className="text-xs text-muted-foreground">✓ Programmatic access</p>
              </div>
            )}
          </div>
        )}

        {/* Export Button */}
        <Button 
          onClick={onExport} 
          disabled={disabled || loading}
          className="w-full"
          size="lg"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating Report...
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export as {selectedOption?.label}
            </>
          )}
        </Button>

        {/* Export Tips */}
        <div className="text-xs text-muted-foreground space-y-1">
          <p>💡 <strong>Tip:</strong> PDF format is recommended for sharing and presentations.</p>
          <p>💡 <strong>Tip:</strong> Use Excel or CSV for further data analysis.</p>
        </div>
      </CardContent>
    </Card>
  );
};