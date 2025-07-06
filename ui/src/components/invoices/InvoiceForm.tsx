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
import { CurrencySelector } from "@/components/ui/currency-selector";
import { apiRequest } from "@/lib/api";

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
  currency: z.string().min(1, "Currency is required"),
  date: z.date(),
  dueDate: z.date(),
  status: z.custom<InvoiceStatus>(),
  paidAmount: z.number().min(0, "Paid amount cannot be negative").optional(),
  items: z.array(invoiceItemSchema).min(1, "At least one item is required"),
  notes: z.string().optional(),
  isRecurring: z.boolean().optional(),
  recurringFrequency: z.string().optional(),
  discountType: z.enum(["percentage", "fixed"] as const).default("percentage"),
  discountValue: z.number().min(0, "Discount value cannot be negative").default(0),
});

type FormValues = z.infer<typeof formSchema>;

const defaultItem = {
  id: undefined,
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
  const [previousDiscount, setPreviousDiscount] = useState<{value: number, type: string} | null>(
    invoice ? { value: invoice.discount_value || 0, type: invoice.discount_type || 'percentage' } : null
  );
  const [updateHistoryCache, setUpdateHistoryCache] = useState<{[key: string]: any[]}>({});
  const [itemKeyCounter, setItemKeyCounter] = useState(0);

  // Fetch update history for the invoice
  const fetchUpdateHistory = useCallback(async (invoiceId: number, invoiceData?: Invoice, previousDiscountInfo?: {value: number, type: string}) => {
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

      // Use provided invoice data or fall back to the prop
      const currentInvoice = invoiceData || invoice;

      // Get existing history from cache
      const existingHistory = updateHistoryCache[invoiceId] || [];

      // Add invoice creation entry (only if not already exists)
      const creationHistory = existingHistory.find(entry => entry.id === 'creation') ? [] : [{
        id: 'creation',
        type: 'creation',
        action: 'Invoice Created',
        amount: currentInvoice?.amount || 0,
        date: currentInvoice?.created_at || new Date().toISOString(),
        details: `Invoice ${currentInvoice?.number} created`,
        notes: null
      }];

      // Add new update entries for this update
      const newUpdateEntries = [];
      
      // Use the actual updated_at timestamp from the invoice, or current time as fallback
      const updateTimestamp = currentInvoice?.updated_at || new Date().toISOString();
      
      // Add discount change entry if there was a change
      console.log("Checking for discount change:", {
        previousDiscountInfo,
        currentDiscountValue: currentInvoice?.discount_value,
        currentDiscountType: currentInvoice?.discount_type,
        hasChange: previousDiscountInfo && currentInvoice?.discount_value !== previousDiscountInfo.value
      });
      
      if (previousDiscountInfo && currentInvoice?.discount_value !== previousDiscountInfo.value) {
        const discountText = currentInvoice?.discount_value && currentInvoice.discount_value > 0
          ? `Discount changed from ${previousDiscountInfo.value}${previousDiscountInfo.type === 'percentage' ? '%' : ' (fixed)'} to ${currentInvoice.discount_value}${currentInvoice.discount_type === 'percentage' ? '%' : ' (fixed)'}`
          : `Discount removed (was ${previousDiscountInfo.value}${previousDiscountInfo.type === 'percentage' ? '%' : ' (fixed)'})`;
        
        console.log("Adding discount change entry:", discountText);
        
        newUpdateEntries.push({
          id: `discount-update-${updateTimestamp}`,
          type: 'update',
          action: 'Discount Changed',
          amount: currentInvoice?.amount || 0,
          date: updateTimestamp,
          details: discountText,
          notes: null
        });
      }

      // Add general update entry for this update
      newUpdateEntries.push({
        id: `update-${updateTimestamp}`,
        type: 'update',
        action: 'Invoice Updated',
        amount: currentInvoice?.amount || 0,
        date: updateTimestamp,
        details: `Invoice details modified`,
        notes: null
      });

      // Combine existing history with new entries
      const allHistory = [...existingHistory, ...creationHistory, ...newUpdateEntries, ...paymentHistory]
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

      // Update cache
      setUpdateHistoryCache(prev => ({
        ...prev,
        [invoiceId]: allHistory
      }));

      setUpdateHistory(allHistory);
    } catch (error) {
      console.error("Failed to fetch update history:", error);
      toast.error("Failed to load update history");
    } finally {
      setLoadingHistory(false);
    }
  }, [invoice, updateHistoryCache]);

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
        // Initialize cache with existing history
        const existingHistory = updateHistoryCache[invoice.id] || [];
        if (existingHistory.length === 0) {
          fetchUpdateHistory(invoice.id, invoice);
        } else {
          setUpdateHistory(existingHistory);
        }
      }
    }, [invoice, isEdit, fetchUpdateHistory, updateHistoryCache]);

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
      currency: invoice?.currency || "USD",
      date: invoice ? safeParseDateString(invoice.date || invoice.created_at) : new Date(),
      dueDate: invoice ? safeParseDateString(invoice.due_date) : new Date(new Date().setDate(new Date().getDate() + 30)),
      status: isValidInvoiceStatus(invoice?.status || "pending") ? invoice?.status || "pending" : "pending",
      paidAmount: invoice?.paid_amount || 0,
      items: safeItems,
      notes: invoice?.notes || "",
      isRecurring: invoice?.is_recurring || false,
      recurringFrequency: invoice?.recurring_frequency || "monthly",
      discountType: (invoice?.discount_type === "percentage" || invoice?.discount_type === "fixed") ? invoice.discount_type : "percentage",
      discountValue: invoice?.discount_value || 0,
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
      console.log("- Discount Type:", invoice.discount_type);
      console.log("- Discount Value:", invoice.discount_value);
      console.log("- Subtotal:", invoice.subtotal);
      console.log("- Amount:", invoice.amount);
      console.log("- Form default paid amount:", form.getValues("paidAmount"));
      console.log("- Form default discount type:", form.getValues("discountType"));
      console.log("- Form default discount value:", form.getValues("discountValue"));
    }
  }, [invoice, isEdit, form]);

  // Reset form when invoice changes (for editing)
  useEffect(() => {
    if (invoice && isEdit) {
      console.log("Resetting form with invoice data...");
      console.log("Invoice discount data:", {
        discount_type: invoice.discount_type,
        discount_value: invoice.discount_value,
        subtotal: invoice.subtotal,
        amount: invoice.amount
      });
      
      const formData = {
        client: invoice.client_id.toString(),
        invoiceNumber: invoice.number,
        currency: invoice.currency || "USD",
        date: safeParseDateString(invoice.date || invoice.created_at),
        dueDate: safeParseDateString(invoice.due_date),
        status: isValidInvoiceStatus(invoice.status) ? invoice.status : "pending",
        paidAmount: invoice.paid_amount || 0,
        items: safeItems,
        notes: invoice.notes || "",
        isRecurring: invoice.is_recurring || false,
        recurringFrequency: invoice.recurring_frequency || "monthly",
        discountType: (invoice.discount_type === "percentage" || invoice.discount_type === "fixed") ? (invoice.discount_type as "percentage" | "fixed") : "percentage",
        discountValue: invoice.discount_value || 0,
      };
      
      console.log("Form data to reset:", formData);
      form.reset(formData);
      console.log("Form reset complete");
      
      // Also set the values individually to ensure they're set
      setTimeout(() => {
        console.log("Setting individual form values...");
        form.setValue("discountType", formData.discountType);
        form.setValue("discountValue", formData.discountValue);
        console.log("Individual form values set");
        console.log("Form values after setting:", {
          discountType: form.getValues("discountType"),
          discountValue: form.getValues("discountValue")
        });
      }, 100);
    }
  }, [invoice, isEdit, form, safeItems]);

  // Initialize preview with current invoice data
  useEffect(() => {
    if (invoice) {
      const itemsWithAmount = invoice.items.map(item => ({
        ...item,
        amount: (item.quantity || 1) * (item.price || 0)
      }));
      const subtotal = itemsWithAmount.reduce((sum, item) => sum + item.amount, 0);
      const discountType = invoice.discount_type || "percentage";
      const discountValue = invoice.discount_value || 0;
      const discount = discountType === "percentage" 
        ? (subtotal * discountValue) / 100
        : Math.min(discountValue, subtotal);
      const totalAmount = Math.max(0, subtotal - discount);
      
      setPreviewInvoice({
        ...invoice,
        items: itemsWithAmount,
        subtotal: subtotal,
        discount_type: discountType,
        discount_value: discountValue,
        amount: totalAmount,
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
        subtotal: itemsWithAmount.reduce((sum, item) => sum + item.amount, 0),
        discount_type: value.discountType || previewInvoice?.discount_type || "percentage",
        discount_value: Number(value.discountValue) || previewInvoice?.discount_value || 0,
        amount: (() => {
          const subtotal = itemsWithAmount.reduce((sum, item) => sum + item.amount, 0);
          const discountType = value.discountType || previewInvoice?.discount_type || "percentage";
          const discountValue = Number(value.discountValue) || previewInvoice?.discount_value || 0;
          const discount = discountType === "percentage" 
            ? (subtotal * discountValue) / 100
            : Math.min(discountValue, subtotal);
          return Math.max(0, subtotal - discount);
        })(),
        client_id: Number(value.client) || previewInvoice?.client_id || 0,
        id: previewInvoice?.id || 0,
        paid_amount: Number(value.paidAmount) || previewInvoice?.paid_amount || 0,
      };
      setPreviewInvoice(updatedPreview);
    });
    return () => subscription.unsubscribe();
  }, [form, clients, previewInvoice]);

  const items = form.watch("items");
  const currentStatus = form.watch("status");
  const isInvoicePaid = isEdit && currentStatus === "paid";

  const addItem = () => {
    const currentItems = form.getValues("items");
    console.log("Current items before add:", currentItems);
    const newItem = { ...defaultItem };
    console.log("New item being added:", newItem);
    const updatedItems = [...currentItems, newItem];
    console.log("Updated items array:", updatedItems);
    form.setValue("items", updatedItems);
    // Increment counter for new item keys
    setItemKeyCounter(prev => prev + 1);
    // Trigger form re-render
    form.trigger("items");
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
    // When editing, use the actual invoice data if form values are not yet loaded
    if (isEdit && invoice && (!items || items.length === 0 || items[0].quantity === 0)) {
      const subtotal = invoice.items.reduce((sum, item) => {
        const quantity = item.quantity || 0;
        const price = item.price || 0;
        return sum + quantity * price;
      }, 0);
      console.log("calculateSubtotal - using invoice data:", subtotal);
      return subtotal;
    }
    
    const subtotal = items.reduce((sum, item) => {
      const quantity = item.quantity || 0;
      const price = item.price || 0;
      return sum + quantity * price;
    }, 0);
    console.log("calculateSubtotal - using form data:", subtotal);
    return subtotal;
  };

  const calculateDiscount = () => {
    const subtotal = calculateSubtotal();
    const discountType = form.watch("discountType");
    const discountValue = form.watch("discountValue") || 0;
    
    console.log("calculateDiscount - subtotal:", subtotal, "discountType:", discountType, "discountValue:", discountValue);
    
    // When editing, use the actual invoice discount data if form values are not yet loaded
    if (isEdit && invoice && discountValue === 0 && invoice.discount_value) {
      const actualDiscountType = invoice.discount_type || "percentage";
      const actualDiscountValue = invoice.discount_value || 0;
      
      console.log("calculateDiscount - using invoice data:", actualDiscountType, actualDiscountValue);
      
      if (actualDiscountType === "percentage") {
        const discount = (subtotal * actualDiscountValue) / 100;
        console.log("calculateDiscount - percentage discount:", discount);
        return discount;
      } else {
        const discount = Math.min(actualDiscountValue, subtotal);
        console.log("calculateDiscount - fixed discount:", discount);
        return discount;
      }
    }
    
    if (discountType === "percentage") {
      const discount = (subtotal * discountValue) / 100;
      console.log("calculateDiscount - form percentage discount:", discount);
      return discount;
    } else {
      const discount = Math.min(discountValue, subtotal);
      console.log("calculateDiscount - form fixed discount:", discount);
      return discount;
    }
  };

  const calculateTotal = () => {
    const subtotal = calculateSubtotal();
    const discount = calculateDiscount();
    return Math.max(0, subtotal - discount);
  };

  const sendInvoiceEmail = async () => {
    if (!invoice?.id) {
      toast.error("Please save the invoice first before sending");
      return;
    }

    setSendingEmail(true);
    try {
      const result = await apiRequest<any>('/email/send-invoice', {
        method: 'POST',
        body: JSON.stringify({
          invoice_id: invoice.id,
          include_pdf: true,
        }),
      });
      
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
          // Calculate amounts with discount
          const subtotal = data.items.reduce((sum, item) => 
            sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0
          );
          const discount = data.discountType === "percentage" 
            ? (subtotal * (data.discountValue || 0)) / 100
            : Math.min(data.discountValue || 0, subtotal);
          const totalAmount = Math.max(0, subtotal - discount);

          // Update the invoice with calculated total amount
          const updateData = {
            amount: totalAmount,
            subtotal: subtotal,
            discount_type: data.discountType,
            discount_value: data.discountValue || 0,
            currency: data.currency,
            due_date: format(data.dueDate, "yyyy-MM-dd'T'HH:mm:ss"),
            notes: data.notes || "",
            status: data.status,
            client_id: Number(data.client),
            items: data.items.map(item => ({
              description: item.description || '',
              quantity: Number(item.quantity) || 1,
              price: Number(item.price) || 0,
              amount: (Number(item.quantity) || 1) * (Number(item.price) || 0),
              id: item.id
            })),
          };
          
          // Capture current discount values before update for change tracking
          const currentDiscountValue = data.discountValue || 0;
          const currentDiscountType = data.discountType || 'percentage';
          
          console.log("Captured discount values before update:", {
            currentDiscountValue,
            currentDiscountType,
            formDiscountValue: form.getValues("discountValue"),
            formDiscountType: form.getValues("discountType"),
            previousDiscountState: previousDiscount
          });
          
          console.log("Updating invoice with data:", updateData);
          const updateResult = await invoiceApi.updateInvoice(invoice.id, updateData);
          console.log("Update result:", updateResult);
          
          // Handle payment amount separately
          const paidAmount = Number(data.paidAmount) || 0;
          const currentPaidAmount = invoice.paid_amount || 0;
          const invoiceTotalAmount = totalAmount; // Use the discounted total amount
          
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
                    await fetchUpdateHistory(invoice.id, updatedInvoice);
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
                      await fetchUpdateHistory(invoice.id, updatedInvoice);
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
          
          // Refresh the invoice data to show updated values
          try {
            // Capture current discount values before refresh for change tracking
            const currentDiscountValue = form.getValues("discountValue") || 0;
            const currentDiscountType = form.getValues("discountType") || 'percentage';
            
            const updatedInvoice = await invoiceApi.getInvoice(invoice.id);
            console.log("Refreshed invoice data after update:", updatedInvoice);
            console.log("Discount data from updated invoice:", {
              discount_type: updatedInvoice.discount_type,
              discount_value: updatedInvoice.discount_value,
              amount: updatedInvoice.amount
            });
            
            // Update the form with the new data
            const newDiscountType = (updatedInvoice.discount_type === "percentage" || updatedInvoice.discount_type === "fixed") ? (updatedInvoice.discount_type as "percentage" | "fixed") : "percentage";
            const newDiscountValue = updatedInvoice.discount_value !== undefined ? updatedInvoice.discount_value : 0;
            
            console.log("Setting form values:", {
              discountType: newDiscountType,
              discountValue: newDiscountValue,
              paidAmount: updatedInvoice.paid_amount || 0
            });
            
            form.setValue("discountType", newDiscountType);
            form.setValue("discountValue", newDiscountValue);
            form.setValue("paidAmount", updatedInvoice.paid_amount || 0);
            
            // Refresh the update history with the updated invoice data and previous discount info
            console.log("Calling fetchUpdateHistory with:", {
              invoiceId: updatedInvoice.id,
              previousDiscountInfo: previousDiscount || {
                value: currentDiscountValue,
                type: currentDiscountType
              }
            });
            
            await fetchUpdateHistory(updatedInvoice.id, updatedInvoice, previousDiscount || {
              value: currentDiscountValue,
              type: currentDiscountType
            });
            
            // Update previous discount for next change tracking
            setPreviousDiscount({
              value: updatedInvoice.discount_value || 0,
              type: updatedInvoice.discount_type || 'percentage'
            });
          } catch (refreshError) {
            console.error("Failed to refresh invoice data after update:", refreshError);
          }
        } catch (error) {
          console.error("API error:", error);
          const errorMessage = error instanceof Error ? error.message : String(error);
          toast.error(`Failed to update invoice: ${errorMessage}`);
        }
      } else {
        // Calculate amounts with discount
        const subtotal = data.items.reduce((sum, item) => 
          sum + (Number(item.quantity) || 0) * (Number(item.price) || 0), 0
        );
        const discount = data.discountType === "percentage" 
          ? (subtotal * (data.discountValue || 0)) / 100
          : Math.min(data.discountValue || 0, subtotal);
        const totalAmount = Math.max(0, subtotal - discount);

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
          subtotal: subtotal,
          discount_type: data.discountType,
          discount_value: data.discountValue || 0,
          currency: data.currency,
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
      <div className="w-full px-6 py-6">
        <div className="flex items-center justify-center h-[50vh]">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>Loading invoice data...</p>
        </div>
      </div>
    );
  }

  if (!clients.length) {
    return (
      <div className="w-full px-6 py-6">
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
    <div className="w-full px-6 py-6 space-y-6">
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
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
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
                            <Input {...field} disabled={isInvoicePaid} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="currency"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Currency</FormLabel>
                          <FormControl>
                            <CurrencySelector
                              value={field.value}
                              onValueChange={field.onChange}
                              placeholder="Select currency"
                              disabled={isInvoicePaid}
                            />
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
                                  disabled={isInvoicePaid}
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
                                onSelect={isInvoicePaid ? undefined : field.onChange}
                                disabled={(date) =>
                                  isInvoicePaid || date < new Date("1900-01-01")
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
                                  disabled={isInvoicePaid}
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
                                onSelect={isInvoicePaid ? undefined : field.onChange}
                                disabled={(date) =>
                                  isInvoicePaid || date < new Date("1900-01-01")
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
                        <FormItem className="flex flex-col">
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
                              {isEdit && <SelectItem value="paid">Paid</SelectItem>}
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
                              disabled={isInvoicePaid}
                            />
                          </FormControl>
                          <div className="mt-2 space-y-1">
                            <div className="text-sm text-muted-foreground">
                              Paid Amount: ${field.value?.toFixed(2) || '0.00'}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Remaining Balance: ${(calculateTotal() - (field.value || 0)).toFixed(2)}
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

                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
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
                              disabled={isInvoicePaid}
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
                            <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isInvoicePaid}>
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
                        disabled={isInvoicePaid}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Add Item
                      </Button>
                    </div>

                    {items.map((item, index) => (
                      <div key={item.id ? `existing-${item.id}` : `new-${itemKeyCounter}-${index}`} className="grid grid-cols-12 gap-4 items-start">
                        <div className="col-span-6">
                          <FormField
                            control={form.control}
                            name={`items.${index}.description`}
                            render={({ field }) => (
                              <FormItem>
                                <FormControl>
                                  <Input 
                                    placeholder="Description" 
                                    {...field}
                                    key={`desc-${index}`}
                                    value={field.value || ''}
                                    onChange={(e) => {
                                      console.log(`Item ${index} description changed to:`, e.target.value);
                                      field.onChange(e);
                                    }}
                                    disabled={isInvoicePaid}
                                  />
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
                                    disabled={isInvoicePaid}
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
                                    disabled={isInvoicePaid}
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
                            disabled={items.length === 1 || isInvoicePaid}
                          >
                            <Trash className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Discount Section */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-medium">Discount</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <FormField
                        control={form.control}
                        name="discountType"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Discount Type</FormLabel>
                            <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isInvoicePaid}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Select discount type" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="percentage">Percentage (%)</SelectItem>
                                <SelectItem value="fixed">Fixed Amount</SelectItem>
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="discountValue"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Discount Value</FormLabel>
                            <FormControl>
                              <Input
                                type="number"
                                min="0"
                                step="0.01"
                                placeholder={form.watch("discountType") === "percentage" ? "0.00" : "0.00"}
                                {...field}
                                onChange={(e) => {
                                  const value = parseFloat(e.target.value) || 0;
                                  const discountType = form.watch("discountType");
                                  
                                  if (discountType === "percentage" && value > 100) {
                                    field.onChange(100);
                                  } else {
                                    field.onChange(value);
                                  }
                                }}
                                disabled={isInvoicePaid}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* Summary Section */}
                    <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Subtotal:</span>
                        <span className="font-medium">${calculateSubtotal().toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">
                          Discount ({(() => {
                            const discountType = form.watch("discountType");
                            const discountValue = form.watch("discountValue") || 0;
                            
                            // When editing, use the actual invoice discount data if form values are not yet loaded
                            if (isEdit && invoice && discountValue === 0 && invoice.discount_value) {
                              const actualDiscountType = invoice.discount_type || "percentage";
                              const actualDiscountValue = invoice.discount_value || 0;
                              return actualDiscountType === "percentage" ? `${actualDiscountValue}%` : "Fixed";
                            }
                            
                            return discountType === "percentage" ? `${discountValue}%` : "Fixed";
                          })()}):
                        </span>
                        <span className="font-medium text-red-600">-${calculateDiscount().toFixed(2)}</span>
                      </div>
                      <div className="border-t pt-2 flex justify-between">
                        <span className="font-semibold">Total:</span>
                        <span className="font-bold text-lg">${calculateTotal().toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <FormField
                    control={form.control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Notes</FormLabel>
                        <FormControl>
                          <Input {...field} disabled={isInvoicePaid} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="flex justify-end gap-4">
                    <Button
                      type="submit"
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