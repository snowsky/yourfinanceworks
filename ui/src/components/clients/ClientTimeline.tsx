import React, { useState, useEffect, useCallback } from "react";
import {
  timelineApi,
  crmApi,
  getErrorMessage,
  TimelineEvent,
  TimelineResponse,
  TimelineParams,
} from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import {
  FileText,
  CreditCard,
  ShoppingCart,
  Landmark,
  StickyNote,
  Loader2,
  ChevronDown,
  Trash2,
  Plus,
  Clock,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// ─── Constants ────────────────────────────────────────────────────────────────

const EVENT_TYPE_CONFIG: Record<
  TimelineEvent["event_type"],
  { icon: React.ElementType; label: string; color: string }
> = {
  invoice: { icon: FileText, label: "Invoice", color: "text-blue-500" },
  payment: { icon: CreditCard, label: "Payment", color: "text-green-500" },
  expense: { icon: ShoppingCart, label: "Expense", color: "text-orange-500" },
  bank_transaction: {
    icon: Landmark,
    label: "Bank",
    color: "text-purple-500",
  },
  note: { icon: StickyNote, label: "Note", color: "text-yellow-500" },
};

const SOURCE_LABELS: Record<TimelineEvent["source"], string> = {
  invoice: "Invoice",
  expense: "Expense",
  bank_statement: "Bank",
  note: "Note",
};

const STATUS_STYLES: Record<string, string> = {
  paid: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  reconciled:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  overdue: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  pending:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  draft: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
  matched:
    "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function relativeDate(isoStr: string): string {
  const date = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffDay > 30) return date.toLocaleDateString();
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHr > 0) return `${diffHr}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return "Just now";
}

function formatAmount(
  amount: number | null,
  currency: string | null
): string {
  if (amount == null) return "";
  const curr = currency || "USD";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: curr,
    }).format(amount);
  } catch {
    return `${curr} ${amount.toFixed(2)}`;
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface FilterChipProps {
  label: string;
  active: boolean;
  onClick: () => void;
}

function FilterChip({ label, active, onClick }: FilterChipProps) {
  return (
    <button
      onClick={onClick}
      className={`
        px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200
        border
        ${
          active
            ? "bg-primary text-primary-foreground border-primary shadow-sm"
            : "bg-muted/50 text-muted-foreground border-border hover:bg-muted hover:border-primary/30"
        }
      `}
    >
      {label}
    </button>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function TimelineSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex gap-4 animate-pulse"
        >
          <div className="w-10 h-10 rounded-full bg-muted shrink-0" />
          <div className="flex-1 space-y-2 py-1">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-3 bg-muted rounded w-1/2" />
            <div className="h-3 bg-muted rounded w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Timeline event card ──────────────────────────────────────────────────────

interface TimelineEventCardProps {
  event: TimelineEvent;
  onDeleteNote?: (noteId: number) => void;
  deletingNoteId: number | null;
}

function TimelineEventCard({
  event,
  onDeleteNote,
  deletingNoteId,
}: TimelineEventCardProps) {
  const config = EVENT_TYPE_CONFIG[event.event_type];
  const IconComponent = config.icon;
  const isMatched = event.metadata?.matched === true;

  // Determine the visual status — use "matched" style for matched bank txns
  const displayStatus = isMatched ? "matched" : event.status;
  const statusStyle =
    displayStatus && STATUS_STYLES[displayStatus]
      ? STATUS_STYLES[displayStatus]
      : "";

  return (
    <div className="flex gap-4 group">
      {/* Timeline dot + line */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-10 h-10 rounded-full border-2 border-border bg-card flex items-center justify-center ${config.color}`}
        >
          <IconComponent className="h-4 w-4" />
        </div>
        <div className="w-0.5 flex-1 bg-border/50 mt-1" />
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <div className="p-4 bg-muted/30 rounded-xl border border-border/50 hover:bg-muted/50 transition-colors">
          {/* Header row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{event.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {event.description}
              </p>
            </div>

            {/* Amount */}
            {event.amount != null && (
              <span className="text-sm font-mono font-semibold whitespace-nowrap">
                {formatAmount(event.amount, event.currency)}
              </span>
            )}
          </div>

          {/* Footer row: badges + date */}
          <div className="flex items-center flex-wrap gap-2 mt-3">
            {/* Source pill */}
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-muted text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
              {SOURCE_LABELS[event.source]}
            </span>

            {/* Status badge */}
            {displayStatus && statusStyle && (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium uppercase tracking-wide ${statusStyle}`}
              >
                {displayStatus}
              </span>
            )}

            {/* Matched label for inferred bank txns */}
            {isMatched && event.event_type === "bank_transaction" && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 text-[10px] font-medium uppercase tracking-wide">
                Matched
              </span>
            )}

            {/* Date */}
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground cursor-default">
                  <Clock className="h-3 w-3" />
                  {relativeDate(event.date)}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {new Date(event.date).toLocaleString()}
              </TooltipContent>
            </Tooltip>

            {/* Delete button for notes */}
            {event.event_type === "note" && onDeleteNote && (
              <button
                onClick={() => {
                  const noteId = event.metadata?.note_id as number;
                  if (noteId) onDeleteNote(noteId);
                }}
                disabled={
                  deletingNoteId === (event.metadata?.note_id as number)
                }
                className="opacity-0 group-hover:opacity-100 transition-opacity ml-1 p-1 rounded hover:bg-destructive/10 text-destructive"
                title="Delete note"
              >
                {deletingNoteId === (event.metadata?.note_id as number) ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface ClientTimelineProps {
  clientId: number;
}

export function ClientTimeline({ clientId }: ClientTimelineProps) {
  const { t } = useTranslation();

  // Data state
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE_SIZE = 20;

  // Filter state
  const [activeEventTypes, setActiveEventTypes] = useState<Set<string>>(
    new Set()
  );
  const [activeSources, setActiveSources] = useState<Set<string>>(new Set());

  // Notes composer state
  const [newNote, setNewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deletingNoteId, setDeletingNoteId] = useState<number | null>(null);

  const buildParams = useCallback(
    (p: number): TimelineParams => {
      const params: TimelineParams = { page: p, page_size: PAGE_SIZE };
      if (activeEventTypes.size > 0) {
        params.event_types = Array.from(activeEventTypes).join(",");
      }
      if (activeSources.size > 0) {
        params.source = Array.from(activeSources).join(",");
      }
      return params;
    },
    [activeEventTypes, activeSources]
  );

  const fetchTimeline = useCallback(
    async (p: number, append = false) => {
      if (!append) setLoading(true);
      else setLoadingMore(true);

      try {
        const data: TimelineResponse = await timelineApi.getTimeline(
          clientId,
          buildParams(p)
        );
        if (append) {
          setEvents((prev) => [...prev, ...data.events]);
        } else {
          setEvents(data.events);
        }
        setTotal(data.total);
        setHasMore(data.has_more);
        setPage(data.page);
      } catch (error) {
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [clientId, buildParams, t]
  );

  // Initial fetch + re-fetch on filter change
  useEffect(() => {
    fetchTimeline(1);
  }, [fetchTimeline]);

  // ─── Filter toggles ──────────────────────────────────────────────────────

  const toggleEventType = (type: string) => {
    setActiveEventTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const toggleSource = (src: string) => {
    setActiveSources((prev) => {
      const next = new Set(prev);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next;
    });
  };

  // ─── Notes actions ────────────────────────────────────────────────────────

  const handleAddNote = async () => {
    if (!newNote.trim()) {
      toast.error("Note cannot be empty.");
      return;
    }
    setSubmitting(true);
    try {
      const addedNote = await crmApi.createNoteForClient(clientId, {
        note: newNote,
      });

      // Optimistically prepend to timeline
      const optimisticEvent: TimelineEvent = {
        id: `note-${addedNote.id}`,
        event_type: "note",
        title: "Client Note",
        description:
          addedNote.note.length > 120
            ? addedNote.note.slice(0, 120) + "…"
            : addedNote.note,
        amount: null,
        currency: null,
        status: null,
        date: addedNote.created_at,
        source: "note",
        metadata: {
          note_id: addedNote.id,
          user_id: addedNote.user_id,
          full_note: addedNote.note,
        },
      };
      setEvents((prev) => [optimisticEvent, ...prev]);
      setTotal((prev) => prev + 1);
      setNewNote("");
      toast.success("Note added successfully.");
    } catch (error) {
      toast.error(getErrorMessage(error, t));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteNote = async (noteId: number) => {
    setDeletingNoteId(noteId);
    try {
      await crmApi.deleteNoteForClient(clientId, noteId);
      setEvents((prev) => prev.filter((e) => e.id !== `note-${noteId}`));
      setTotal((prev) => prev - 1);
      toast.success("Note deleted successfully.");
    } catch (error) {
      toast.error(getErrorMessage(error, t));
    } finally {
      setDeletingNoteId(null);
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <ProfessionalCard className="w-full backdrop-blur-sm bg-card/95 shadow-xl border-primary/10">
      <ProfessionalCardHeader className="pb-4 border-b border-border/50">
        <ProfessionalCardTitle className="text-xl font-bold flex items-center gap-2">
          <Clock className="h-5 w-5 text-primary" />
          Activity Timeline
        </ProfessionalCardTitle>

        {/* Filter bar */}
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium mr-1">
              Type:
            </span>
            {(
              Object.entries(EVENT_TYPE_CONFIG) as [
                TimelineEvent["event_type"],
                (typeof EVENT_TYPE_CONFIG)[TimelineEvent["event_type"]]
              ][]
            ).map(([type, cfg]) => (
              <FilterChip
                key={type}
                label={cfg.label}
                active={activeEventTypes.has(type)}
                onClick={() => toggleEventType(type)}
              />
            ))}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium mr-1">
              Source:
            </span>
            {(
              Object.entries(SOURCE_LABELS) as [
                TimelineEvent["source"],
                string
              ][]
            ).map(([src, label]) => (
              <FilterChip
                key={src}
                label={label}
                active={activeSources.has(src)}
                onClick={() => toggleSource(src)}
              />
            ))}
          </div>
        </div>
      </ProfessionalCardHeader>

      <ProfessionalCardContent className="pt-6">
        {/* Notes composer */}
        <div className="mb-6 space-y-3 p-4 bg-muted/20 rounded-xl border border-border/50">
          <ProfessionalTextarea
            placeholder="Add a note…"
            value={newNote}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setNewNote(e.target.value)
            }
            rows={2}
            variant="filled"
          />
          <div className="flex justify-end">
            <ProfessionalButton
              onClick={handleAddNote}
              disabled={submitting || !newNote.trim()}
              variant="default"
              size="sm"
              leftIcon={
                submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )
              }
            >
              Add Note
            </ProfessionalButton>
          </div>
        </div>

        {/* Timeline content */}
        {loading ? (
          <TimelineSkeleton />
        ) : events.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Clock className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No activity yet</p>
            <p className="text-sm mt-1">
              Invoices, payments, expenses, and notes will appear here.
            </p>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground mb-4">
              {total} event{total !== 1 ? "s" : ""} total
            </p>
            <div>
              {events.map((event) => (
                <TimelineEventCard
                  key={event.id}
                  event={event}
                  onDeleteNote={handleDeleteNote}
                  deletingNoteId={deletingNoteId}
                />
              ))}
            </div>

            {/* Load more */}
            {hasMore && (
              <div className="flex justify-center mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchTimeline(page + 1, true)}
                  disabled={loadingMore}
                  className="gap-2"
                >
                  {loadingMore ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}
