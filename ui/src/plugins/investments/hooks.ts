/**
 * Investment Plugin Hooks
 *
 * Custom React hooks for investment management operations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface Holding {
  id: number;
  portfolio_id: number;
  security_symbol: string;
  security_name?: string;
  security_type: string;
  asset_class: string;
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  current_price?: number;
  price_updated_at?: string;
  imported_price?: number;
  imported_price_date?: string;
  is_closed: boolean;
  average_cost_per_share: number;
  current_value: number;
  unrealized_gain_loss: number;
  created_at: string;
  updated_at: string;
}

interface Portfolio {
  id: number;
  name: string;
  portfolio_type: string;
  currency: string;
  created_at: string;
  updated_at: string;
}

/**
 * Hook to fetch holdings for a portfolio
 */
export const useHoldings = (portfolioId: number) => {
  return useQuery<Holding[]>({
    queryKey: ['holdings', portfolioId],
    queryFn: async () => {
      const response = await api.get(
        `/investments/portfolios/${portfolioId}/holdings`
      );
      return Array.isArray(response) ? response : [];
    },
    enabled: !!portfolioId,
  });
};

/**
 * Hook to fetch a single holding
 */
export const useHolding = (holdingId: number) => {
  return useQuery<Holding>({
    queryKey: ['holding', holdingId],
    queryFn: async () => {
      const response = await api.get(`/investments/holdings/${holdingId}`);
      return response as Holding;
    },
    enabled: !!holdingId,
  });
};

/**
 * Hook to fetch portfolio details
 */
export const usePortfolio = (portfolioId: number) => {
  return useQuery<Portfolio>({
    queryKey: ['portfolio', portfolioId],
    queryFn: async () => {
      const response = await api.get(`/investments/portfolios/${portfolioId}`);
      return response as Portfolio;
    },
    enabled: !!portfolioId,
  });
};

/**
 * Hook to create a new holding
 */
export const useCreateHolding = (portfolioId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (holdingData: any) => {
      const payload = {
        ...holdingData,
        quantity: parseFloat(holdingData.quantity),
        cost_basis: parseFloat(holdingData.cost_basis),
      };
      const response = await api.post(
        `/investments/portfolios/${portfolioId}/holdings`,
        payload
      );
      return response;
    },
    onSuccess: () => {
      toast.success('Holding created successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to create holding';
      toast.error(errorMessage);
    },
  });
};

/**
 * Hook to update a holding
 */
export const useUpdateHolding = (portfolioId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ holdingId, data }: { holdingId: number; data: any }) => {
      const payload = {
        ...data,
        quantity: parseFloat(data.quantity),
        cost_basis: parseFloat(data.cost_basis),
      };
      await api.put(`/investments/holdings/${holdingId}`, payload);
    },
    onSuccess: () => {
      toast.success('Holding updated successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to update holding';
      toast.error(errorMessage);
    },
  });
};

/**
 * Hook to update holding price
 */
export const useUpdateHoldingPrice = (portfolioId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ holdingId, price }: { holdingId: number; price: number }) => {
      // Use PUT instead of PATCH since the API client doesn't have patch method
      await api.put(`/investments/holdings/${holdingId}/price`, {
        current_price: price,
      });
    },
    onSuccess: () => {
      toast.success('Price updated successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to update price';
      toast.error(errorMessage);
    },
  });
};

/**
 * Hook to delete a holding
 */
export const useDeleteHolding = (portfolioId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (holdingId: number) => {
      await api.delete(`/investments/holdings/${holdingId}`);
    },
    onSuccess: () => {
      toast.success('Holding deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to delete holding';
      toast.error(errorMessage);
    },
  });
};

/**
 * Hook to calculate portfolio statistics
 */
export const usePortfolioStats = (holdings: Holding[]) => {
  const stats = {
    totalValue: holdings.reduce((sum, h) => sum + h.current_value, 0),
    totalCostBasis: holdings.reduce((sum, h) => sum + h.cost_basis, 0),
    totalUnrealizedGain: holdings.reduce((sum, h) => sum + h.unrealized_gain_loss, 0),
    activeHoldingsCount: holdings.filter(h => !h.is_closed).length,
    closedHoldingsCount: holdings.filter(h => h.is_closed).length,
    totalHoldingsCount: holdings.length,
    returnPercentage: holdings.reduce((sum, h) => sum + h.cost_basis, 0) > 0
      ? (holdings.reduce((sum, h) => sum + h.unrealized_gain_loss, 0) / holdings.reduce((sum, h) => sum + h.cost_basis, 0)) * 100
      : 0,
  };

  return stats;
};

/**
 * Hook to group holdings by asset class
 */
export const useHoldingsByAssetClass = (holdings: Holding[]) => {
  const grouped: Record<string, Holding[]> = {};

  holdings.forEach(holding => {
    if (!grouped[holding.asset_class]) {
      grouped[holding.asset_class] = [];
    }
    grouped[holding.asset_class].push(holding);
  });

  return grouped;
};

/**
 * Hook to calculate asset allocation percentages
 */
export const useAssetAllocation = (holdings: Holding[]) => {
  const totalValue = holdings.reduce((sum, h) => sum + h.current_value, 0);

  const allocation = Object.entries(
    holdings.reduce((acc: Record<string, number>, holding) => {
      acc[holding.asset_class] = (acc[holding.asset_class] || 0) + holding.current_value;
      return acc;
    }, {})
  ).map(([assetClass, value]) => ({
    assetClass,
    value,
    percentage: totalValue > 0 ? (value / totalValue) * 100 : 0,
  }));

  return allocation;
};

/**
 * Format currency value
 */
export const formatCurrency = (amount: number, currency = 'USD') => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount);
};

/**
 * Format percentage value
 */
export const formatPercentage = (percentage: number, decimals = 2) => {
  return `${percentage >= 0 ? '+' : ''}${percentage.toFixed(decimals)}%`;
};

/**
 * Get color for gain/loss
 */
export const getGainLossColor = (value: number) => {
  if (value > 0) return 'text-green-600';
  if (value < 0) return 'text-red-600';
  return 'text-gray-600';
};

/**
 * Get asset class color
 */
export const getAssetClassColor = (assetClass: string) => {
  const colors: Record<string, string> = {
    'stocks': 'bg-blue-100 text-blue-800',
    'bonds': 'bg-green-100 text-green-800',
    'cash': 'bg-gray-100 text-gray-800',
    'real_estate': 'bg-orange-100 text-orange-800',
    'commodities': 'bg-yellow-100 text-yellow-800',
  };
  return colors[assetClass] || 'bg-gray-100 text-gray-800';
};


/**
 * Hook to archive a portfolio
 */
export const useArchivePortfolio = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (portfolioId: number) => {
      await api.put(`/investments/portfolios/${portfolioId}`, {
        is_archived: true,
      });
    },
    onSuccess: () => {
      toast.success('Portfolio archived successfully');
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to archive portfolio';
      toast.error(errorMessage);
    },
  });
};

/**
 * Hook to unarchive a portfolio
 */
export const useUnarchivePortfolio = () => {
  const queryClient = useQueryClient();

  return useMutation({
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
};
