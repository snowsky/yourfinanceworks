import { useSearch } from "@/components/search/SearchProvider";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import { InAppNotifications } from "@/components/reminders";
import { useTranslation } from "react-i18next";
import { SidebarTrigger } from "@/components/ui/sidebar";

export function AppHeader() {
  const { setIsOpen } = useSearch();
  const { t } = useTranslation();

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <SidebarTrigger />
        {/* Add any other header content here */}
      </div>
      <div className="flex items-center gap-2">
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
