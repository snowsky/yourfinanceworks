import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Camera, ChartColumnBig, Inbox, ReceiptText } from "lucide-react";

import { cn } from "@/lib/utils";

const navItems = [
  { to: "/m/capture", label: "Capture", icon: Camera },
  { to: "/m/inbox", label: "Inbox", icon: Inbox },
  { to: "/m/timeline", label: "Timeline", icon: ReceiptText },
  { to: "/m/insights", label: "Insights", icon: ChartColumnBig },
];

const titles: Record<string, string> = {
  "/m/capture": "Capture",
  "/m/inbox": "Inbox",
  "/m/timeline": "Timeline",
  "/m/insights": "Insights",
};

export default function MobileLayout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.12),_transparent_40%),linear-gradient(180deg,_hsl(var(--background))_0%,_hsl(var(--muted)/0.35)_100%)] text-foreground">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col">
        <header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 px-5 py-4 backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            YourFinanceWORKS Mobile
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            {titles[location.pathname] ?? "Finance"}
          </h1>
        </header>

        <main className="flex-1 px-4 pb-28 pt-4">
          <Outlet />
        </main>

        <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/95 px-3 pb-5 pt-3 backdrop-blur">
          <div className="mx-auto grid max-w-md grid-cols-4 gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex flex-col items-center justify-center rounded-2xl px-2 py-2 text-xs font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )
                  }
                >
                  <Icon className="mb-1 h-4 w-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      </div>
    </div>
  );
}
