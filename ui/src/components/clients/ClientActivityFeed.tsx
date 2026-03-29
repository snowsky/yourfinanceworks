import { useMemo, useState } from "react";
import { Clock, CreditCard, FileText, Filter, ListChecks, Loader2, StickyNote } from "lucide-react";

import { type ClientActivityItem } from "@/lib/api";
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { Badge } from "@/components/ui/badge";

const ACTIVITY_TYPE_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  note_created: { label: "Notes", icon: StickyNote, color: "text-yellow-500" },
  task_created: { label: "Tasks", icon: ListChecks, color: "text-blue-500" },
  task_completed: { label: "Tasks", icon: ListChecks, color: "text-green-500" },
  invoice_created: { label: "Invoices", icon: FileText, color: "text-sky-500" },
  invoice_overdue: { label: "Invoices", icon: FileText, color: "text-red-500" },
  payment_received: { label: "Payments", icon: CreditCard, color: "text-emerald-500" },
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "notes", label: "Notes" },
  { id: "tasks", label: "Tasks" },
  { id: "invoices", label: "Invoices" },
  { id: "payments", label: "Payments" },
];

function formatWhen(value: string) {
  return new Date(value).toLocaleString();
}

function formatRelative(value: string) {
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMinutes > 0) return `${diffMinutes}m ago`;
  return "Just now";
}

function matchesFilter(item: ClientActivityItem, filter: string) {
  if (filter === "all") return true;
  if (filter === "notes") return item.type.startsWith("note");
  if (filter === "tasks") return item.type.startsWith("task");
  if (filter === "invoices") return item.type.startsWith("invoice");
  if (filter === "payments") return item.type.startsWith("payment");
  return true;
}

interface ClientActivityFeedProps {
  activity: ClientActivityItem[];
  newNote: string;
  onNoteChange: (value: string) => void;
  onAddNote: () => void;
  onMarkContacted?: () => void;
  onCreateTaskFromActivity?: (item: ClientActivityItem) => void;
  submittingNote?: boolean;
  markingContacted?: boolean;
}

export function ClientActivityFeed({
  activity,
  newNote,
  onNoteChange,
  onAddNote,
  onMarkContacted,
  onCreateTaskFromActivity,
  submittingNote = false,
  markingContacted = false,
}: ClientActivityFeedProps) {
  const [activeFilter, setActiveFilter] = useState("all");

  const filtered = useMemo(
    () => activity.filter((item) => matchesFilter(item, activeFilter)),
    [activity, activeFilter]
  );

  return (
    <ProfessionalCard className="w-full backdrop-blur-sm bg-card/95 shadow-xl border-primary/10">
      <ProfessionalCardHeader className="pb-4 border-b border-border/50">
        <ProfessionalCardTitle className="text-xl font-bold flex items-center gap-2">
          <Clock className="h-5 w-5 text-primary" />
          Client Activity
        </ProfessionalCardTitle>

        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm text-muted-foreground">
              Track notes, tasks, invoices, and payments in one contact record.
            </p>
            {onMarkContacted && (
              <ProfessionalButton
                size="sm"
                variant="outline"
                onClick={onMarkContacted}
                loading={markingContacted}
                leftIcon={<Clock className="h-4 w-4" />}
              >
                Mark Contacted
              </ProfessionalButton>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="h-3.5 w-3.5 text-muted-foreground" />
            {FILTERS.map((filter) => (
              <button
                key={filter.id}
                onClick={() => setActiveFilter(filter.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                  activeFilter === filter.id
                    ? "bg-primary text-primary-foreground border-primary shadow-sm"
                    : "bg-muted/50 text-muted-foreground border-border hover:bg-muted hover:border-primary/30"
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </ProfessionalCardHeader>

      <ProfessionalCardContent className="pt-6 space-y-6">
        <div className="space-y-3 p-4 bg-muted/20 rounded-xl border border-border/50">
          <ProfessionalTextarea
            placeholder="Add a note to this client record..."
            value={newNote}
            onChange={(e) => onNoteChange(e.target.value)}
            rows={2}
            variant="filled"
          />
          <div className="flex justify-end">
            <ProfessionalButton
              onClick={onAddNote}
              disabled={submittingNote || !newNote.trim()}
              size="sm"
              leftIcon={submittingNote ? <Loader2 className="h-4 w-4 animate-spin" /> : <StickyNote className="h-4 w-4" />}
            >
              Add Note
            </ProfessionalButton>
          </div>
        </div>

        <div className="space-y-4">
          {filtered.length === 0 ? (
            <div className="rounded-xl border border-border/50 bg-muted/20 p-6 text-sm text-muted-foreground">
              No activity matches this filter yet.
            </div>
          ) : (
            filtered.map((item) => {
              const meta = ACTIVITY_TYPE_META[item.type] || {
                label: item.type,
                icon: Clock,
                color: "text-muted-foreground",
              };
              const Icon = meta.icon;

              return (
                <div key={`${item.entity_type}-${item.entity_id}-${item.timestamp}`} className="flex gap-4">
                  <div className={`mt-1 rounded-xl border border-border/50 bg-card p-3 ${meta.color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 rounded-xl border border-border/50 bg-muted/20 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{item.title}</p>
                        {item.description && (
                          <p className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{item.description}</p>
                        )}
                      </div>
                      <Badge variant="outline">{meta.label}</Badge>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      {item.actor_name && <span>{item.actor_name}</span>}
                      <span>{formatRelative(item.timestamp)}</span>
                      <span>{formatWhen(item.timestamp)}</span>
                    </div>

                    {onCreateTaskFromActivity &&
                      (item.type === "invoice_overdue" || item.type === "payment_received" || item.type === "note_created") && (
                        <div className="mt-4 flex justify-end">
                          <ProfessionalButton
                            size="sm"
                            variant="outline"
                            onClick={() => onCreateTaskFromActivity(item)}
                          >
                            Create Follow-Up
                          </ProfessionalButton>
                        </div>
                      )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}
