import { useState, useEffect, useCallback, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { parseISO, isValid } from "date-fns";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Invoice, Client, Settings, DiscountRule, Expense } from "@/lib/api";
import { clientApi, settingsApi, discountRulesApi, tenantApi, expenseApi } from "@/lib/api";
import { isAdmin } from "@/utils/auth";

const invoiceItemSchema = z.object({
  description: z.string().min(1, "Description is required"),
  quantity: z.preprocess(
    (val) => {
      if (val === "" || val === null || val === undefined) return undefined;
      const num = Number(val);
      return isNaN(num) ? undefined : num;
    },
    z.number().min(0.01, "Quantity must be greater than 0")
  ),
  price: z.preprocess(
    (val) => {
      if (val === "" || val === null || val === undefined) return undefined;
      const num = Number(val);
      return isNaN(num) ? undefined : num;
    },
    z.number().min(0.01, "Price must be greater than 0")
  ),
  id: z.number().optional(),
  inventory_item_id: z.number().optional().nullable(),
  unit_of_measure: z.string().optional().nullable(),
});

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
  status: z.enum(["draft", "pending", "paid", "partially_paid", "overdue", "pending_approval", "approved"] as const),
  paidAmount: z.number().min(0, "Paid amount cannot be negative").optional(),
  items: z.array(invoiceItemSchema).min(1, "At least one item is required"),
  notes: z.string().optional(),
  isRecurring: z.boolean().optional(),
  recurringFrequency: z.string().optional(),
  discountType: z.enum(["percentage", "fixed", "rule"] as const).default("percentage"),
  discountValue: z.number().min(0, "Discount value cannot be negative").default(0),
  customFields: z.array(customFieldSchema).default([]),
  showDiscountInPdf: z.boolean().optional().default(false),
  payer: z.enum(["You", "Client"] as const).default("Client"),
  labels: z.array(z.string()).default([]),
});

export type FormValues = z.infer<typeof formSchema>;

const defaultItem = {
  id: undefined,
  description: "",
  quantity: 1,
  price: 0,
  amount: 0,
  inventory_item_id: undefined,
  unit_of_measure: undefined
};

interface UseInvoiceFormProps {
  invoice?: Invoice;
  isEdit?: boolean;
  initialData?: any;
  prefillNewClient?: { name?: string; email?: string; address?: string; phone?: string } | null;
}

