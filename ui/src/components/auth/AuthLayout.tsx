import type { ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ThemeSwitcher } from "@/components/ui/theme-switcher";
import { LanguageSwitcher } from "@/components/ui/language-switcher";
import { cn } from "@/lib/utils";
import { AuthBrandPanel } from "./AuthBrandPanel";
import { BrandMark } from "./BrandMark";

interface AuthLayoutProps {
  children: ReactNode;
  /** "top" suits long forms that scroll; "center" suits short ones. */
  align?: "center" | "top";
}

/**
 * Page frame shared by the sign-in family (sign in, sign up, forgot and reset
 * password): brand panel on the left, language and theme controls top-right,
 * and one narrow form column.
 */
export function AuthLayout({ children, align = "center" }: AuthLayoutProps) {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <AuthBrandPanel />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="flex items-center justify-end gap-3 px-6 pt-4">
          <LanguageSwitcher />
          <ThemeSwitcher />
        </div>

        <main
          className={cn(
            "flex-1 flex flex-col items-center px-6 sm:px-10",
            align === "center" ? "justify-center py-10" : "justify-start pt-8 pb-12",
          )}
        >
          {/* Small-screen logo; the brand panel carries it on desktop */}
          <div className="lg:hidden mb-8 text-center w-full">
            <BrandMark size="sm" className="justify-center mb-1" />
            <p className="text-muted-foreground text-xs">{t("auth.brand.product_line")}</p>
          </div>

          <div className="w-full max-w-sm">{children}</div>
        </main>
      </div>
    </div>
  );
}

export function AuthHeading({ title, description }: { title: ReactNode; description?: ReactNode }) {
  return (
    <div className="mb-8">
      <h1 className="text-2xl font-bold text-foreground tracking-tight">{title}</h1>
      {description && <p className="text-muted-foreground text-sm mt-1">{description}</p>}
    </div>
  );
}

export function AuthErrorBanner({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="mb-5 flex items-start gap-3 bg-destructive/10 border border-destructive/30 text-destructive px-4 py-3 rounded-xl"
    >
      <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" aria-hidden="true" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
