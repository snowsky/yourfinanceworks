import { AppLayout } from "./AppLayout";
import { Outlet } from "react-router-dom";

export function AuthenticatedLayout() {
    return (
        <AppLayout>
            <Outlet />
        </AppLayout>
    );
}
