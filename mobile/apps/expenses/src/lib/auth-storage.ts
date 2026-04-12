import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_KEY = "yfw.expenses.accessToken";
const USER_KEY = "yfw.expenses.user";

export type MobileUser = {
  id: number;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  role: string;
  tenant_id: number;
  organizations?: Array<{ id: number; name: string; role?: string }>;
};

export async function getAccessToken() {
  return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
}

export async function setAccessToken(token: string) {
  return SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token);
}

export async function clearAccessToken() {
  return SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
}

export async function getStoredUser(): Promise<MobileUser | null> {
  const value = await SecureStore.getItemAsync(USER_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as MobileUser;
  } catch {
    return null;
  }
}

export async function setStoredUser(user: MobileUser) {
  return SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
}

export async function clearStoredUser() {
  return SecureStore.deleteItemAsync(USER_KEY);
}

export async function clearSession() {
  await Promise.all([clearAccessToken(), clearStoredUser()]);
}
