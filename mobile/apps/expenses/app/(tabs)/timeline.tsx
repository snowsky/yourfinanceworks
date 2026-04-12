import { useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { expensesApi } from "../../src/lib/api";
import { useAuth } from "../../src/providers/AuthProvider";

const filters = [
  { key: "all", label: "All" },
  { key: "today", label: "Today" },
  { key: "week", label: "This week" },
  { key: "month", label: "This month" },
] as const;

function formatMoney(amount: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount ?? 0);
}

function formatDateLabel(dateString: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${dateString}T00:00:00`));
}

export default function TimelineScreen() {
  const { accessToken } = useAuth();
  const [activeFilter, setActiveFilter] = useState<(typeof filters)[number]["key"]>("all");
  const query = useQuery({
    queryKey: ["expenses", "timeline"],
    queryFn: expensesApi.getExpenses,
    enabled: Boolean(accessToken),
  });

  const expenses = useMemo(() => {
    const all = query.data?.expenses ?? [];
    const now = new Date();

    return all.filter((expense) => {
      if (activeFilter === "all") return true;

      const expenseDate = new Date(`${expense.expense_date}T00:00:00`);
      const diffDays = Math.floor((now.getTime() - expenseDate.getTime()) / 86400000);

      if (activeFilter === "today") return diffDays === 0;
      if (activeFilter === "week") return diffDays >= 0 && diffDays < 7;
      if (activeFilter === "month") {
        return expenseDate.getMonth() === now.getMonth() && expenseDate.getFullYear() === now.getFullYear();
      }

      return true;
    });
  }, [activeFilter, query.data?.expenses]);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.headerCard}>
        <Text style={styles.headerTitle}>Recent spending</Text>
        <Text style={styles.headerBody}>
          Keep the mobile view scannable: amount first, details second.
        </Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
          {filters.map((filter) => {
            const active = filter.key === activeFilter;
            return (
              <Pressable
                key={filter.key}
                onPress={() => setActiveFilter(filter.key)}
                style={[styles.filterPill, active ? styles.filterPillActive : styles.filterPillInactive]}
              >
                <Text style={[styles.filterText, active ? styles.filterTextActive : styles.filterTextInactive]}>
                  {filter.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {query.isLoading ? (
        <View style={styles.card}>
          <Text style={styles.emptyText}>Loading expenses...</Text>
        </View>
      ) : expenses.length === 0 ? (
        <View style={styles.card}>
          <Text style={styles.emptyTitle}>No expenses found</Text>
          <Text style={styles.emptyText}>Nothing matches this time window.</Text>
        </View>
      ) : (
        expenses.map((item) => (
          <View key={item.id} style={styles.card}>
            <View>
              <Text style={styles.amount}>{formatMoney(item.amount, item.currency)}</Text>
              <Text style={styles.vendor}>{item.vendor ?? "Unknown vendor"}</Text>
              <Text style={styles.category}>{item.category}</Text>
            </View>
            <View style={styles.rightMeta}>
              <Text style={styles.dateText}>{formatDateLabel(item.expense_date)}</Text>
              <Text style={styles.currencyText}>{item.currency ?? "USD"}</Text>
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#f4f8f7" },
  content: { padding: 16, gap: 16 },
  headerCard: {
    borderRadius: 28,
    padding: 18,
    gap: 12,
    backgroundColor: "#ffffff",
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0f172a",
  },
  headerBody: {
    fontSize: 14,
    lineHeight: 20,
    color: "#64748b",
  },
  filterRow: {
    gap: 8,
    paddingRight: 4,
  },
  filterPill: {
    minHeight: 38,
    paddingHorizontal: 14,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
  },
  filterPillActive: {
    backgroundColor: "#0f766e",
  },
  filterPillInactive: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#cbd5e1",
  },
  filterText: {
    fontSize: 14,
    fontWeight: "600",
  },
  filterTextActive: {
    color: "#ffffff",
  },
  filterTextInactive: {
    color: "#334155",
  },
  card: {
    borderRadius: 28,
    padding: 18,
    backgroundColor: "#ffffff",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  amount: {
    fontSize: 24,
    fontWeight: "700",
    color: "#0f172a",
  },
  vendor: {
    marginTop: 2,
    fontSize: 14,
    color: "#64748b",
  },
  category: {
    marginTop: 8,
    fontSize: 11,
    letterSpacing: 1.4,
    textTransform: "uppercase",
    color: "#94a3b8",
  },
  rightMeta: {
    alignItems: "flex-end",
    gap: 4,
  },
  dateText: {
    fontSize: 14,
    color: "#64748b",
  },
  currencyText: {
    fontSize: 14,
    color: "#94a3b8",
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
  },
  emptyText: {
    fontSize: 14,
    lineHeight: 20,
    color: "#64748b",
  },
});
