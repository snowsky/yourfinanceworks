/**
 * Consolidated API client for yfw-surveys.
 * Supports both standalone (with API key) and plugin (with session auth) modes.
 */

import { STORAGE_KEYS, API_PREFIX, BASE_URL } from "./config";

export interface Question {
  id: string;
  survey_id: string;
  question_type: string;
  label: string;
  required: boolean;
  order_index: number;
  options?: string[] | Record<string, unknown> | null;
}

export interface Survey {
  id: string;
  title: string;
  description?: string;
  slug: string;
  is_active: boolean;
  allow_anonymous: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
  expires_at?: string;
  questions: Question[];
  response_count: number;
}

export interface SurveySummary {
  id: string;
  title: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  expires_at?: string;
  response_count: number;
}

export interface QuestionCreate {
  question_type: string;
  label: string;
  required?: boolean;
  order_index?: number;
  options?: string[] | Record<string, unknown> | null;
}

export interface SurveyCreate {
  title: string;
  description?: string;
  allow_anonymous?: boolean;
  expires_at?: string;
  questions?: QuestionCreate[];
}

export interface SurveyUpdate {
  title?: string;
  description?: string;
  is_active?: boolean;
  allow_anonymous?: boolean;
  expires_at?: string;
}

export interface ResponseSummary {
  id: string;
  respondent_email?: string;
  submitted_at: string;
}

export interface AnswerOut {
  question_id: string;
  value: unknown;
}

export interface ResponseOut {
  id: string;
  survey_id: string;
  respondent_email?: string;
  submitted_at: string;
  answers: AnswerOut[];
}

export interface ShareInternalRequest {
  tenant_ids: number[];
  due_date: string | null;
}

/**
 * Core fetch utility that handles both standalone and plugin environments.
 */
export async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const isStandalone = !!localStorage.getItem(STORAGE_KEYS.apiKey);
  const fullUrl = isStandalone ? `${BASE_URL}${path}` : path;
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> || {}),
  };

  if (isStandalone) {
    const apiKey = localStorage.getItem(STORAGE_KEYS.apiKey);
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }
  }

  const res = await fetch(fullUrl, {
    ...opts,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

/**
 * Survey API methods.
 */
export const surveysApi = {
  list: (skip = 0, limit = 50) =>
    apiFetch<SurveySummary[]>(`${API_PREFIX}?skip=${skip}&limit=${limit}`),

  get: (id: string) => apiFetch<Survey>(`${API_PREFIX}/${id}`),

  create: (body: SurveyCreate) =>
    apiFetch<Survey>(API_PREFIX, { method: "POST", body: JSON.stringify(body) }),

  update: (id: string, body: SurveyUpdate) =>
    apiFetch<Survey>(`${API_PREFIX}/${id}`, { method: "PUT", body: JSON.stringify(body) }),

  delete: (id: string) => apiFetch<void>(`${API_PREFIX}/${id}`, { method: "DELETE" }),

  listResponses: (surveyId: string) =>
    apiFetch<ResponseSummary[]>(`${API_PREFIX}/${surveyId}/responses`),

  getResponse: (surveyId: string, responseId: string) =>
    apiFetch<ResponseOut>(`${API_PREFIX}/${surveyId}/responses/${responseId}`),

  shareInternal: (surveyId: string, body: ShareInternalRequest) =>
    apiFetch<{ message: string; status: string }>(`${API_PREFIX}/${surveyId}/share-internal`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  exportUrl: (surveyId: string) => {
    const isStandalone = !!localStorage.getItem(STORAGE_KEYS.apiKey);
    return isStandalone ? `${BASE_URL}${API_PREFIX}/${surveyId}/export` : `${API_PREFIX}/${surveyId}/export`;
  }
};
