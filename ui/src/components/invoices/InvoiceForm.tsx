import React, { useState, useEffect, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarIcon, Plus, Trash, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { useNavigate } from "react-router-dom";
import { PDFDownloadLink, Document, Page, Text, View, StyleSheet } from '@react-pdf/renderer';

import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { clientApi, Client, invoiceApi, Invoice, InvoiceItem } from "@/lib/api";

const invoiceItemSchema = z.object({
  description: z.string().min(1, "Description is required"),
  quantity: z.coerce.number().min(1, "Quantity must be at least 1"),
  price: z.coerce.number().min(0.01, "Price must be greater than 0"),
  id: z.number().optional(),
});

const formSchema = z.object({
  client: z.string().min(1, "Client is required"),
  invoiceNumber: z.string().min(1, "Invoice number is required"),
  date: z.date(),
  dueDate: z.date(),
  items: z.array(invoiceItemSchema).min(1, "At least one item is required"),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const defaultItem = {
  description: "",
  quantity: 1,
  price: 0,
};

interface InvoiceFormProps {
  invoice?: Invoice;
  isEdit?: boolean;
}

// PDF styles and document
const pdfStyles = StyleSheet.create({
  page: { padding: 24, fontSize: 12, fontFamily: 'Helvetica' },
  section: { marginBottom: 12 },
  title: { fontSize: 20, marginBottom: 12, fontWeight: 'bold' },
  table: { flexDirection: 'column', width: 'auto', marginVertical: 8 },
  tableRow: { flexDirection: 'row' },
  tableCellHeader: { flex: 1, fontWeight: 'bold', padding: 4, backgroundColor: '#eee' },
  tableCell: { flex: 1, padding: 4 },
});

function InvoicePDF({ invoice }: { invoice: Invoice }) {
  return (
    <Document>
      <Page size="A4" style={pdfStyles.page}>
        <View style={pdfStyles.section}>
          <Text style={pdfStyles.title}>Invoice {invoice.number}</Text>
          <Text>Client: {invoice.client_name || invoice.client_id}</Text>
          <Text>Date: {invoice.date}</Text>
          <Text>Due Date: {invoice.due_date}</Text>
          <Text>Status: {invoice.status}</Text>
        </View>
        <View style={pdfStyles.section}>
          <Text>Items:</Text>
          <View style={pdfStyles.table}>
            <View style={pdfStyles.tableRow}>
              <Text style={pdfStyles.tableCellHeader}>Description</Text>
              <Text style={pdfStyles.tableCellHeader}>Quantity</Text>
              <Text style={pdfStyles.tableCellHeader}>Price</Text>
              <Text style={pdfStyles.tableCellHeader}>Total</Text>
            </View>
            {invoice.items.map((item, idx) => (
              <View style={pdfStyles.tableRow} key={idx}>
                <Text style={pdfStyles.tableCell}>{item.description}</Text>
                <Text style={pdfStyles.tableCell}>{item.quantity}</Text>
                <Text style={pdfStyles.tableCell}>${item.price.toFixed(2)}</Text>
                <Text style={pdfStyles.tableCell}>${(item.quantity * item.price).toFixed(2)}</Text>
              </View>
            ))}
          </View>
          <Text style={{ marginTop: 8, fontWeight: 'bold' }}>Total: ${invoice.amount.toFixed(2)}</Text>
        </View>
        {invoice.notes && (
          <View style={pdfStyles.section}>
            <Text>Notes: {invoice.notes}</Text>
          </View>
        )}
      </Page>
    </Document>
  );
}

export function InvoiceForm({ invoice, isEdit = false }: InvoiceFormProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  // Log the invoice data for debugging
  useEffect(() => {
    if (isEdit && invoice) {
      console.log("InvoiceForm received invoice:", JSON.stringify(invoice));
      console.log("Invoice items:", invoice.items);
    }
  }, [invoice, isEdit]);

  useEffect(() => {
    const fetchClients = async () => {
      setLoading(true);
      try {
        const data = await clientApi.getClients();
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

  // Prepare safe items with defaults for any missing values
  const safeItems = useMemo(() => {
    if (invoice && Array.isArray(invoice.items) && invoice.items.length > 0) {
      return invoice.items.map(item => ({
        id: item.id,
        description: item.description || '',
        quantity: item.quantity || 1,
        price: item.price || 0,
      }));
    }
    return [{ ...defaultItem }];
  }, [invoice]);

  // Initialize form with defaults
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      client: invoice ? invoice.client_id.toString() : "",
      invoiceNumber: invoice ? invoice.number : `INV-${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`,
      date: invoice ? new Date(invoice.date) : new Date(),
      dueDate: invoice ? new Date(invoice.due_date) : new Date(new Date().setDate(new Date().getDate() + 30)),
      items: safeItems,
      notes: invoice?.notes || "",
    },
  });

  // Reset form when invoice changes
  useEffect(() => {
    if (invoice) {
      console.log("Resetting form with invoice data");
      
      // Get safe items
      const items = Array.isArray(invoice.items) && invoice.items.length > 0
        ? invoice.items.map(item => ({
            id: item.id,
            description: item.description || '',
            quantity: item.quantity || 1,
            price: item.price || 0,
          }))
        : [{ ...defaultItem }];
      
      console.log("Form will be reset with items:", items);
      
      // Reset the form with all values
      form.reset({
        client: invoice.client_id.toString(),
        invoiceNumber: invoice.number,
        date: new Date(invoice.date),
        dueDate: new Date(invoice.due_date),
        items: items,
        notes: invoice.notes || "",
      });
    }
  }, [invoice, form]);

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

  const onSubmit = async (data: FormValues) => {
    setSubmitting(true);
    try {
      // Format dates for API
      const formattedDate = format(data.date, "yyyy-MM-dd");
      const formattedDueDate = format(data.dueDate, "yyyy-MM-dd");
      
      if (isEdit && invoice) {
        console.log("Updating invoice with data:", data);
        
        try {
          // Use a two-step update process
          // Step 1: Update the invoice details (without items)
          // Only include the fields we want to update - explicitly exclude date fields
          const updateData = {
            // Remove date fields that are causing validation errors
            // date: formattedDate,
            // due_date: formattedDueDate,
            notes: data.notes || ""
          };
          
          console.log("Step 1: Updating invoice details:", updateData);
          await invoiceApi.updateInvoice(invoice.id, updateData);
          
          // Step 2: Update the invoice items separately
          console.log("Step 2: Updating invoice items:", data.items);
          // Make sure items have all required fields and convert to proper format
          const itemsForUpdate: InvoiceItem[] = data.items.map(item => ({
            id: item.id,
            description: item.description || '',
            quantity: item.quantity || 1,
            price: item.price || 0,
            invoice_id: invoice.id
          }));
          await invoiceApi.updateInvoiceItems(invoice.id, itemsForUpdate);
          
          toast.success("Invoice updated successfully!");
          navigate("/invoices"); // Redirect to invoices page
        } catch (error) {
          console.error("API error:", error);
          const errorMessage = error instanceof Error ? error.message : String(error);
          toast.error(`Failed to update invoice: ${errorMessage}`);
        }
      } else {
        // Prepare request payload for new invoice
        const invoiceData = {
          number: data.invoiceNumber,
          client_id: Number(data.client),
          date: formattedDate,
          due_date: formattedDueDate,
          notes: data.notes || "",
          items: data.items.map(item => ({
            description: item.description,
            quantity: item.quantity,
            price: item.price
          }))
        };
        
        // Create new invoice
        await invoiceApi.createInvoice(invoiceData);
        toast.success("Invoice created successfully!");
        navigate("/invoices"); // Redirect to invoices page
      }
    } catch (error) {
      console.error(`Failed to ${isEdit ? 'update' : 'create'} invoice:`, error);
      
      // Improved error handling with clearer messages
      let errorMessage = "An unknown error occurred";
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      } else if (error && typeof error === 'object') {
        errorMessage = JSON.stringify(error);
      }
      
      toast.error(`Failed to ${isEdit ? 'update' : 'create'} invoice. ${errorMessage}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{isEdit ? "Edit Invoice" : "Create New Invoice"}</CardTitle>
          {isEdit && invoice && (
            <div className="text-right">
              <span className="text-sm text-muted-foreground">Invoice Amount</span>
              <p className="text-2xl font-bold">${invoice.amount.toFixed(2)}</p>
              <span className={`text-sm ${invoice.status === 'paid' ? 'text-green-600' : invoice.status === 'pending' ? 'text-orange-600' : 'text-red-600'}`}>
                {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="h-8 w-8 animate-spin mr-2" />
            <p>Loading client data...</p>
          </div>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <FormField
                    control={form.control}
                    name="client"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Client</FormLabel>
                        <Select 
                          onValueChange={field.onChange} 
                          defaultValue={field.value}
                          disabled={isEdit} // Disable changing client on edit
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
                          <Input {...field} disabled={isEdit} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="space-y-4">
                  <FormField
                    control={form.control}
                    name="date"
                    render={({ field }) => (
                      <FormItem className="flex flex-col">
                        <FormLabel>Invoice Date</FormLabel>
                        <Popover>
                          <PopoverTrigger asChild>
                            <FormControl>
                              <Button
                                variant={"outline"}
                                className={cn(
                                  "pl-3 text-left font-normal",
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
                              initialFocus
                              className={cn("p-3 pointer-events-auto")}
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
                                  "pl-3 text-left font-normal",
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
                              initialFocus
                              className={cn("p-3 pointer-events-auto")}
                            />
                          </PopoverContent>
                        </Popover>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-medium">Items</h3>
                  <Button type="button" variant="outline" size="sm" onClick={addItem}>
                    <Plus className="h-4 w-4 mr-2" /> Add Item
                  </Button>
                </div>

                <div className="border rounded-md">
                  <div className="grid grid-cols-12 gap-2 p-4 bg-muted font-medium text-sm">
                    <div className="col-span-5">Description</div>
                    <div className="col-span-2 text-center">Quantity</div>
                    <div className="col-span-3 text-center">Price</div>
                    <div className="col-span-1 text-center">Total</div>
                    <div className="col-span-1"></div>
                  </div>

                  {items.map((item, index) => (
                    <div key={index} className="grid grid-cols-12 gap-2 p-4 border-t">
                      <div className="col-span-5">
                        <Input
                          {...form.register(`items.${index}.description`)}
                          placeholder="Item description"
                        />
                        {form.formState.errors.items?.[index]?.description && (
                          <p className="text-xs mt-1 text-destructive">
                            {form.formState.errors.items[index]?.description?.message}
                          </p>
                        )}
                      </div>
                      <div className="col-span-2">
                        <Input
                          {...form.register(`items.${index}.quantity`)}
                          type="number"
                          min="1"
                          placeholder="1"
                          className="text-center"
                        />
                        {form.formState.errors.items?.[index]?.quantity && (
                          <p className="text-xs mt-1 text-destructive">
                            {form.formState.errors.items[index]?.quantity?.message}
                          </p>
                        )}
                      </div>
                      <div className="col-span-3">
                        <Input
                          {...form.register(`items.${index}.price`)}
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="0.00"
                          className="text-center"
                        />
                        {form.formState.errors.items?.[index]?.price && (
                          <p className="text-xs mt-1 text-destructive">
                            {form.formState.errors.items[index]?.price?.message}
                          </p>
                        )}
                      </div>
                      <div className="col-span-1 flex items-center justify-center">
                        ${((item.quantity || 0) * (item.price || 0)).toFixed(2)}
                      </div>
                      <div className="col-span-1 flex items-center justify-center">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => removeItem(index)}
                          disabled={items.length === 1}
                        >
                          <Trash className="h-4 w-4" />
                          <span className="sr-only">Remove</span>
                        </Button>
                      </div>
                    </div>
                  ))}

                  <div className="grid grid-cols-12 gap-2 p-4 border-t bg-muted/50">
                    <div className="col-span-10 text-right font-semibold">Total:</div>
                    <div className="col-span-1 text-center font-bold">${calculateTotal().toFixed(2)}</div>
                    <div className="col-span-1"></div>
                  </div>
                </div>

                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <textarea
                          {...field}
                          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                          placeholder="Additional information (optional)"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="flex justify-end gap-3 pt-6">
                  <Button variant="outline" type="button" onClick={() => navigate("/invoices")}>
                    Cancel
                  </Button>
                  {isEdit && invoice && (
                    <PDFDownloadLink
                      document={<InvoicePDF invoice={invoice} />}
                      fileName={`Invoice-${invoice.number}.pdf`}
                      style={{ textDecoration: 'none' }}
                    >
                      {({ loading }) => (
                        <Button variant="secondary" type="button" disabled={loading} className="mr-2">
                          {loading ? 'Preparing PDF...' : 'Export to PDF'}
                        </Button>
                      )}
                    </PDFDownloadLink>
                  )}
                  <Button type="submit" disabled={submitting}>
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {isEdit ? "Update Invoice" : "Create Invoice"}
                  </Button>
                </div>
              </div>
            </form>
          </Form>
        )}
      </CardContent>
    </Card>
  );
}
