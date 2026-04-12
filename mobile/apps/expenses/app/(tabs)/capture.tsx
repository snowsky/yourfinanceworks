import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Feather } from "@expo/vector-icons";
import { Audio } from "expo-av";

import { expensesApi, type ExpenseDraft, type ParsedVoiceExpense } from "../../src/lib/api";
import { useAuth } from "../../src/providers/AuthProvider";

type VoicePhase = "idle" | "recording" | "transcribing" | "parsed" | "saving" | "saved";
type ReceiptPhase = "idle" | "previewing" | "uploading" | "done";

export default function CaptureScreen() {
  const { user, logout } = useAuth();

  // ── Voice state ──────────────────────────────────────────────────────────
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("idle");
  const [transcript, setTranscript] = useState("");
  const [voiceDraft, setVoiceDraft] = useState<ParsedVoiceExpense | null>(null);
  const [voiceError, setVoiceError] = useState("");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Receipt state ────────────────────────────────────────────────────────
  const [receiptPhase, setReceiptPhase] = useState<ReceiptPhase>("idle");
  const [receiptUri, setReceiptUri] = useState<string | null>(null);
  const [receiptFileName, setReceiptFileName] = useState<string | null>(null);
  const [receiptMime, setReceiptMime] = useState<string>("image/jpeg");
  const [receiptExpenseId, setReceiptExpenseId] = useState<number | null>(null);
  const [receiptError, setReceiptError] = useState("");

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      recordingRef.current?.stopAndUnloadAsync().catch(() => undefined);
    };
  }, []);

  // ── Voice: start / stop recording ───────────────────────────────────────

  async function handleToggleRecording() {
    if (voicePhase === "recording") {
      await stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    setVoiceError("");
    setVoiceDraft(null);
    setTranscript("");
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        setVoiceError("Microphone permission is required.");
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setVoicePhase("recording");
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Could not start recording.");
    }
  }

  async function stopRecording() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const recording = recordingRef.current;
    if (!recording) return;
    setVoicePhase("transcribing");
    try {
      await recording.stopAndUnloadAsync();
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      const uri = recording.getURI();
      recordingRef.current = null;

      if (!uri) throw new Error("No recording URI available.");

      const fileName = `expense_${Date.now()}.m4a`;
      const result = await expensesApi.transcribeAudio(uri, fileName, "audio/m4a");
      setTranscript(result.transcript);
      await parseDraft(result.transcript);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Transcription failed.";
      setVoiceError(msg);
      setVoicePhase("idle");
    }
  }

  // ── Voice: parse transcript ──────────────────────────────────────────────

  async function parseDraft(text?: string) {
    const source = (text ?? transcript).trim();
    if (!source) {
      setVoiceError("Please enter or record an expense description.");
      return;
    }
    setVoiceError("");
    if (voicePhase !== "transcribing") setVoicePhase("transcribing");
    try {
      const parsed = await expensesApi.parseVoice(source);
      setVoiceDraft(parsed);
      setTranscript(parsed.transcript);
      setVoicePhase("parsed");
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Parsing failed.");
      setVoicePhase("idle");
    }
  }

  // ── Voice: save expense ──────────────────────────────────────────────────

  async function saveVoiceExpense() {
    if (!voiceDraft) return;
    setVoicePhase("saving");
    try {
      const draft: ExpenseDraft = {
        amount: voiceDraft.amount ?? null,
        currency: voiceDraft.currency,
        expense_date: voiceDraft.expense_date,
        category: voiceDraft.category,
        vendor: voiceDraft.vendor,
        notes: voiceDraft.notes ?? (voiceDraft.transcript ? `Voice: "${voiceDraft.transcript}"` : null),
      };
      await expensesApi.createExpense(draft);
      setVoicePhase("saved");
    } catch (e) {
      setVoiceError(e instanceof Error ? e.message : "Failed to save expense.");
      setVoicePhase("parsed");
    }
  }

  function resetVoice() {
    setVoicePhase("idle");
    setTranscript("");
    setVoiceDraft(null);
    setVoiceError("");
    setRecordingSeconds(0);
  }

  // ── Receipt: capture photo ───────────────────────────────────────────────

  async function handlePickReceipt() {
    setReceiptError("");
    try {
      const ImagePicker = await import("expo-image-picker");
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        setReceiptError("Camera permission is required.");
        return;
      }
      const result = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8 });
      if (result.canceled) return;

      const asset = result.assets[0];
      const ext = (asset.fileName ?? asset.uri).split(".").pop()?.toLowerCase() ?? "jpg";
      const mime = ext === "png" ? "image/png" : "image/jpeg";
      setReceiptUri(asset.uri);
      setReceiptFileName(asset.fileName ?? `receipt_${Date.now()}.${ext}`);
      setReceiptMime(mime);
      setReceiptExpenseId(null);
      setReceiptPhase("previewing");
    } catch (e) {
      setReceiptError(e instanceof Error ? e.message : "Camera error.");
    }
  }

  // ── Receipt: create expense + upload ────────────────────────────────────

  async function handleUploadReceipt() {
    if (!receiptUri || !receiptFileName) return;
    setReceiptPhase("uploading");
    setReceiptError("");
    try {
      const today = new Date().toISOString().split("T")[0];
      const expense = await expensesApi.createExpense({
        amount: null,
        currency: "USD",
        expense_date: today,
        category: "General",
        notes: "Uploaded via mobile receipt scan — pending OCR review.",
      });

      await expensesApi.uploadReceipt(expense.id, receiptUri, receiptFileName, receiptMime);
      setReceiptExpenseId(expense.id);
      setReceiptPhase("done");
    } catch (e) {
      setReceiptError(e instanceof Error ? e.message : "Upload failed.");
      setReceiptPhase("previewing");
    }
  }

  function resetReceipt() {
    setReceiptPhase("idle");
    setReceiptUri(null);
    setReceiptFileName(null);
    setReceiptExpenseId(null);
    setReceiptError("");
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const confidenceLabel = (c: number) => {
    if (c >= 0.8) return "High confidence";
    if (c >= 0.5) return "Medium confidence";
    return "Low confidence";
  };

  const confidenceColor = (c: number) => {
    if (c >= 0.8) return "#059669";
    if (c >= 0.5) return "#d97706";
    return "#dc2626";
  };

  // ── Render ───────────────────────────────────────────────────────────────

  const isVoiceBusy = voicePhase === "transcribing" || voicePhase === "saving";
  const canScanReceipt = receiptPhase === "idle" || receiptPhase === "done";

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>

      {/* ── Hero card ── */}
      <View style={styles.heroCard}>
        <Text style={styles.heroTitle}>Capture in seconds</Text>
        <Text style={styles.heroBody}>
          Speak an expense or snap a receipt — we handle the rest.
        </Text>

        <Pressable
          style={[styles.heroAction, styles.heroActionPrimary]}
          onPress={canScanReceipt ? handlePickReceipt : resetReceipt}
          disabled={receiptPhase === "uploading"}
        >
          {receiptPhase === "uploading" ? (
            <ActivityIndicator color="#064e3b" />
          ) : (
            <>
              <Feather name={receiptPhase === "done" ? "check-circle" : "camera"} size={18} color="#064e3b" />
              <Text style={styles.heroActionPrimaryText}>
                {receiptPhase === "done" ? "Receipt saved — scan another" : "Scan receipt"}
              </Text>
            </>
          )}
        </Pressable>

        <Pressable
          style={[
            styles.heroAction,
            voicePhase === "recording" ? styles.heroActionRecording : styles.heroActionSecondary,
          ]}
          onPress={voicePhase === "saved" ? resetVoice : handleToggleRecording}
          disabled={isVoiceBusy}
        >
          {isVoiceBusy ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <>
              <Feather
                name={voicePhase === "recording" ? "square" : voicePhase === "saved" ? "check-circle" : "mic"}
                size={18}
                color="#ffffff"
              />
              <Text style={styles.heroActionSecondaryText}>
                {voicePhase === "recording"
                  ? `Stop recording  ${fmtTime(recordingSeconds)}`
                  : voicePhase === "saved"
                  ? "Saved — tap to record another"
                  : "Record voice expense"}
              </Text>
            </>
          )}
        </Pressable>
      </View>

      {/* ── Voice section ── */}
      <View style={styles.sectionCard}>
        <View style={styles.sectionHeader}>
          <View style={styles.sectionTitleRow}>
            <Feather name="mic" size={16} color="#0f766e" />
            <Text style={styles.sectionTitle}>Voice expense</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Record with the button above, or type a description and tap Parse.
          </Text>
        </View>

        <TextInput
          multiline
          numberOfLines={3}
          value={transcript}
          onChangeText={setTranscript}
          placeholder='e.g. "Spent $18 on lunch at Freshii today"'
          placeholderTextColor="#94a3b8"
          style={styles.textarea}
          editable={voicePhase !== "recording" && voicePhase !== "transcribing"}
        />

        {voicePhase !== "saved" && voicePhase !== "recording" && (
          <View style={styles.inlineRow}>
            <Pressable
              style={[styles.inlineBtn, styles.outlineBtn]}
              onPress={() => parseDraft()}
              disabled={isVoiceBusy || !transcript.trim()}
            >
              <Text style={styles.outlineBtnText}>
                {voicePhase === "transcribing" ? "Parsing…" : "Parse draft"}
              </Text>
            </Pressable>
          </View>
        )}

        {voiceError ? <Text style={styles.errorText}>{voiceError}</Text> : null}

        {/* Draft preview */}
        {voiceDraft && voicePhase !== "idle" && voicePhase !== "saved" && (
          <View style={styles.draftCard}>
            <View style={styles.draftRow}>
              <Text style={styles.draftAmount}>
                {voiceDraft.amount != null
                  ? `${voiceDraft.currency} ${voiceDraft.amount.toFixed(2)}`
                  : "Amount unknown"}
              </Text>
              <Text style={[styles.draftConfidence, { color: confidenceColor(voiceDraft.confidence) }]}>
                {confidenceLabel(voiceDraft.confidence)}
              </Text>
            </View>
            <Text style={styles.draftMeta}>
              {[voiceDraft.category, voiceDraft.vendor, voiceDraft.expense_date]
                .filter(Boolean)
                .join("  ·  ")}
            </Text>
            <Text style={styles.draftParser}>
              {voiceDraft.parser_used.toUpperCase()} · {Math.round(voiceDraft.confidence * 100)}%
            </Text>

            <Pressable
              style={[styles.inlineBtn, styles.primaryBtn]}
              onPress={saveVoiceExpense}
              disabled={voicePhase === "saving"}
            >
              {voicePhase === "saving" ? (
                <ActivityIndicator color="#ffffff" size="small" />
              ) : (
                <Text style={styles.primaryBtnText}>Save expense</Text>
              )}
            </Pressable>
          </View>
        )}

        {voicePhase === "saved" && (
          <View style={styles.successBanner}>
            <Feather name="check-circle" size={18} color="#059669" />
            <Text style={styles.successText}>Expense saved — visible in Inbox</Text>
          </View>
        )}
      </View>

      {/* ── Receipt section ── */}
      <View style={styles.sectionCard}>
        <View style={styles.sectionHeader}>
          <View style={styles.sectionTitleRow}>
            <Feather name="camera" size={16} color="#0f766e" />
            <Text style={styles.sectionTitle}>Receipt scan</Text>
          </View>
          <Text style={styles.sectionDescription}>
            Snap a photo — a draft expense is created and sent for OCR review.
          </Text>
        </View>

        {receiptUri && receiptPhase !== "idle" && (
          <Image source={{ uri: receiptUri }} style={styles.receiptPreview} resizeMode="cover" />
        )}

        {receiptError ? <Text style={styles.errorText}>{receiptError}</Text> : null}

        {receiptPhase === "previewing" && (
          <View style={styles.inlineRow}>
            <Pressable style={[styles.inlineBtn, styles.primaryBtn]} onPress={handleUploadReceipt}>
              <Feather name="upload" size={15} color="#ffffff" />
              <Text style={styles.primaryBtnText}>Upload & save</Text>
            </Pressable>
            <Pressable style={[styles.inlineBtn, styles.outlineBtn]} onPress={resetReceipt}>
              <Text style={styles.outlineBtnText}>Discard</Text>
            </Pressable>
          </View>
        )}

        {receiptPhase === "uploading" && (
          <View style={styles.uploadingRow}>
            <ActivityIndicator color="#0f766e" />
            <Text style={styles.uploadingText}>Uploading receipt…</Text>
          </View>
        )}

        {receiptPhase === "done" && (
          <View style={styles.successBanner}>
            <Feather name="check-circle" size={18} color="#059669" />
            <Text style={styles.successText}>
              Receipt uploaded — expense #{receiptExpenseId} queued for OCR
            </Text>
          </View>
        )}

        {receiptPhase === "idle" && (
          <Pressable style={[styles.inlineBtn, styles.outlineBtn, { alignSelf: "flex-start" }]} onPress={handlePickReceipt}>
            <Feather name="camera" size={15} color="#0f172a" />
            <Text style={styles.outlineBtnText}>Open camera</Text>
          </Pressable>
        )}
      </View>

      {/* ── Session footer ── */}
      <View style={styles.sessionRow}>
        <Text style={styles.sessionLabel}>{user?.email ?? "Not signed in"}</Text>
        <Pressable onPress={logout} hitSlop={10}>
          <Text style={styles.signOut}>Sign out</Text>
        </Pressable>
      </View>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#f4f8f7" },
  content: { padding: 16, gap: 16, paddingBottom: 40 },

  // Hero card
  heroCard: { borderRadius: 28, padding: 20, gap: 12, backgroundColor: "#10b981" },
  heroTitle: { fontSize: 30, fontWeight: "700", color: "#ffffff" },
  heroBody: { fontSize: 15, lineHeight: 22, color: "#ecfdf5" },
  heroAction: {
    minHeight: 56, borderRadius: 20, paddingHorizontal: 16,
    alignItems: "center", flexDirection: "row", gap: 10,
  },
  heroActionPrimary: { backgroundColor: "rgba(255,255,255,0.96)" },
  heroActionSecondary: { backgroundColor: "rgba(255,255,255,0.14)" },
  heroActionRecording: { backgroundColor: "#dc2626" },
  heroActionPrimaryText: { fontSize: 16, fontWeight: "700", color: "#064e3b" },
  heroActionSecondaryText: { fontSize: 16, fontWeight: "600", color: "#ffffff" },

  // Section cards
  sectionCard: { borderRadius: 28, padding: 18, gap: 14, backgroundColor: "#ffffff" },
  sectionHeader: { gap: 6 },
  sectionTitleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { fontSize: 20, fontWeight: "700", color: "#0f172a" },
  sectionDescription: { fontSize: 14, lineHeight: 20, color: "#64748b" },

  // Text input
  textarea: {
    minHeight: 88, borderWidth: 1, borderColor: "#cbd5e1", borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 14, backgroundColor: "#f8fafc",
    color: "#0f172a", textAlignVertical: "top", fontSize: 15,
  },

  // Inline buttons
  inlineRow: { flexDirection: "row", gap: 10, flexWrap: "wrap" },
  inlineBtn: {
    minHeight: 46, paddingHorizontal: 18, borderRadius: 18,
    alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8,
  },
  outlineBtn: { borderWidth: 1, borderColor: "#cbd5e1", backgroundColor: "#ffffff" },
  outlineBtnText: { color: "#0f172a", fontWeight: "700", fontSize: 15 },
  primaryBtn: { backgroundColor: "#0f766e" },
  primaryBtnText: { color: "#ffffff", fontWeight: "700", fontSize: 15 },

  // Draft preview
  draftCard: {
    borderRadius: 20, padding: 16, gap: 8, backgroundColor: "#f0fdf4",
    borderWidth: 1, borderColor: "#bbf7d0",
  },
  draftRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  draftAmount: { fontSize: 22, fontWeight: "700", color: "#065f46" },
  draftConfidence: { fontSize: 12, fontWeight: "600", marginTop: 4 },
  draftMeta: { fontSize: 14, color: "#374151", lineHeight: 20 },
  draftParser: { fontSize: 12, color: "#6b7280", letterSpacing: 0.5 },

  // Receipt preview
  receiptPreview: {
    width: "100%", height: 200, borderRadius: 20, backgroundColor: "#f1f5f9",
  },

  // Status rows
  successBanner: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: "#f0fdf4", borderRadius: 16, padding: 12,
  },
  successText: { fontSize: 14, color: "#065f46", fontWeight: "600", flex: 1 },
  uploadingRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  uploadingText: { fontSize: 14, color: "#475569" },
  errorText: { fontSize: 13, color: "#dc2626", lineHeight: 18 },

  // Session footer
  sessionRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 4,
  },
  sessionLabel: { fontSize: 13, color: "#64748b" },
  signOut: { color: "#0f766e", fontWeight: "700", fontSize: 14 },
});
