import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { expenseApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const filters = [
  { key: "all", label: "All" },
  { key: "today", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
] as const;

export default function MobileTimeline() {
  const [activeFilter, setActiveFilter] = useState<(typeof filters)[number]["key"]>("all");
  const { data, isLoading } = useQuery({
    queryKey: ["mobile-timeline"],
    queryFn: () => expenseApi.getExpensesPaginated({ limit: 50, skip: 0 }),
  });

  const expenses = useMemo(() => {
    const all = data?.expenses ?? [];
    const now = new Date();

    return all.filter((expense) => {
      if (activeFilter === "all") return true;

      const expenseDate = new Date(`${expense.expense_date}T00:00:00`);
      const diffDays = Math.floor((now.getTime() - expenseDate.getTime()) / 86_400_000);

      if (activeFilter === "today") return diffDays === 0;
      if (activeFilter === "week") return diffDays >= 0 && diffDays < 7;
      if (activeFilter === "month") {
        return expenseDate.getMonth() === now.getMonth() && expenseDate.getFullYear() === now.getFullYear();
      }

      return true;
    });
  }, [activeFilter, data?.expenses]);

  return (
    <div className="space-y-4">
      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-lg">Recent spending</CardTitle>
          <CardDescription>
            Keep the mobile view scannable: amount first, details second.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2 overflow-x-auto pb-1">
          {filters.map((filter) => (
            <Button
              key={filter.key}
              variant={activeFilter === filter.key ? "default" : "outline"}
              className="rounded-full"
              onClick={() => setActiveFilter(filter.key)}
            >
              {filter.label}
            </Button>
          ))}
        </CardContent>
      </Card>

      {isLoading ? (
        <Card className="rounded-3xl">
          <CardContent className="p-6 text-sm text-muted-foreground">Loading expenses...</CardContent>
        </Card>
      ) : expenses.length === 0 ? (
        <Card className="rounded-3xl">
          <CardContent className="p-6 text-sm text-muted-foreground">
            No expenses found for this time window.
          </CardContent>
        </Card>
      ) : (
        expenses.map((expense) => (
          <Card key={expense.id} className="rounded-3xl">
            <CardContent className="flex items-center justify-between gap-4 p-5">
              <div>
                <p className="text-lg font-semibold">${Number(expense.amount || 0).toFixed(2)}</p>
                <p className="text-sm text-muted-foreground">{expense.vendor || "Unknown vendor"}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  {expense.category}
                </p>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                <p>{formatDate(expense.expense_date)}</p>
                <p className="mt-1">{expense.currency || "USD"}</p>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
