import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, usePathname, useRouter } from "expo-router";

import { setAccessToken, setStoredUser } from "../src/lib/auth-storage";
import { useAuth } from "../src/providers/AuthProvider";

function decodeUserParam(userParam: string) {
  const normalized = userParam.replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  return JSON.parse(globalThis.atob(`${normalized}${padding}`));
}

export default function NotFoundScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useLocalSearchParams<{ token?: string; user?: string; next?: string }>();
  const { refreshMe } = useAuth();
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function recoverOAuthRedirect() {
      const token = typeof params.token === "string" ? params.token : null;
      const userParam = typeof params.user === "string" ? params.user : null;
      const next = typeof params.next === "string" ? params.next : "/capture";

      if (!token || !userParam) {
        return;
      }

      try {
        const user = decodeUserParam(userParam);
        await Promise.all([
          setAccessToken(token),
          setStoredUser(user),
        ]);
        await refreshMe();
        router.replace(next as never);
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "Failed to finish Google sign-in.");
      }
    }

    recoverOAuthRedirect();
  }, [params.next, params.token, params.user, refreshMe, router]);

  const isOAuthFallback = Boolean(params.token && params.user);

  return (
    <View style={styles.screen}>
      <View style={styles.card}>
        {isOAuthFallback ? <ActivityIndicator size="large" color="#0f766e" /> : null}
        <Text style={styles.title}>
          {isOAuthFallback ? "Finishing sign-in" : "Page not found"}
        </Text>
        <Text style={styles.subtitle}>
          {isOAuthFallback
            ? message ?? "We caught an OAuth redirect on Expo’s fallback route and are sending you back into the app."
            : `No route matched ${pathname}.`}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#f4f8f7",
  },
  card: {
    width: "100%",
    borderRadius: 28,
    padding: 24,
    gap: 14,
    backgroundColor: "#ffffff",
    alignItems: "center",
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: "#0f172a",
    textAlign: "center",
  },
  subtitle: {
    fontSize: 15,
    lineHeight: 22,
    color: "#475569",
    textAlign: "center",
  },
});
