import React from 'react';
import { Button } from '@/components/ui/button';
import { FileText, Users, CreditCard, Receipt, Building, Package, FileSpreadsheet } from 'lucide-react';
import { ReportType } from '@/lib/api';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

interface ReportTypeSelectorProps {
  reportTypes: ReportType[];
  selectedType: string | null;
  onTypeSelect: (type: string) => void;
  loading?: boolean;
}

const getReportIcon = (type: string) => {
  switch (type) {
    case 'client':
      return <Users className="h-6 w-6" />;
    case 'invoice':
      return <FileText className="h-6 w-6" />;
    case 'payment':
      return <CreditCard className="h-6 w-6" />;
    case 'expense':
      return <Receipt className="h-6 w-6" />;
    case 'statement':
      return <Building className="h-6 w-6" />;
    case 'inventory':
      return <Package className="h-6 w-6" />;
    default:
      return <FileText className="h-6 w-6" />;
  }
};

export const ReportTypeSelector: React.FC<ReportTypeSelectorProps> = ({
  reportTypes,
  selectedType,
  onTypeSelect,
  loading = false,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="animate-pulse">
            <div className="h-32 bg-muted/50 rounded-xl border border-border/50 p-6">
              <div className="flex items-center space-x-3 mb-4">
                <div className="h-8 w-8 bg-muted rounded-lg"></div>
                <div className="h-4 bg-muted rounded w-20"></div>
              </div>
              <div className="h-3 bg-muted rounded w-full mb-2"></div>
              <div className="h-3 bg-muted rounded w-3/4"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {reportTypes.map((reportType) => (
        <Button
          key={reportType.type}
          variant={selectedType === reportType.type ? "default" : "outline"}
          className={`
            h-auto p-6 flex flex-col items-center space-y-4 rounded-xl border-2 transition-all duration-200
            ${selectedType === reportType.type
              ? 'border-primary shadow-lg scale-105'
              : 'border-border/50 hover:border-primary/30 hover:shadow-md'
            }
          `}
          onClick={() => {
            onTypeSelect(reportType.type);
            navigate(`/reports/${reportType.type}`);
          }}
        >
          <div className={`
            p-3 rounded-xl transition-colors duration-200
            ${selectedType === reportType.type
              ? 'bg-primary-foreground text-primary'
              : 'bg-muted/50 text-muted-foreground'
            }
          `}>
            {getReportIcon(reportType.type)}
          </div>
          <div className="text-center space-y-2">
            <div className={`
              font-semibold text-sm
              ${selectedType === reportType.type
                ? 'text-primary-foreground'
                : 'text-foreground'
              }
            `}>
              {reportType.name}
            </div>
            <div className={`
              text-xs leading-relaxed
              ${selectedType === reportType.type
                ? 'text-primary-foreground/80'
                : 'text-muted-foreground'
              }
            `}>
              {reportType.description}
            </div>
          </div>
        </Button>
      ))}

      <Button
        key="accounting-tax-export"
        variant={selectedType === 'accounting-tax-export' ? "default" : "outline"}
        className={`
          h-auto p-6 flex flex-col items-center space-y-4 rounded-xl border-2 transition-all duration-200
          ${selectedType === 'accounting-tax-export'
            ? 'border-primary shadow-lg scale-105'
            : 'border-border/50 hover:border-primary/30 hover:shadow-md'
          }
        `}
        onClick={() => {
          onTypeSelect('accounting-tax-export');
          navigate('/reports/accounting-tax-export');
        }}
      >
        <div className={`
          p-3 rounded-xl transition-colors duration-200
          ${selectedType === 'accounting-tax-export'
            ? 'bg-primary-foreground text-primary'
            : 'bg-muted/50 text-muted-foreground'
          }
        `}>
          <FileSpreadsheet className="h-6 w-6" />
        </div>
        <div className="text-center space-y-2">
          <div className={`
            font-semibold text-sm
            ${selectedType === 'accounting-tax-export'
              ? 'text-primary-foreground'
              : 'text-foreground'
            }
          `}>
            {t('reports.accounting_tax_export.title', 'Accounting & Tax Export')}
          </div>
          <div className={`
            text-xs leading-relaxed
            ${selectedType === 'accounting-tax-export'
              ? 'text-primary-foreground/80'
              : 'text-muted-foreground'
            }
          `}>
            {t(
              'reports.accounting_tax_export.description',
              'Dedicated accountant-facing exports, separate from processed-document exports.'
            )}
          </div>
        </div>
      </Button>
    </div>
  );
};
