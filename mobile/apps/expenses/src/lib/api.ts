import { z } from "zod";

import { API_BASE_URL } from "./config";
import { getAccessToken, getStoredUser } from "./auth-storage";

// ── Schemas ───────────────────────────────────────────────────────────────────

const mobileUserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  role: z.string(),
  tenant_id: z.number(),
  organizations: z.array(z.object({
    id: z.number(),
    name: z.string(),
    role: z.string().optional()
  })).optional().default([])
});

const loginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  user: mobileUserSchema
});

const ssoStatusSchema = z.object({
  google: z.boolean(),
  microsoft: z.boolean(),
  has_sso: z.boolean()
});

const parsedVoiceExpenseSchema = z.object({
  transcript: z.string(),
  amount: z.number().nullable().optional(),
  currency: z.string(),
  expense_date: z.string(),
  category: z.string(),
  vendor: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  confidence: z.number(),
  parser_used: z.string()
});

const transcribeResponseSchema = z.object({
  transcript: z.string(),
  success: z.boolean()
});

const expenseListItemSchema = z.object({
  id: z.number(),
  amount: z.number(),
  currency: z.string().default("USD"),
  expense_date: z.string(),
  category: z.string(),
  vendor: z.string().nullable().optional(),
  analysis_status: z.string().nullable().optional(),
  review_status: z.string().nullable().optional(),
  attachments_count: z.number().nullable().optional()
});

const expenseSchema = z.object({
  id: z.number(),
  amount: z.number().nullable().optional(),
  currency: z.string().default("USD"),
  expense_date: z.string(),
  category: z.string(),
  vendor: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  analysis_status: z.string().nullable().optional(),
  review_status: z.string().nullable().optional(),
  attachments_count: z.number().nullable().optional()
});

const expenseListSchema = z.object({
  success: z.boolean(),
  expenses: z.array(expenseListItemSchema),
  total: z.number()
});

const expenseSummarySchema = z.object({
  current_period: z.object({
    total_amount: z.number().optional().default(0),
    count: z.number().optional().default(0)
  }).optional().default({ total_amount: 0, count: 0 }),
  previous_period: z.object({
    total_amount: z.number().optional().default(0),
    count: z.number().optional().default(0)
  }).optional().default({ total_amount: 0, count: 0 }),
  changes: z.object({
    total_amount_percent: z.number().optional().default(0)
  }).optional().default({ total_amount_percent: 0 }),
  category_breakdown: z.array(z.object({
    category: z.string(),
    total_amount: z.number().optional().default(0),
    percentage: z.number().optional().default(0)
  })).optional().default([])
});

// ── Exported types ────────────────────────────────────────────────────────────

export type MobileUser = z.infer<typeof mobileUserSchema>;
export type LoginResponse = z.infer<typeof loginResponseSchema>;
export type SSOStatus = z.infer<typeof ssoStatusSchema>;
export type ParsedVoiceExpense = z.infer<typeof parsedVoiceExpenseSchema>;
export type Expense = z.infer<typeof expenseSchema>;
export type ExpenseListItem = z.infer<typeof expenseListItemSchema>;
export type ExpenseSummary = z.infer<typeof expenseSummarySchema>;

export type ExpenseDraft = {
  amount: number | null;
  currency: string;
  expense_date: string;
  category: string;
  vendor?: string | null;
  notes?: string | null;
};

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  schema?: z.ZodSchema<T>,
  options?: { skipAuth?: boolean; skipTenant?: boolean }
): Promise<T> {
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (!options?.skipAuth) {
    const token = await getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  if (!options?.skipTenant) {
    const user = await getStoredUser();
    if (user?.tenant_id) {
      headers.set("X-Tenant-ID", String(user.tenant_id));
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });

  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text);
      throw new Error(parsed.detail || parsed.message || `Request failed with status ${response.status}`);
    } catch {
      throw new Error(text || `Request failed with status ${response.status}`);
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  const json = await response.json();
  return schema ? schema.parse(json) : json;
}

// ── Auth API ──────────────────────────────────────────────────────────────────

export const authApi = {
  login(email: string, password: string) {
    return apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    }, loginResponseSchema, { skipAuth: true, skipTenant: true });
  },
  getSSOStatus() {
    return apiRequest("/auth/sso-status", { method: "GET" }, ssoStatusSchema, { skipAuth: true, skipTenant: true });
  },
  me() {
    return apiRequest("/auth/me", { method: "GET" }, mobileUserSchema, { skipTenant: true });
  }
};

// ── Expenses API ──────────────────────────────────────────────────────────────

export const expensesApi = {
  parseVoice(transcript: string) {
    return apiRequest("/expenses/parse-voice", {
      method: "POST",
      body: JSON.stringify({ transcript })
    }, parsedVoiceExpenseSchema);
  },

  async transcribeAudio(uri: string, fileName: string, mimeType: string) {
    const token = await getAccessToken();
    const user = await getStoredUser();

    const formData = new FormData();
    formData.append("file", { uri, name: fileName, type: mimeType } as unknown as Blob);

    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (user?.tenant_id) headers["X-Tenant-ID"] = String(user.tenant_id);

    const response = await fetch(`${API_BASE_URL}/expenses/transcribe-audio`, {
      method: "POST",
      headers,
      body: formData
    });

    if (!response.ok) {
      const text = await response.text();
      try {
        const parsed = JSON.parse(text);
        throw new Error(parsed.detail || `Transcription failed (${response.status})`);
      } catch {
        throw new Error(text || `Transcription failed (${response.status})`);
      }
    }

    const json = await response.json();
    return transcribeResponseSchema.parse(json);
  },

  createExpense(draft: ExpenseDraft) {
    return apiRequest("/expenses/", {
      method: "POST",
      body: JSON.stringify({
        ...draft,
        status: "recorded"
      })
    }, expenseSchema);
  },

  async uploadReceipt(expenseId: number, uri: string, fileName: string, mimeType: string) {
    const token = await getAccessToken();
    const user = await getStoredUser();

    const formData = new FormData();
    formData.append("file", { uri, name: fileName, type: mimeType } as unknown as Blob);

    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (user?.tenant_id) headers["X-Tenant-ID"] = String(user.tenant_id);

    const response = await fetch(`${API_BASE_URL}/expenses/${expenseId}/upload-receipt`, {
      method: "POST",
      headers,
      body: formData
    });

    if (!response.ok) {
      const text = await response.text();
      try {
        const parsed = JSON.parse(text);
        throw new Error(parsed.detail || `Upload failed (${response.status})`);
      } catch {
        throw new Error(text || `Upload failed (${response.status})`);
      }
    }

    return response.json();
  },

  getExpenses() {
    return apiRequest("/expenses/?include_total=true&limit=30", {}, expenseListSchema);
  },

  getSummary() {
    return apiRequest("/expenses/analytics/summary?period=month&compare_with_previous=true", {}, expenseSummarySchema);
  }
};
