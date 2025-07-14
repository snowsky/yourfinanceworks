import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Plus, Search, Filter, FileText, Loader2, Pencil } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { invoiceApi, Invoice } from "@/lib/api";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate } from '@/lib/utils';

const formatStatus = (status: string) => {
  return status.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

const Invoices = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  
  useEffect(() => {
    const fetchInvoices = async () => {
      setLoading(true);
      try {
        const status = statusFilter !== "all" ? statusFilter : undefined;
        const data = await invoiceApi.getInvoices(status);
        console.log("Invoices data received:", data);
        data.forEach(invoice => {
          console.log(`Invoice ${invoice.number}: amount=${invoice.amount}, paid_amount=${invoice.paid_amount}, outstanding=${invoice.amount - (invoice.paid_amount || 0)}`);
        });
        setInvoices(data);
      } catch (error) {
        console.error("Failed to fetch invoices:", error);
        toast.error("Failed to load invoices");
      } finally {
        setLoading(false);
      }
    };
    
    fetchInvoices();
  }, [statusFilter]);
  
  const filteredInvoices = (invoices || []).filter(invoice => {
    const matchesSearch = 
      invoice.number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (invoice.client_name && invoice.client_name.toLowerCase().includes(searchQuery.toLowerCase()));

    return matchesSearch;
  });

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Invoices</h1>
            <p className="text-muted-foreground">Create and manage your invoices</p>
          </div>
          <Link to="/invoices/new">
            <Button className="sm:self-end whitespace-nowrap">
              <Plus className="mr-2 h-4 w-4" /> New Invoice
            </Button>
          </Link>
        </div>
        
        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>Invoice List</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search invoices..."
                    className="pl-8 w-full sm:w-[200px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="flex gap-2 items-center">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-full sm:w-[150px]">
                      <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Statuses</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="paid">Paid</SelectItem>
                      <SelectItem value="overdue">Overdue</SelectItem>
                      <SelectItem value="partially_paid">Partially Paid</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead className="hidden sm:table-cell">Date</TableHead>
                    <TableHead className="hidden md:table-cell">Due Date</TableHead>
                    <TableHead className="text-right">Total Paid</TableHead>
                    <TableHead className="text-right">Outstanding Balance</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          Loading invoices...
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : filteredInvoices.length > 0 ? (
                    filteredInvoices.map((invoice) => (
                      <TableRow key={invoice.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">
                          <span className="inline-flex items-center">
                            <FileText className="h-4 w-4 mr-2 text-muted-foreground" />
                            {invoice.number}
                          </span>
                        </TableCell>
                        <TableCell>{invoice.client_name}</TableCell>
                        <TableCell className="hidden sm:table-cell">{formatDate(invoice.created_at)}</TableCell>
                        <TableCell className="hidden md:table-cell">{formatDate(invoice.due_date)}</TableCell>
                        <TableCell className="text-right font-medium">
                          <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={(invoice.amount - (invoice.paid_amount || 0)) > 0 ? 'text-orange-600 font-medium' : 'text-green-600 font-medium'}>
                            <CurrencyDisplay amount={invoice.amount - (invoice.paid_amount || 0)} currency={invoice.currency} />
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge 
                            variant={
                              invoice.status === 'paid' ? 'default' : 
                              invoice.status === 'pending' ? 'secondary' : 
                              invoice.status === 'draft' ? 'outline' :
                              'destructive'
                            }
                            className={
                              invoice.status === 'paid' ? 'bg-green-100 text-green-800 hover:bg-green-100' : 
                              invoice.status === 'pending' ? 'bg-orange-100 text-orange-800 hover:bg-orange-100' : 
                              invoice.status === 'draft' ? 'bg-gray-100 text-gray-800 hover:bg-gray-100' :
                              'bg-red-100 text-red-800 hover:bg-red-100'
                            }
                          >
                            {formatStatus(invoice.status)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Link to={`/invoices/edit/${invoice.id}`}>
                            <Button variant="ghost" size="icon">
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        No invoices found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
};

export default Invoices;
