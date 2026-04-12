import { Redirect, Tabs } from "expo-router";
import { Feather } from "@expo/vector-icons";

import { useAuth } from "../../src/providers/AuthProvider";

export default function TabsLayout() {
  const { isReady, accessToken } = useAuth();

  if (!isReady) return null;
  if (!accessToken) {
    return <Redirect href="/login" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#0f766e",
        tabBarInactiveTintColor: "#64748b",
        tabBarStyle: {
          height: 78,
          paddingTop: 10,
          paddingBottom: 10,
          backgroundColor: "#ffffff",
          borderTopColor: "#e2e8f0",
        },
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: "600",
        }
      }}
    >
      <Tabs.Screen
        name="capture"
        options={{
          title: "Capture",
          tabBarIcon: ({ color, size }) => <Feather name="camera" size={size} color={color} />
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: "Inbox",
          tabBarIcon: ({ color, size }) => <Feather name="inbox" size={size} color={color} />
        }}
      />
      <Tabs.Screen
        name="timeline"
        options={{
          title: "Timeline",
          tabBarIcon: ({ color, size }) => <Feather name="list" size={size} color={color} />
        }}
      />
      <Tabs.Screen
        name="insights"
        options={{
          title: "Insights",
          tabBarIcon: ({ color, size }) => <Feather name="bar-chart-2" size={size} color={color} />
        }}
      />
    </Tabs>
  );
}
