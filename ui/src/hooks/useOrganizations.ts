import { useQuery } from "@tanstack/react-query";
import { getCurrentUser } from "@/utils/auth";
import { useMe } from "./useMe";

export type Organization = {
    id: number;
    name: string;
    role?: string;
};

export function useOrganizations() {
    const user = getCurrentUser();
    const { data: meData } = useMe();

    return useQuery({
        queryKey: ["user-organizations", user?.id],
        queryFn: async () => {
            // Use data from useMe hook instead of making a duplicate request
            return (meData?.organizations ?? []) as Organization[];
        },
        enabled: !!user?.id && !!meData,
        staleTime: 1000 * 60 * 15, // 15 minutes cache
        gcTime: 1000 * 60 * 30, // 30 minutes garbage collection
    });
}
