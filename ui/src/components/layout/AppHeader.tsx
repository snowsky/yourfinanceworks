import { useSearch } from "@/components/search/SearchProvider";
import { Button } from "@/components/ui/button";
import { Search, Rows3, Rows2 } from "lucide-react";
import { InAppNotifications } from "@/components/reminders";
import { useTranslation } from "react-i18next";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useListDensity } from "@/hooks/use-list-density";

export function AppHeader() {
  const { setIsOpen } = useSearch();
  const { t } = useTranslation();
  const { density, toggleDensity } = useListDensity();

  return (
    <header className="flex items-center justify-between px-5 py-3 border-b bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <SidebarTrigger />
        {/* Add any other header content here */}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          onClick={toggleDensity}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
          title={density === "compact"
            ? t("common.list_density_comfortable", { defaultValue: "Switch to comfortable list density" })
            : t("common.list_density_compact", { defaultValue: "Switch to compact list density" })}
          aria-label={density === "compact"
            ? t("common.list_density_comfortable", { defaultValue: "Switch to comfortable list density" })
            : t("common.list_density_compact", { defaultValue: "Switch to compact list density" })}
        >
          {density === "compact" ? <Rows3 className="h-4 w-4" /> : <Rows2 className="h-4 w-4" />}
          <span className="hidden sm:inline">
            {density === "compact"
              ? t("common.comfortable", { defaultValue: "Comfortable" })
              : t("common.compact", { defaultValue: "Compact" })}
          </span>
        </Button>
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
