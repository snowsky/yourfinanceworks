import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClientForm } from "@/components/clients/ClientForm";
import { clientApi, Client, ClientRecordResponse, getErrorMessage, userApi } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, ArrowLeft, CheckCircle2, Clock3, DollarSign, Plus } from "lucide-react";
import { ClientNotes } from "@/components/clients/ClientNotes";
import { ClientActivityFeed } from "@/components/clients/ClientActivityFeed";
import { CrmContactsPanel } from "@/components/clients/CrmContactsPanel";
import { useTranslation } from 'react-i18next';
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalCard, ProfessionalCardContent, ProfessionalCardHeader, ProfessionalCardTitle } from "@/components/ui/professional-card";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalTextarea } from "@/components/ui/professional-textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePlugins } from "@/contexts/PluginContext";
import { ShareButton } from "@/components/sharing/ShareButton";
import type { User } from "@/types";

const BASE_TABS = ["Overview", "Details", "Activity", "Tasks"] as const;
type TabValue = "Overview" | "Details" | "Activity" | "Tasks" | "Contacts";

const STAGE_OPTIONS = [
  { value: "lead", label: "Lead" },
  { value: "prospect", label: "Prospect" },
  { value: "quoted", label: "Quoted" },
  { value: "active_client", label: "Active Client" },
  { value: "at_risk", label: "At Risk" },
  { value: "inactive", label: "Inactive" },
];

const RELATIONSHIP_OPTIONS = [
  { value: "healthy", label: "Healthy" },
  { value: "needs_follow_up", label: "Needs Follow Up" },
  { value: "at_risk", label: "At Risk" },
  { value: "inactive", label: "Inactive" },
];

const TASK_PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

function formatDateTime(value?: string | null) {
  if (!value) return "Not set";
  return new Date(value).toLocaleString();
}

function toLocalDateTimeInputValue(date: Date) {
  const offset = date.getTimezoneOffset();
  const localDate = new Date(date.getTime() - offset * 60_000);
  return localDate.toISOString().slice(0, 16);
}

