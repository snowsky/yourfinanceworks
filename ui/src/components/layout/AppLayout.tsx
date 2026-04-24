
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { Toaster } from "sonner";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background" style={{
        backgroundImage: 'radial-gradient(hsl(var(--border)) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }}>
        <AppSidebar />
        <div className="min-w-0 flex-1 flex flex-col min-h-screen">
          <AppHeader />
          <main className="min-w-0 flex-1 p-4 md:p-8">
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
