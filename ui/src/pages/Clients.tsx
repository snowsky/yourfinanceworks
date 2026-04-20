import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, Search, Loader2, Pencil, Trash2, Users, Tag, Minus, X, MoreHorizontal, DollarSign, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect, useMemo } from "react";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useColumnVisibility, type ColumnDef } from "@/hooks/useColumnVisibility";
import { ColumnPicker } from "@/components/ui/column-picker";
import { ShareButton } from "@/components/sharing/ShareButton";
import { Share2 } from "lucide-react";
import { ContentSection } from "@/components/ui/professional-layout";

const CLIENT_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name', essential: true },
  { key: 'email', label: 'Email', essential: true },
  { key: 'labels', label: 'Labels' },
  { key: 'phone', label: 'Phone' },
  { key: 'address', label: 'Address' },
  { key: 'currency', label: 'Preferred Currency' },
  { key: 'total_paid', label: 'Total Paid' },
  { key: 'outstanding_balance', label: 'Outstanding Balance' },
  { key: 'actions', label: 'Actions', essential: true },
];

const Clients = () => {
  const { t } = useTranslation();
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('clients', CLIENT_COLUMNS);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [clientToDelete, setClientToDelete] = useState<Client | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  // Selection and Bulk Actions
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkLabel, setBulkLabel] = useState("");
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalClients, setTotalClients] = useState(0);

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();
  const [shareClientId, setShareClientId] = useState<number | null>(null);

  // Get current tenant ID to trigger refetch when organization switches
  const getCurrentTenantId = () => {
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        return selectedTenantId;
      }
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user?.tenant_id?.toString();
      }
    } catch (e) {
      console.error('Error getting tenant ID:', e);
    }
    return null;
  };

  // Update tenant ID when it changes
  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Clients: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
      }
    };

    updateTenantId();

    // Listen for storage changes
    const handleStorageChange = () => {
      updateTenantId();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [currentTenantId]);

  useEffect(() => {
    const fetchClients = async () => {
      setLoading(true);
      try {
        // Ensure page and pageSize are valid numbers
        const currentPage = typeof page === 'number' ? Math.max(1, page) : 1;
        const currentPageSize = typeof pageSize === 'number' ? Math.max(1, pageSize) : 50;
        const skip = (currentPage - 1) * currentPageSize;

        const data = await clientApi.getClients(skip, currentPageSize, labelFilter || undefined);
        setClients(data.items);
        setTotalClients(data.total);
      } catch (error) {
        console.error("Failed to fetch clients:", error);
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
      }
    };

    fetchClients();
  }, [currentTenantId, page, pageSize, labelFilter]); // Use state variables as dependency

  const filteredClients = useMemo(
    () => (clients || []).filter(client =>
      client.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (client.email || '').toLowerCase().includes(searchQuery.toLowerCase())
    ),
    [clients, searchQuery]
  );

  const filteredSummary = useMemo(() => {
    const totals = filteredClients.reduce(
      (acc, client) => {
        acc.paid += Number(client.paid_amount || 0);
        acc.outstanding += Number(client.outstanding_balance || 0);
        if ((client.labels || []).length > 0) acc.withLabels += 1;
        return acc;
      },
      { paid: 0, outstanding: 0, withLabels: 0 }
    );
    return totals;
  }, [filteredClients]);

  const handleDelete = async () => {
    if (!clientToDelete) return;

    setDeleting(true);
    try {
      await clientApi.deleteClient(clientToDelete.id);
      setClients((clients || []).filter(c => c.id !== clientToDelete.id));
      toast.success(t('clients.client_deleted'));
    } catch (error) {
      console.error("Failed to delete client:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setDeleting(false);
      setClientToDelete(null);
    }
  };

  const handleBulkDelete = async () => {
    setDeleting(true);
    try {
      await Promise.all(selectedIds.map(id => clientApi.deleteClient(id)));
      setClients(prev => prev.filter(c => !selectedIds.includes(c.id)));
      setSelectedIds([]);
      setBulkDeleteModalOpen(false);
      toast.success(t('clients.bulk_delete_success', { count: selectedIds.length, defaultValue: 'Clients deleted successfully' }));
    } catch (error) {
      console.error("Failed to delete clients:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="h-full space-y-8 fade-in dashboard-highlight-mode dashboard-shell">
        {/* Hero Header */}
        <div className="dashboard-highlight-block dashboard-highlight-block-primary dashboard-hero bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 md:p-7 backdrop-blur-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2 flex-1">
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">{t('clients.title')}</h1>
              <p className="text-muted-foreground text-sm md:text-base max-w-2xl">{t('clients.description')}</p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/25">
                  <Users className="h-3 w-3 mr-1" />
                  {t('common.total', { defaultValue: 'Total' })}: {totalClients}
                </Badge>
                <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20">
                  <DollarSign className="h-3 w-3 mr-1" />
                  {t('clients.table.total_paid')}: ${filteredSummary.paid.toFixed(2)}
                </Badge>
                <Badge variant="secondary" className="bg-orange-500/10 text-orange-700 border-orange-500/20">
                  <AlertCircle className="h-3 w-3 mr-1" />
                  {t('clients.table.outstanding_balance')}: ${filteredSummary.outstanding.toFixed(2)}
                </Badge>
              </div>
            </div>
            {canPerformAction && (
              <Link to="/clients/new">
                <ProfessionalButton variant="gradient" size="default" className="shadow-lg whitespace-nowrap">
                  <Plus className="h-4 w-4" />
                  {t('clients.add_client')}
                </ProfessionalButton>
              </Link>
            )}
          </div>
        </div>

        <ProfessionalCard className="slide-in dashboard-highlight-block dashboard-highlight-block-primary" variant="elevated">
          <ContentSection
            title={t('clients.client_list')}
            description={t('clients.manage_clients_description')}
            className="space-y-6 dashboard-section rounded-2xl p-5 md:p-6"
            headerClassName="dashboard-section-header"
            titleClassName="dashboard-section-title"
            descriptionClassName="dashboard-section-description"
          >
            <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4 pb-5 border-b border-border/50">
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <div className="relative w-full sm:w-auto">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('clients.search_placeholder')}
                    className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Tag className="h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('clients.filter_by_label', { defaultValue: 'Filter by label' })}
                    className="w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={labelFilter}
                    onChange={(e) => setLabelFilter(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 flex-wrap justify-end">
                <ColumnPicker columns={CLIENT_COLUMNS} isVisible={isVisible} onToggle={toggle} onReset={reset} hiddenCount={hiddenCount} />
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
                  <Select value={String(pageSize)} onValueChange={(v) => {
                    const pageSizeValue = typeof v === 'string' ? Number(v) : 50;
                    setPageSize(pageSizeValue);
                    setPage(1);
                  }}>
                    <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 20, 50, 100].map(n => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Bulk actions bar */}
            {selectedIds.length > 0 && (
              <div className="dashboard-highlight-item flex flex-col md:flex-row items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl shadow-sm gap-4 slide-in">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
                  <span className="text-sm font-bold text-foreground">
                    {selectedIds.length} client{selectedIds.length !== 1 ? 's' : ''} selected
                  </span>
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedIds([])}
                    className="h-8 text-xs hover:bg-primary/10 transition-colors"
                  >
                    Clear
                  </ProfessionalButton>
                </div>

                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
                  <div className="relative group flex-1 md:flex-initial min-w-[200px]">
                    <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      placeholder={t('clients.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
                      value={bulkLabel}
                      onChange={(e) => setBulkLabel(e.target.value)}
                      className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <ProfessionalButton
                      variant="outline"
                      size="sm"
                      disabled={!canPerformAction || !bulkLabel.trim()}
                      onClick={async () => {
                        try {
                          await clientApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                          // Ensure page and pageSize are valid numbers
                          const currentPage = typeof page === 'number' ? Math.max(1, page) : 1;
                          const currentPageSize = typeof pageSize === 'number' ? Math.max(1, pageSize) : 50;
                          const skip = (currentPage - 1) * currentPageSize;

                          const data = await clientApi.getClients(skip, currentPageSize, labelFilter || undefined);
                          setClients(data.items);
                          setTotalClients(data.total);
                          setSelectedIds([]);
                          setBulkLabel('');
                          toast.success(t('clients.labels.added', { defaultValue: 'Labels added' }));
                        } catch (e: any) {
                          toast.error(e?.message || t('clients.labels.add_failed', { defaultValue: 'Failed to add label' }));
                        }
                      }}
                      className="h-9 px-3 gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add
                    </ProfessionalButton>

                    <ProfessionalButton
                      variant="outline"
                      size="sm"
                      disabled={!canPerformAction || !bulkLabel.trim()}
                      onClick={async () => {
                        try {
                          await clientApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                          // Ensure page and pageSize are valid numbers
                          const currentPage = typeof page === 'number' ? Math.max(1, page) : 1;
                          const currentPageSize = typeof pageSize === 'number' ? Math.max(1, pageSize) : 50;
                          const skip = (currentPage - 1) * currentPageSize;

                          const data = await clientApi.getClients(skip, currentPageSize, labelFilter || undefined);
                          setClients(data.items);
                          setTotalClients(data.total);
                          setSelectedIds([]);
                          setBulkLabel('');
                          toast.success(t('clients.labels.removed', { defaultValue: 'Labels removed' }));
                        } catch (e: any) {
                          toast.error(e?.message || t('clients.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                        }
                      }}
                      className="h-9 px-3 gap-1.5"
                    >
                      <Minus className="h-3.5 w-3.5" />
                      Remove
                    </ProfessionalButton>
                  </div>

                  <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

                  <ProfessionalButton
                    variant="destructive"
                    size="sm"
                    onClick={() => setBulkDeleteModalOpen(true)}
                    disabled={!canPerformAction}
                    className="h-9 px-3 gap-1.5 shadow-sm"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete Selected
                  </ProfessionalButton>
                </div>
              </div>
            )}

            {/* Content */}
            {loading ? (
              <div className="flex justify-center items-center h-40">
                <div className="flex flex-col items-center gap-4">
                  <div className="relative w-12 h-12">
                    <Loader2 className="h-12 w-12 animate-spin text-primary/60" />
                  </div>
                  <p className="text-muted-foreground font-medium">{t('clients.loading')}</p>
                </div>
              </div>
            ) : filteredClients.length > 0 ? (
              <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                      <TableHead className="w-[40px]">
                        <Checkbox
                          checked={filteredClients.length > 0 && selectedIds.length === filteredClients.length}
                          aria-label={t('common.select_all', { defaultValue: 'Select all' })}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedIds(filteredClients.map(c => c.id));
                            } else {
                              setSelectedIds([]);
                            }
                          }}
                        />
                      </TableHead>
                      {isVisible('id') && <TableHead className="font-bold text-foreground">{t('common.id', { defaultValue: 'ID' })}</TableHead>}
                      <TableHead className="font-bold text-foreground">{t('clients.table.name')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('clients.table.email')}</TableHead>
                      {isVisible('labels') && <TableHead className="font-bold text-foreground">{t('common.labels', { defaultValue: 'Labels' })}</TableHead>}
                      {isVisible('phone') && <TableHead className="font-bold text-foreground">{t('clients.table.phone')}</TableHead>}
                      {isVisible('address') && <TableHead className="font-bold text-foreground">{t('clients.table.address')}</TableHead>}
                      {isVisible('currency') && <TableHead className="font-bold text-foreground">{t('clients.table.preferred_currency')}</TableHead>}
                      {isVisible('total_paid') && <TableHead className="text-right font-bold text-foreground">{t('clients.table.total_paid')}</TableHead>}
                      {isVisible('outstanding_balance') && <TableHead className="text-right font-bold text-foreground">{t('clients.table.outstanding_balance')}</TableHead>}
                      <TableHead className="w-[100px] text-right font-bold text-foreground">{t('clients.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredClients.map((client) => (
                      <TableRow key={client.id} className={`hover:bg-muted/50 transition-all duration-200 border-b border-border/30 ${selectedIds.includes(client.id) ? 'bg-primary/5' : ''}`}>
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.includes(client.id)}
                            aria-label={t('clients.select_client', { defaultValue: 'Select client' })}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedIds(prev => [...prev, client.id]);
                              } else {
                                setSelectedIds(prev => prev.filter(id => id !== client.id));
                              }
                            }}
                          />
                        </TableCell>
                        {isVisible('id') && <TableCell className="font-mono text-xs text-muted-foreground">{client.id}</TableCell>}
                        <TableCell className="font-semibold text-foreground">{client.name}</TableCell>
                        <TableCell className="text-foreground">{client.email}</TableCell>
                        {isVisible('labels') && <TableCell>
                          <div className="flex flex-wrap gap-1 items-center min-w-[150px]">
                            {client.labels && client.labels.map((label, idx) => (
                              <Badge
                                key={idx}
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                              >
                                {label}
                                <button
                                  aria-label={t('clients.remove_label', { defaultValue: 'Remove label' })}
                                  className="hover:text-destructive transition-colors"
                                  onClick={() => {
                                    const next = client.labels?.filter((_, i) => i !== idx) || [];
                                    clientApi.updateClient(client.id, { labels: next }).then(() => {
                                      setClients((prev) => prev.map((x) => (x.id === client.id ? { ...x, labels: next } : x)));
                                    }).catch((err: any) => {
                                      toast.error(err?.message || t('clients.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                    });
                                  }}
                                >
                                  <X className="h-2.5 w-2.5" />
                                </button>
                              </Badge>
                            ))}
                            <Input
                              placeholder={t('expenses.labels.label_placeholder', { defaultValue: 'Add label...' })}
                              className="w-[100px] h-7 text-[10px] px-2 bg-muted/20 border-border/40 focus:bg-background transition-all"
                              value={newLabelValueById[client.id] || ''}
                              onChange={(ev) => setNewLabelValueById((prev) => ({ ...prev, [client.id]: ev.target.value }))}
                              onKeyDown={(ev) => {
                                if (ev.key === 'Enter' && newLabelValueById[client.id]?.trim()) {
                                  const raw = newLabelValueById[client.id].trim();
                                  const existing = client.labels || [];
                                  if (existing.includes(raw)) { 
                                    setNewLabelValueById((prev) => ({ ...prev, [client.id]: '' })); 
                                    return; 
                                  }
                                  const next = [...existing, raw].slice(0, 10);
                                  clientApi.updateClient(client.id, { labels: next }).then(() => {
                                    setClients((prev) => prev.map((x) => (x.id === client.id ? { ...x, labels: next } : x)));
                                    setNewLabelValueById((prev) => ({ ...prev, [client.id]: '' }));
                                  }).catch((err: any) => {
                                    toast.error(err?.message || t('clients.labels.add_failed', { defaultValue: 'Failed to add label' }));
                                  });
                                }
                              }}
                            />
                          </div>
                        </TableCell>}
                        {isVisible('phone') && <TableCell className="text-foreground">{client.phone}</TableCell>}
                        {isVisible('address') && <TableCell className="text-foreground">{client.address}</TableCell>}
                        {isVisible('currency') && <TableCell className="text-foreground">{client.preferred_currency || 'USD'}</TableCell>}
                        {isVisible('total_paid') && <TableCell className="text-right font-semibold text-foreground">
                          ${client.paid_amount.toFixed(2)}
                        </TableCell>}
                        {isVisible('outstanding_balance') && <TableCell className="text-right">
                          <span className={(client.outstanding_balance || 0) > 0 ? 'text-orange-600 font-semibold' : 'text-green-600 font-semibold'}>
                            ${(client.outstanding_balance || 0).toFixed(2)}
                          </span>
                        </TableCell>}
                        <TableCell className="text-right">
                          {canPerformAction && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem asChild>
                                  <Link to={`/clients/edit/${client.id}`} className="flex items-center">
                                    <Pencil className="mr-2 h-4 w-4" /> {t('common.edit', 'Edit')}
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => setShareClientId(client.id)}>
                                  <Share2 className="mr-2 h-4 w-4" /> Share
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setClientToDelete(client)}>
                                  <Trash2 className="mr-2 h-4 w-4" /> {t('common.delete', 'Delete')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 gap-4">
                <div className="p-4 rounded-full bg-muted/50">
                  <Users className="h-10 w-10 text-muted-foreground/50" />
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-bold text-foreground mb-2">{t('clients.no_clients', 'No clients yet')}</h3>
                  <p className="text-muted-foreground max-w-sm mx-auto mb-6">
                    {t('clients.no_clients_description', 'Start building your customer base. Add your first client to begin managing invoices and payments.')}
                  </p>
                  {canPerformAction && (
                    <ProfessionalButton asChild variant="gradient" size="lg">
                      <Link to="/clients/new">
                        <Plus className="h-4 w-4" /> {t('clients.add_client')}
                      </Link>
                    </ProfessionalButton>
                  )}
                </div>
              </div>
            )}

            {/* Pagination */}
            {filteredClients.length > 0 && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
                <div className="text-sm text-muted-foreground">
                {t('common.showing_results', {
                  shown: filteredClients.length,
                  total: totalClients,
                  defaultValue: 'Showing {{shown}} of {{total}} results'
                })}
                </div>
                <div className="flex items-center gap-2">
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(prev => Math.max(1, prev - 1))}
                    disabled={page === 1}
                    className="h-9 px-4"
                  >
                    {t('common.previous')}
                  </ProfessionalButton>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.ceil(totalClients / pageSize) }, (_, i) => i + 1)
                      .filter(p => p === 1 || p === Math.ceil(totalClients / pageSize) || Math.abs(p - page) <= 1)
                      .map((p, i, arr) => (
                        <div key={p} className="flex items-center">
                          {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                          <ProfessionalButton
                            variant={page === p ? "default" : "outline"}
                            size="sm"
                            onClick={() => setPage(p)}
                            className={`h-9 w-9 p-0 ${page === p ? 'shadow-md shadow-primary/20' : ''}`}
                          >
                            {p}
                          </ProfessionalButton>
                        </div>
                      ))}
                  </div>
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(prev => Math.min(Math.ceil(totalClients / pageSize), prev + 1))}
                    disabled={page >= Math.ceil(totalClients / pageSize)}
                    className="h-9 px-4"
                  >
                    {t('common.next')}
                  </ProfessionalButton>
                </div>
              </div>
            )}
          </ContentSection>
        </ProfessionalCard>
      </div>

      <Dialog open={!!clientToDelete} onOpenChange={() => setClientToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('clients.delete_client')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>{t('clients.delete_confirm', { name: clientToDelete?.name })}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClientToDelete(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('clients.bulk_delete_title', { defaultValue: 'Delete Multiple Clients' })}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>{t('clients.bulk_delete_confirm', { count: selectedIds.length, defaultValue: `Are you sure you want to delete ${selectedIds.length} clients? This action cannot be undone.` })}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDeleteModalOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleBulkDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {shareClientId !== null && (
        <ShareButton recordType="client" recordId={shareClientId} open onOpenChange={(open) => { if (!open) setShareClientId(null); }} />
      )}
    </>
  );
};

export default Clients;
