import { TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";

// Decorative sample figures for the product preview. Not real data.
const SAMPLE_BALANCE = "$84,210.55";
const SAMPLE_INVOICES = [
  { id: "INV-1042", client: "Northwind", amount: "$3,400.00", status: "paid" as const },
  { id: "INV-1043", client: "Lakeside", amount: "$1,250.00", status: "due" as const },
];
const TREND_LINE = "M0 34 L24 30 L48 32 L72 24 L96 26 L120 18 L144 21 L168 13 L192 15 L216 8 L240 5";

/**
 * Left-hand panel shared by the sign-in and sign-up pages (desktop only).
 * Shows a small product preview instead of marketing claims. Uses theme
 * tokens only, so it follows whichever theme is active.
 */
export function AuthBrandPanel() {
  const { t } = useTranslation();

  return (
    <aside className="hidden lg:flex lg:w-[44%] xl:w-2/5 max-w-3xl flex-shrink-0 flex-col p-12 bg-muted/40 border-r border-border lg:sticky lg:top-0 lg:h-screen lg:self-start overflow-hidden">
      {/* One centred column, so the logo and preview stay together on wide screens */}
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col min-h-0">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
          <TrendingUp className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
        </div>
        <span className="text-foreground text-lg font-bold tracking-tight leading-none">
          YourFinanceWORKS
        </span>
      </div>

      <div className="flex flex-1 flex-col justify-center py-10 min-h-0">
        <h2 className="text-foreground text-3xl font-semibold tracking-tight leading-tight">
          {t("auth.brand.headline")}
        </h2>
        <p className="text-muted-foreground text-sm leading-relaxed mt-3 text-balance">
          {t("auth.brand.tagline")}
        </p>

        <div aria-hidden="true" className="mt-10 space-y-4 select-none">
          <div className="rounded-xl border border-border bg-card text-card-foreground p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("auth.brand.cash_position")}
            </p>
            <div className="mt-1 flex items-baseline gap-2 flex-wrap">
              <span className="font-mono text-3xl font-bold tracking-tight">{SAMPLE_BALANCE}</span>
              <span className="text-xs font-semibold text-primary">{t("auth.brand.trend")}</span>
            </div>
            <svg viewBox="0 0 240 44" preserveAspectRatio="none" className="mt-3 block h-14 w-full text-primary">
              <path d={`${TREND_LINE} L240 44 L0 44Z`} fill="currentColor" opacity="0.1" />
              <path
                d={TREND_LINE}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
          </div>

          <div className="rounded-xl border border-border bg-card text-card-foreground px-5 py-1 shadow-sm divide-y divide-border">
            {SAMPLE_INVOICES.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between gap-3 py-3 text-sm">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="truncate">
                    {inv.id} · {inv.client}
                  </span>
                  <span
                    className={
                      inv.status === "paid"
                        ? "flex-shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary"
                        : "flex-shrink-0 rounded-full bg-warning/15 px-2 py-0.5 text-[11px] font-semibold text-warning"
                    }
                  >
                    {inv.status === "paid" ? t("auth.brand.status_paid") : t("auth.brand.status_due")}
                  </span>
                </span>
                <span className="font-mono font-medium flex-shrink-0">{inv.amount}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      </div>
    </aside>
  );
}
