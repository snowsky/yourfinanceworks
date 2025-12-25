import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";
import { getCurrentUser } from "@/utils/auth";

export type Organization = {
    id: number;
    name: string;
};

export function useOrganizations() {
    const user = getCurrentUser();

    return useQuery({
        queryKey: ["user-organizations", user?.id],
        queryFn: async () => {
            if (!user?.id) return [];
            console.log('🏢 Fetching organizations for user:', user.email);
            const response: any = await apiRequest("/auth/me", {}, { skipTenant: true });
            return (response?.organizations ?? []) as Organization[];
        },
        enabled: !!user?.id,
        staleTime: 1000 * 60 * 15, // 15 minutes cache
        gcTime: 1000 * 60 * 30, // 30 minutes garbage collection
    });
}
