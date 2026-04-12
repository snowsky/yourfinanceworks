import { Redirect } from "expo-router";

import { useAuth } from "../src/providers/AuthProvider";

export default function Index() {
  const { isReady, accessToken } = useAuth();

  if (!isReady) return null;

  return <Redirect href={accessToken ? "/capture" : "/login"} />;
}
