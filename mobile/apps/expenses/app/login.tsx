import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Redirect } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { AntDesign, Feather } from "@expo/vector-icons";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import Constants, { ExecutionEnvironment } from "expo-constants";
import { SafeAreaView } from "react-native-safe-area-context";

import { authApi } from "../src/lib/api";
import { setAccessToken, setStoredUser } from "../src/lib/auth-storage";
import { API_BASE_URL } from "../src/lib/config";
import { useAuth } from "../src/providers/AuthProvider";

export default function LoginScreen() {
  const { accessToken, isReady, login, refreshMe } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const isExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
  const ssoStatus = useQuery({
    queryKey: ["auth", "sso-status"],
    queryFn: authApi.getSSOStatus,
    enabled: !isExpoGo,
  });
  const showGoogleSSO = !isExpoGo && ssoStatus.data?.google !== false;

  if (!isReady) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#0f766e" />
      </View>
    );
  }

  if (accessToken) {
    return <Redirect href="/capture" />;
  }

  async function handleLogin() {
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleLogin() {
    setError(null);
    setIsGoogleLoading(true);
    try {
      const redirectUri = Linking.createURL("/oauth-callback");
      const authUrl =
        `${API_BASE_URL}/auth/google/login?next=${encodeURIComponent("/capture")}` +
        `&mobile_redirect_uri=${encodeURIComponent(redirectUri)}`;

      const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUri);
      if (result.type !== "success" || !result.url) {
        return;
      }

      const parsed = Linking.parse(result.url);
      const token = typeof parsed.queryParams?.token === "string" ? parsed.queryParams.token : null;
      const userParam = typeof parsed.queryParams?.user === "string" ? parsed.queryParams.user : null;

      if (!token || !userParam) {
        throw new Error("Google SSO did not return a complete mobile session.");
      }

      const normalized = userParam.replace(/-/g, "+").replace(/_/g, "/");
      const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
      const user = JSON.parse(globalThis.atob(`${normalized}${padding}`));

      await Promise.all([setAccessToken(token), setStoredUser(user)]);
      await refreshMe();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed.");
    } finally {
      setIsGoogleLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.heroCard}>
          <Text style={styles.kicker}>YFW Expenses</Text>
          <Text style={styles.heroTitle}>Capture in seconds</Text>
          <Text style={styles.heroBody}>
            The standalone app keeps personal finance tracking simple, fast, and easy to use.
          </Text>

          <View style={styles.featureRow}>
            <Feather name="camera" size={16} color="#ecfdf5" />
            <Text style={styles.featureText}>Scan receipts in a few taps</Text>
          </View>
          <View style={styles.featureRow}>
            <Feather name="mic" size={16} color="#ecfdf5" />
            <Text style={styles.featureText}>Turn voice notes into drafts</Text>
          </View>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.formTitle}>Sign in</Text>
          <Text style={styles.formBody}>
            Use your YourFinanceWORKS account to continue into the mobile capture flow.
          </Text>

          <TextInput
            style={styles.input}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="Email"
            placeholderTextColor="#64748b"
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor="#64748b"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {error ? (
            <View style={styles.errorCard}>
              <Feather name="alert-circle" size={16} color="#b91c1c" />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <Pressable style={styles.primaryButton} onPress={handleLogin} disabled={isSubmitting}>
            {isSubmitting ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.primaryButtonText}>Continue</Text>
            )}
          </Pressable>

          {showGoogleSSO ? (
            <Pressable style={styles.secondaryButton} onPress={handleGoogleLogin} disabled={isGoogleLoading}>
              {isGoogleLoading ? (
                <ActivityIndicator color="#0f172a" />
              ) : (
                <>
                  <AntDesign name="google" size={16} color="#0f172a" />
                  <Text style={styles.secondaryButtonText}>Continue with Google</Text>
                </>
              )}
            </Pressable>
          ) : null}

          {isExpoGo ? (
            <View style={styles.infoCard}>
              <Feather name="info" size={16} color="#0f766e" />
              <Text style={styles.infoText}>
                Google sign-in is available in a dev build or standalone app. Expo Go can still be used for email/password testing.
              </Text>
            </View>
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f4f8f7",
  },
  content: {
    padding: 16,
    gap: 14,
    paddingTop: 8,
    paddingBottom: 24,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f4f8f7",
  },
  heroCard: {
    borderRadius: 28,
    paddingHorizontal: 18,
    paddingVertical: 16,
    gap: 6,
    backgroundColor: "#10b981",
  },
  kicker: {
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
    color: "#d1fae5",
  },
  heroTitle: {
    fontSize: 24,
    fontWeight: "700",
    color: "#ffffff",
  },
  heroBody: {
    fontSize: 14,
    lineHeight: 20,
    color: "#ecfdf5",
    marginBottom: 2,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  featureText: {
    fontSize: 13,
    color: "#ecfdf5",
  },
  formCard: {
    borderRadius: 28,
    padding: 20,
    gap: 14,
    backgroundColor: "#ffffff",
  },
  formTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: "#0f172a",
  },
  formBody: {
    fontSize: 14,
    lineHeight: 20,
    color: "#64748b",
  },
  input: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: "#0f172a",
    backgroundColor: "#f8fafc",
  },
  errorCard: {
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  errorText: {
    flex: 1,
    color: "#b91c1c",
    lineHeight: 20,
  },
  infoCard: {
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: "#ecfeff",
    borderWidth: 1,
    borderColor: "#a5f3fc",
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  infoText: {
    flex: 1,
    color: "#115e59",
    lineHeight: 20,
  },
  primaryButton: {
    minHeight: 54,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0f766e",
  },
  primaryButtonText: {
    color: "#ffffff",
    fontWeight: "700",
    fontSize: 16,
  },
  secondaryButton: {
    minHeight: 54,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#e2e8f0",
    flexDirection: "row",
    gap: 8,
  },
  secondaryButtonText: {
    color: "#0f172a",
    fontWeight: "700",
    fontSize: 16,
  },
});
