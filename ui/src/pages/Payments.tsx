import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Search, Filter, Loader2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { paymentApi, Payment } from "@/lib/api";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";

const Payments = () => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState("all");
  
  useEffect(() => {
    const fetchPayments = async () => {
      setLoading(true);
      try {
        const data = await paymentApi.getPayments();
        setPayments(data);
      } catch (error) {
        console.error("Failed to fetch payments:", error);
        toast.error("Failed to load payments");
      } finally {
        setLoading(false);
      }
    };
    
    fetchPayments();
  }, []);
  
  const filteredPayments = (payments || []).filter(payment => {
    const matchesSearch = 
      (payment.invoice_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (payment.client_name || '').toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesMethod = methodFilter === "all" || payment.payment_method === methodFilter;
    
    return matchesSearch && matchesMethod;
  });

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">Payments</h1>
          <p className="text-muted-foreground">View and manage payment records</p>
        </div>
        
        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>Payment List</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search payments..."
                    className="pl-8 w-full sm:w-[200px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="flex gap-2 items-center">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Select value={methodFilter} onValueChange={setMethodFilter}>
                    <SelectTrigger className="w-full sm:w-[150px]">
                      <SelectValue placeholder="Filter by method" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Methods</SelectItem>
                      <SelectItem value="credit_card">Credit Card</SelectItem>
                      <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="system">System</SelectItem>
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
                    <TableHead>Date</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          Loading payments...
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (filteredPayments || []).length > 0 ? (
                    (filteredPayments || []).map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell>{payment.invoice_number || 'N/A'}</TableCell>
                        <TableCell>{payment.client_name || 'N/A'}</TableCell>
                        <TableCell>{payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                        <TableCell>
                          <CurrencyDisplay amount={payment.amount || 0} currency={payment.currency || 'USD'} />
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {payment.payment_method || 'N/A'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {payment.status || 'N/A'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        No payments found
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

export default Payments;
