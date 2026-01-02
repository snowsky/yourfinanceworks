import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { discountRulesApi, DiscountRule, DiscountRuleCreate, DiscountRuleUpdate } from '@/lib/api';

// Query key factory
export const discountRulesKeys = {
  all: ['discount-rules'] as const,
  lists: () => [...discountRulesKeys.all, 'list'] as const,
  list: () => [...discountRulesKeys.lists(), 'all'] as const,
  details: () => [...discountRulesKeys.all, 'detail'] as const,
  detail: (id: number) => [...discountRulesKeys.details(), id] as const,
};

// Hook for fetching discount rules with caching
export const useDiscountRules = (enabled = true) => {
  return useQuery({
    queryKey: discountRulesKeys.list(),
    queryFn: () => discountRulesApi.getDiscountRules(),
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
    retry: 2,
    refetchOnWindowFocus: false,
  });
};

// Hook for fetching a single discount rule
export const useDiscountRule = (id: number, enabled = true) => {
  return useQuery({
    queryKey: discountRulesKeys.detail(id),
    queryFn: () => discountRulesApi.getDiscountRule(id),
    enabled: enabled && !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });
};

// Hook for creating discount rules
export const useCreateDiscountRule = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (discountRule: DiscountRuleCreate) => discountRulesApi.createDiscountRule(discountRule),
    onSuccess: () => {
      toast.success('Discount rule created successfully');
      queryClient.invalidateQueries({ queryKey: discountRulesKeys.lists() });
    },
    onError: (error) => {
      toast.error(`Failed to create discount rule: ${error.message}`);
    },
  });
};

// Hook for updating discount rules
export const useUpdateDiscountRule = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, discountRule }: { id: number; discountRule: DiscountRuleUpdate }) =>
      discountRulesApi.updateDiscountRule(id, discountRule),
    onSuccess: (_, { id }) => {
      toast.success('Discount rule updated successfully');
      queryClient.invalidateQueries({ queryKey: discountRulesKeys.lists() });
      queryClient.invalidateQueries({ queryKey: discountRulesKeys.detail(id) });
    },
    onError: (error) => {
      toast.error(`Failed to update discount rule: ${error.message}`);
    },
  });
};

// Hook for deleting discount rules
export const useDeleteDiscountRule = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => discountRulesApi.deleteDiscountRule(id),
    onSuccess: () => {
      toast.success('Discount rule deleted successfully');
      queryClient.invalidateQueries({ queryKey: discountRulesKeys.lists() });
    },
    onError: (error) => {
      toast.error(`Failed to delete discount rule: ${error.message}`);
    },
  });
};

// Hook for calculating discounts
export const useCalculateDiscount = () => {
  return useMutation({
    mutationFn: (subtotal: number) => discountRulesApi.calculateDiscount(subtotal),
    onError: (error) => {
      console.error('Failed to calculate discount:', error);
    },
  });
};
