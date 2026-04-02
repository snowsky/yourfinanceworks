import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PUBLIC_PREFIX } from "../config";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Question {
  id: string;
  question_type: string;
  label: string;
  required: boolean;
  order_index: number;
  options?: string[] | null;
}

interface Survey {
  id: string;
  title: string;
  description?: string;
  allow_anonymous: boolean;
  questions: Question[];
  expires_at?: string;
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#f9fafb", padding: "40px 16px", fontFamily: "system-ui, sans-serif" },
  card: { maxWidth: 640, margin: "0 auto", background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 32, boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.1)" },
  title: { margin: "0 0 8px", fontSize: 24, fontWeight: 700, color: "#111827" },
  desc: { margin: "0 0 28px", color: "#6b7280", fontSize: 15, lineHeight: 1.5 },
  label: { display: "block", fontWeight: 500, marginBottom: 6, fontSize: 15, color: "#374151" },
  required: { color: "#dc2626", marginLeft: 3 },
  input: { width: "100%", padding: "10px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 15, boxSizing: "border-box" as const, outline: "none" },
  textarea: { width: "100%", padding: "10px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 15, boxSizing: "border-box" as const, minHeight: 100, resize: "vertical" as const, outline: "none" },
  optionRow: { display: "flex", alignItems: "center", gap: 10, marginBottom: 10, cursor: "pointer", fontSize: 15 },
  qBlock: { marginBottom: 32 },
  btn: { padding: "12px 24px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 16, fontWeight: 600, background: "#2563eb", color: "#fff", width: "100%", marginTop: 8, transition: "background 0.2s" },
  error: { color: "#dc2626", fontSize: 14, marginBottom: 16, padding: "12px", background: "#fef2f2", borderRadius: 6, border: "1px solid #fee2e2" },
  success: { textAlign: "center" as const, padding: "48px 0" },
  ratingRow: { display: "flex", gap: 8, flexWrap: "wrap" as const },
  ratingBtn: { padding: "10px 16px", borderRadius: 6, border: "1px solid #d1d5db", cursor: "pointer", fontSize: 15, fontWeight: 500, background: "#fff", flex: 1, minWidth: 44 },
  ratingBtnActive: { background: "#2563eb", color: "#fff", borderColor: "#2563eb" },
  footer: {
    marginTop: 32,
    paddingTop: 16,
    borderTop: "1px solid #f3f4f6",
    textAlign: "center" as const,
    fontSize: 13,
    color: "#9ca3af",
  },
  closeDate: {
    fontSize: 13,
    color: "#dc2626",
    fontWeight: 600,
    marginBottom: 20,
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
};

// ── Components ─────────────────────────────────────────────────────────────────

function QuestionField({ q, value, onChange }: { q: Question; value: unknown; onChange: (v: unknown) => void }) {
  if (q.question_type === "text") {
    return <input style={s.input} value={(value as string) ?? ""} onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value)} placeholder="Your answer" />;
  }
  if (q.question_type === "paragraph") {
    return <textarea style={s.textarea} value={(value as string) ?? ""} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)} placeholder="Your answer" />;
  }
  if (q.question_type === "boolean") {
    return (
      <div style={s.ratingRow}>
        {["Yes", "No"].map((opt) => (
          <button
            key={opt}
            type="button"
            style={{ ...s.ratingBtn, ...(value === opt ? s.ratingBtnActive : {}) }}
            onClick={() => onChange(opt)}
          >
            {opt}
          </button>
        ))}
      </div>
    );
  }
  if (q.question_type === "rating") {
    return (
      <div style={s.ratingRow}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            style={{ ...s.ratingBtn, ...(value === String(n) || value === n ? s.ratingBtnActive : {}) }}
            onClick={() => onChange(n)}
          >
            {n}
          </button>
        ))}
      </div>
    );
  }
  if (q.question_type === "multiple_choice") {
    const opts = Array.isArray(q.options) ? q.options : [];
    return (
      <div>
        {opts.map((opt) => (
          <label key={opt} style={s.optionRow}>
            <input type="radio" checked={value === opt} onChange={() => onChange(opt)} />
            {opt}
          </label>
        ))}
      </div>
    );
  }
  if (q.question_type === "checkbox") {
    const opts = Array.isArray(q.options) ? q.options : [];
    const selected = Array.isArray(value) ? value : [];
    const toggle = (opt: string) => {
      const next = selected.includes(opt) ? selected.filter((x: string) => x !== opt) : [...selected, opt];
      onChange(next);
    };
    return (
      <div>
        {opts.map((opt) => (
          <label key={opt} style={s.optionRow}>
            <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} />
            {opt}
          </label>
        ))}
      </div>
    );
  }
  return null;
}

