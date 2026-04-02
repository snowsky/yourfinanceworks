import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { saveSetupConfig, loadSetupConfig } from "../setup";

export async function testConnection(apiUrl: string, apiKey: string): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/health`, { headers: { "X-API-Key": apiKey } });
    return res.ok;
  } catch {
    return false;
  }
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f9fafb", fontFamily: "system-ui, sans-serif" },
  card: { background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10, padding: 32, width: "100%", maxWidth: 440, boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)" },
  h1: { margin: "0 0 8px", fontSize: 22, fontWeight: 700 },
  sub: { margin: "0 0 24px", color: "#6b7280", fontSize: 14 },
  label: { display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "#374151" },
  input: { width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, marginBottom: 16, boxSizing: "border-box" as const },
  btn: { width: "100%", padding: "10px 0", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 15, fontWeight: 600, background: "#2563eb", color: "#fff" },
  error: { color: "#dc2626", fontSize: 14, marginBottom: 12 },
  success: { color: "#16a34a", fontSize: 14, marginBottom: 12 },
};

export default function SetupPage() {
  const navigate = useNavigate();
  const saved = loadSetupConfig();
  const [apiUrl, setApiUrl] = useState(saved.apiUrl || "http://localhost:8001");
  const [apiKey, setApiKey] = useState(saved.apiKey);
  const [status, setStatus] = useState<"idle" | "testing" | "ok" | "err">("idle");
  const [message, setMessage] = useState("");

  const handleSave = async () => {
    if (!apiUrl || !apiKey) { setMessage("Both fields are required"); setStatus("err"); return; }
    setStatus("testing");
    setMessage("Connecting…");
    const ok = await testConnection(apiUrl, apiKey);
    if (ok) {
      saveSetupConfig({ apiUrl, apiKey });
      setStatus("ok");
      setMessage("Connected! Redirecting…");
      setTimeout(() => navigate("/"), 800);
    } else {
      setStatus("err");
      setMessage("Could not connect. Check the URL and API key.");
    }
  };

  return (
    <div style={s.page}>
      <div style={s.card}>
        <h1 style={s.h1}>YFW Surveys Setup</h1>
        <p style={s.sub}>Connect to your YourFinanceWORKS instance.</p>
        {message && <p style={status === "err" ? s.error : s.success}>{message}</p>}
        <label style={s.label}>API URL</label>
        <input style={s.input} value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="http://localhost:8001" />
        <label style={s.label}>API Key</label>
        <input style={s.input} type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="ak_..." />
        <button style={s.btn} onClick={handleSave} disabled={status === "testing"}>
          {status === "testing" ? "Connecting…" : "Save & Connect"}
        </button>
      </div>
    </div>
  );
}
