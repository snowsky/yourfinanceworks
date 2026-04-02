/**
 * Survey Responses Viewer Page.
 * Displays a list of responses and allows viewing details/exporting CSV.
 */

import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { surveysApi, ResponseSummary, ResponseOut } from "../api";

const s: Record<string, React.CSSProperties> = {
  container: { padding: "24px", maxWidth: 800, margin: "0 auto", fontFamily: "system-ui, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  h1: { margin: 0, fontSize: 20, fontWeight: 600 },
  btn: { padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 500 },
  btnSecondary: { background: "#f3f4f6", color: "#111", border: "1px solid #e5e7eb" },
  table: { width: "100%", borderCollapse: "collapse", background: "#fff", borderRadius: 8, overflow: "hidden", border: "1px solid #e5e7eb" },
  th: { textAlign: "left", padding: "12px 16px", borderBottom: "1px solid #e5e7eb", background: "#f9fafb", fontSize: 13, color: "#6b7280", fontWeight: 500 },
  td: { padding: "12px 16px", borderBottom: "1px solid #f3f4f6", fontSize: 14 },
  tr: { cursor: "pointer" },
  modal: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 },
  modalBox: { background: "#fff", borderRadius: 10, padding: 24, width: "100%", maxWidth: 600, maxHeight: "80vh", overflowY: "auto" },
  qLabel: { fontWeight: 600, fontSize: 13, color: "#374151", marginBottom: 4 },
  aVal: { fontSize: 14, color: "#111", marginBottom: 16, background: "#f9fafb", padding: 10, borderRadius: 6 },
};

export default function SurveyResponsesPage() {
  const { surveyId } = useParams<{ surveyId: string }>();
  const navigate = useNavigate();
  const [responses, setResponses] = useState<ResponseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedResponse, setSelectedResponse] = useState<ResponseOut | null>(null);

  useEffect(() => {
    if (surveyId) {
      surveysApi.listResponses(surveyId)
        .then(setResponses)
        .finally(() => setLoading(false));
    }
  }, [surveyId]);

  const viewResponse = async (rid: string) => {
    if (!surveyId) return;
    const full = await surveysApi.getResponse(surveyId, rid);
    setSelectedResponse(full);
  };

  const handleExport = () => {
    if (!surveyId) return;
    window.open(surveysApi.exportUrl(surveyId), "_blank");
  };

  if (loading) return <div style={s.container}>Loading responses…</div>;

  return (
    <div style={s.container}>
      <div style={s.header}>
        <button style={{ ...s.btn, ...s.btnSecondary }} onClick={() => navigate(-1)}>← Back</button>
        <h1 style={s.h1}>Responses</h1>
        <button style={{ ...s.btn, ...s.btnSecondary }} onClick={handleExport}>Export CSV</button>
      </div>

      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Respondent</th>
            <th style={s.th}>Date</th>
          </tr>
        </thead>
        <tbody>
          {responses.length === 0 ? (
            <tr><td colSpan={2} style={{ ...s.td, textAlign: "center", color: "#6b7280" }}>No responses yet.</td></tr>
          ) : (
            responses.map((r) => (
              <tr key={r.id} style={s.tr} onClick={() => viewResponse(r.id)}>
                <td style={s.td}>{r.respondent_email || "Anonymous"}</td>
                <td style={s.td}>{new Date(r.submitted_at).toLocaleString()}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {selectedResponse && (
        <div style={s.modal} onClick={() => setSelectedResponse(null)}>
          <div style={s.modalBox} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>Response Details</h2>
              <button style={s.btn} onClick={() => setSelectedResponse(null)}>✕</button>
            </div>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 20 }}>
              From: {selectedResponse.respondent_email || "Anonymous"}<br/>
              Submitted: {new Date(selectedResponse.submitted_at).toLocaleString()}
            </p>
            {selectedResponse.answers.map((a, i) => (
              <div key={i}>
                <div style={s.qLabel}>Question ID: {a.question_id}</div>
                <div style={s.aVal}>{Array.isArray(a.value) ? a.value.join(", ") : String(a.value ?? "N/A")}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
