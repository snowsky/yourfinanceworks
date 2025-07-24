import React, { useState, useEffect, useMemo, useCallback } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarIcon, Plus, Trash, Loader2, DollarSign, FileText, Edit, Mail } from "lucide-react";
import { format, parseISO, isValid } from "date-fns";
import { useNavigate } from "react-router-dom";
import { PDFDownloadLink } from '@react-pdf/renderer';
import { useTranslation } from "react-i18next";

import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage, FormDescription } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { cn, formatDateTime } from "@/lib/utils";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { isAdmin } from "@/utils/auth";
import { clientApi, Client, invoiceApi, paymentApi, Invoice, InvoiceItem, InvoiceStatus, settingsApi, Settings, discountRulesApi, DiscountCalculation, DiscountRule } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { InvoicePDF } from "./InvoicePDF";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { apiRequest } from "@/lib/api";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { InvoiceHistoryDetailsModal } from "./InvoiceHistoryDetailsModal";
import { getErrorMessage } from '@/lib/api';
import { Checkbox } from "@/components/ui/checkbox";

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

const customFieldSchema = z.object({
  key: z.string().min(1, "Field name is required"),
  value: z.string().optional(),
});

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
  discountType: z.enum(["percentage", "fixed", "rule"] as const).default("percentage"),
  discountValue: z.number().min(0, "Discount value cannot be negative").default(0),
  customFields: z.array(customFieldSchema)
    .refine((fields) => {
      const keys = fields.map(f => f.key.trim()).filter(Boolean);
      return new Set(keys).size === keys.length;
    }, { message: "Custom field names must be unique" }),
  showDiscountInPdf: z.boolean().optional().default(false),
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
    preferred_currency: "",
  });
  const [settings, setSettings] = useState<Settings | null>(null);
  const [updateHistory, setUpdateHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [isRecurring, setIsRecurring] = useState(invoice?.is_recurring || false);


  const [itemKeyCounter, setItemKeyCounter] = useState(0);
  const [appliedDiscountRule, setAppliedDiscountRule] = useState<{
    id: number;
    name: string;
    min_amount: number;
    discount_type: 'percentage' | 'fixed';
    discount_value: number;
  } | null>(null);
  const [availableDiscountRules, setAvailableDiscountRules] = useState<DiscountRule[]>([]);
  const [isRefreshingForm, setIsRefreshingForm] = useState(false);
  const [currenciesLoaded, setCurrenciesLoaded] = useState(false);
  const [selectedHistoryEntry, setSelectedHistoryEntry] = useState<any>(null);
  const [showHistoryDetailsModal, setShowHistoryDetailsModal] = useState(false);
  // Custom fields state for UI
  const [customFields, setCustomFields] = useState<{ key: string; value: string }[]>(() => {
    if (invoice?.custom_fields && typeof invoice.custom_fields === 'object') {
      return Object.entries(invoice.custom_fields).map(([key, value]) => ({ key: key || '', value: value !== undefined && value !== null ? String(value) : '' }));
    }
    return [];
  });

  const { t } = useTranslation();

  // Update customFields when invoice changes
  useEffect(() => {
    console.log("[DEBUG] customFields useEffect triggered");
    console.log("[DEBUG] invoice:", invoice);
    console.log("[DEBUG] invoice?.custom_fields:", invoice?.custom_fields);
    console.log("[DEBUG] typeof invoice?.custom_fields:", typeof invoice?.custom_fields);
    console.log("[DEBUG] invoice keys:", invoice ? Object.keys(invoice) : "no invoice");
    console.log("[DEBUG] Full invoice object:", JSON.stringify(invoice, null, 2));
    
    if (invoice?.custom_fields && typeof invoice.custom_fields === 'object') {
      const newCustomFields = Object.entries(invoice.custom_fields).map(([key, value]) => ({ 
        key: key || '', 
        value: value !== undefined && value !== null ? String(value) : '' 
      }));
      setCustomFields(newCustomFields);
      console.log("[DEBUG] Updated customFields from invoice:", newCustomFields);
    } else {
      setCustomFields([]);
      console.log("[DEBUG] Reset customFields to empty array");
    }
  }, [invoice]);

  // Handle opening the history details modal
  const handleOpenHistoryDetails = (entry: any) => {
    setSelectedHistoryEntry(entry);
    setShowHistoryDetailsModal(true);
  };

  const handleCloseHistoryDetails = () => {
    setShowHistoryDetailsModal(false);
    setSelectedHistoryEntry(null);
  };

  // Get current user from localStorage
  const getCurrentUser = () => {
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user.name || user.email || 'Current User';
      }
    } catch (error) {
      console.error('Error parsing user from localStorage:', error);
    }
    return 'Current User';
  };

  // Fetch update history for the invoice
  const fetchUpdateHistory = useCallback(async (invoiceId: number) => {
    setLoadingHistory(true);
    try {
      // Get history from API
      const history = await invoiceApi.getInvoiceHistory(invoiceId);
      
      // Get all payments for this invoice
      const allPayments = await paymentApi.getPayments();
      const invoicePayments = (allPayments || [])
        .filter(payment => payment.invoice_id === invoiceId)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      // Get current user for payment history
      const currentUser = getCurrentUser();

      // Create history entries for payments
      // Create payment history entries with appropriate filtering
      const paymentHistory = invoicePayments
        .map(payment => {
          // Determine the action and details based on how the payment was created
          let action = 'Payment Added';
          let details = `${payment.payment_method} - ${payment.reference_number || 'No reference'}`;
          // Always use current user for payment history entries
          let userName = currentUser;
          if (payment.notes && payment.notes.includes('Payment entered via invoice form')) {
            action = 'Paid Amount Updated';
            details = `Payment amount changed via invoice form`;
          } else if (payment.notes && payment.notes.includes('Payment reduced via invoice form')) {
            action = 'Payment Reduced';
            details = `Payment amount reduced via invoice form`;
          }
          
          return {
            id: `payment-${payment.id}`,
            type: 'payment',
            action: action,
            amount: payment.amount,
            date: payment.created_at,
            details: details,
            notes: payment.notes,
            user_name: userName,
          };
        });

      // Combine API history with payment history
      const allHistory = [...history, ...paymentHistory]
        .sort((a, b) => {
          const dateA = 'date' in a ? a.date : a.created_at;
          const dateB = 'date' in b ? b.date : b.created_at;
          return new Date(dateB).getTime() - new Date(dateA).getTime();
        });

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
        // Get current user role using utility function
        const isAdminUser = isAdmin();
        
        // Fetch clients and discount rules (always)
        const [clientsData, discountRulesData] = await Promise.all([
          clientApi.getClients(),
          discountRulesApi.getDiscountRules()
        ]);
        setClients(clientsData);
        setAvailableDiscountRules(discountRulesData);
        
        // Only fetch settings for admin users
        if (isAdminUser) {
          try {
            const settingsData = await settingsApi.getSettings();
            setSettings(settingsData);
          } catch (error) {
            console.log("Settings not accessible for current user role");
            // Set default settings for non-admin users
            setSettings({
              company_info: {
                name: 'InvoiceApp',
                email: '',
                phone: '',
                address: '',
                tax_id: '',
                logo: ''
              },
              invoice_settings: {
                prefix: 'INV-',
                next_number: '0001',
                terms: 'Payment due within 30 days from the date of invoice.',
                notes: 'Thank you for your business!',
                send_copy: true,
                auto_reminders: true
              },
              enable_ai_assistant: false
            });
          }
        } else {
          // Set default settings for non-admin users
          setSettings({
            company_info: {
              name: 'InvoiceApp',
              email: '',
              phone: '',
              address: '',
              tax_id: '',
              logo: ''
            },
            invoice_settings: {
              prefix: 'INV-',
              next_number: '0001',
              terms: 'Payment due within 30 days from the date of invoice.',
              notes: 'Thank you for your business!',
              send_copy: true,
              auto_reminders: true
            },
            enable_ai_assistant: false
          });
        }
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

  useEffect(() => {
    if (invoice) {
      console.log("[DEBUG] Invoice object received by InvoiceForm:", invoice);
      console.log("[DEBUG] Invoice currency:", invoice.currency);
    }
  }, [invoice]);

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
        preferred_currency: "",
      });
      toast.success("Client created successfully!");
    } catch (error) {
      console.error("Failed to create client:", error);
      if (error instanceof Error && error.message.includes('Authentication failed')) {
        toast.error(getErrorMessage(error, t));
        navigate('/login');
      } else {
        toast.error(getErrorMessage(error, t));
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
      discountType: "percentage", // Will be overridden by form reset logic if discount rule is found
      discountValue: invoice?.discount_value || 0,
      customFields: customFields,
      showDiscountInPdf: invoice?.show_discount_in_pdf || false,
    },
  });

  // Debug logging for form initialization
  useEffect(() => {
    if (invoice && isEdit) {
      console.log("[DEBUG] Form initialized with invoice data:", invoice);
      console.log("[DEBUG] Form currency default:", form.getValues("currency"));
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
      console.log("- Available discount rules:", availableDiscountRules.map(r => ({ name: r.name, type: r.discount_type, value: r.discount_value, min_amount: r.min_amount })));
    }
  }, [invoice, isEdit, form, availableDiscountRules]);

  // Reset form when invoice changes (for editing)
  useEffect(() => {
    console.log("[DEBUG] Form reset useEffect triggered. Invoice:", invoice);
    if (invoice) {
      console.log("[DEBUG] Invoice currency at reset:", invoice.currency);
    }
    console.log("Form reset useEffect triggered:", {
      hasInvoice: !!invoice,
      isEdit,
      availableDiscountRulesLength: availableDiscountRules.length,
      isRefreshingForm,
      currentDiscountType: form.getValues("discountType"),
      currentDiscountValue: form.getValues("discountValue")
    });
    
    if (invoice && isEdit && availableDiscountRules.length > 0 && !isRefreshingForm) {
      // Check if form is already correctly set to avoid unnecessary resets
      const currentDiscountType = form.getValues("discountType");
      const currentDiscountValue = form.getValues("discountValue");
      
      console.log("Form reset check - current values:", {
        currentDiscountType,
        currentDiscountValue,
        invoiceDiscountValue: invoice.discount_value,
        invoiceDiscountType: invoice.discount_type
      });
      
      // Always check for discount rules when editing an invoice with a discount value
      const shouldReset = currentDiscountValue !== (invoice.discount_value || 0) || 
        (invoice.discount_value && invoice.discount_value > 0 && currentDiscountType !== "rule");
      
      if (shouldReset) {
        console.log("Resetting form with invoice data...");
        console.log("Invoice discount data:", {
          discount_type: invoice.discount_type,
          discount_value: invoice.discount_value,
          subtotal: invoice.subtotal,
          amount: invoice.amount
        });
        console.log("Available discount rules:", availableDiscountRules);
        
        // Check if the existing discount matches any available discount rule
        const discountValue = invoice.discount_value || 0;
        let discountType: "percentage" | "fixed" | "rule" = "percentage";
        let matchingRule = null;
        
        console.log("Checking for matching rules...");
        console.log("Looking for rule with:", {
          discount_type: invoice.discount_type,
          discount_value: discountValue,
          available_rules_count: availableDiscountRules.length
        });
        
        if (discountValue > 0 && availableDiscountRules.length > 0) {
          const invoiceSubtotal = invoice.subtotal || calculateSubtotal();
          matchingRule = availableDiscountRules.find(rule => {
            // Check if this rule matches the saved discount type and value
            // Don't check minimum amount during form reset - the invoice might have been saved when it met the minimum
            const typeMatches = rule.discount_type === invoice.discount_type;
            const valueMatches = rule.discount_value === discountValue;
            const isActive = rule.is_active;
            
            const matches = isActive && typeMatches && valueMatches;
            
            console.log(`Checking rule "${rule.name}":`, {
              is_active: isActive,
              rule_type: rule.discount_type,
              rule_value: rule.discount_value,
              rule_min_amount: rule.min_amount,
              invoice_type: invoice.discount_type,
              invoice_value: discountValue,
              invoice_subtotal: invoiceSubtotal,
              type_matches: typeMatches,
              value_matches: valueMatches,
              meets_minimum: invoiceSubtotal >= rule.min_amount,
              matches: matches,
              note: "Minimum amount check disabled during form reset"
            });
            return matches;
          });
          
          if (matchingRule) {
            discountType = "rule";
            setAppliedDiscountRule({
              id: matchingRule.id,
              name: matchingRule.name,
              min_amount: matchingRule.min_amount,
              discount_type: matchingRule.discount_type,
              discount_value: matchingRule.discount_value
            });
            console.log("Found matching rule:", matchingRule.name);
          } else {
            discountType = (invoice.discount_type === "percentage" || invoice.discount_type === "fixed") ? (invoice.discount_type as "percentage" | "fixed") : "percentage";
            setAppliedDiscountRule(null);
            console.log("No matching rule found, using:", discountType);
          }
        } else {
          discountType = (invoice.discount_type === "percentage" || invoice.discount_type === "fixed") ? (invoice.discount_type as "percentage" | "fixed") : "percentage";
          setAppliedDiscountRule(null);
          console.log("No discount value or no rules available, using:", discountType);
        }
        
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
          discountType: discountType,
          discountValue: discountValue,
        };
        
        console.log("Form data to reset:", formData);
        console.log("Discount rule matching:", {
          discountValue,
          invoiceDiscountType: invoice.discount_type,
          matchingRule: matchingRule?.name,
          finalDiscountType: discountType,
          availableRules: availableDiscountRules.map(r => ({ name: r.name, type: r.discount_type, value: r.discount_value })),
          appliedDiscountRule: appliedDiscountRule
        });
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
    }
  }, [invoice, isEdit, form, safeItems, availableDiscountRules]);

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
      // Debug discount type changes
      if (value.discountType) {
        console.log("Form discount type changed:", {
          newType: value.discountType,
          newValue: value.discountValue,
          appliedRule: appliedDiscountRule?.name
        });
      }
      
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
        currency: value.currency || previewInvoice?.currency || 'USD',
        items: itemsWithAmount,
        subtotal: itemsWithAmount.reduce((sum, item) => sum + item.amount, 0), // Subtotal is always pre-discount
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

  // Auto-apply discount rules when subtotal changes
  useEffect(() => {
    const subtotal = calculateSubtotal();
    if (subtotal > 0) {
      // Debounce the API call to avoid too many requests
      const timeoutId = setTimeout(async () => {
        try {
          const discountCalculation = await discountRulesApi.calculateDiscount(subtotal);
          
          if (discountCalculation.discount_type !== 'none' && discountCalculation.discount_amount > 0) {
            // Show suggestion for both new and editing invoices
            if (discountCalculation.applied_rule) {
              toast.info(`Discount rule available: ${discountCalculation.applied_rule.name} - ${discountCalculation.discount_value}${discountCalculation.discount_type === 'percentage' ? '%' : '$'} discount`, {
                action: {
                  label: 'Apply',
                  onClick: () => {
                    form.setValue("discountType", "rule");
                    form.setValue("discountValue", discountCalculation.discount_value);
                    setAppliedDiscountRule({
                      id: discountCalculation.applied_rule.id,
                      name: discountCalculation.applied_rule.name,
                      min_amount: discountCalculation.applied_rule.min_amount,
                      discount_type: discountCalculation.discount_type as 'percentage' | 'fixed',
                      discount_value: discountCalculation.discount_value
                    });
                    toast.success(`Applied ${discountCalculation.applied_rule.name}`);
                  }
                }
              });
            }
          }
        } catch (error) {
          console.error("Failed to apply discount rules:", error);
        }
      }, 1000);
      
      return () => clearTimeout(timeoutId);
    }
  }, [form.watch("items"), isEdit]);

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

  // Function to automatically apply discount rules
  const applyDiscountRules = async (subtotal: number) => {
    try {
      const discountCalculation = await discountRulesApi.calculateDiscount(subtotal);
      
      if (discountCalculation.discount_type !== 'none' && discountCalculation.discount_amount > 0) {
        // Auto-apply the discount rule
        form.setValue("discountType", discountCalculation.discount_type);
        form.setValue("discountValue", discountCalculation.discount_value);
        
        // Show a toast notification about the applied rule
        if (discountCalculation.applied_rule) {
          toast.success(`Applied ${discountCalculation.applied_rule.name}: ${discountCalculation.discount_value}${discountCalculation.discount_type === 'percentage' ? '%' : '$'} discount`);
        }
        
        return discountCalculation.discount_amount;
      }
    } catch (error) {
      console.error("Failed to apply discount rules:", error);
    }
    return 0;
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
    
    // Handle discount rule type
    if (discountType === "rule" && appliedDiscountRule) {
      // Check if subtotal meets minimum amount requirement
      if (subtotal < appliedDiscountRule.min_amount) {
        console.log("calculateDiscount - rule not applied, subtotal below minimum:", {
          subtotal,
          min_amount: appliedDiscountRule.min_amount,
          rule_name: appliedDiscountRule.name
        });
        return 0;
      }
      
      if (appliedDiscountRule.discount_type === "percentage") {
        const discount = (subtotal * appliedDiscountRule.discount_value) / 100;
        console.log("calculateDiscount - rule percentage discount:", discount);
        return discount;
      } else {
        const discount = Math.min(appliedDiscountRule.discount_value, subtotal);
        console.log("calculateDiscount - rule fixed discount:", discount);
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
          show_discount_in_pdf: form.getValues("showDiscountInPdf"), // Pass the new field value
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
    console.log("onSubmit called", { isEdit, data });
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
          
          let discount = 0;
          if (data.discountType === "rule" && appliedDiscountRule) {
            if (appliedDiscountRule.discount_type === "percentage") {
              discount = (subtotal * appliedDiscountRule.discount_value) / 100;
            } else {
              discount = Math.min(appliedDiscountRule.discount_value, subtotal);
            }
          } else if (data.discountType === "percentage") {
            discount = (subtotal * (data.discountValue || 0)) / 100;
          } else {
            discount = Math.min(data.discountValue || 0, subtotal);
          }
          
          const totalAmount = Math.max(0, subtotal - discount);

          // Update the invoice with calculated total amount
          const updateData = {
            amount: totalAmount,
            subtotal: subtotal,
            discount_type: data.discountType === "rule" && appliedDiscountRule ? appliedDiscountRule.discount_type : data.discountType,
            discount_value: data.discountType === "rule" && appliedDiscountRule ? appliedDiscountRule.discount_value : (data.discountValue || 0),
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
            is_recurring: data.isRecurring,
            recurring_frequency: data.recurringFrequency,
            custom_fields: (data.customFields || []).reduce((acc, { key, value }) => {
              if (key.trim()) acc[key.trim()] = value;
              return acc;
            }, {}),
            show_discount_in_pdf: data.showDiscountInPdf,
          };
          
          console.log("Custom fields from form data:", data.customFields);
          console.log("Custom fields being sent in updateData:", updateData.custom_fields);
          
          console.log("Saving invoice with discount data:", {
            formDiscountType: data.discountType,
            formDiscountValue: data.discountValue,
            appliedDiscountRule: appliedDiscountRule,
            finalDiscountType: updateData.discount_type,
            finalDiscountValue: updateData.discount_value
          });
          
          // Capture current values before update for change tracking
          const currentDiscountValue = data.discountValue || 0;
          const currentDiscountType = data.discountType || 'percentage';
          const currentCurrency = data.currency || 'USD';
          
          console.log("Captured values before update:", {
            currentDiscountValue,
            currentDiscountType,
            currentCurrency,
            formDiscountValue: form.getValues("discountValue"),
            formDiscountType: form.getValues("discountType"),
            formCurrency: form.getValues("currency")
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
                  const invoicePayments = (allPayments || [])
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
                      amount: lastPaymentToModify.newAmount,
                      notes: "Payment reduced via invoice form"
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
                  toast.error(getErrorMessage(reductionError, t));
                  form.setValue("paidAmount", currentPaidAmount);
                }
              }
            } catch (paymentError) {
              console.error("Failed to handle payment:", paymentError);
              console.error("Payment error details:", paymentError);
              toast.error(getErrorMessage(paymentError, t));
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
            const newDiscountValue = updatedInvoice.discount_value !== undefined ? updatedInvoice.discount_value : 0;
            
            // Check if this discount value matches any available discount rule
            let newDiscountType: "percentage" | "fixed" | "rule" = "percentage";
            let matchingRule = null;
            
            if (newDiscountValue > 0) {
              const subtotal = calculateSubtotal();
              matchingRule = availableDiscountRules.find(rule => {
                // Check if this rule matches the saved discount type and value
                const typeMatches = rule.discount_type === updatedInvoice.discount_type;
                const valueMatches = rule.discount_value === newDiscountValue;
                const isActive = rule.is_active;
                const meetsMinimum = subtotal >= rule.min_amount;
                
                const matches = isActive && typeMatches && valueMatches && meetsMinimum;
                
                console.log(`Checking rule "${rule.name}":`, {
                  is_active: isActive,
                  rule_type: rule.discount_type,
                  rule_value: rule.discount_value,
                  rule_min_amount: rule.min_amount,
                  invoice_type: updatedInvoice.discount_type,
                  invoice_value: newDiscountValue,
                  invoice_subtotal: subtotal,
                  type_matches: typeMatches,
                  value_matches: valueMatches,
                  meets_minimum: meetsMinimum,
                  matches: matches
                });
                return matches;
              });
              
              if (matchingRule) {
                newDiscountType = "rule";
                setAppliedDiscountRule({
                  id: matchingRule.id,
                  name: matchingRule.name,
                  min_amount: matchingRule.min_amount,
                  discount_type: matchingRule.discount_type,
                  discount_value: matchingRule.discount_value
                });
              } else {
                newDiscountType = (updatedInvoice.discount_type === "percentage" || updatedInvoice.discount_type === "fixed") ? (updatedInvoice.discount_type as "percentage" | "fixed") : "percentage";
                setAppliedDiscountRule(null);
              }
            } else {
              newDiscountType = (updatedInvoice.discount_type === "percentage" || updatedInvoice.discount_type === "fixed") ? (updatedInvoice.discount_type as "percentage" | "fixed") : "percentage";
              setAppliedDiscountRule(null);
            }
            
            console.log("Setting form values:", {
              discountType: newDiscountType,
              discountValue: newDiscountValue,
              paidAmount: updatedInvoice.paid_amount || 0,
              matchingRule: matchingRule?.name
            });
            
            setIsRefreshingForm(true);
            form.setValue("discountType", newDiscountType);
            form.setValue("discountValue", newDiscountValue);
            form.setValue("paidAmount", updatedInvoice.paid_amount || 0);
            
            // Reset the flag after a short delay
            setTimeout(() => {
              setIsRefreshingForm(false);
            }, 200);
            
            // Refresh the update history with the updated invoice data and previous discount info
            console.log("Calling fetchUpdateHistory with:", {
              invoiceId: updatedInvoice.id
            });
            
            await fetchUpdateHistory(updatedInvoice.id);
            

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
        
        let discount = 0;
        if (data.discountType === "rule" && appliedDiscountRule) {
          if (appliedDiscountRule.discount_type === "percentage") {
            discount = (subtotal * appliedDiscountRule.discount_value) / 100;
          } else {
            discount = Math.min(appliedDiscountRule.discount_value, subtotal);
          }
        } else if (data.discountType === "percentage") {
          discount = (subtotal * (data.discountValue || 0)) / 100;
        } else {
          discount = Math.min(data.discountValue || 0, subtotal);
        }
        
        const totalAmount = Math.max(0, subtotal - discount);

        // Prepare request payload for new invoice
        const selectedClient = clients.find(c => c.id.toString() === data.client);
        // Convert customFields array to object
        const customFieldsObj = (data.customFields || []).reduce((acc, { key, value }) => {
          if (key.trim()) acc[key.trim()] = value;
          return acc;
        }, {} as Record<string, string>);
        const invoiceData = {
          number: data.invoiceNumber,
          client_id: Number(data.client),
          client_name: selectedClient?.name || '',
          client_email: selectedClient?.email || '',
          date: format(data.date, "yyyy-MM-dd'T'HH:mm:ss"),
          due_date: formattedDueDate,
          amount: totalAmount,
          subtotal: subtotal,
          discount_type: data.discountType === "rule" && appliedDiscountRule ? appliedDiscountRule.discount_type : data.discountType,
          discount_value: data.discountType === "rule" && appliedDiscountRule ? appliedDiscountRule.discount_value : (data.discountValue || 0),
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
          custom_fields: Object.keys(customFieldsObj).length > 0 ? customFieldsObj : undefined,
          show_discount_in_pdf: data.showDiscountInPdf,
        };
        console.log("Invoice data being sent:", invoiceData);
        
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

  useEffect(() => {
    if (currenciesLoaded && invoice?.currency) {
      form.setValue('currency', invoice.currency);
    }
  }, [currenciesLoaded, invoice, form]);

  // Keep customFields state in sync with form
  useEffect(() => {
    form.setValue("customFields", customFields);
  }, [customFields]);

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
          <p className="text-lg">{t('invoices.no_clients_found')}</p>
          <Button onClick={() => setShowNewClientDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            {t('invoices.add_new_client')}
          </Button>
        </div>

        <Dialog open={showNewClientDialog} onOpenChange={setShowNewClientDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('invoices.add_new_client')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="name">{t('invoices.name')}</Label>
                <Input
                  id="name"
                  value={newClientForm.name}
                  onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="email">{t('invoices.email')}</Label>
                <Input
                  id="email"
                  type="email"
                  value={newClientForm.email}
                  onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="phone">{t('invoices.phone')}</Label>
                <Input
                  id="phone"
                  value={newClientForm.phone || ''}
                  onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="address">{t('invoices.address')}</Label>
                <Input
                  id="address"
                  value={newClientForm.address || ''}
                  onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="preferred_currency">{t('invoices.preferred_currency')}</Label>
                <CurrencySelector
                  value={newClientForm.preferred_currency || ''}
                  onValueChange={(val) => setNewClientForm({ ...newClientForm, preferred_currency: val })}
                  placeholder={t('invoices.select_preferred_currency')}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowNewClientDialog(false)}>
                {t('invoices.cancel')}
              </Button>
              <Button onClick={handleCreateClient}>{t('invoices.add_client')}</Button>
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
                  <h3 className="text-lg font-semibold mb-3">{t('invoices.update_history')}</h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto bg-gray-50 p-4 rounded-lg border">
                    {loadingHistory ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin mr-2" />
                        <span className="text-sm text-muted-foreground">{t('invoices.loading_history')}</span>
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
                               <span className="font-medium text-sm">
                                 {entry.action === 'update' ? t('invoices.update') : entry.action === 'creation' ? t('invoices.invoice_created') : entry.action}
                                 {entry.user_name && (
                                   <span className="ml-2 text-xs text-muted-foreground">{t('invoices.by', { user: entry.user_name })}</span>
                                 )}
                               </span>
                             </div>
                            <span className="text-xs text-muted-foreground">
                              {formatDateTime((entry as any).date || (entry as any).created_at)}
                            </span>
                          </div>
                          <div className="text-sm space-y-1">
                            {entry.amount && (
                              <div className="text-muted-foreground">
                                {t('invoices.amount')}: <span className="font-medium">${entry.amount.toFixed(2)}</span>
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
                            {/* View Details Link - Only show for entries with previous/current values */}
                            {(entry.previous_values || entry.current_values) && (
                              <div className="pt-2 border-t border-gray-200">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleOpenHistoryDetails(entry)}
                                  className="h-6 px-2 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50"
                                >
                                  {t('invoices.view_details')}
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-muted-foreground">
                        <p className="text-sm">{t('invoices.no_update_history_available')}</p>
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
                          <FormLabel>{t('invoices.client')}</FormLabel>
                          <div className="flex gap-2">
                            <Select
                              disabled={isEdit}
                              onValueChange={field.onChange}
                              defaultValue={field.value}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder={t('invoices.select_a_client')} />
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
                                {t('invoices.new_client')}
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
                          <FormLabel>{t('invoices.invoice_number')}</FormLabel>
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
                          <FormLabel>{t('invoices.currency')}</FormLabel>
                          <FormControl>
                            <CurrencySelector
                              value={field.value}
                              onValueChange={field.onChange}
                              placeholder={t('invoices.select_currency')}
                              disabled={isInvoicePaid}
                              onCurrenciesLoaded={() => setCurrenciesLoaded(true)}
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
                          <FormLabel>{t('invoices.date')}</FormLabel>
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
                                    <span>{t('invoices.pick_a_date')}</span>
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
                          <FormLabel>{t('invoices.due_date')}</FormLabel>
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
                                    <span>{t('invoices.pick_a_date')}</span>
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
                          <FormLabel>{t('invoices.status_label')}</FormLabel>
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
                                <SelectValue placeholder={t('invoices.select_status')}>
                                  {field.value && formatStatus(field.value)}
                                </SelectValue>
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="pending">{t('invoices.pending')}</SelectItem>
                              {isEdit && <SelectItem value="paid">{t('invoices.paid')}</SelectItem>}
                              <SelectItem value="partially_paid">{t('invoices.partially_paid')}</SelectItem>
                              <SelectItem value="overdue">{t('invoices.overdue')}</SelectItem>
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
                          <FormLabel>{t('invoices.paid_amount')}</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min="0"
                              step="0.01"
                              placeholder={t('invoices.enter_paid_amount')}
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
                              {t('invoices.paid_amount')}: <CurrencyDisplay amount={field.value || 0} currency={form.watch("currency") || invoice?.currency || 'USD'} />
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {t('invoices.remaining_balance')}: <CurrencyDisplay amount={Math.max(0, calculateTotal() - (field.value || 0))} currency={form.watch("currency") || invoice?.currency || 'USD'} />
                            </div>
                            {isEdit && (
                              <div className="text-xs text-blue-600 bg-blue-50 p-2 rounded border border-blue-200">
                                <strong>{t('invoices.note')}:</strong> {t('invoices.you_can_increase_or_decrease_paid_amount_here')} {t('invoices.for_decreases_the_system_will_automatically_remove_modify_the_most_recent_payments')} {t('invoices.for_complex_payment_management_use_the_Payments_section')}.
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
                          <FormLabel>{t('invoices.invoice_type')}</FormLabel>
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
                                <FormLabel className="font-normal">{t('invoices.one_time')}</FormLabel>
                              </FormItem>
                              <FormItem className="flex items-center space-x-2">
                                <FormControl>
                                  <RadioGroupItem value="true" />
                                </FormControl>
                                <FormLabel className="font-normal">{t('invoices.recurring')}</FormLabel>
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
                            <FormLabel>{t('invoices.recurring_frequency')}</FormLabel>
                            <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isInvoicePaid}>
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder={t('invoices.select_frequency')} />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="daily">{t('invoices.daily')}</SelectItem>
                                <SelectItem value="weekly">{t('invoices.weekly')}</SelectItem>
                                <SelectItem value="monthly">{t('invoices.monthly')}</SelectItem>
                                <SelectItem value="yearly">{t('invoices.yearly')}</SelectItem>
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
                      <h3 className="text-lg font-medium">{t('invoices.items')}</h3>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={addItem}
                        disabled={isInvoicePaid}
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        {t('invoices.add_item')}
                      </Button>
                    </div>

                    {/* Column headers for items */}
                    <div className="grid grid-cols-12 gap-4 font-semibold text-sm text-gray-600 mb-2">
                      <div className="col-span-6">{t('invoices.description')}</div>
                      <div className="col-span-2">{t('invoices.quantity')}</div>
                      <div className="col-span-3">{t('invoices.price')}</div>
                      <div className="col-span-1">{t('invoices.actions')}</div>
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
                                    placeholder={t('invoices.description')} 
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
                                    placeholder={t('invoices.qty')}
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
                                    placeholder={t('invoices.price')}
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
                    <h3 className="text-lg font-medium">{t('invoices.discount')}</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <FormField
                        control={form.control}
                        name="discountType"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t('invoices.discount_type')}</FormLabel>
                            <Select 
                              onValueChange={(value) => {
                                field.onChange(value);
                                // Clear applied rule when switching away from rule type
                                if (value !== "rule") {
                                  setAppliedDiscountRule(null);
                                }
                              }} 
                              value={field.value} 
                              disabled={isInvoicePaid}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder={t('invoices.select_discount_type')} />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="percentage">{t('invoices.percentage')}</SelectItem>
                                <SelectItem value="fixed">{t('invoices.fixed_amount')}</SelectItem>
                                <SelectItem value="rule">{t('invoices.discount_rule')}</SelectItem>
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
                            <FormLabel>{t('invoices.discount_value')}</FormLabel>
                            <FormControl>
                              {form.watch("discountType") === "rule" ? (
                                <Select 
                                  value={appliedDiscountRule?.id?.toString() || ""}
                                  onValueChange={(value) => {
                                    const selectedRule = availableDiscountRules.find(
                                      rule => rule.id.toString() === value
                                    );
                                    if (
                                      selectedRule &&
                                      (selectedRule.currency || '').trim().toUpperCase() === (form.watch("currency") || '').trim().toUpperCase()
                                    ) {
                                      field.onChange(selectedRule.discount_value);
                                      setAppliedDiscountRule({
                                        id: selectedRule.id,
                                        name: selectedRule.name,
                                        min_amount: selectedRule.min_amount,
                                        discount_type: selectedRule.discount_type,
                                        discount_value: selectedRule.discount_value
                                      });
                                    } else {
                                      field.onChange(0);
                                      setAppliedDiscountRule(null);
                                      toast.error("Selected discount rule does not match the invoice currency.");
                                    }
                                  }}
                                  disabled={isInvoicePaid}
                                >
                                  <SelectTrigger>
                                    <SelectValue placeholder={t('invoices.select_a_discount_rule')} />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {availableDiscountRules
                                      .sort((a, b) => b.priority - a.priority || b.min_amount - a.min_amount)
                                      .map((rule) => {
                                        const dropdownCurrency = form.watch("currency");
                                        console.log("DiscountRule currency:", rule.currency, "Dropdown value:", dropdownCurrency);
                                        return (
                                          <SelectItem
                                            key={rule.id}
                                            value={rule.id.toString()}
                                            disabled={(rule.currency || '').trim().toUpperCase() !== (dropdownCurrency || '').trim().toUpperCase()}
                                          >
                                            {rule.name} - {rule.discount_value}{rule.discount_type === 'percentage' ? '%' : '$'} ({t('invoices.min', { amount: rule.min_amount })})
                                            {(rule.currency || '').trim().toUpperCase() !== (dropdownCurrency || '').trim().toUpperCase() && (
                                              <span style={{ color: '#888', fontSize: '0.85em', marginLeft: 8 }}>
                                                ({t('invoices.not_available_for', { currency: dropdownCurrency })}
                                              </span>
                                            )}
                                          </SelectItem>
                                        );
                                      })}
                                  </SelectContent>
                                </Select>
                              ) : (
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
                              )}
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* Discount Rule Indicator */}
                    {form.watch("discountType") === "rule" && appliedDiscountRule && (
                      <div className={`text-sm p-4 rounded-md border ${
                        calculateSubtotal() >= appliedDiscountRule.min_amount 
                          ? "text-blue-600 bg-blue-50 border-blue-200" 
                          : "text-orange-600 bg-orange-50 border-orange-200"
                      }`}>
                        <div className="font-medium mb-2">
                          {calculateSubtotal() >= appliedDiscountRule.min_amount ? t('invoices.applied_discount_rule') : t('invoices.discount_rule_not_applied')}
                        </div>
                        <div className="space-y-1">
                          <div><span className="font-medium">{t('invoices.rule')}:</span> {appliedDiscountRule.name}</div>
                          <div><span className="font-medium">{t('invoices.minimum_amount')}:</span> ${appliedDiscountRule.min_amount.toFixed(2)}</div>
                          <div><span className="font-medium">{t('invoices.current_subtotal')}:</span> ${calculateSubtotal().toFixed(2)}</div>
                          <div><span className="font-medium">{t('invoices.discount')}:</span> {appliedDiscountRule.discount_value}{appliedDiscountRule.discount_type === 'percentage' ? '%' : '$'}</div>
                          <div><span className="font-medium">{t('invoices.discount_amount')}:</span> -${calculateDiscount().toFixed(2)}</div>
                        </div>
                        <div className={`text-xs mt-2 pt-2 border-t ${
                          calculateSubtotal() >= appliedDiscountRule.min_amount 
                            ? "text-blue-500 border-blue-200" 
                            : "text-orange-500 border-orange-200"
                        }`}>
                          {calculateSubtotal() >= appliedDiscountRule.min_amount ? t('invoices.this_discount_rule_was_automatically_applied_based_on_your_invoice_subtotal') : t('invoices.this_discount_rule_requires_a_minimum_subtotal_of', { amount: appliedDiscountRule.min_amount.toFixed(2) })}
                        </div>
                      </div>
                    )}
                    
                    {/* Legacy discount indicator for non-rule discounts */}
                    {form.watch("discountValue") > 0 && form.watch("discountType") !== "rule" && (
                      <div className="text-sm text-blue-600 bg-blue-50 p-2 rounded-md border border-blue-200">
                        <span className="font-medium">{t('invoices.discount_applied')}:</span> {form.watch("discountValue")}{form.watch("discountType") === "percentage" ? "%" : "$"} {t('invoices.discount')}
                      </div>
                    )}

                    {/* Summary Section */}
                    <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">Subtotal:</span>
                        <span className="font-medium">${calculateSubtotal().toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-gray-600">
                          Discount: {t('invoices.discount_type', { type: t('invoices.discount_type', { type: form.watch("discountType") }) })} {t('invoices.discount_value', { value: form.watch("discountValue") })}
                        </span>
                        <span className="font-medium text-red-600">${(() => {
                          const discountType = form.watch("discountType");
                          const discountValue = form.watch("discountValue") || 0;
                          const subtotal = calculateSubtotal();
                          if (discountType === "rule" && appliedDiscountRule) {
                            if (subtotal < appliedDiscountRule.min_amount) return (0).toFixed(2);
                            if (appliedDiscountRule.discount_type === "percentage") {
                              return ((subtotal * appliedDiscountRule.discount_value) / 100).toFixed(2);
                            } else {
                              return (Math.min(appliedDiscountRule.discount_value, subtotal)).toFixed(2);
                            }
                          }
                          if (discountType === "percentage") {
                            return ((subtotal * discountValue) / 100).toFixed(2);
                          } else {
                            return (Math.min(discountValue, subtotal)).toFixed(2);
                          }
                        })()}</span>
                      </div>
                      <div className="border-t pt-2 flex justify-between">
                        <span className="font-semibold">Total:</span>
                        <span className="font-bold text-lg">${calculateTotal().toFixed(2)}</span>
                      </div>
                    </div>

                    <FormField
                      control={form.control}
                      name="showDiscountInPdf"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4 shadow">
                          <FormControl>
                            <Checkbox
                              checked={field.value}
                              onCheckedChange={field.onChange}
                            />
                          </FormControl>
                          <div className="space-y-1 leading-none">
                            <FormLabel>
                              {t('invoices.show_discount_in_pdf')}
                            </FormLabel>
                            <FormDescription>
                              {t('invoices.if_checked_discount_details_will_be_visible_in_the_pdf_preview_and_download')}
                            </FormDescription>
                          </div>
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={form.control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('invoices.notes')}</FormLabel>
                        <FormControl>
                          <Input {...field} disabled={isInvoicePaid} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="space-y-4">
                    <div className="font-semibold">{t('invoices.custom_fields')}</div>
                    {form.watch("customFields").map((field, idx) => (
                      <div key={idx} className="flex gap-2 items-center">
                        <Input
                          placeholder={t('invoices.field_name')}
                          value={field.key}
                          onChange={e => {
                            const updated = form.getValues("customFields").map((f, i) => i === idx ? { key: e.target.value, value: f.value ?? '' } : { key: f.key ?? '', value: f.value ?? '' });
                            setCustomFields(updated);
                          }}
                          className="w-1/3"
                        />
                        <Input
                          placeholder={t('invoices.field_value')}
                          value={field.value}
                          onChange={e => {
                            const updated = form.getValues("customFields").map((f, i) => i === idx ? { key: f.key ?? '', value: e.target.value } : { key: f.key ?? '', value: f.value ?? '' });
                            setCustomFields(updated);
                          }}
                          className="w-1/2"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => {
                            setCustomFields(
                              form.getValues("customFields")
                                .filter((_, i) => i !== idx)
                                .map(f => ({ key: typeof f.key === 'string' ? f.key : '', value: typeof f.value === 'string' ? f.value : '' }))
                            );
                          }}
                        >
                          <Trash className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setCustomFields([
                        ...form.getValues("customFields").map(f => ({ key: typeof f.key === 'string' ? f.key : '', value: typeof f.value === 'string' ? f.value : '' })),
                        { key: '', value: '' }
                      ])}
                      className="mt-2"
                    >
                      <Plus className="w-4 h-4 mr-2" /> {t('invoices.add_field')}
                    </Button>
                    {form.formState.errors.customFields && (
                      <div className="text-red-500 text-sm mt-1">{form.formState.errors.customFields.message as string}</div>
                    )}
                  </div>

                  <div className="flex justify-end gap-4">
                    <Button
                      type="submit"
                    >
                      {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {isEdit ? t('invoices.update_invoice') : t('invoices.create_invoice')}
                    </Button>
                  </div>
                </form>
              </Form>
            </div>
            
            {/* Preview Section - Right Side */}
            <div className="w-full lg:w-96 order-3">
              <div className="mb-2 font-semibold text-lg">{t('invoices.preview')}</div>
              <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
                <div className="h-[500px] overflow-auto">
                  <React.Suspense fallback={<div className="p-4">{t('invoices.loading_preview')}</div>}>
                    {previewInvoice && settings && (
                      <PDFDownloadLink 
                        document={
                          <InvoicePDF 
                            invoice={previewInvoice} 
                            companyName={settings.company_info?.name || "Your Company"} 
                            showDiscount={form.watch("showDiscountInPdf")}
                          />
                        } 
                        fileName={`invoice-${previewInvoice.number}.pdf`}
                        key={previewKey}
                      >
                        {({ url, loading }) =>
                          loading ? (
                            <div className="p-4">{t('invoices.loading_preview')}</div>
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
                          showDiscount={form.watch("showDiscountInPdf")}
                        />
                      } 
                      fileName={`invoice-${previewInvoice.number}.pdf`}
                    >
                      {({ loading }) =>
                        loading ? t('invoices.preparing_pdf') : <span className="text-blue-600 hover:underline cursor-pointer">{t('invoices.download_pdf')}</span>
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
                      {sendingEmail ? t('invoices.sending') : t('invoices.send_email')}
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
            <DialogTitle>{t('invoices.warning')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>{t('invoices.paid_amount_cannot_exceed_total_invoice_amount')}</p>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowExcessAmountDialog(false)}>{t('invoices.ok')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showNewClientDialog} onOpenChange={setShowNewClientDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('invoices.add_new_client')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">{t('invoices.name')}</Label>
              <Input
                id="name"
                value={newClientForm.name}
                onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="email">{t('invoices.email')}</Label>
              <Input
                id="email"
                type="email"
                value={newClientForm.email}
                onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="phone">{t('invoices.phone')}</Label>
              <Input
                id="phone"
                value={newClientForm.phone || ''}
                onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="address">{t('invoices.address')}</Label>
              <Input
                id="address"
                value={newClientForm.address || ''}
                onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="preferred_currency">{t('invoices.preferred_currency')}</Label>
              <CurrencySelector
                value={newClientForm.preferred_currency || ''}
                onValueChange={(val) => setNewClientForm({ ...newClientForm, preferred_currency: val })}
                placeholder={t('invoices.select_preferred_currency')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewClientDialog(false)}>
              {t('invoices.cancel')}
            </Button>
            <Button onClick={handleCreateClient}>{t('invoices.add_client')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Details Modal */}
      {selectedHistoryEntry && (
        <InvoiceHistoryDetailsModal
          open={showHistoryDetailsModal}
          onClose={handleCloseHistoryDetails}
          historyEntry={selectedHistoryEntry}
        />
      )}
    </div>
  );
}