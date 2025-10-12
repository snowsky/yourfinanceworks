import React, { useState, useEffect, useMemo, useCallback } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash, Loader2, DollarSign, FileText, Edit, Mail, User, Calculator, Settings as SettingsIcon, Package } from "lucide-react";
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
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { isAdmin } from "@/utils/auth";
import { clientApi, invoiceApi, paymentApi, Invoice, InvoiceItem, InvoiceStatus, settingsApi, discountRulesApi, DiscountCalculation, DiscountRule, tenantApi, API_BASE_URL, expenseApi, Expense, Settings } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { InvoicePDF } from "../invoices/InvoicePDF";
import { TemplateSelector } from "../invoices/TemplateSelector";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { apiRequest } from "@/lib/api";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { InvoiceHistoryDetailsModal } from "../invoices/InvoiceHistoryDetailsModal";
import { getErrorMessage } from '@/lib/api';
import { Checkbox } from "@/components/ui/checkbox";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { InventoryInvoiceItem } from "./InventoryInvoiceItem";

const invoiceItemSchema = z.object({
  description: z.string().min(1, "Description is required"),
  quantity: z.coerce.number().positive("Quantity must be greater than 0"),
  price: z.coerce.number().min(0, "Price cannot be negative"),
  id: z.number().optional(),
  inventory_item_id: z.number().optional(),
  unit_of_measure: z.string().optional(),
});

