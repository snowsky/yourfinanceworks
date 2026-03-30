import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Mic, MicOff, Plus, ScanLine, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { expenseApi, type Expense, type ParsedVoiceExpense } from "@/lib/api";
import { EXPENSE_CATEGORY_OPTIONS } from "@/constants/expenses";

type DraftExpense = Pick<Expense, "amount" | "currency" | "expense_date" | "category" | "vendor" | "notes" | "status">;

const today = () => new Date().toISOString().split("T")[0];

function defaultDraft(): DraftExpense {
  return {
    amount: 0,
    currency: "USD",
    expense_date: today(),
    category: "General",
    vendor: "",
    notes: "",
    status: "recorded",
  };
}

type SpeechRecognitionAlternative = { transcript: string };
type SpeechRecognitionResult = {
  isFinal: boolean;
  0: SpeechRecognitionAlternative;
};
type SpeechRecognitionEvent = Event & {
  resultIndex: number;
  results: SpeechRecognitionResult[];
};
type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

declare global {
  interface Window {
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
    SpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export default function MobileCapture() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [draft, setDraft] = useState<DraftExpense>(defaultDraft);
  const [voiceText, setVoiceText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSavingFile, setIsSavingFile] = useState(false);
  const [isSavingQuickAdd, setIsSavingQuickAdd] = useState(false);
  const [isParsingVoice, setIsParsingVoice] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceMeta, setVoiceMeta] = useState<ParsedVoiceExpense | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);

  const speechSupported = typeof window !== "undefined" && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  const draftPreview = useMemo(() => ({
    amount: draft.amount > 0 ? `$${draft.amount.toFixed(2)}` : "Add amount",
    vendor: draft.vendor || "Vendor optional",
  }), [draft.amount, draft.vendor]);

  const openCamera = () => fileInputRef.current?.click();

  const handleFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (!file) return;

    setIsSavingFile(true);
    try {
      const created = await expenseApi.createExpense({
        ...defaultDraft(),
        notes: `Captured from mobile upload: ${file.name}`,
      });
      await expenseApi.uploadReceipt(created.id, file);
      toast.success("Receipt uploaded. AI analysis is in progress.");
      setSelectedFile(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to upload receipt");
    } finally {
      event.target.value = "";
      setIsSavingFile(false);
    }
  };

  const applyParsedVoiceDraft = (parsed: ParsedVoiceExpense) => {
    setDraft({
      amount: parsed.amount ?? 0,
      currency: parsed.currency || "USD",
      expense_date: parsed.expense_date || today(),
      category: EXPENSE_CATEGORY_OPTIONS.includes(parsed.category) ? parsed.category : "General",
      vendor: parsed.vendor || "",
      notes: parsed.notes || parsed.transcript,
      status: "recorded",
    });
    setVoiceMeta(parsed);
  };

  const applyVoiceDraft = async () => {
    if (!voiceText.trim()) {
      toast.error("Add a voice note or transcript first.");
      return;
    }

    setIsParsingVoice(true);
    try {
      const parsed = await expenseApi.parseVoice(voiceText, draft.currency || "USD");
      applyParsedVoiceDraft(parsed);
      toast.success(`Draft filled using ${parsed.parser_used} parsing.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to parse voice note");
    } finally {
      setIsParsingVoice(false);
    }
  };

  const toggleListening = () => {
    if (!speechSupported) {
      toast.error("Speech capture is not supported in this browser.");
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      toast.error("Speech capture is not supported in this browser.");
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      setVoiceText(transcript);
    };
    recognition.onerror = (event) => {
      setIsListening(false);
      toast.error(event.error === "not-allowed" ? "Microphone access was blocked." : "Speech capture failed.");
    };
    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const saveQuickExpense = async () => {
    if (!draft.amount || draft.amount <= 0) {
      toast.error("Enter an amount before saving.");
      return;
    }

    setIsSavingQuickAdd(true);
    try {
      await expenseApi.createExpense(draft);
      toast.success("Expense saved.");
      setDraft(defaultDraft());
      setVoiceText("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save expense");
    } finally {
      setIsSavingQuickAdd(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden border-none bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl">Capture in seconds</CardTitle>
          <CardDescription className="text-emerald-50">
            The mobile app should feel like a pocket inbox, not a miniature back office.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <Button
            size="lg"
            variant="secondary"
            className="h-14 justify-start rounded-2xl bg-white/95 px-4 text-base text-emerald-900 hover:bg-white"
            onClick={openCamera}
            disabled={isSavingFile}
          >
            {isSavingFile ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />}
            {isSavingFile ? "Uploading receipt..." : "Scan receipt"}
          </Button>
          <Button
            size="lg"
            variant="secondary"
            className="h-14 justify-start rounded-2xl bg-white/15 px-4 text-base text-white hover:bg-white/20"
            onClick={applyVoiceDraft}
            disabled={isParsingVoice}
          >
            {isParsingVoice ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
            {isParsingVoice ? "Parsing voice note..." : "Parse voice note into a draft"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            capture="environment"
            className="hidden"
            onChange={handleFileSelected}
          />
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Sparkles className="h-4 w-4 text-primary" />
            Voice note
          </CardTitle>
          <CardDescription>
            Try: “Spent 18 dollars on lunch at Freshii today.”
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={voiceText}
            onChange={(event) => setVoiceText(event.target.value)}
            rows={4}
            placeholder="Type or paste a spoken expense here."
            className="rounded-2xl"
          />
          <div className="grid grid-cols-2 gap-3">
            <Button
              variant={isListening ? "default" : "outline"}
              className="w-full rounded-2xl"
              onClick={toggleListening}
              disabled={!speechSupported}
            >
              {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {isListening ? "Stop dictation" : speechSupported ? "Start dictation" : "No mic support"}
            </Button>
            <Button variant="outline" className="w-full rounded-2xl" onClick={applyVoiceDraft} disabled={isParsingVoice}>
              {isParsingVoice ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Parse transcript
            </Button>
          </div>
          {voiceMeta && (
            <div className="rounded-2xl border border-border/60 bg-muted/40 p-3 text-sm text-muted-foreground">
              Parser: <span className="font-medium text-foreground">{voiceMeta.parser_used}</span> • Confidence:{" "}
              <span className="font-medium text-foreground">{Math.round(voiceMeta.confidence * 100)}%</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-3xl">
        <CardHeader>
          <CardTitle className="text-lg">Quick add</CardTitle>
          <CardDescription>
            Save a simple expense without leaving the capture screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={draft.amount || ""}
              onChange={(event) => setDraft((current) => ({ ...current, amount: Number(event.target.value) }))}
              placeholder="Amount"
              className="rounded-2xl"
            />
            <Input
              value={draft.category}
              onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value || "General" }))}
              placeholder="Category"
              className="rounded-2xl"
            />
          </div>
          <Input
            value={draft.vendor || ""}
            onChange={(event) => setDraft((current) => ({ ...current, vendor: event.target.value }))}
            placeholder="Vendor"
            className="rounded-2xl"
          />
          <Input
            type="date"
            value={draft.expense_date}
            onChange={(event) => setDraft((current) => ({ ...current, expense_date: event.target.value }))}
            className="rounded-2xl"
          />
          <Textarea
            value={draft.notes || ""}
            onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
            rows={3}
            placeholder="Optional note"
            className="rounded-2xl"
          />
          <div className="rounded-2xl bg-muted/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Draft preview</p>
            <p className="mt-2 text-lg font-semibold">{draftPreview.amount}</p>
            <p className="text-sm text-muted-foreground">{draftPreview.vendor}</p>
            <p className="mt-1 text-sm text-muted-foreground">{draft.category} on {draft.expense_date}</p>
            {selectedFile && <p className="mt-2 text-sm text-muted-foreground">Pending file: {selectedFile.name}</p>}
          </div>
          <Button className="w-full rounded-2xl" onClick={saveQuickExpense} disabled={isSavingQuickAdd}>
            {isSavingQuickAdd ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {isSavingQuickAdd ? "Saving..." : "Save expense"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
