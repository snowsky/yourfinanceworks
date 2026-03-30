import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Wallet } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { expenseApi } from "@/lib/api";

function asCurrency(value: number | undefined, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

export default function MobileInsights() {
  const { data, isLoading } = useQuery({
    queryKey: ["mobile-insights"],
    queryFn: () => expenseApi.getExpenseSummary({ period: "month", compare_with_previous: true }),
  });

  const cards = useMemo(() => {
    const currentTotal = data?.current_period?.total_amount ?? 0;
    const previousTotal = data?.previous_period?.total_amount ?? 0;
    const change = data?.changes?.total_amount_percent ?? 0;

    return [
      {
        title: "This month",
        value: asCurrency(currentTotal),
        detail: `${data?.current_period?.count ?? 0} expenses`,
        icon: Wallet,
      },
      {
        title: "Previous month",
        value: asCurrency(previousTotal),
        detail: `${data?.previous_period?.count ?? 0} expenses`,
        icon: change > 0 ? ArrowUpRight : ArrowDownRight,
      },
      {
        title: "Change",
        value: `${change >= 0 ? "+" : ""}${Number(change).toFixed(1)}%`,
        detail: "Compared with previous period",
        icon: change > 0 ? ArrowUpRight : ArrowDownRight,
      },
    ];
  }, [data]);

  return (
    <div className="space-y-4">
      <Card className="rounded-3xl border-none bg-gradient-to-br from-slate-950 to-slate-800 text-white shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl">Simple, personal, glanceable</CardTitle>
          <CardDescription className="text-slate-300">
            Mobile insights should answer “how am I doing?” in a few seconds.
          </CardDescription>
        </CardHeader>
      </Card>

      {isLoading ? (
        <Card className="rounded-3xl">
          <CardContent className="p-6 text-sm text-muted-foreground">Loading monthly summary...</CardContent>
        </Card>
      ) : (
        cards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.title} className="rounded-3xl">
              <CardContent className="flex items-center justify-between p-5">
                <div>
                  <p className="text-sm text-muted-foreground">{card.title}</p>
                  <p className="mt-1 text-2xl font-semibold">{card.value}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{card.detail}</p>
                </div>
                <div className="rounded-2xl bg-muted p-3">
                  <Icon className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>
          );
        })
      )}

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-lg">Category breakdown</CardTitle>
          <CardDescription>
            This is a placeholder for the first mobile chart card.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(data?.category_breakdown ?? []).slice(0, 5).map((category: any) => (
            <div key={category.category} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span>{category.category}</span>
                <span className="font-medium">{asCurrency(category.total_amount)}</span>
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div
                  className="h-2 rounded-full bg-primary"
                  style={{ width: `${Math.min(100, Number(category.percentage || 0))}%` }}
                />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