export default function PublicSurveyPage() {
  const { slug } = useParams<{ slug: string }>();
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState("");

  const isExpired = survey?.expires_at ? new Date(survey.expires_at) < new Date() : false;

  useEffect(() => {
    if (!slug) return;
    fetch(`${PUBLIC_PREFIX}/${slug}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(body.detail || "Failed to load survey");
        }
        return res.json();
      })
      .then(setSurvey)
      .catch((e: Error) => setLoadError(e.message));
  }, [slug]);

  const handleSubmit = async () => {
    if (!survey || !slug) return;
    setError("");

    // Check email if Not Anonymous
    if (!survey.allow_anonymous && !email.trim()) {
      setError("Email is required for this survey.");
      return;
    }

    // Check required questions
    const missing = survey.questions.filter((q: Question) => q.required && !answers[q.id]);
    if (missing.length > 0) {
      setError(`Please answer all required questions (${missing.length} remaining).`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${PUBLIC_PREFIX}/${slug}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          respondent_email: email.trim() || undefined,
          answers: survey.questions.map((q: Question) => ({
            question_id: q.id,
            value: answers[q.id] ?? null,
          })),
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || "Submission failed");
      }

      setSubmitted(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "An unexpected error occurred.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <div style={s.page}>
        <div style={s.card}>
          <div style={s.error}>{loadError}</div>
          <p style={{ textAlign: "center", color: "#6b7280" }}>The survey link might be invalid or has been removed.</p>
        </div>
      </div>
    );
  }

  if (!survey) {
    return (
      <div style={s.page}>
        <div style={{ ...s.card, textAlign: "center", color: "#6b7280" }}>Loading survey…</div>
      </div>
    );
  }

  if (isExpired) {
    return (
      <div style={s.page}>
        <div style={{ ...s.card, textAlign: "center" }}>
          <p style={{ fontSize: 48, margin: "0 0 16px" }}>🔒</p>
          <h1 style={s.title}>Survey Closed</h1>
          <p style={s.desc}>This survey is no longer accepting responses.</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div style={s.page}>
        <div style={s.card}>
          <div style={s.success}>
            <p style={{ fontSize: 48, margin: "0 0 16px" }}>✅</p>
            <h2 style={s.title}>Thank you!</h2>
            <p style={s.desc}>Your response has been successfully recorded.</p>
          </div>
          <div style={s.footer}>
            Powered by <strong>YourFinanceWORKS</strong>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.title}>{survey.title}</h1>
        {survey.description && <p style={s.desc}>{survey.description}</p>}
        {survey.expires_at && (
          <div style={s.closeDate}>
            <span>🕒 Closes:</span>
            {new Date(survey.expires_at).toLocaleString(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </div>
        )}

        <div style={{ borderTop: "1px solid #f3f4f6", paddingTop: 24 }}>
          <div style={s.qBlock}>
            <label style={s.label}>
              Your Email
              {!survey.allow_anonymous && <span style={s.required}>*</span>}
            </label>
            <input
              style={s.input}
              type="email"
              value={email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
            {survey.allow_anonymous && (
              <small style={{ color: "#9ca3af", display: "block", marginTop: 4 }}>Optional: survey is anonymous by default.</small>
            )}
          </div>

          {survey.questions.map((q) => (
            <div key={q.id} style={s.qBlock}>
              <label style={s.label}>
                {q.label}
                {q.required && <span style={s.required}>*</span>}
              </label>
              <QuestionField
                q={q}
                value={answers[q.id]}
                onChange={(v: unknown) => setAnswers((prev: Record<string, unknown>) => ({ ...prev, [q.id]: v }))}
              />
            </div>
          ))}

          {error && <div style={s.error}>{error}</div>}

          <button
            style={s.btn}
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? "Submitting…" : "Submit Response"}
          </button>
        </div>
        <div style={s.footer}>
          Powered by <strong>YourFinanceWORKS</strong>
        </div>
      </div>
    </div>
  );
}
