import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Plus, Search, Loader2, Pencil, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';

const Clients = () => {
  const { t } = useTranslation();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [clientToDelete, setClientToDelete] = useState<Client | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();
  
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
  }, []);
  
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
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{t('clients.title')}</h1>
            <p className="text-muted-foreground">{t('clients.description')}</p>
          </div>
          {canPerformAction && (
            <Link to="/clients/new">
              <Button className="sm:self-end whitespace-nowrap">
                <Plus className="mr-2 h-4 w-4" /> {t('clients.add_client')}
              </Button>
            </Link>
          )}
        </div>
        
        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>{t('clients.client_list')}</CardTitle>
              <div className="relative max-w-sm">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('clients.search_placeholder')}
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('clients.table.name')}</TableHead>
                    <TableHead>{t('clients.table.email')}</TableHead>
                    <TableHead>{t('clients.table.phone')}</TableHead>
                    <TableHead className="hidden md:table-cell">{t('clients.table.address')}</TableHead>
                    <TableHead className="text-right">{t('clients.table.total_paid')}</TableHead>
                    <TableHead className="text-right">{t('clients.table.outstanding_balance')}</TableHead>
                    <TableHead className="w-[100px]">{t('clients.table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('clients.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : filteredClients.length > 0 ? (
                    filteredClients.map((client) => (
                      <TableRow key={client.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">{client.name}</TableCell>
                        <TableCell>{client.email}</TableCell>
                        <TableCell>{client.phone}</TableCell>
                        <TableCell className="hidden md:table-cell">{client.address}</TableCell>
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
                      <TableCell colSpan={6} className="h-24 text-center">
                        {t('clients.no_clients')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
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
