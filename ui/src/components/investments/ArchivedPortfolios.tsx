import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Archive, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface Portfolio {
  id: number;
  name: string;
  portfolio_type: string;
  currency: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

const ArchivedPortfolios: React.FC = () => {
  const queryClient = useQueryClient();
  const [isExpanded, setIsExpanded] = useState(false);

  // Fetch archived portfolios
  const { data: archivedPortfolios = [], isLoading } = useQuery<Portfolio[]>({
    queryKey: ['portfolios', 'archived'],
    queryFn: async () => {
      const response = await api.get('/investments/portfolios?include_archived=true');
      const allPortfolios = Array.isArray(response) ? response : [];
      return allPortfolios.filter((p: Portfolio) => p.is_archived);
    },
  });

  // Unarchive portfolio mutation
  const unarchivePortfolioMutation = useMutation({
    mutationFn: async (portfolioId: number) => {
      await api.put(`/investments/portfolios/${portfolioId}`, {
        is_archived: false,
      });
    },
    onSuccess: () => {
      toast.success('Portfolio restored successfully');
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to restore portfolio';
      toast.error(errorMessage);
    },
  });

  const getPortfolioTypeColor = (type: string) => {
    switch (type) {
      case 'taxable':
        return 'bg-blue-100 text-blue-800';
      case 'retirement':
        return 'bg-green-100 text-green-800';
      case 'business':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getPortfolioTypeLabel = (type: string) => {
    switch (type) {
      case 'taxable':
        return 'Taxable';
      case 'retirement':
        return 'Retirement';
      case 'business':
        return 'Business';
      default:
        return type;
    }
  };

  if (archivedPortfolios.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-muted hover:bg-muted/80 rounded-lg border border-border transition-colors"
      >
        <div className="flex items-center gap-3">
          <Archive className="w-5 h-5 text-muted-foreground" />
          <div className="text-left">
            <h3 className="font-medium text-foreground">Archived Portfolios</h3>
            <p className="text-sm text-muted-foreground">{archivedPortfolios.length} archived</p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"></div>
            </div>
          ) : (
            archivedPortfolios.map((portfolio) => (
              <ProfessionalCard key={portfolio.id} className="opacity-75">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg text-muted-foreground">{portfolio.name}</CardTitle>
                      <CardDescription>
                        Archived {new Date(portfolio.updated_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                    <Badge className={getPortfolioTypeColor(portfolio.portfolio_type)}>
                      {getPortfolioTypeLabel(portfolio.portfolio_type)}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => unarchivePortfolioMutation.mutate(portfolio.id)}
                    disabled={unarchivePortfolioMutation.isPending}
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Restore
                  </Button>
                </CardContent>
              </ProfessionalCard>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default ArchivedPortfolios;
