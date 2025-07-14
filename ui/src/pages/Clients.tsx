import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Plus, Search, Loader2, Pencil, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";
import { clientApi, Client } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { canPerformActions } from "@/utils/auth";

const Clients = () => {
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
        toast.error("Failed to load clients");
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
      toast.success("Client deleted successfully");
    } catch (error) {
      console.error("Failed to delete client:", error);
      toast.error("Failed to delete client");
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
            <h1 className="text-3xl font-bold">Clients</h1>
            <p className="text-muted-foreground">Manage your client information and balances</p>
          </div>
          {canPerformAction && (
            <Link to="/clients/new">
              <Button className="sm:self-end whitespace-nowrap">
                <Plus className="mr-2 h-4 w-4" /> Add Client
              </Button>
            </Link>
          )}
        </div>
        
        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>Client List</CardTitle>
              <div className="relative max-w-sm">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search clients..."
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
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead className="hidden md:table-cell">Address</TableHead>
                    <TableHead className="text-right">Total Paid</TableHead>
                    <TableHead className="text-right">Outstanding Balance</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          Loading clients...
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
                        No clients found.
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
            <DialogTitle>Delete Client</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>Are you sure you want to delete {clientToDelete?.name}? This action cannot be undone.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClientToDelete(null)}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
};

export default Clients;
