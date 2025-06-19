import React, { useState, useEffect, useMemo, useCallback } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarIcon, Plus, Trash, Loader2, DollarSign, FileText, Edit, Mail } from "lucide-react";
import { format, parseISO, isValid } from "date-fns";
import { useNavigate } from "react-router-dom";
import { PDFDownloadLink } from '@react-pdf/renderer';

import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { clientApi, Client, invoiceApi, paymentApi, Invoice, InvoiceItem, InvoiceStatus, settingsApi, Settings } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { InvoicePDF } from "./InvoicePDF";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

const invoiceItemSchema = z.object({
  description: z.string().min(1, "Description is required"),
  quantity: z.coerce.number().min(1, "Quantity must be at least 1"),
  price: z.coerce.number().min(0.01, "Price must be greater than 0"),
  id: z.number().optional(),
});

const isValidInvoiceStatus = (status: string): status is InvoiceStatus => {
  return ["pending", "paid", "overdue", "partially_paid"].includes(status);
};

const formatStatus = (status: string) => {
  return status.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

const formSchema = z.object({
  client: z.string().min(1, "Client is required"),
  invoiceNumber: z.string().min(1, "Invoice number is required"),
  date: z.date(),
  dueDate: z.date(),
  status: z.enum(["pending", "paid", "overdue", "partially_paid"] as const),
  paidAmount: z.number().min(0, "Paid amount cannot be negative").optional(),
  items: z.array(invoiceItemSchema).min(1, "At least one item is required"),
  notes: z.string().optional(),
  isRecurring: z.boolean().optional(),
  recurringFrequency: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const defaultItem = {
  description: "",
  quantity: 1,
  price: 0,
  amount: 0
};

interface InvoiceFormProps {
  invoice?: Invoice;
  isEdit?: boolean;
}

export function InvoiceForm({ invoice, isEdit = false }: InvoiceFormProps) {
  const navigate = useNavigate();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [previewInvoice, setPreviewInvoice] = useState<Invoice | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [showExcessAmountDialog, setShowExcessAmountDialog] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [showNewClientDialog, setShowNewClientDialog] = useState(false);
  const [newClientForm, setNewClientForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
  });
  const [settings, setSettings] = useState<Settings | null>(null);
  const [updateHistory, setUpdateHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [isRecurring, setIsRecurring] = useState(invoice?.is_recurring || false);

  // Fetch update history for the invoice
  const fetchUpdateHistory = useCallback(async (invoiceId: number) => {
    setLoadingHistory(true);
    try {
      // Get all payments for this invoice
      const allPayments = await paymentApi.getPayments();
      const invoicePayments = allPayments
        .filter(payment => payment.invoice_id === invoiceId)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      // Create history entries for payments
      const paymentHistory = invoicePayments.map(payment => ({
        id: `payment-${payment.id}`,
        type: 'payment',
        action: 'Payment Added',
        amount: payment.amount,
        date: payment.created_at,
        details: `${payment.payment_method} - ${payment.reference_number || 'No reference'}`,
        notes: payment.notes
      }));

      // Add invoice creation entry
      const creationHistory = [{
        id: 'creation',
        type: 'creation',
        action: 'Invoice Created',
        amount: invoice?.amount || 0,
        date: invoice?.created_at || new Date().toISOString(),
        details: `Invoice ${invoice?.number} created`,
        notes: null
      }];

      // Add invoice updates (we'll simulate this for now, could be enhanced with actual audit log)
      const updateHistoryItems = [];
      if (invoice?.updated_at && invoice.updated_at !== invoice.created_at) {
        updateHistoryItems.push({
          id: 'update',
          type: 'update',
          action: 'Invoice Updated',
          amount: invoice.amount,
          date: invoice.updated_at,
          details: `Status: ${formatStatus(invoice.status)}`,
          notes: null
        });
      }

      // Combine and sort all history items
      const allHistory = [...creationHistory, ...updateHistoryItems, ...paymentHistory]
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

      setUpdateHistory(allHistory);
    } catch (error) {
      console.error("Failed to fetch update history:", error);
      toast.error("Failed to load update history");
    } finally {
      setLoadingHistory(false);
    }
  }, [invoice]);

  // Fetch clients and settings
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [clientsData, settingsData] = await Promise.all([
          clientApi.getClients(),
          settingsApi.getSettings()
        ]);
        setClients(clientsData);
        setSettings(settingsData);
      } catch (error) {
        console.error("Failed to fetch data:", error);
        toast.error("Failed to load data");
        navigate('/invoices'); // Navigate back if data loading fails
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [navigate]);

  // Fetch update history when invoice is available
  useEffect(() => {
    if (invoice && isEdit) {
      fetchUpdateHistory(invoice.id);
    }
  }, [invoice, isEdit, fetchUpdateHistory]);

  const handleCreateClient = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        toast.error("Please log in to create a client");
        return;
      }

      const newClient = await clientApi.createClient({
        ...newClientForm,
        balance: 0,
        paid_amount: 0,
      });
      setClients([...clients, newClient]);
      form.setValue("client", newClient.id.toString());
      setShowNewClientDialog(false);
      setNewClientForm({
        name: "",
        email: "",
        phone: "",
        address: "",
      });
      toast.success("Client created successfully!");
    } catch (error) {
      console.error("Failed to create client:", error);
      if (error instanceof Error && error.message.includes('Authentication failed')) {
        toast.error("Please log in again to create a client");
        navigate('/login');
      } else {
        toast.error("Failed to create client. Please try again.");
      }
    }
  };

  // Prepare safe items with defaults for any missing values
  const safeItems = useMemo(() => {
    if (invoice && Array.isArray(invoice.items) && invoice.items.length > 0) {
      return invoice.items.map(item => ({
        id: item.id,
        description: item.description || '',
        quantity: item.quantity || 1,
        price: item.price || 0,
        amount: (item.quantity || 1) * (item.price || 0)
      }));
    }
    return [{ ...defaultItem }];
  }, [invoice]);

  // Helper function to safely parse dates
  const safeParseDateString = (dateString?: string): Date => {
    if (!dateString) return new Date();
    
    try {
      const parsedDate = parseISO(dateString);
      return isValid(parsedDate) ? parsedDate : new Date();
    } catch (error) {
      console.warn('Failed to parse date:', dateString, error);
      return new Date();
    }
  };

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      client: invoice ? invoice.client_id.toString() : "",
      invoiceNumber: invoice ? invoice.number : `INV-${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`,
      date: invoice ? safeParseDateString(invoice.date || invoice.created_at) : new Date(),
      dueDate: invoice ? safeParseDateString(invoice.due_date) : new Date(new Date().setDate(new Date().getDate() + 30)),
      status: isValidInvoiceStatus(invoice?.status || "pending") ? invoice?.status || "pending" : "pending",
      paidAmount: invoice?.paid_amount || 0,
      items: safeItems,
      notes: invoice?.notes || "",
      isRecurring: invoice?.is_recurring || false,
      recurringFrequency: invoice?.recurring_frequency || "monthly",
    },
  });

  // Debug logging for form initialization
  useEffect(() => {
    if (invoice && isEdit) {
      console.log("Form initialized with invoice data:");
      console.log("- Client ID:", invoice.client_id);
      console.log("- Invoice Number:", invoice.number);
      console.log("- Status:", invoice.status);
      console.log("- Paid Amount:", invoice.paid_amount);
      console.log("- Notes:", invoice.notes);
      console.log("- Items:", invoice.items);
      console.log("- Due Date:", invoice.due_date);
      console.log("- Form default paid amount:", form.getValues("paidAmount"));
    }
  }, [invoice, isEdit, form]);

  // Initialize preview with current invoice data
  useEffect(() => {
    if (invoice) {
      const itemsWithAmount = invoice.items.map(item => ({
        ...item,
        amount: (item.quantity || 1) * (item.price || 0)
      }));
      setPreviewInvoice({
        ...invoice,
        items: itemsWithAmount,
        paid_amount: invoice.paid_amount || 0
      });
    }
  }, [invoice]);

  // Update preview when form values change
  useEffect(() => {
    const subscription = form.watch((value) => {
      const selectedClient = clients.find(c => c.id.toString() === value.client);
      const itemsWithAmount = (value.items || previewInvoice?.items || []).map(item => ({
        description: item.description || '',
        quantity: Number(item.quantity) || 1,
        price: Number(item.price) || 0,
        amount: (Number(item.quantity) || 1) * (Number(item.price) || 0),
        id: item.id
      }));
      const updatedPreview: Invoice = {
        ...previewInvoice,
        number: value.invoiceNumber || previewInvoice?.number || '',
        client_name: selectedClient?.name || '',
        client_email: selectedClient?.email || '',
        date: value.date ? format(value.date, 'yyyy-MM-dd') : previewInvoice?.date || '',
        due_date: value.dueDate ? format(value.dueDate, 'yyyy-MM-dd') : previewInvoice?.due_date || '',
        status: value.status || previewInvoice?.status || 'pending',
        notes: value.notes || previewInvoice?.notes || '',
        items: itemsWithAmount,
        amount: itemsWithAmount.reduce((sum, item) => sum + item.amount, 0),
        client_id: Number(value.client) || previewInvoice?.client_id || 0,
        id: previewInvoice?.id || 0,
        paid_amount: Number(value.paidAmount) || previewInvoice?.paid_amount || 0,
      };
      setPreviewInvoice(updatedPreview);
    });
    return () => subscription.unsubscribe();
  }, [form, clients, previewInvoice]);

  const items = form.watch("items");

  const addItem = () => {
    form.setValue("items", [...items, { ...defaultItem }]);
  };

  const removeItem = (index: number) => {
    if (items.length > 1) {
      form.setValue(
        "items",
        items.filter((_, i) => i !== index)
      );
    }
  };

  const calculateSubtotal = () => {
    return items.reduce((sum, item) => {
      const quantity = item.quantity || 0;
      const price = item.price || 0;
      return sum + quantity * price;
    }, 0);
  };

  const calculateTotal = () => {
    return calculateSubtotal();
  };

  const sendInvoiceEmail = async () => {
    if (!invoice?.id) {
      toast.error("Please save the invoice first before sending");
      return;
    }

    setSendingEmail(true);
    try {
      const response = await fetch('/api/email/send-invoice', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          invoice_id: invoice.id,
          include_pdf: true,
        }),
      });

      const result = await response.json();
      
      if (result.success) {
        toast.success("Invoice sent successfully!");
      } else {
        toast.error(`Failed to send invoice: ${result.message}`);
      }
    } catch (error) {
      console.error("Error sending invoice email:", error);
      toast.error("Failed to send invoice email");
    } finally {
      setSendingEmail(false);
    }
  };

  const onSubmit = async (data: FormValues) => {
    setSubmitting(true);
    try {
      // Update preview before submitting
      const updatedPreview: Invoice = {
        ...invoice,
        number: data.invoiceNumber || invoice?.number || '',
        client_name: clients.find(c => c.id.toString() === data.client)?.name || '',
        client_email: clients.find(c => c.id.toString() === data.client)?.email || '',
        date: data.date ? format(data.date, 'yyyy-MM-dd') : invoice?.date || '',
        due_date: data.dueDate ? format(data.dueDate, 'yyyy-MM-dd') : invoice?.due_date || '',
        status: data.status || invoice?.status || 'pending',
        notes: data.notes || invoice?.notes || '',
        items: (data.items || invoice?.items || []).map(item => ({
          description: item.description || '',
          quantity: Number(item.quantity) || 1,
          price: Number(item.price) || 0,
          amount: (Number(item.quantity) || 1) * (Number(item.price) || 0),
          id: item.id
        })),
        amount: (data.items || []).reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0),
        client_id: Number(data.client) || invoice?.client_id || 0,
        id: invoice?.id || 0,
        paid_amount: Number(data.paidAmount) || 0,
      };
      setPreviewInvoice(updatedPreview);
      setPreviewKey(prev => prev + 1);

      // Format dates for API with time
      const formattedDate = format(data.date, "yyyy-MM-dd'T'HH:mm:ss");
      const formattedDueDate = format(data.dueDate, "yyyy-MM-dd'T'HH:mm:ss");
      
      if (isEdit && invoice) {
        console.log("Updating invoice with data:", data);
       
        try {
          // Calculate total amount from items
          const totalAmount = data.items.reduce((sum, item) => 
            sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0
          );

          // Update the invoice with calculated total amount
          const updateData = {
            amount: totalAmount,
            due_date: format(data.dueDate, "yyyy-MM-dd'T'HH:mm:ss"),
            notes: data.notes || "",
            status: data.status,
            client_id: Number(data.client),
          };
          
          console.log("Updating invoice with data:", updateData);
          await invoiceApi.updateInvoice(invoice.id, updateData);
          
          // Handle payment amount separately
          const paidAmount = Number(data.paidAmount) || 0;
          const currentPaidAmount = invoice.paid_amount || 0;
          const invoiceTotalAmount = data.items.reduce((sum, item) => 
            sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0
          );
          
          console.log("Payment comparison:");
          console.log("- New paid amount:", paidAmount);
          console.log("- Current paid amount:", currentPaidAmount);
          console.log("- Invoice total amount:", invoiceTotalAmount);
          console.log("- Difference:", paidAmount - currentPaidAmount);
          
          // Validate paid amount doesn't exceed total
          if (paidAmount > invoiceTotalAmount) {
            toast.error(`Paid amount ($${paidAmount.toFixed(2)}) cannot exceed invoice total ($${invoiceTotalAmount.toFixed(2)})`);
            return;
          }
          
          if (paidAmount !== currentPaidAmount) {
            console.log("Payment amount changed, processing...");
            try {
              if (paidAmount > currentPaidAmount) {
                // Create additional payment for the difference
                const paymentDifference = paidAmount - currentPaidAmount;
                const paymentData = {
                  invoice_id: invoice.id,
                  amount: paymentDifference,
                  payment_date: format(new Date(), "yyyy-MM-dd"),
                  payment_method: "manual", // Default method for manual entries
                  reference_number: `PAY-${invoice.number}-${Date.now()}`,
                  notes: "Payment entered via invoice form"
                };
                
                console.log("Creating additional payment:", paymentData);
                const paymentResult = await paymentApi.createPayment(paymentData);
                console.log("Payment created successfully:", paymentResult);
                toast.success(`Payment of $${paymentDifference.toFixed(2)} recorded successfully!`);
                
                // Refresh the invoice data to show updated paid amount
                if (isEdit && invoice) {
                  try {
                    const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
                    console.log("Refreshed invoice data:", updatedInvoice);
                    // Update the form with the new paid amount
                    form.setValue("paidAmount", updatedInvoice.paid_amount);
                    // Refresh the update history
                    await fetchUpdateHistory(invoice.id);
                  } catch (refreshError) {
                    console.error("Failed to refresh invoice data:", refreshError);
                  }
                }
              } else if (paidAmount < currentPaidAmount) {
                // Handle reduction in payment amount
                const reductionAmount = currentPaidAmount - paidAmount;
                console.log(`Payment amount reduced by $${reductionAmount.toFixed(2)}. From $${currentPaidAmount} to $${paidAmount}`);
                
                try {
                  // Get all payments for this invoice to determine how to reduce
                  const allPayments = await paymentApi.getPayments();
                  const invoicePayments = allPayments
                    .filter(payment => payment.invoice_id === invoice.id)
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()); // Most recent first
                  
                  console.log("Existing payments for invoice:", invoicePayments);
                  
                  let remainingReduction = reductionAmount;
                  const paymentsToDelete: number[] = [];
                  let lastPaymentToModify: any = null;
                  
                  // Find which payments to delete/modify to achieve the target amount
                  for (const payment of invoicePayments) {
                    if (remainingReduction <= 0) break;
                    
                    if (payment.amount <= remainingReduction) {
                      // Delete this entire payment
                      paymentsToDelete.push(payment.id);
                      remainingReduction -= payment.amount;
                      console.log(`Will delete payment ${payment.id} (amount: $${payment.amount})`);
                    } else {
                      // Partially reduce this payment
                      lastPaymentToModify = {
                        id: payment.id,
                        newAmount: payment.amount - remainingReduction
                      };
                      remainingReduction = 0;
                      console.log(`Will reduce payment ${payment.id} from $${payment.amount} to $${lastPaymentToModify.newAmount}`);
                    }
                  }
                  
                  if (remainingReduction > 0) {
                    toast.error(`Cannot reduce payment by $${reductionAmount.toFixed(2)}. Only $${(reductionAmount - remainingReduction).toFixed(2)} can be reduced based on existing payments.`);
                    form.setValue("paidAmount", currentPaidAmount);
                    return;
                  }
                  
                  // Execute the payment modifications
                  for (const paymentId of paymentsToDelete) {
                    console.log(`Deleting payment ${paymentId}`);
                    await paymentApi.deletePayment(paymentId);
                  }
                  
                  if (lastPaymentToModify) {
                    console.log(`Updating payment ${lastPaymentToModify.id} to amount ${lastPaymentToModify.newAmount}`);
                    await paymentApi.updatePayment(lastPaymentToModify.id, {
                      amount: lastPaymentToModify.newAmount
                    });
                  }
                  
                  console.log("Payment reduction completed successfully");
                  toast.success(`Payment reduced by $${reductionAmount.toFixed(2)} successfully!`);
                  
                  // Refresh the invoice data to show updated paid amount
                  if (isEdit && invoice) {
                    try {
                      const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
                      console.log("Refreshed invoice data after reduction:", updatedInvoice);
                      // Update the form with the new paid amount
                      form.setValue("paidAmount", updatedInvoice.paid_amount);
                      // Refresh the update history
                      await fetchUpdateHistory(invoice.id);
                    } catch (refreshError) {
                      console.error("Failed to refresh invoice data:", refreshError);
                    }
                  }
                  
                } catch (reductionError) {
                  console.error("Failed to reduce payment:", reductionError);
                  toast.error("Failed to reduce payment. Please use the Payments section for manual adjustments.");
                  form.setValue("paidAmount", currentPaidAmount);
                }
              }
            } catch (paymentError) {
              console.error("Failed to handle payment:", paymentError);
              console.error("Payment error details:", paymentError);
              toast.error("Invoice updated but failed to record payment changes. Please add payment separately.");
            }
          } else {
            console.log("No change in payment amount, skipping payment processing");
          }
          
          toast.success("Invoice updated successfully!");
        } catch (error) {
          console.error("API error:", error);
          const errorMessage = error instanceof Error ? error.message : String(error);
          toast.error(`Failed to update invoice: ${errorMessage}`);
        }
      } else {
        // Calculate total amount from items
        const totalAmount = data.items.reduce((sum, item) => 
          sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0
        );

        // Prepare request payload for new invoice
        const selectedClient = clients.find(c => c.id.toString() === data.client);
        const invoiceData = {
          number: data.invoiceNumber,
          client_id: Number(data.client),
          client_name: selectedClient?.name || '',
          client_email: selectedClient?.email || '',
          date: format(data.date, "yyyy-MM-dd'T'HH:mm:ss"),
          due_date: formattedDueDate,
          amount: totalAmount,
          paid_amount: data.paidAmount || 0,
          status: data.status,
          notes: data.notes || "",
          items: data.items.map(item => ({
            description: item.description || '',
            quantity: Number(item.quantity) || 1,
            price: Number(item.price) || 0,
            amount: (Number(item.quantity) || 1) * (Number(item.price) || 0)
          })),
          is_recurring: data.isRecurring,
          recurring_frequency: data.recurringFrequency,
        };
        
        // Create new invoice
        await invoiceApi.createInvoice(invoiceData);
        toast.success("Invoice created successfully!");
        navigate("/invoices"); // Only navigate back for new invoices
      }
    } catch (err) {
      console.error("Failed to submit invoice:", err);
      toast.error("Failed to save invoice");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center justify-center h-[50vh]">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>Loading invoice data...</p>
        </div>
      </div>
    );
  }

  if (!clients.length) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex flex-col items-center justify-center h-[50vh] space-y-4">
          <p className="text-lg">No clients found. Please add a client first.</p>
          <Button onClick={() => setShowNewClientDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add New Client
          </Button>
        </div>

        <Dialog open={showNewClientDialog} onOpenChange={setShowNewClientDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Client</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={newClientForm.name}
                  onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={newClientForm.email}
                  onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  value={newClientForm.phone}
                  onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  value={newClientForm.address}
                  onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowNewClientDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateClient}>Add Client</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <Card>
        <CardContent>
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Update History Section - Left Side */}
            {isEdit && (
              <div className="w-full lg:w-80 order-2 lg:order-1">
                <div className="mb-4">
                  <h3 className="text-lg font-semibold mb-3">Update History</h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto bg-gray-50 p-4 rounded-lg border">
                    {loadingHistory ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin mr-2" />
                        <span className="text-sm text-muted-foreground">Loading history...</span>
                      </div>
                    ) : updateHistory.length > 0 ? (
                      updateHistory.map((entry) => (
                        <div key={entry.id} className="bg-white p-3 rounded border border-gray-200 shadow-sm">
                                                     <div className="flex items-start justify-between mb-2">
                             <div className="flex items-center gap-2">
                               {entry.type === 'payment' && (
                                 <DollarSign className="w-4 h-4 text-green-600" />
                               )}
                               {entry.type === 'creation' && (
                                 <FileText className="w-4 h-4 text-blue-600" />
                               )}
                               {entry.type === 'update' && (
                                 <Edit className="w-4 h-4 text-orange-600" />
                               )}
                               <span className="font-medium text-sm">{entry.action}</span>
                             </div>
                            <span className="text-xs text-muted-foreground">
                              {format(new Date(entry.date), "MMM dd, HH:mm")}
                            </span>
                          </div>
                          <div className="text-sm space-y-1">
                            {entry.amount && (
                              <div className="text-muted-foreground">
                                Amount: <span className="font-medium">${entry.amount.toFixed(2)}</span>
                              </div>
                            )}
                            {entry.details && (
                              <div className="text-muted-foreground">{entry.details}</div>
                            )}
                            {entry.notes && (
                              <div className="text-xs text-gray-600 bg-gray-100 p-2 rounded">
                                {entry.notes}
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-muted-foreground">
                        <p className="text-sm">No update history available</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {/* Main Form Section */}
            <div className="flex-1 order-1 lg:order-2">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <FormField
                      control={form.control}
                      name="client"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Client</FormLabel>
                          <div className="flex gap-2">
                            <Select
                              disabled={isEdit}
                              onValueChange={field.onChange}
                              defaultValue={field.value}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Select a client" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {clients.map((client) => (
                                  <SelectItem key={client.id} value={client.id.toString()}>
                                    {client.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {!isEdit && (
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setShowNewClientDialog(true)}
                              >
                                <Plus className="h-4 w-4 mr-2" />
                                New Client
                              </Button>
                            )}
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="invoiceNumber"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Invoice Number</FormLabel>
                          <FormControl>
                            <Input {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="date"
                      render={({ field }) => (
                        <FormItem className="flex flex-col">
                          <FormLabel>Date</FormLabel>
                          <Popover>
                            <PopoverTrigger asChild>
                              <FormControl>
                                <Button
                                  variant={"outline"}
                                  className={cn(
                                    "w-full pl-3 text-left font-normal",
                                    !field.value && "text-muted-foreground"
                                  )}
                                >
                                  {field.value ? (
                                    format(field.value, "PPP")
                                  ) : (
                                    <span>Pick a date</span>
                                  )}
                                  <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                                </Button>
                              </FormControl>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                              <Calendar
                                mode="single"
                                selected={field.value}
                                onSelect={field.onChange}
                                disabled={(date) =>
                                  date < new Date("1900-01-01")
                                }
                                initialFocus
                              />
                            </PopoverContent>
                          </Popover>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="dueDate"
                      render={({ field }) => (
                        <FormItem className="flex flex-col">
                          <FormLabel>Due Date</FormLabel>
                          <Popover>
                            <PopoverTrigger asChild>
                              <FormControl>
                                <Button
                                  variant={"outline"}
                                  className={cn(
                                    "w-full pl-3 text-left font-normal",
                                    !field.value && "text-muted-foreground"
                                  )}
                                >
                                  {field.value ? (
                                    format(field.value, "PPP")
                                  ) : (
                                    <span>Pick a date</span>
                                  )}
                                  <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                                </Button>
                              </FormControl>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                              <Calendar
                                mode="single"
                                selected={field.value}
                                onSelect={field.onChange}
                                disabled={(date) =>
                                  date < new Date("1900-01-01")
                                }
                                initialFocus
                              />
                            </PopoverContent>
                          </Popover>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="status"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Status</FormLabel>
                          <Select
                            onValueChange={(value) => {
                              field.onChange(value);
                              // Set paid amount based on status
                              if (value === "paid") {
                                form.setValue("paidAmount", form.getValues("items").reduce((sum, item) => 
                                  sum + (item.quantity || 0) * (item.price || 0), 0));
                              } else if (value === "pending" || value === "overdue") {
                                form.setValue("paidAmount", 0);
                              }
                            }}
                            defaultValue={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Select status">
                                  {field.value && formatStatus(field.value)}
                                </SelectValue>
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="pending">Pending</SelectItem>
                              <SelectItem value="paid">Paid</SelectItem>
                              <SelectItem value="partially_paid">Partially Paid</SelectItem>
                              <SelectItem value="overdue">Overdue</SelectItem>
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="paidAmount"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Paid Amount</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              placeholder="Enter paid amount"
                              {...field}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                const value = parseFloat(e.target.value) || 0;
                                const totalAmount = form.watch("items").reduce((sum, item) => 
                                  sum + (item.quantity || 0) * (item.price || 0), 0);
                                
                                if (value > totalAmount) {
                                  setShowExcessAmountDialog(true);
                                  field.onChange(totalAmount);
                                } else {
                                  field.onChange(value);
                                }
                                
                                // Update status based on paid amount
                                if (value === 0) {
                                  form.setValue("status", "pending");
                                } else if (value >= totalAmount) {
                                  form.setValue("status", "paid");
                                } else if (value > 0) {
                                  form.setValue("status", "partially_paid");
                                }
                              }}
                              onBlur={(e: React.FocusEvent<HTMLInputElement>) => {
                                const blurValue = parseFloat(e.target.value) || 0;
                                const blurTotalAmount = form.watch("items").reduce((sum, item) => 
                                  sum + (item.quantity || 0) * (item.price || 0), 0);
                                
                                if (blurValue === 0) {
                                  form.setValue("status", "pending");
                                } else if (blurValue >= blurTotalAmount) {
                                  form.setValue("status", "paid");
                                } else if (blurValue > 0) {
                                  form.setValue("status", "partially_paid");
                                }
                              }}
                              disabled={form.watch("status") === "paid"}
                            />
                          </FormControl>
                          <div className="mt-2 space-y-1">
                            <div className="text-sm text-muted-foreground">
                              Paid Amount: ${field.value?.toFixed(2) || '0.00'}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Remaining Balance: ${(form.watch("items").reduce((sum, item) => 
                                sum + (item.quantity || 0) * (item.price || 0), 0) - (field.value || 0)).toFixed(2)}
                            </div>
                            {isEdit && (
                              <div className="text-xs text-blue-600 bg-blue-50 p-2 rounded border border-blue-200">
                                <strong>Note:</strong> You can increase or decrease the paid amount here. For decreases, the system will automatically remove/modify the most recent payments. For complex payment management, use the Payments section.
                              </div>
                            )}
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <FormField
                      control={form.control}
                      name="isRecurring"
                      render={({ field }) => (
                        <FormItem className="space-y-3">
                          <FormLabel>Invoice Type</FormLabel>
                          <FormControl>
                            <RadioGroup
                              onValueChange={(value) => {
                                const recurring = value === "true";
                                field.onChange(recurring);
                                setIsRecurring(recurring);
                              }}
                              defaultValue={field.value?.toString() || "false"}
                              className="flex space-x-4"
                            >
                              <FormItem className="flex items-center space-x-2">
                                <FormControl>
                                  <RadioGroupItem value="false" />
                                </FormControl>
                                <FormLabel className="font-normal">One-time</FormLabel>
                              </FormItem>
                              <FormItem className="flex items-center space-x-2">
                                <FormControl>
                                  <RadioGroupItem value="true" />
                                </FormControl>
                                <FormLabel className="font-normal">Recurring</FormLabel>
                              </FormItem>
                            </RadioGroup>
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    {isRecurring && (
                      <FormField
                        control={form.control}
                        name="recurringFrequency"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Recurring Frequency</FormLabel>
                            <Select onValueChange={field.onChange} defaultValue={field.value}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Select frequency" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="daily">Daily</SelectItem>
                                <SelectItem value="weekly">Weekly</SelectItem>
                                <SelectItem value="monthly">Monthly</SelectItem>
                                <SelectItem value="yearly">Yearly</SelectItem>
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-medium">Items</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={addItem}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Add Item
                      </Button>
                    </div>

                    {items.map((_, index) => (
                      <div key={index} className="grid grid-cols-12 gap-4 items-start">
                        <div className="col-span-6">
                          <FormField
                            control={form.control}
                            name={`items.${index}.description`}
                            render={({ field }) => (
                              <FormItem>
                                <FormControl>
                                  <Input placeholder="Description" {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                        <div className="col-span-2">
                          <FormField
                            control={form.control}
                            name={`items.${index}.quantity`}
                            render={({ field }) => (
                              <FormItem>
                                <FormControl>
                                  <Input
                                    type="number"
                                    min="1"
                                    placeholder="Qty"
                                    {...field}
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                        <div className="col-span-3">
                          <FormField
                            control={form.control}
                            name={`items.${index}.price`}
                            render={({ field }) => (
                              <FormItem>
                                <FormControl>
                                  <Input
                                    type="number"
                                    min="0.01"
                                    step="0.01"
                                    placeholder="Price"
                                    {...field}
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                        <div className="col-span-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeItem(index)}
                            disabled={items.length === 1}
                          >
                            <Trash className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <FormField
                    control={form.control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Notes</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="flex justify-end gap-4">
                    <Button
                      type="submit"
                      disabled={submitting}
                    >
                      {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {isEdit ? "Update Invoice" : "Create Invoice"}
                    </Button>
                  </div>
                </form>
              </Form>
            </div>
            
            {/* Preview Section - Right Side */}
            <div className="w-full lg:w-96 order-3">
              <div className="mb-2 font-semibold text-lg">Preview</div>
              <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
                <div className="h-[500px] overflow-auto">
                  <React.Suspense fallback={<div className="p-4">Loading preview...</div>}>
                    {previewInvoice && settings && (
                      <PDFDownloadLink 
                        document={
                          <InvoicePDF 
                            invoice={previewInvoice} 
                            companyName={settings.company_info?.name || "Your Company"} 
                          />
                        } 
                        fileName={`invoice-${previewInvoice.number}.pdf`}
                        key={previewKey}
                      >
                        {({ url, loading }) =>
                          loading ? (
                            <div className="p-4">Loading preview...</div>
                          ) : (
                            <iframe
                              src={url || ''}
                              title="Invoice PDF Preview"
                              className="w-full h-[480px] border-none"
                            />
                          )
                        }
                      </PDFDownloadLink>
                    )}
                  </React.Suspense>
                </div>
                <div className="p-2 border-t flex justify-between items-center">
                  {previewInvoice && settings && (
                    <PDFDownloadLink 
                      document={
                        <InvoicePDF 
                          invoice={previewInvoice} 
                          companyName={settings.company_info?.name || "Your Company"} 
                        />
                      } 
                      fileName={`invoice-${previewInvoice.number}.pdf`}
                    >
                      {({ loading }) =>
                        loading ? 'Preparing PDF...' : <span className="text-blue-600 hover:underline cursor-pointer">Download PDF</span>
                      }
                    </PDFDownloadLink>
                  )}
                  
                  {invoice?.id && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={sendInvoiceEmail}
                      disabled={sendingEmail}
                      className="flex items-center gap-2"
                    >
                      {sendingEmail ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Mail className="h-4 w-4" />
                      )}
                      {sendingEmail ? 'Sending...' : 'Send Email'}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showExcessAmountDialog} onOpenChange={setShowExcessAmountDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Warning</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>The paid amount cannot exceed the total invoice amount. The paid amount has been adjusted to match the total amount.</p>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowExcessAmountDialog(false)}>OK</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showNewClientDialog} onOpenChange={setShowNewClientDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Client</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={newClientForm.name}
                onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={newClientForm.email}
                onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={newClientForm.phone}
                onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                value={newClientForm.address}
                onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewClientDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateClient}>Add Client</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}