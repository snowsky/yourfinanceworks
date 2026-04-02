import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { surveysApi, Survey, Question, QuestionCreate } from "../api";

const QUESTION_TYPES = [
  { value: "text", label: "Short text" },
  { value: "paragraph", label: "Paragraph" },
  { value: "multiple_choice", label: "Multiple choice" },
  { value: "checkbox", label: "Checkboxes" },
  { value: "rating", label: "Rating (1–5)" },
  { value: "boolean", label: "Yes / No" },
];

const s: Record<string, React.CSSProperties> = {
  page: { maxWidth: 760, margin: "0 auto", padding: "32px 24px", fontFamily: "system-ui, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 },
  h1: { margin: 0, fontSize: 22, fontWeight: 700 },
  btn: { padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 500 },
  btnPrimary: { background: "#2563eb", color: "#fff" },
  btnSecondary: { background: "#f3f4f6", color: "#111827", border: "1px solid #e5e7eb" },
  btnDanger: { background: "#fee2e2", color: "#dc2626", border: "1px solid #fecaca" },
  section: { background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 16, boxShadow: "0 1px 2px rgba(0,0,0,0.05)" },
  label: { display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "#374151" },
  input: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box" as const, marginBottom: 12 },
  textarea: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, boxSizing: "border-box" as const, marginBottom: 12, minHeight: 72, resize: "vertical" as const },
  row: { display: "flex", gap: 8, alignItems: "center" },
  error: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  qCard: { border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 10, background: "#fff" },
};

interface DraftQuestion extends QuestionCreate {
  _id?: string;
}

export default function SurveyEditorPage() {
  const { surveyId } = useParams<{ surveyId?: string }>();
  const navigate = useNavigate();
  const isEdit = !!surveyId;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [allowAnon, setAllowAnon] = useState(true);
  const [expiresAt, setExpiresAt] = useState("");
  const [questions, setQuestions] = useState<DraftQuestion[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!surveyId) return;
    surveysApi.get(surveyId).then((s: Survey) => {
      setTitle(s.title);
      setDescription(s.description ?? "");
      setAllowAnon(s.allow_anonymous);
      setExpiresAt(s.expires_at ? new Date(s.expires_at).toISOString().slice(0, 16) : "");
      setQuestions(s.questions.map((q: Question) => ({
        _id: q.id,
        question_type: q.question_type,
        label: q.label,
        required: q.required,
        order_index: q.order_index,
        options: q.options,
      })));
    }).catch((e: Error) => setError(e.message));
  }, [surveyId]);

  const addQ = () =>
    setQuestions((qs) => [...qs, { question_type: "text", label: "", required: false, order_index: qs.length }]);

  const removeQ = (i: number) => setQuestions((qs) => qs.filter((_, idx) => idx !== i));

  const updateQ = (i: number, patch: Partial<DraftQuestion>) =>
    setQuestions((qs) => qs.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));

  const handleSave = async () => {
    if (!title.trim()) { setError("Title is required"); return; }
    setSaving(true);
    setError("");
    try {
      const payload = {
        title,
        description,
        allow_anonymous: allowAnon,
        expires_at: expiresAt || undefined
      };

      if (isEdit && surveyId) {
        await surveysApi.update(surveyId, payload);
      } else {
        await surveysApi.create({ ...payload, questions });
      }
      navigate("/");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h1 style={s.h1}>{isEdit ? "Edit Survey" : "New Survey"}</h1>
        <div style={s.row}>
          <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => navigate("/")}>Cancel</button>
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save Survey"}
          </button>
        </div>
      </div>

      {error && <p style={s.error}>{error}</p>}

      <div style={s.section}>
        <label style={s.label}>Title *</label>
        <input style={s.input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Survey title" />
        <label style={s.label}>Description</label>
        <textarea style={s.textarea} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description shown to respondents" />

        <div style={{ ...s.row, marginBottom: 12, gap: 16 }}>
          <label style={{ ...s.label, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", marginBottom: 0 }}>
            <input type="checkbox" checked={allowAnon} onChange={(e) => setAllowAnon(e.target.checked)} />
            Allow anonymous responses
          </label>
          <div style={{ flex: 1 }}>
            <label style={s.label}>Close Date (Optional)</label>
            <input
              style={{ ...s.input, marginBottom: 0 }}
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <strong>Questions ({questions.length})</strong>
        <button style={{ ...s.btn, ...s.btnSecondary }} onClick={addQ}>+ Add Question</button>
      </div>

      {questions.map((q, i) => (
        <div key={i} style={s.qCard}>
          <div style={{ ...s.row, marginBottom: 8 }}>
            <span style={{ fontWeight: 500, fontSize: 13, color: "#6b7280", minWidth: 20 }}>{i + 1}.</span>
            <select
              style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
              value={q.question_type}
              onChange={(e) => updateQ(i, { question_type: e.target.value })}
            >
              {QUESTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, marginLeft: "auto", cursor: "pointer" }}>
              <input type="checkbox" checked={q.required} onChange={(e) => updateQ(i, { required: e.target.checked })} />
              Required
            </label>
            <button style={{ ...s.btn, ...s.btnDanger, padding: "4px 10px" }} onClick={() => removeQ(i)}>✕</button>
          </div>

          <input
            style={s.input}
            value={q.label}
            onChange={(e) => updateQ(i, { label: e.target.value })}
            placeholder="Question text"
          />

          {(q.question_type === "multiple_choice" || q.question_type === "checkbox") && (
            <>
              <label style={s.label}>Options (one per line)</label>
              <textarea
                style={{ ...s.textarea, marginBottom: 0 }}
                value={Array.isArray(q.options) ? (q.options as string[]).join("\n") : ""}
                onChange={(e) => updateQ(i, { options: e.target.value.split("\n").filter(Boolean) })}
                placeholder={"Option A\nOption B\nOption C"}
              />
            </>
          )}
        </div>
      ))}
    </div>
  );
}
