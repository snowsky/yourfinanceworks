import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { Feather } from "@expo/vector-icons";

import { expensesApi } from "../../src/lib/api";
import { useAuth } from "../../src/providers/AuthProvider";

function asCurrency(value: number | undefined, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value ?? 0);
}

export default function InsightsScreen() {
  const { accessToken } = useAuth();
  const query = useQuery({
    queryKey: ["expenses", "insights"],
    queryFn: expensesApi.getSummary,
    enabled: Boolean(accessToken),
  });

  const current = query.data?.current_period;
  const previous = query.data?.previous_period;
  const change = query.data?.changes?.total_amount_percent ?? 0;

  const cards = [
    {
      title: "This month",
      value: asCurrency(current?.total_amount),
      detail: `${current?.count ?? 0} expenses`,
      icon: "credit-card",
    },
    {
      title: "Previous month",
      value: asCurrency(previous?.total_amount),
      detail: `${previous?.count ?? 0} expenses`,
      icon: change > 0 ? "trending-up" : "trending-down",
    },
    {
      title: "Change",
      value: `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`,
      detail: "Compared with previous period",
      icon: change > 0 ? "arrow-up-right" : "arrow-down-right",
    },
  ];

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.heroCard}>
        <Text style={styles.heroTitle}>Simple, personal, glanceable</Text>
        <Text style={styles.heroBody}>
          Mobile insights should answer “how am I doing?” in a few seconds.
        </Text>
      </View>

      {query.isLoading ? (
        <View style={styles.metricCard}>
          <Text style={styles.emptyText}>Loading monthly summary...</Text>
        </View>
      ) : (
        cards.map((card) => (
          <View key={card.title} style={styles.metricCard}>
            <View>
              <Text style={styles.metricLabel}>{card.title}</Text>
              <Text style={styles.metricValue}>{card.value}</Text>
              <Text style={styles.metricDetail}>{card.detail}</Text>
            </View>
            <View style={styles.metricIconWrap}>
              <Feather name={card.icon as any} size={18} color="#0f172a" />
            </View>
          </View>
        ))
      )}

      <View style={styles.breakdownCard}>
        <Text style={styles.breakdownTitle}>Category breakdown</Text>
        <Text style={styles.breakdownBody}>
          This is the first glanceable chart card for the standalone app.
        </Text>

        {(query.data?.category_breakdown ?? []).slice(0, 5).map((category) => (
          <View key={category.category} style={styles.categoryRow}>
            <View style={styles.categoryRowTop}>
              <Text style={styles.categoryName}>{category.category}</Text>
              <Text style={styles.categoryAmount}>{asCurrency(category.total_amount)}</Text>
            </View>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  { width: `${Math.min(100, Number(category.percentage || 0))}%` },
                ]}
              />
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#f4f8f7" },
  content: { padding: 16, gap: 16 },
  heroCard: {
    borderRadius: 28,
    padding: 20,
    gap: 8,
    backgroundColor: "#111827",
  },
  heroTitle: {
    fontSize: 30,
    fontWeight: "700",
    color: "#ffffff",
  },
  heroBody: {
    fontSize: 15,
    lineHeight: 22,
    color: "#cbd5e1",
  },
  metricCard: {
    borderRadius: 28,
    padding: 18,
    backgroundColor: "#ffffff",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  metricLabel: {
    fontSize: 14,
    color: "#64748b",
  },
  metricValue: {
    marginTop: 4,
    fontSize: 28,
    fontWeight: "700",
    color: "#0f172a",
  },
  metricDetail: {
    marginTop: 4,
    fontSize: 14,
    color: "#64748b",
  },
  metricIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f1f5f9",
  },
  breakdownCard: {
    borderRadius: 28,
    padding: 18,
    gap: 12,
    backgroundColor: "#ffffff",
  },
  breakdownTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0f172a",
  },
  breakdownBody: {
    fontSize: 14,
    lineHeight: 20,
    color: "#64748b",
  },
  categoryRow: {
    gap: 6,
  },
  categoryRowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  categoryName: {
    fontSize: 14,
    color: "#0f172a",
  },
  categoryAmount: {
    fontSize: 14,
    fontWeight: "600",
    color: "#0f172a",
  },
  barTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "#e2e8f0",
    overflow: "hidden",
  },
  barFill: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "#0f766e",
  },
  emptyText: {
    fontSize: 14,
    lineHeight: 20,
    color: "#64748b",
  },
});