function SummaryCard({
  title,
  value,
  description,
  icon,
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{title}</p>
            <p className="mt-2 text-2xl font-bold text-foreground">{value}</p>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
          <div className="rounded-xl bg-primary/10 p-3 text-primary">{icon}</div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}

const EditClient = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isPluginEnabled } = usePlugins();
  const queryClient = useQueryClient();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState<TabValue>("Overview");
  const [recordForm, setRecordForm] = useState({
    owner_user_id: "",
    stage: "active_client",
    relationship_status: "healthy",
    source: "",
    last_contact_at: "",
    next_follow_up_at: "",
  });
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    due_date: "",
    priority: "medium",
    assigned_to_id: "",
  });
  const [activityNote, setActivityNote] = useState("");

  const tabs: TabValue[] = [...BASE_TABS, ...(isPluginEnabled('crm') ? ['Contacts' as const] : [])];

  const clientId = id ? parseInt(id, 10) : null;

  const { data: clientRecord, isLoading: recordLoading } = useQuery<ClientRecordResponse>({
    queryKey: ['client-record', clientId],
    queryFn: () => clientApi.getClientRecord(clientId!),
    enabled: !!clientId,
  });

  const { data: users = [] } = useQuery<User[]>({
    queryKey: ['client-record-users'],
    queryFn: () => userApi.getUsers(),
    enabled: !!clientId,
  });

  useEffect(() => {
    if (clientRecord?.client) {
      setRecordForm({
        owner_user_id: clientRecord.client.owner_user_id ? String(clientRecord.client.owner_user_id) : "",
        stage: clientRecord.client.stage || "active_client",
        relationship_status: clientRecord.client.relationship_status || "healthy",
        source: clientRecord.client.source || "",
        last_contact_at: clientRecord.client.last_contact_at ? clientRecord.client.last_contact_at.slice(0, 16) : "",
        next_follow_up_at: clientRecord.client.next_follow_up_at ? clientRecord.client.next_follow_up_at.slice(0, 16) : "",
      });
      setTaskForm((current) => ({
        ...current,
        assigned_to_id: current.assigned_to_id || (clientRecord.client.owner_user_id ? String(clientRecord.client.owner_user_id) : ""),
      }));
    }
  }, [clientRecord]);

  const updateRecordMutation = useMutation({
    mutationFn: () => clientApi.updateClientRecord(clientId!, {
      owner_user_id: recordForm.owner_user_id ? Number(recordForm.owner_user_id) : null,
      stage: recordForm.stage,
      relationship_status: recordForm.relationship_status,
      source: recordForm.source || null,
      last_contact_at: recordForm.last_contact_at ? new Date(recordForm.last_contact_at).toISOString() : null,
      next_follow_up_at: recordForm.next_follow_up_at ? new Date(recordForm.next_follow_up_at).toISOString() : null,
    }),
    onSuccess: (updatedClient) => {
      setClient(updatedClient);
      toast.success("Client record updated");
      queryClient.invalidateQueries({ queryKey: ['client-record', clientId] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, t));
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: () => clientApi.createClientTask(clientId!, {
      title: taskForm.title,
      description: taskForm.description || null,
      due_date: new Date(taskForm.due_date).toISOString(),
      priority: taskForm.priority,
      assigned_to_id: Number(taskForm.assigned_to_id),
    }),
    onSuccess: () => {
      toast.success("Client task created");
      setTaskForm({
        title: "",
        description: "",
        due_date: "",
        priority: "medium",
        assigned_to_id: recordForm.owner_user_id || "",
      });
      queryClient.invalidateQueries({ queryKey: ['client-record', clientId] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, t));
    },
  });

  const createActivityNoteMutation = useMutation({
    mutationFn: async (note: string) => {
      const { crmApi } = await import("@/lib/api");
      return crmApi.createNoteForClient(clientId!, { note });
    },
    onSuccess: () => {
      toast.success("Note added");
      setActivityNote("");
      queryClient.invalidateQueries({ queryKey: ['client-record', clientId] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, t));
    },
  });

  const markContactedMutation = useMutation({
    mutationFn: () => clientApi.updateClientRecord(clientId!, {
      last_contact_at: new Date().toISOString(),
    }),
    onSuccess: (updatedClient) => {
      setClient(updatedClient);
      toast.success("Client marked as contacted");
      queryClient.invalidateQueries({ queryKey: ['client-record', clientId] });
      queryClient.invalidateQueries({ queryKey: ['clients'] });
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, t));
    },
  });

  useEffect(() => {
    const fetchClient = async () => {
      if (!id) {
        navigate("/clients");
        return;
      }

      setLoading(true);
      try {
        const data = await clientApi.getClient(parseInt(id));
        setClient(data);
      } catch (error) {
        console.error("Failed to fetch client:", error);
        toast.error(getErrorMessage(error, t));
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchClient();
  }, [id, navigate, t]);

  const addActivityNote = async () => {
    if (!clientId || !activityNote.trim()) {
      toast.error("Note cannot be empty.");
      return;
    }

    createActivityNoteMutation.mutate(activityNote.trim());
  };

  const openFollowUpTask = (options?: {
    title?: string;
    description?: string;
    priority?: string;
  }) => {
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + 1);
    dueDate.setHours(9, 0, 0, 0);

    setTaskForm((current) => ({
      ...current,
      title: options?.title ?? current.title,
      description: options?.description ?? current.description,
      priority: options?.priority ?? current.priority,
      due_date: current.due_date || toLocalDateTimeInputValue(dueDate),
      assigned_to_id: current.assigned_to_id || recordForm.owner_user_id,
    }));
    setActiveTab("Tasks");
  };

  const handleCreateTaskFromActivity = (item: ClientRecordResponse["recent_activity"][number]) => {
    if (!client) return;

    if (item.type === "invoice_overdue") {
      openFollowUpTask({
        title: `Follow up on ${item.title.replace(" is overdue", "")}`,
        description: item.description || `Contact ${client.name} about the overdue balance and confirm the payment timeline.`,
        priority: "high",
      });
      return;
    }

    if (item.type === "payment_received") {
      openFollowUpTask({
        title: `Follow up after payment from ${client.name}`,
        description: "Send a thank-you note, confirm receipt details, or schedule the next step.",
        priority: "medium",
      });
      return;
    }

    if (item.type === "note_created") {
      openFollowUpTask({
        title: `Continue follow-up for ${client.name}`,
        description: item.description || "Review the latest note and decide on the next client action.",
        priority: "medium",
      });
    }
  };

  if (loading) {
    return (
      <>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('editClient.loadingClientData')}</p>
        </div>
      </>
    );
  }

  if (error || !client) {
    return (
      <>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t('editClient.clientNotFound')}</h1>
            <p className="text-muted-foreground">{t('editClient.clientNotFoundDescription')}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <ProfessionalButton
                  variant="outline"
                  size="icon-sm"
                  onClick={() => navigate('/clients')}
                  className="rounded-full"
                >
                  <ArrowLeft className="h-4 w-4" />
                </ProfessionalButton>
              </div>
              <h1 className="text-4xl font-bold tracking-tight">{t('editClient.editClient')}</h1>
              <p className="text-lg text-muted-foreground">{t('editClient.updateClientInformation')}</p>
            </div>
            {client?.id && <ShareButton recordType="client" recordId={client.id} />}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-5 py-2.5 text-sm font-medium transition-all duration-200 -mb-px
                border-b-2
                ${
                  activeTab === tab
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
                }
              `}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "Overview" && client && clientRecord && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard
                title="Outstanding"
                value={new Intl.NumberFormat(undefined, { style: 'currency', currency: client.preferred_currency || 'USD' }).format(clientRecord.summary.total_outstanding || 0)}
                description={`${clientRecord.summary.overdue_invoices_count} overdue invoice(s)`}
                icon={<DollarSign className="h-5 w-5" />}
              />
              <SummaryCard
                title="Open Invoices"
                value={String(clientRecord.summary.open_invoices_count)}
                description="Invoices still awaiting payment"
                icon={<Clock3 className="h-5 w-5" />}
              />
              <SummaryCard
                title="Open Tasks"
                value={String(clientRecord.summary.open_tasks_count)}
                description="Reminder-backed follow-ups"
                icon={<CheckCircle2 className="h-5 w-5" />}
              />
              <SummaryCard
                title="Last Contact"
                value={client.last_contact_at ? new Date(client.last_contact_at).toLocaleDateString() : "Not set"}
                description={`Next: ${client.next_follow_up_at ? new Date(client.next_follow_up_at).toLocaleDateString() : "not scheduled"}`}
                icon={<Clock3 className="h-5 w-5" />}
              />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
              <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                  <ProfessionalCardTitle>Relationship Record</ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-5">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Owner</label>
                      <Select value={recordForm.owner_user_id || "unassigned"} onValueChange={(value) => setRecordForm((current) => ({ ...current, owner_user_id: value === "unassigned" ? "" : value }))}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select owner" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="unassigned">Unassigned</SelectItem>
                          {users.map((user) => (
                            <SelectItem key={user.id} value={String(user.id)}>
                              {user.name || user.email}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium">Stage</label>
                      <Select value={recordForm.stage} onValueChange={(value) => setRecordForm((current) => ({ ...current, stage: value }))}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {STAGE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium">Relationship Status</label>
                      <Select value={recordForm.relationship_status} onValueChange={(value) => setRecordForm((current) => ({ ...current, relationship_status: value }))}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {RELATIONSHIP_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <ProfessionalInput
                      label="Source"
                      value={recordForm.source}
                      onChange={(event) => setRecordForm((current) => ({ ...current, source: event.target.value }))}
                      placeholder="Referral, website, accountant..."
                    />

                    <ProfessionalInput
                      label="Last Contact"
                      type="datetime-local"
                      value={recordForm.last_contact_at}
                      onChange={(event) => setRecordForm((current) => ({ ...current, last_contact_at: event.target.value }))}
                    />

                    <ProfessionalInput
                      label="Next Follow-Up"
                      type="datetime-local"
                      value={recordForm.next_follow_up_at}
                      onChange={(event) => setRecordForm((current) => ({ ...current, next_follow_up_at: event.target.value }))}
                    />
                  </div>

                  <div className="flex justify-end">
                    <ProfessionalButton
                      variant="gradient"
                      onClick={() => updateRecordMutation.mutate()}
                      loading={updateRecordMutation.isPending}
                    >
                      Save record
                    </ProfessionalButton>
                  </div>
                </ProfessionalCardContent>
              </ProfessionalCard>

              <ProfessionalCard variant="elevated">
                <ProfessionalCardHeader>
                  <ProfessionalCardTitle>Open Tasks</ProfessionalCardTitle>
                </ProfessionalCardHeader>
                <ProfessionalCardContent className="space-y-4">
                  {clientRecord.open_tasks.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No open client tasks yet.</p>
                  ) : (
                    clientRecord.open_tasks.map((task) => (
                      <div key={task.id} className="rounded-xl border border-border/50 bg-muted/20 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{task.title}</p>
                            <p className="mt-1 text-sm text-muted-foreground">{task.description || "No description"}</p>
                          </div>
                          <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                            {task.priority}
                          </span>
                        </div>
                        <p className="mt-3 text-xs text-muted-foreground">
                          Due {formatDateTime(task.due_date)} {task.task_origin ? `• ${task.task_origin}` : ""}
                        </p>
                      </div>
                    ))
                  )}
                </ProfessionalCardContent>
              </ProfessionalCard>
            </div>
          </div>
        )}

        {activeTab === "Details" && (
          <>
            <ClientForm client={client} isEdit={true} />
            {client && <ClientNotes clientId={client.id} />}
          </>
        )}

        {activeTab === "Activity" && client && clientRecord && (
          <ClientActivityFeed
            activity={clientRecord.recent_activity}
            newNote={activityNote}
            onNoteChange={setActivityNote}
            onAddNote={addActivityNote}
            onMarkContacted={() => markContactedMutation.mutate()}
            onCreateTaskFromActivity={handleCreateTaskFromActivity}
            submittingNote={createActivityNoteMutation.isPending}
            markingContacted={markContactedMutation.isPending}
          />
        )}

        {activeTab === "Tasks" && client && (
          <div className="space-y-6">
            <ProfessionalCard variant="elevated">
              <ProfessionalCardHeader>
                <ProfessionalCardTitle>Create Follow-Up Task</ProfessionalCardTitle>
              </ProfessionalCardHeader>
              <ProfessionalCardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <ProfessionalInput
                    label="Title"
                    value={taskForm.title}
                    onChange={(event) => setTaskForm((current) => ({ ...current, title: event.target.value }))}
                    placeholder="Call about overdue invoice"
                  />
                  <ProfessionalInput
                    label="Due Date"
                    type="datetime-local"
                    value={taskForm.due_date}
                    onChange={(event) => setTaskForm((current) => ({ ...current, due_date: event.target.value }))}
                  />
                </div>

                <ProfessionalTextarea
                  label="Description"
                  value={taskForm.description}
                  onChange={(event) => setTaskForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Confirm payment timing and document the conversation."
                />

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Priority</label>
                    <Select value={taskForm.priority} onValueChange={(value) => setTaskForm((current) => ({ ...current, priority: value }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TASK_PRIORITY_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Assign To</label>
                    <Select value={taskForm.assigned_to_id || "unassigned"} onValueChange={(value) => setTaskForm((current) => ({ ...current, assigned_to_id: value === "unassigned" ? "" : value }))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="unassigned">Select user</SelectItem>
                        {users.map((user) => (
                          <SelectItem key={user.id} value={String(user.id)}>
                            {user.name || user.email}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="flex justify-end">
                  <ProfessionalButton
                    variant="gradient"
                    leftIcon={<Plus className="h-4 w-4" />}
                    onClick={() => createTaskMutation.mutate()}
                    loading={createTaskMutation.isPending}
                    disabled={!taskForm.title || !taskForm.due_date || !taskForm.assigned_to_id}
                  >
                    Create task
                  </ProfessionalButton>
                </div>
              </ProfessionalCardContent>
            </ProfessionalCard>

            <ProfessionalCard variant="elevated">
              <ProfessionalCardHeader>
                <ProfessionalCardTitle>Current Client Tasks</ProfessionalCardTitle>
              </ProfessionalCardHeader>
              <ProfessionalCardContent className="space-y-4">
                {recordLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </div>
                ) : clientRecord?.open_tasks.length ? (
                  clientRecord.open_tasks.map((task) => (
                    <div key={task.id} className="rounded-xl border border-border/50 bg-muted/20 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold">{task.title}</p>
                          <p className="mt-1 text-sm text-muted-foreground">{task.description || "No description"}</p>
                        </div>
                        <span className="rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                          {task.priority}
                        </span>
                      </div>
                      <p className="mt-3 text-xs text-muted-foreground">Due {formatDateTime(task.due_date)}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No client-linked tasks yet.</p>
                )}
              </ProfessionalCardContent>
            </ProfessionalCard>
          </div>
        )}

        {activeTab === "Contacts" && client && (
          <CrmContactsPanel clientId={client.id} />
        )}
      </div>
    </>
  );
};

export default EditClient; 
