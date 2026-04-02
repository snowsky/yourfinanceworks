import React, { useState } from "react";
import { surveysApi } from "../api";

// This hook might only exist in the main app (plugin mode)
// We use a dynamic import or an optional prop to handle this
interface Organization {
  id: number;
  name: string;
  role?: string;
}

interface ShareInternalModalProps {
  survey: { id: string; title: string };
  onClose: () => void;
  // If organizations are passed, we show the list. Otherwise, we can't share.
  organizations?: Organization[];
  isLoadingOrganizations?: boolean;
}

const styles = {
  modal: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.4)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modalBox: {
    background: "#fff",
    borderRadius: 10,
    padding: 28,
    width: "100%",
    maxWidth: 500,
    boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
  },
  btn: {
    padding: "8px 16px",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
    border: "none",
    transition: "all 0.2s",
  },
  btnPrimary: { background: "#2563eb", color: "#fff" },
  btnSecondary: { background: "#f3f4f6", color: "#374151" },
  orgItem: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #e5e7eb",
    marginBottom: 8,
    cursor: "pointer",
  },
  orgItemActive: {
    borderColor: "#2563eb",
    background: "#eff6ff",
  },
  label: { display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "#374151" },
  error: { color: "#dc2626", fontSize: 13, marginBottom: 12 },
  success: { color: "#059669", fontSize: 13, marginBottom: 12 },
};

export function ShareInternalModal({ survey, onClose, organizations, isLoadingOrganizations }: ShareInternalModalProps) {
  const [selectedOrgs, setSelectedOrgs] = useState<number[]>([]);
  const [sending, setSending] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const toggleOrg = (id: number) => {
    setSelectedOrgs((prev) =>
      prev.includes(id) ? prev.filter((o) => o !== id) : [...prev, id]
    );
  };

  const handleShare = async () => {
    if (selectedOrgs.length === 0) {
      setError("Please select at least one organization.");
      return;
    }

    setSending(true);
    setError("");
    setSuccess("");

    try {
      await surveysApi.shareInternal(survey.id, { 
        tenant_ids: selectedOrgs,
        due_date: dueDate || null
      });
      setSuccess("Survey successfully shared with selected organizations!");
      setTimeout(onClose, 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to share survey");
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={styles.modal} onClick={onClose}>
      <div style={styles.modalBox} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0, marginBottom: 8 }}>Internal Share: {survey.title}</h3>
        <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 20 }}>
          Select organizations to share this survey with. This will create a reminder for all users in those organizations.
        </p>

        <div style={{ marginBottom: 20 }}>
          <label style={styles.label}>Reminder Due Date (Optional)</label>
          <input
            type="datetime-local"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              fontSize: 14,
              boxSizing: "border-box",
            }}
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>

        {error && <div style={styles.error}>{error}</div>}
        {success && <div style={styles.success}>{success}</div>}

        <div style={{ maxHeight: 300, overflowY: "auto", marginBottom: 20 }}>
          {isLoadingOrganizations ? (
            <p style={{ fontSize: 14, color: "#6b7280" }}>Loading organizations...</p>
          ) : organizations && organizations.length > 0 ? (
            organizations.map((org) => (
              <div
                key={org.id}
                style={{
                  ...styles.orgItem,
                  ...(selectedOrgs.includes(org.id) ? styles.orgItemActive : {}),
                }}
                onClick={() => toggleOrg(org.id)}
              >
                <input
                  type="checkbox"
                  checked={selectedOrgs.includes(org.id)}
                  readOnly
                  style={{ pointerEvents: "none" }}
                />
                <span style={{ fontSize: 14, fontWeight: 500 }}>{org.name}</span>
                {org.role && (
                  <span style={{ fontSize: 12, color: "#6b7280", marginLeft: "auto" }}>
                    Role: {org.role}
                  </span>
                )}
              </div>
            ))
          ) : (
            <p style={{ fontSize: 14, color: "#6b7280" }}>No organizations found.</p>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button style={{ ...styles.btn, ...styles.btnSecondary }} onClick={onClose}>
            Cancel
          </button>
          <button
            style={{ ...styles.btn, ...styles.btnPrimary }}
            onClick={handleShare}
            disabled={sending || selectedOrgs.length === 0}
          >
            {sending ? "Sharing..." : "Share & Create Reminders"}
          </button>
        </div>
      </div>
    </div>
  );
}
