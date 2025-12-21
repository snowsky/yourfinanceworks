import { AppLayout } from "@/components/layout/AppLayout";
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
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('clients.title')}
          description={t('clients.description')}
          actions={canPerformAction && (
            <Link to="/clients/new">
              <Button className="sm:self-end whitespace-nowrap h-9">
                <Plus className="mr-2 h-4 w-4" /> {t('clients.add_client')}
              </Button>
            </Link>
          )}
        />

        <ProfessionalCard className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>{t('clients.client_list')}</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('clients.search_placeholder')}
                    className="pl-8 w-full sm:w-[250px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>{t('clients.table.name')}</TableHead>
                    <TableHead>{t('clients.table.email')}</TableHead>
                    <TableHead>{t('clients.table.phone')}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('clients.table.address')}</TableHead>
                    <TableHead className="hidden lg:table-cell">{t('clients.table.preferred_currency')}</TableHead>
                    <TableHead className="text-right">{t('clients.table.total_paid')}</TableHead>
                    <TableHead className="text-right">{t('clients.table.outstanding_balance')}</TableHead>
                    <TableHead className="w-[100px]">{t('clients.table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={9} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('clients.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : filteredClients.length > 0 ? (
                    filteredClients.map((client) => (
                      <TableRow key={client.id} className="hover:bg-muted/50">
                        <TableCell className="font-mono text-xs text-muted-foreground">{client.id}</TableCell>
                        <TableCell className="font-medium">{client.name}</TableCell>
                        <TableCell>{client.email}</TableCell>
                        <TableCell>{client.phone}</TableCell>
                        <TableCell className="hidden md:table-cell">{client.address}</TableCell>
                        <TableCell className="hidden lg:table-cell">{client.preferred_currency || 'USD'}</TableCell>
                        <TableCell className="text-right font-medium">
                          ${client.paid_amount.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={(client.outstanding_balance || 0) > 0 ? 'text-orange-600 font-medium' : 'text-green-600 font-medium'}>
                            ${(client.outstanding_balance || 0).toFixed(2)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {canPerformAction && (
                              <>
                                <Link to={`/clients/edit/${client.id}`}>
                                  <Button variant="ghost" size="icon">
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                </Link>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => setClientToDelete(client)}
                                >
                                  <Trash2 className="h-4 w-4 text-red-500" />
                                </Button>
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={9} className="h-auto p-0 border-none">
                        <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                          <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Users className="h-8 w-8 text-primary" />
                          </div>
                          <h3 className="text-xl font-bold mb-2">{t('clients.no_clients', 'No clients yet')}</h3>
                          <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                            {t('clients.no_clients_description', 'Start building your customer base. Add your first client to begin managing invoices and payments.')}
                          </p>
                          {canPerformAction && (
                            <ProfessionalButton asChild variant="gradient" className="h-10 px-8">
                              <Link to="/clients/new">
                                <Plus className="mr-2 h-4 w-4" /> {t('clients.add_client')}
                              </Link>
                            </ProfessionalButton>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
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
    </AppLayout>
  );
};

export default Clients;
