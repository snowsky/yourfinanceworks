import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Clock3, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { expenseApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";

function getInboxState(expense: { analysis_status?: string; review_status?: string }) {
  if (expense.analysis_status === "failed" || expense.review_status === "failed") {
    return { label: "Needs attention", icon: AlertCircle, tone: "text-amber-600" };
  }

  if (expense.analysis_status === "processing" || expense.analysis_status === "queued" || expense.review_status === "pending") {
    return { label: "Processing", icon: Clock3, tone: "text-sky-600" };
  }

  return { label: "Ready to review", icon: CheckCircle2, tone: "text-emerald-600" };
}

export default function MobileInbox() {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["mobile-inbox"],
    queryFn: () => expenseApi.getExpensesPaginated({ limit: 20, skip: 0 }),
  });

  const items = useMemo(
    () =>
      (data?.expenses ?? []).filter((expense) =>
        expense.attachments_count ||
        expense.analysis_status === "processing" ||
        expense.analysis_status === "queued" ||
        expense.analysis_status === "failed" ||
        expense.review_status === "pending" ||
        expense.review_status === "diff_found",
      ),
    [data?.expenses],
  );

  return (
    <div className="space-y-4">
      <Card className="rounded-3xl">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-lg">Review queue</CardTitle>
            <CardDescription>
              OCR and voice drafts that still need a quick human pass.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" className="rounded-xl" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCcw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
        </CardHeader>
      </Card>

      {isLoading ? (
        <Card className="rounded-3xl">
          <CardContent className="p-6 text-sm text-muted-foreground">Loading mobile inbox...</CardContent>
        </Card>
      ) : items.length === 0 ? (
        <Card className="rounded-3xl">
          <CardContent className="p-6">
            <p className="font-medium">Nothing waiting right now.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              New receipt uploads and voice drafts will appear here.
            </p>
          </CardContent>
        </Card>
      ) : (
        items.map((expense) => {
          const state = getInboxState(expense);
          const Icon = state.icon;
          return (
            <Card key={expense.id} className="rounded-3xl">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-semibold">${Number(expense.amount || 0).toFixed(2)}</p>
                    <p className="text-sm text-muted-foreground">{expense.vendor || "Unknown vendor"}</p>
                  </div>
                  <div className={`flex items-center gap-1 text-xs font-medium ${state.tone}`}>
                    <Icon className="h-4 w-4" />
                    {state.label}
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
                  <span>{expense.category}</span>
                  <span>{formatDate(expense.expense_date)}</span>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Attachments: {expense.attachments_count ?? 0} • Analysis: {expense.analysis_status ?? "not_started"}
                </p>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}
