import { AppLayout } from "./AppLayout";
import { Outlet } from "react-router-dom";
import { TimerProvider } from "@/contexts/TimerContext";
import { TimerWidget } from "@/components/projects/TimerWidget";

export function AuthenticatedLayout() {
    return (
        <TimerProvider>
            <AppLayout>
                <Outlet />
                <TimerWidget />
            </AppLayout>
        </TimerProvider>
    );
}
