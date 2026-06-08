import React from "react";
import { useTranslation } from "react-i18next";
import { Check, Palette } from "lucide-react";
import {
  ProfessionalCard,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardContent,
} from "@/components/ui/professional-card";
import { useTheme, type ThemeDefinition } from "@/components/ui/theme-provider";
import { cn } from "@/lib/utils";

/**
 * A small "browser window" preview rendered from a theme's swatch colors so
 * users can see each theme at a glance before selecting it.
 */
function ThemeSwatch({ preview }: { preview: ThemeDefinition["preview"] }) {
  return (
    <div
      className="relative h-20 w-full overflow-hidden rounded-md border border-black/10 shadow-inner"
      style={{ backgroundColor: preview.bg }}
      aria-hidden="true"
    >
      {/* title bar */}
      <div
        className="flex items-center gap-1 px-2 py-1"
        style={{ backgroundColor: preview.surface }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: preview.accent }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full opacity-60"
          style={{ backgroundColor: preview.text }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full opacity-30"
          style={{ backgroundColor: preview.text }}
        />
      </div>
      {/* body: a metric card mock */}
      <div className="space-y-1.5 p-2">
        <div
          className="rounded-sm px-1.5 py-1"
          style={{ backgroundColor: preview.surface }}
        >
          <div
            className="h-1.5 w-8 rounded-full"
            style={{ backgroundColor: preview.accent }}
          />
          <div
            className="mt-1 h-2 w-12 rounded-full"
            style={{ backgroundColor: preview.text }}
          />
        </div>
        <div className="flex gap-1">
          <div
            className="h-1.5 w-10 rounded-full opacity-70"
            style={{ backgroundColor: preview.text }}
          />
          <div
            className="h-1.5 w-6 rounded-full"
            style={{ backgroundColor: preview.accent }}
          />
        </div>
      </div>
    </div>
  );
}

export const ThemePicker: React.FC = () => {
  const { t } = useTranslation();
  const { theme, setTheme, themes } = useTheme();

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="text-base font-semibold flex items-center gap-2">
          <Palette className="w-4 h-4 text-primary" />
          {t("settings.appearance.theme", "Theme")}
        </ProfessionalCardTitle>
        <p className="text-sm text-muted-foreground">
          {t(
            "settings.appearance.theme_description",
            "Choose the color scheme used across the app. Your choice is saved on this device."
          )}
        </p>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div
          role="radiogroup"
          aria-label={t("settings.appearance.theme", "Theme")}
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
        >
          {themes.map((def) => {
            const selected = theme === def.id;
            const label = t(
              `settings.appearance.themes.${def.id}`,
              def.label
            ) as string;
            const description = t(
              `settings.appearance.themes.${def.id}_description`,
              def.description
            ) as string;
            return (
              <button
                key={def.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setTheme(def.id)}
                className={cn(
                  "group relative flex flex-col gap-3 rounded-xl border p-3 text-left transition-all duration-200",
                  "hover:border-primary/60 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected
                    ? "border-primary ring-2 ring-primary/30 bg-primary/5"
                    : "border-border bg-muted/20"
                )}
              >
                {selected && (
                  <span className="absolute right-2 top-2 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
                    <Check className="h-3 w-3" strokeWidth={3} />
                  </span>
                )}
                <ThemeSwatch preview={def.preview} />
                <div className="space-y-0.5">
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="text-xs leading-snug text-muted-foreground">
                    {description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};
