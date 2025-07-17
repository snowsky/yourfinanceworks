
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { Toaster } from "sonner";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AppSidebar />
        <main className="flex-1 min-h-screen p-6 md:p-8 overflow-auto">
          {children}
        </main>
        <Toaster position="bottom-center" richColors />
      </div>
    </SidebarProvider>
  );
}
