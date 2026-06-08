import {
  Moon,
  Sun,
  Monitor,
  TerminalSquare,
  Flame,
  BookOpen,
  Palette,
  Check,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useTheme, type ThemeId } from './theme-provider';
import { ProfessionalButton } from './professional-button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from './dropdown-menu';

const THEME_ICONS: Record<ThemeId, LucideIcon> = {
  light: Sun,
  dark: Moon,
  terminal: TerminalSquare,
  'amber-terminal': Flame,
  sepia: BookOpen,
  system: Monitor,
};

export function ThemeSwitcher() {
  const { t } = useTranslation();
  const { theme, setTheme, themes } = useTheme();

  const ActiveIcon = THEME_ICONS[theme] ?? Palette;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <ProfessionalButton
          variant="ghost"
          size="icon-sm"
          className="h-8 w-8 border border-border/30 bg-background/20 hover:bg-background/30 transition-all duration-200"
          title={t('settings.appearance.theme', 'Theme')}
        >
          <ActiveIcon className="h-4 w-4" />
          <span className="sr-only">{t('settings.appearance.theme', 'Theme')}</span>
        </ProfessionalButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuLabel>{t('settings.appearance.theme', 'Theme')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {themes.map((def) => {
          const Icon = THEME_ICONS[def.id] ?? Palette;
          const selected = theme === def.id;
          const label = t(`settings.appearance.themes.${def.id}`, def.label) as string;
          return (
            <DropdownMenuItem
              key={def.id}
              onClick={() => setTheme(def.id)}
              className="flex items-center gap-2.5 cursor-pointer"
            >
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px] border border-black/10"
                style={{ backgroundColor: def.preview.bg, color: def.preview.accent }}
              >
                <Icon className="h-3 w-3" />
              </span>
              <span className="flex-1 text-sm">{label}</span>
              {selected && <Check className="h-4 w-4 text-primary" strokeWidth={3} />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