const isValidInvoiceStatus = (status: string): status is InvoiceStatus => {
  return ["draft", "pending", "paid", "overdue", "partially_paid"].includes(status);
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
  invoiceNumber: z.string().optional(),
  currency: z.string().min(1, "Currency is required"),
  date: z.date(),
  dueDate: z.date(),
  status: z.enum(["draft", "pending", "paid", "overdue", "partially_paid", "cancelled"] as const),
  paidAmount: z.number().min(0, "Paid amount cannot be negative").optional(),
  items: z.array(invoiceItemSchema).min(1, "At least one item is required"),
  notes: z.string().optional(),
  isRecurring: z.boolean().optional(),
  recurringFrequency: z.string().optional(),
  discountType: z.enum(["percentage", "fixed", "rule"] as const).default("percentage"),
  discountValue: z.number().min(0, "Discount value cannot be negative").default(0),
  customFields: z.array(customFieldSchema)
    .refine((fields) => {
      const nonEmptyFields = fields.filter(f => f.key.trim().length > 0);
      const keys = nonEmptyFields.map(f => f.key.trim());
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
  inventory_item_id: undefined,
  unit_of_measure: undefined,
};

interface InventoryInvoiceFormProps {
  invoice?: Invoice;
  isEdit?: boolean;
  onInvoiceUpdate?: (updatedInvoice: Invoice) => void;
  initialData?: any;
  attachment?: File | null;
  prefillNewClient?: { name?: string; email?: string; address?: string; phone?: string } | null;
}

export const InventoryInvoiceForm: React.FC<InventoryInvoiceFormProps> = ({
  invoice,
  isEdit = false,
  onInvoiceUpdate,
  initialData,
  attachment,
  prefillNewClient
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [invoiceHistory, setInvoiceHistory] = useState([]);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [tenants, setTenants] = useState([]);
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);
  const [customFields, setCustomFields] = useState([]);

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

  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Invoice Form: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
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

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onTouched", // Only validate when fields are touched
    defaultValues: {
      client: "",
      invoiceNumber: "",
      currency: "USD",
      date: new Date(),
      dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
      status: "pending",
      paidAmount: 0,
      items: [defaultItem],
      notes: "",
      isRecurring: false,
      recurringFrequency: "",
      discountType: "percentage",
      discountValue: 0,
      customFields: [],
      showDiscountInPdf: false,
    },
  });

  const watchedItems = form.watch("items");
  const watchedDiscountType = form.watch("discountType");
  const watchedDiscountValue = form.watch("discountValue");
  const watchedCurrency = form.watch("currency");

  // Calculate subtotal
  const subtotal = useMemo(() => {
    return watchedItems?.reduce((sum, item) => sum + ((item.quantity || 0) * (item.price || 0)), 0) || 0;
  }, [watchedItems]);

  // Calculate discount amount
  const discountAmount = useMemo(() => {
    if (!watchedDiscountValue || watchedDiscountValue === 0) return 0;

    if (watchedDiscountType === "fixed") {
      return Math.min(watchedDiscountValue, subtotal);
    } else if (watchedDiscountType === "percentage") {
      return (subtotal * watchedDiscountValue) / 100;
    }

    return 0;
  }, [subtotal, watchedDiscountType, watchedDiscountValue]);

  // Calculate total
  const total = useMemo(() => {
    return subtotal - discountAmount;
  }, [subtotal, discountAmount]);

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [clientsData, settingsData, discountRulesData] = await Promise.all([
          clientApi.getClients(),
          settingsApi.getSettings(),
          discountRulesApi.getDiscountRules(),
        ]);

        setClients(clientsData);
        setSettings(settingsData);
        setDiscountRules(discountRulesData);

        // Set default currency from settings
        if ((settingsData as { default_currency?: string })?.default_currency) {
          form.setValue("currency", (settingsData as { default_currency?: string }).default_currency!);
        }

        // Load invoice data if editing
        if (isEdit && invoice) {
          form.reset({
            client: invoice.client_id.toString(),
            invoiceNumber: invoice.number,
            currency: invoice.currency || "USD",
            date: parseISO(invoice.date),
            dueDate: parseISO(invoice.due_date),
            status: invoice.status,
            paidAmount: invoice.paid_amount,
            items: invoice.items.map(item => ({
              id: item.id,
              description: item.description,
              quantity: item.quantity,
              price: item.price,
              amount: item.amount,
              inventory_item_id: item.inventory_item_id,
              unit_of_measure: item.unit_of_measure,
            })),
            notes: invoice.notes || "",
            isRecurring: invoice.is_recurring || false,
            recurringFrequency: invoice.recurring_frequency || "",
            discountType: invoice.discount_type as any || "percentage",
            discountValue: invoice.discount_value || 0,
            customFields: invoice.custom_fields ? Object.entries(invoice.custom_fields).map(([key, value]) => ({ key, value: value as string })) : [],
            showDiscountInPdf: invoice.show_discount_in_pdf || false,
          });
        }

        // Handle initial data (for prefilled forms)
        if (initialData) {
          form.reset({
            ...form.getValues(),
            ...initialData,
          });
        }

        // Handle prefilled client
        if (prefillNewClient) {
          // This would typically create a new client and set the client ID
          console.log("Prefilling with new client:", prefillNewClient);
        }
      } catch (error) {
        console.error("Failed to load data:", error);
        toast.error(getErrorMessage(error, t));
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [invoice, isEdit, form, initialData, prefillNewClient, currentTenantId]);

  const addItem = useCallback(() => {
    const currentItems = form.getValues("items");
    form.setValue("items", [...currentItems, {
      id: undefined,
      description: "",
      quantity: 1,
      price: 0,
      inventory_item_id: undefined,
      unit_of_measure: undefined,
    }]);
  }, [form]);

  const removeItem = useCallback((index: number) => {
    const currentItems = form.getValues("items");
    if (currentItems.length > 1) {
      form.setValue("items", currentItems.filter((_, i) => i !== index));
    }
  }, [form]);

  const updateItem = useCallback((index: number, item: any) => {
    const currentItems = form.getValues("items");
    currentItems[index] = item;
    form.setValue("items", [...currentItems]);
  }, [form]);

  const onSubmit = async (data: FormValues) => {
    console.log("🔥 InventoryInvoiceForm onSubmit called", { isEdit, data });
    console.log("🔥 Form data validation:", form.formState.errors);
    console.log("🔥 Form is valid:", form.formState.isValid);
    console.log("🔥 Detailed form state:", {
      isValid: form.formState.isValid,
      isDirty: form.formState.isDirty,
      isSubmitted: form.formState.isSubmitted,
      submitCount: form.formState.submitCount,
      errors: form.formState.errors
    });
    setSaving(true);
    try {
      // Validate stock availability for inventory items
      const inventoryItems = data.items.filter(item => item.inventory_item_id);
      if (inventoryItems.length > 0) {
        try {
          const stockValidation = await apiRequest('/api/inventory/invoice-items/validate-stock', {
            method: 'POST',
            body: JSON.stringify({
              invoice_items: inventoryItems.map(item => ({
                inventory_item_id: item.inventory_item_id,
                quantity: item.quantity
              }))
            })
          });

          if (!(stockValidation as { is_valid: boolean; items: any[] }).is_valid) {
            const warnings = (stockValidation as { is_valid: boolean; items: any[] }).items.filter((item: any) => !item.is_available);
            if (warnings.length > 0) {
              const proceed = window.confirm(
                `Warning: Some items have insufficient stock:\n${warnings.map((w: any) => `- ${w.item_name}: ${w.message}`).join('\n')}\n\nDo you want to proceed anyway?`
              );
              if (!proceed) {
                setSaving(false);
                return;
              }
            }
          }
        } catch (error) {
          console.error("Failed to validate stock:", error);
          // Continue with invoice creation even if stock validation fails
        }
      }

      // Calculate the total amount
      const subtotal = data.items.reduce((sum, item) => sum + ((item.quantity || 0) * (item.price || 0)), 0);
      const discountAmount = data.discountType === "fixed"
        ? Math.min(data.discountValue || 0, subtotal)
        : (subtotal * (data.discountValue || 0)) / 100;
      const totalAmount = subtotal - discountAmount;

      // Get client details for the invoice
      const selectedClient = clients.find((client: any) => client.id === parseInt(data.client));

      const invoiceData = {
        client_id: parseInt(data.client),
        client_name: selectedClient?.name || '',
        client_email: selectedClient?.email || '',
        number: data.invoiceNumber,
        amount: totalAmount,
        currency: data.currency,
        date: format(data.date, "yyyy-MM-dd"),
        due_date: format(data.dueDate, "yyyy-MM-dd"),
        status: data.status,
        paid_amount: data.paidAmount || 0,
        items: data.items.map(item => ({
          id: item.id,
          description: item.description,
          quantity: item.quantity,
          price: item.price,
          amount: item.quantity * item.price,
          inventory_item_id: item.inventory_item_id,
          unit_of_measure: item.unit_of_measure,
        })),
        notes: data.notes,
        is_recurring: data.isRecurring,
        recurring_frequency: data.recurringFrequency,
        discount_type: data.discountType,
        discount_value: data.discountValue,
        custom_fields: data.customFields.reduce((acc, field) => {
          if (field.key.trim()) {
            acc[field.key.trim()] = field.value || '';
          }
          return acc;
        }, {} as Record<string, string>),
        show_discount_in_pdf: data.showDiscountInPdf,
      };

      console.log("🔥 InventoryInvoiceForm sending invoice data:", {
        subtotal,
        discountAmount,
        totalAmount,
        invoiceData
      });

      let savedInvoice: Invoice;
      if (isEdit && invoice) {
        savedInvoice = await invoiceApi.updateInvoice(invoice.id, invoiceData);
        toast.success(t('invoices.invoice_updated'));
      } else {
        savedInvoice = await invoiceApi.createInvoice(invoiceData);
        toast.success(t('invoices.invoice_created'));
      }

      if (onInvoiceUpdate) {
        onInvoiceUpdate(savedInvoice);
      } else {
        navigate(`/invoices/edit/${savedInvoice.id}`);
      }
    } catch (error) {
      console.error("Failed to save invoice:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    console.log("🔥 InventoryInvoiceForm is in loading state");
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  // Check if there are no clients
  if (!clients.length) {
    return (
      <div className="w-full px-6 py-6">
        <div className="flex flex-col items-center justify-center h-[50vh] space-y-4">
          <p className="text-lg">{t('invoices.no_clients_found')}</p>
          <Button onClick={() => navigate('/clients/new')}>
            <Plus className="h-4 w-4 mr-2" />
            {t('invoices.add_new_client', 'Add New Client')}
          </Button>
        </div>
      </div>
    );
  }

  console.log("🔥 InventoryInvoiceForm rendering", {
    isEdit,
    saving,
    loading,
    formState: {
      isValid: form.formState.isValid,
      isDirty: form.formState.isDirty,
      isSubmitted: form.formState.isSubmitted,
      errors: form.formState.errors
    },
    formValues: form.getValues()
  });
  return (
    <div className="space-y-6">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Invoice Header */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                {t('invoices.invoice_details', 'Invoice Details')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="client"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('invoices.client', 'Client')} *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder={t('invoices.select_client', 'Select a client')} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {clients.map((client: any) => (
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
                      <FormLabel>{t('invoices.invoice_number', 'Invoice Number')}</FormLabel>
                      <FormControl>
                        <Input placeholder="Leave empty to auto-generate" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="date"
                  render={({ field }) => (
                    <FormItem className="flex flex-col">
                      <FormLabel>{t('invoices.invoice_date', 'Invoice Date')}</FormLabel>
                      <Popover>
                        <PopoverTrigger asChild>
                          <FormControl>
                            <Button
                              variant="outline"
                              className={cn(
                                "w-full pl-3 text-left font-normal",
                                !field.value && "text-muted-foreground"
                              )}
                            >
                              {field.value ? (
                                format(field.value, "PPP")
                              ) : (
                                <span>{t('invoices.pick_a_date', 'Pick a date')}</span>
                              )}
                            </Button>
                          </FormControl>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0">
                          <Calendar
                            mode="single"
                            selected={field.value}
                            onSelect={field.onChange}
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
                      <FormLabel>{t('invoices.due_date', 'Due Date')}</FormLabel>
                      <Popover>
                        <PopoverTrigger asChild>
                          <FormControl>
                            <Button
                              variant="outline"
                              className={cn(
                                "w-full pl-3 text-left font-normal",
                                !field.value && "text-muted-foreground"
                              )}
                            >
                              {field.value ? (
                                format(field.value, "PPP")
                              ) : (
                                <span>{t('invoices.pick_a_date', 'Pick a date')}</span>
                              )}
                            </Button>
                          </FormControl>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0">
                          <Calendar
                            mode="single"
                            selected={field.value}
                            onSelect={field.onChange}
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
                  name="currency"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('invoices.currency', 'Currency')}</FormLabel>
                      <FormControl>
                        <CurrencySelector value={field.value} onValueChange={field.onChange} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </CardContent>
          </Card>

          {/* Invoice Items */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Package className="h-5 w-5" />
                  {t('invoices.items', 'Invoice Items')}
                </CardTitle>
                <Button type="button" onClick={addItem} variant="outline" size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  {t('invoices.add_item', 'Add Item')}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {watchedItems?.map((item, index) => (
                <InventoryInvoiceItem
                  key={index}
                  item={{
                    ...item,
                    description: item.description || '',
                    quantity: item.quantity || 0,
                    price: item.price || 0,
                    amount: (item.quantity || 0) * (item.price || 0)
                  }}
                  onChange={(updatedItem) => updateItem(index, updatedItem)}
                  onRemove={() => removeItem(index)}
                  index={index}
                  currency={watchedCurrency}
                />
              ))}
            </CardContent>
          </Card>

          {/* Invoice Summary */}
          <Card>
            <CardHeader>
              <CardTitle>{t('invoices.invoice_summary', 'Invoice Summary')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span>{t('invoices.subtotal', 'Subtotal')}:</span>
                <CurrencyDisplay amount={subtotal} currency={watchedCurrency} />
              </div>

              {discountAmount > 0 && (
                <div className="flex justify-between items-center text-green-600">
                  <span>{t('invoices.discount', 'Discount')} ({watchedDiscountType === "percentage" ? `${watchedDiscountValue}%` : t('invoices.discount_fixed', 'Fixed')}):</span>
                  <span>-<CurrencyDisplay amount={discountAmount} currency={watchedCurrency} /></span>
                </div>
              )}

              <div className="border-t pt-4 flex justify-between items-center font-bold text-lg">
                <span>{t('invoices.total', 'Total')}:</span>
                <CurrencyDisplay amount={total} currency={watchedCurrency} />
              </div>
            </CardContent>
          </Card>

          {/* Form Actions */}
          <div className="flex justify-end gap-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/invoices')}
              disabled={saving}
            >
              {t('common.cancel', 'Cancel')}
            </Button>
                  {(() => {
                    const errors = form.formState.errors;
                    const values = form.getValues();
                    console.log("🔥 Inventory InvoiceForm rendering submit button", {
                      saving,
                      isEdit,
                      formIsValid: form.formState.isValid,
                      formErrors: errors,
                      formValues: values,
                      validationDetails: {
                        client: { value: values.client, error: errors.client?.message },
                        invoiceNumber: { value: values.invoiceNumber, error: errors.invoiceNumber?.message },
                        currency: { value: values.currency, error: errors.currency?.message },
                        status: { value: values.status, error: errors.status?.message },
                        items: { count: values.items?.length, error: errors.items?.message },
                        customFields: {
                          count: values.customFields?.length,
                          error: errors.customFields?.message,
                          fields: values.customFields?.map(f => ({ key: f.key, hasKey: f.key.trim().length > 0 }))
                        }
                      }
                    });
                    return null;
                  })()}
                  <Button
                    type="submit"
                    disabled={saving} // Temporarily disable validation check
                    onClick={() => console.log("🔥 Inventory Create Invoice button clicked", {
                      formData: form.getValues(),
                      formErrors: form.formState.errors,
                      formIsValid: form.formState.isValid
                    })}
                  >
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {saving
                ? (isEdit ? t('invoices.updating', 'Updating...') : t('invoices.creating', 'Creating...'))
                : (isEdit ? t('invoices.update_invoice', 'Update Invoice') : t('invoices.create_invoice', 'Create Invoice'))
              }
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
};