export function useInvoiceForm({
  invoice,
  isEdit = false,
  initialData,
  prefillNewClient
}: UseInvoiceFormProps) {
  const { t } = useTranslation();

  // Core state
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tenantInfo, setTenantInfo] = useState<{ default_currency: string } | null>(null);
  const [availableDiscountRules, setAvailableDiscountRules] = useState<DiscountRule[]>([]);
  const [appliedDiscountRule, setAppliedDiscountRule] = useState<{
    id: number;
    name: string;
    min_amount: number;
    discount_type: 'percentage' | 'fixed';
    discount_value: number;
  } | null>(null);
  const [unlinkedExpenses, setUnlinkedExpenses] = useState<Expense[]>([]);

  // Form initialization
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

  const safeItems = useMemo(() => {
    if (invoice && Array.isArray(invoice.items) && invoice.items.length > 0) {
      return invoice.items.map(item => ({
        id: item.id,
        description: item.description || '',
        quantity: Number(item.quantity) || 1,
        price: Number(item.price) || 0,
        amount: (Number(item.quantity) || 1) * (Number(item.price) || 0),
        inventory_item_id: item.inventory_item_id,
        unit_of_measure: item.unit_of_measure,
        inventory_item: item.inventory_item
      }));
    }
    return [{ ...defaultItem }];
  }, [invoice]);

  const formDefaultValues = {
    client: initialData?.client || (invoice ? invoice.client_id.toString() : ""),
    invoiceNumber: initialData?.invoiceNumber || (invoice ? invoice.number : ""),
    currency: initialData?.currency || invoice?.currency || tenantInfo?.default_currency || "USD",
    date: initialData?.date || (invoice ? safeParseDateString(invoice.date || invoice.created_at) : new Date()),
    dueDate: initialData?.dueDate || (invoice ? safeParseDateString(invoice.due_date) : new Date(new Date().setDate(new Date().getDate() + 30))),
    status: initialData?.status || (invoice ? (invoice.status as any) : "pending"),
    paidAmount: initialData?.paidAmount ?? (invoice?.paid_amount || 0),
    items: initialData?.items || safeItems,
    notes: initialData?.notes || invoice?.notes || "",
    isRecurring: initialData?.isRecurring ?? (invoice?.is_recurring || false),
    recurringFrequency: initialData?.recurringFrequency || invoice?.recurring_frequency || "monthly",
    discountType: initialData?.discountType || "percentage" as const,
    discountValue: initialData?.discountValue ?? (invoice?.discount_value || 0),
    customFields: initialData?.customFields || [],
    showDiscountInPdf: initialData?.showDiscountInPdf ?? (invoice?.show_discount_in_pdf || false),
    payer: initialData?.payer || (invoice as any)?.payer || "Client",
    labels: initialData?.labels || invoice?.labels || [],
  };

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: formDefaultValues,
    mode: "onChange"
  });

  // Reset form when initialData changes (e.g., PDF upload)
  useEffect(() => {
    if (initialData && !invoice) {
      const mergedValues = {
        client: initialData.client || "",
        invoiceNumber: initialData.invoiceNumber || "",
        currency: initialData.currency || tenantInfo?.default_currency || "USD",
        date: initialData.date || new Date(),
        dueDate: initialData.dueDate || new Date(new Date().setDate(new Date().getDate() + 30)),
        status: initialData.status || "pending",
        paidAmount: initialData.paidAmount ?? 0,
        items: initialData.items || [{ ...defaultItem }],
        notes: initialData.notes || "",
        isRecurring: initialData.isRecurring ?? false,
        recurringFrequency: initialData.recurringFrequency || "monthly",
        discountType: initialData.discountType || "percentage" as const,
        discountValue: initialData.discountValue ?? 0,
        customFields: initialData.customFields || [],
        showDiscountInPdf: initialData.showDiscountInPdf ?? false,
        payer: initialData.payer || "Client",
        labels: initialData.labels || [],
      };
      form.reset(mergedValues);
    }
  }, [initialData, invoice, form, tenantInfo]);

  // Data fetching
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const isAdminUser = isAdmin();

        const [clientsData, discountRulesData, tenantData] = await Promise.all([
          clientApi.getClients(),
          discountRulesApi.getDiscountRules(),
          tenantApi.getTenantInfo()
        ]);

        setClients(clientsData.items || []);
        setAvailableDiscountRules(discountRulesData);
        setTenantInfo(tenantData);
        
        console.log("InvoiceForm - Clients loaded:", clientsData.items);
        console.log("InvoiceForm - Clients length:", clientsData.items?.length);

        if (isAdminUser) {
          try {
            const settingsData = await settingsApi.getSettings();
            setSettings(settingsData);
          } catch (error) {
            setSettings({
              company_info: { name: 'InvoiceApp', email: '', phone: '', address: '', tax_id: '', logo: '' },
              invoice_settings: { prefix: 'INV-', next_number: '0001', terms: 'Net 30 days', notes: 'Thank you for your business!', send_copy: true, auto_reminders: true },
              enable_ai_assistant: false
            });
          }
        } else {
          setSettings({
            company_info: { name: 'InvoiceApp', email: '', phone: '', address: '', tax_id: '', logo: '' },
            invoice_settings: { prefix: 'INV-', next_number: '0001', terms: 'Net 30 days', notes: 'Thank you for your business!', send_copy: true, auto_reminders: true },
            enable_ai_assistant: false
          });
        }

        try {
          const list = await expenseApi.getExpensesFiltered({ unlinkedOnly: true });
          const onlyUnlinked = (list || []).filter(e => e.invoice_id == null);
          setUnlinkedExpenses(onlyUnlinked);
        } catch { }
      } catch (error) {
        console.error("Failed to fetch data:", error);
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Form reset for editing
  useEffect(() => {
    if (invoice && isEdit) {
      const discountValue = invoice.discount_value || 0;
      let discountType: "percentage" | "fixed" | "rule" = "percentage";
      let matchingRule = null;

      if (discountValue > 0 && availableDiscountRules.length > 0) {
        const invoiceSubtotal = invoice.subtotal || calculateSubtotal();
        matchingRule = availableDiscountRules.find(rule => {
          const typeMatches = rule.discount_type === invoice.discount_type;
          const valueMatches = rule.discount_value === discountValue;
          const isActive = rule.is_active;
          return isActive && typeMatches && valueMatches;
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
        } else {
          // Use the actual discount type from the invoice
          discountType = (invoice.discount_type === "percentage" || invoice.discount_type === "fixed")
            ? (invoice.discount_type as "percentage" | "fixed")
            : "percentage";
          setAppliedDiscountRule(null);
        }
      } else if (invoice.discount_type) {
        // Handle case where there's a discount type but no discount value or rules
        discountType = (invoice.discount_type === "percentage" || invoice.discount_type === "fixed")
          ? (invoice.discount_type as "percentage" | "fixed")
          : "percentage";
        setAppliedDiscountRule(null);
      }

      const formData = {
        client: invoice.client_id.toString(),
        invoiceNumber: invoice.number,
        currency: invoice.currency || "USD",
        date: safeParseDateString(invoice.date || invoice.created_at),
        dueDate: safeParseDateString(invoice.due_date),
        status: invoice.status as any,
        paidAmount: invoice.paid_amount || 0,
        items: safeItems,
        notes: invoice.notes || "",
        isRecurring: invoice.is_recurring || false,
        recurringFrequency: invoice.recurring_frequency || "monthly",
        discountType: discountType,
        discountValue: discountValue,
        customFields: [],
        payer: (invoice as any)?.payer || "Client",
      };

      form.reset(formData);
    }
  }, [invoice, isEdit, form, safeItems, availableDiscountRules]);

  // Calculations
  const calculateSubtotal = useCallback((itemsToUse?: any[]) => {
    const currentItems = itemsToUse || form.watch("items");
    const subtotal = currentItems.reduce((sum, item) => {
      const quantity = Number(item.quantity) || 0;
      const price = Number(item.price) || 0;
      return sum + quantity * price;
    }, 0);
    return subtotal;
  }, [form]);

  const calculateDiscount = useCallback(() => {
    const subtotal = calculateSubtotal();
    const discountType = form.watch("discountType");
    const discountValue = form.watch("discountValue") || 0;

    if (discountType === "rule" && appliedDiscountRule) {
      if (subtotal < appliedDiscountRule.min_amount) return 0;
      return appliedDiscountRule.discount_type === "percentage"
        ? (subtotal * appliedDiscountRule.discount_value) / 100
        : Math.min(appliedDiscountRule.discount_value, subtotal);
    }

    return discountType === "percentage"
      ? (subtotal * discountValue) / 100
      : Math.min(discountValue, subtotal);
  }, [form, calculateSubtotal, appliedDiscountRule]);

  const calculateTotal = useCallback((itemsToUse?: any[]) => {
    const subtotal = calculateSubtotal(itemsToUse);
    const discount = calculateDiscount();
    return Math.max(0, subtotal - discount);
  }, [calculateSubtotal, calculateDiscount]);

  // Client management
  const refreshClientList = useCallback(async () => {
    try {
      const clientsData = await clientApi.getClients();
      setClients(clientsData.items);
    } catch (error) {
      console.error("Failed to refresh client list:", error);
    }
  }, []);

  // Discount rule application
  const applyDiscountRule = useCallback((rule: DiscountRule) => {
    setAppliedDiscountRule({
      id: rule.id,
      name: rule.name,
      min_amount: rule.min_amount,
      discount_type: rule.discount_type,
      discount_value: rule.discount_value
    });
    form.setValue("discountType", "rule");
    form.setValue("discountValue", rule.discount_value);
    toast.success(`Applied ${rule.name}: ${rule.discount_value}${rule.discount_type === 'percentage' ? '%' : '$'} discount`);
  }, [form]);

  return {
    // State
    clients,
    setClients,
    loading,
    submitting,
    settings,
    tenantInfo,
    availableDiscountRules,
    appliedDiscountRule,
    unlinkedExpenses,

    // Form
    form,
    isEdit,

    // Calculations
    calculateSubtotal,
    calculateDiscount,
    calculateTotal,

    // Actions
    refreshClientList,
    applyDiscountRule,
    setSubmitting,
    setAppliedDiscountRule,

    // Initial data
    initialData,
    prefillNewClient
  };
}
