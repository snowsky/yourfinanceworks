import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Plus, Search, Loader2, Pencil, Trash2, Users } from "lucide-react";
import { useState, useEffect } from "react";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

const Clients = () => {
  const { t } = useTranslation();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [clientToDelete, setClientToDelete] = useState<Client | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();

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
        const data = await clientApi.getClients();
        console.log("Clients data from API:", data);
        data.forEach(client => {
          console.log(`Client ${client.name}: paid_amount=${client.paid_amount}, balance=${client.balance}`);
        });
        setClients(data);
      } catch (error) {
        console.error("Failed to fetch clients:", error);
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
      }
    };

    fetchClients();
  }, [currentTenantId]); // Use state variable as dependency

  const filteredClients = (clients || []).filter(client =>
    client.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    client.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

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

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">{t('clients.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('clients.description')}</p>
            </div>
            {canPerformAction && (
              <Link to="/clients/new">
                <ProfessionalButton variant="default" size="default" className="shadow-lg whitespace-nowrap">
                  <Plus className="h-4 w-4" />
                  {t('clients.add_client')}
                </ProfessionalButton>
              </Link>
            )}
          </div>
        </div>

        <ProfessionalCard className="slide-in" variant="elevated">
          <div className="space-y-6">
            {/* Header with filters */}
            <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
              <div>
                <h2 className="text-2xl font-bold text-foreground">{t('clients.client_list')}</h2>
                <p className="text-muted-foreground mt-1">{t('clients.manage_clients_description')}</p>
              </div>
              <div className="flex items-center">
                <div className="relative w-full lg:w-auto">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('clients.search_placeholder')}
                    className="pl-9 w-full lg:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
            </div>

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
                      <TableHead className="font-bold text-foreground">ID</TableHead>
                      <TableHead className="font-bold text-foreground">{t('clients.table.name')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('clients.table.email')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('clients.table.phone')}</TableHead>
                      <TableHead className="hidden md:table-cell font-bold text-foreground">{t('clients.table.address')}</TableHead>
                      <TableHead className="hidden lg:table-cell font-bold text-foreground">{t('clients.table.preferred_currency')}</TableHead>
                      <TableHead className="text-right font-bold text-foreground">{t('clients.table.total_paid')}</TableHead>
                      <TableHead className="text-right font-bold text-foreground">{t('clients.table.outstanding_balance')}</TableHead>
                      <TableHead className="w-[100px] text-right font-bold text-foreground">{t('clients.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredClients.map((client) => (
                      <TableRow key={client.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                        <TableCell className="font-mono text-xs text-muted-foreground">{client.id}</TableCell>
                        <TableCell className="font-semibold text-foreground">{client.name}</TableCell>
                        <TableCell className="text-foreground">{client.email}</TableCell>
                        <TableCell className="text-foreground">{client.phone}</TableCell>
                        <TableCell className="hidden md:table-cell text-foreground">{client.address}</TableCell>
                        <TableCell className="hidden lg:table-cell text-foreground">{client.preferred_currency || 'USD'}</TableCell>
                        <TableCell className="text-right font-semibold text-foreground">
                          ${client.paid_amount.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={(client.outstanding_balance || 0) > 0 ? 'text-orange-600 font-semibold' : 'text-green-600 font-semibold'}>
                            ${(client.outstanding_balance || 0).toFixed(2)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center justify-end gap-2">
                            {canPerformAction && (
                              <>
                                <Link to={`/clients/edit/${client.id}`}>
                                  <ProfessionalButton variant="ghost" size="icon-sm" className="hover:bg-primary/10 hover:text-primary">
                                    <Pencil className="h-4 w-4" />
                                  </ProfessionalButton>
                                </Link>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => setClientToDelete(client)}
                                  className="hover:bg-destructive/10 hover:text-destructive"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </ProfessionalButton>
                              </>
                            )}
                          </div>
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
          </div>
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
    </>
  );
};

export default Clients;
