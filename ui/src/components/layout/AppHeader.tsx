import { useState, useEffect } from "react";
import { useSearch } from "@/components/search/SearchProvider";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import { InAppNotifications } from "@/components/reminders";
import { useTranslation } from "react-i18next";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useAppearanceSettings } from "@/hooks/useAppearanceSettings";
import { useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";

function useLiveClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export function AppHeader() {
  const { setIsOpen } = useSearch();
  const { t } = useTranslation();
  const clock = useLiveClock();
  const { settings } = useAppearanceSettings();
  const { data: tenantSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 5 * 60 * 1000,
  });
  const localTimezone = tenantSettings?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <SidebarTrigger />
      </div>
      <div className="flex items-center gap-4">
        {settings.showClock && (settings.showLocalClock || settings.showUTCClock) && (
          <div className="text-right hidden sm:block select-none space-y-0.5">
            {settings.showLocalClock && (
              <div className="flex items-center justify-end gap-1.5">
                <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">LCL</span>
                <div className="text-sm font-mono font-medium tabular-nums leading-tight">
                  {clock.toLocaleTimeString('en-US', { timeZone: localTimezone, hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
              </div>
            )}
            {settings.showUTCClock && (
              <div className="flex items-center justify-end gap-1.5">
                <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-wide">UTC</span>
                <div className="text-sm font-mono font-medium tabular-nums leading-tight">
                  {clock.toLocaleTimeString('en-US', { timeZone: 'UTC', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
              </div>
            )}
            {settings.showDate && (
              <div className="text-[11px] text-muted-foreground leading-tight">
                {clock.toLocaleDateString('en-US', { timeZone: localTimezone, weekday: 'short', month: 'short', day: 'numeric' })}
              </div>
            )}
          </div>
        )}
        <InAppNotifications />
        <Button
          variant="outline"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">{t('common.search')}</span>
          <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </Button>
      </div>
    </header>
  );
}
