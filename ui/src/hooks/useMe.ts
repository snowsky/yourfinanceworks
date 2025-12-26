import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api";
import { getCurrentUser } from "@/utils/auth";

export type MeResponse = {
    id: number;
    email: string;
    role: string;
    first_name?: string;
    last_name?: string;
    tenant_id?: number;
    is_superuser?: boolean;
    organizations?: any[];
};

export function useMe() {
    const user = getCurrentUser();

    return useQuery<MeResponse | null>({
        queryKey: ["me", user?.id],
        queryFn: async () => {
            if (!user?.id) return null;
            console.log('👤 Fetching user profile (me)');
            return await apiRequest("/auth/me") as MeResponse;
        },
        enabled: !!user?.id,
        staleTime: 1000 * 60 * 5, // 5 minutes cache
        gcTime: 1000 * 60 * 10, // 10 minutes garbage collection
    });
}
