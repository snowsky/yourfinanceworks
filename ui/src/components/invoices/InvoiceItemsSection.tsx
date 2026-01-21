import React from "react";
import { UseFormReturn } from "react-hook-form";
import { Plus, Trash } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { FormField, FormItem, FormControl, FormMessage } from "@/components/ui/form";
import { toast } from "sonner";
import { inventoryApi } from "@/lib/api";
import { InventoryItemSelector } from "@/components/inventory/InventoryItemSelector";
import { FormValues } from "@/hooks/useInvoiceForm";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton, ButtonGroup } from "@/components/ui/professional-button";
import { ShoppingCart, CheckCircle2, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface InvoiceItemsSectionProps {
  form: UseFormReturn<FormValues>;
  isEdit: boolean;
  isInvoicePaid: boolean;
  submitting: boolean;
  itemKeyCounter: number;
  setItemKeyCounter: (counter: number | ((prev: number) => number)) => void;
}

const defaultItem = {
  id: undefined,
  description: "",
  quantity: 1,
  price: 0,
  amount: 0,
  inventory_item_id: undefined,
  unit_of_measure: undefined
};

export function InvoiceItemsSection({
  form,
  isEdit,
  isInvoicePaid,
  submitting,
  itemKeyCounter,
  setItemKeyCounter,
}: InvoiceItemsSectionProps) {
  const { t } = useTranslation();
  const items = form.watch("items");

  const addItem = () => {
    const currentItems = form.getValues("items");
    const newItem = { ...defaultItem };
    const updatedItems = [...currentItems, newItem];
    form.setValue("items", updatedItems);
    setItemKeyCounter(prev => prev + 1);
  };

  const removeItem = (index: number) => {
    if (items.length > 1) {
      const newItems = items.filter((_, i) => i !== index);

      // Clear all errors for the items array first
      form.clearErrors("items");

      // Update the items with validation disabled initially
      form.setValue("items", newItems, { shouldValidate: false });

      // Force re-render and re-validation after state update
      requestAnimationFrame(() => {
        form.trigger("items");
      });
    }
  };
  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-100 dark:bg-indigo-900/30 rounded-xl">
              <ShoppingCart className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.items')}</h2>
                <HelpTooltip
                  content="Add products or services to your invoice. Include detailed descriptions, quantities, and prices for accurate billing."
                  title="Invoice Items"
                />
              </div>
              <p className="text-sm text-muted-foreground">
                {t('invoices.items_section_description', 'Manage the products and services for this invoice.')}
              </p>
            </div>
          </div>

          <ButtonGroup size="sm">
            <ProfessionalButton
              type="button"
              variant="outline"
              onClick={async () => {
                const inventoryItems = items.filter(item => item.inventory_item_id);
                if (inventoryItems.length === 0) {
                  toast.info("No inventory items to validate");
                  return;
                }

                try {
                  const validationResult = await inventoryApi.validateInvoiceStock(inventoryItems);
                  const results = (validationResult as any).validation_results;

                  const insufficient = results.filter((r: any) => !r.sufficient);
                  const warnings = results.filter((r: any) => r.sufficient && r.current_stock <= (r.minimum_stock || 0) * 1.2);

                  if (insufficient.length > 0) {
                    const messages = insufficient.map((item: any) =>
                      `${item.item_name}: ${item.requested_quantity} requested, ${item.current_stock} available`
                    );
                    toast.error(`Insufficient stock:\n${messages.join('\n')}`, { duration: 8000 });
                  } else if (warnings.length > 0) {
                    const messages = warnings.map((item: any) =>
                      `${item.item_name}: ${item.current_stock} remaining`
                    );
                    toast.warning(`Low stock warnings:\n${messages.join('\n')}`, { duration: 6000 });
                  } else {
                    toast.success(`All ${inventoryItems.length} inventory items validated successfully`);
                  }
                } catch (error) {
                  console.error("Bulk inventory validation failed:", error);
                  toast.error("Failed to validate inventory stock");
                }
              }}
              disabled={isInvoicePaid || submitting}
              leftIcon={<CheckCircle2 className="h-4 w-4" />}
            >
              Validate
            </ProfessionalButton>

            <ProfessionalButton
              type="button"
              variant="outline"
              onClick={async () => {
                try {
                  const inventoryResponse = await inventoryApi.getItems({ limit: 100 });
                  const availableInventory = inventoryResponse.items.filter(invItem =>
                    !items.some(invoiceItem => invoiceItem.inventory_item_id === invItem.id)
                  );

                  if (availableInventory.length === 0) {
                    toast.info("No additional inventory items available to add");
                    return;
                  }

                  const itemsToAdd = availableInventory.slice(0, 3);
                  const currentItems = form.getValues("items");

                  const newItems = itemsToAdd.map(invItem => ({
                    description: invItem.name,
                    quantity: 1,
                    price: invItem.unit_price,
                    inventory_item_id: invItem.id,
                    unit_of_measure: invItem.unit_of_measure,
                    id: undefined
                  }));

                  const updatedItems = [...currentItems, ...newItems];
                  form.setValue("items", updatedItems);

                  toast.success(`Added ${itemsToAdd.length} inventory items to invoice`);
                } catch (error) {
                  console.error("Failed to populate from inventory:", error);
                  toast.error("Failed to add inventory items");
                }
              }}
              disabled={isInvoicePaid || submitting}
              leftIcon={<Zap className="h-4 w-4" />}
            >
              Quick Add
            </ProfessionalButton>

            <ProfessionalButton
              type="button"
              variant="gradient"
              onClick={addItem}
              disabled={isInvoicePaid}
              leftIcon={<Plus className="h-4 w-4" />}
            >
              {t('invoices.add_item')}
            </ProfessionalButton>
          </ButtonGroup>
        </div>
      </div>

      <div className="space-y-4" data-tour="invoice-items">
        {/* Column headers for items */}
        <div className="grid grid-cols-12 gap-4 px-4 py-2 bg-muted/30 rounded-lg text-xs font-bold text-muted-foreground uppercase tracking-widest mb-4">
          <div className="col-span-12 md:col-span-6">{t('invoices.item_description')}</div>
          <div className="hidden md:block md:col-span-2 text-center">{t('invoices.quantity')}</div>
          <div className="hidden md:block md:col-span-3 text-right pr-4">{t('invoices.price')}</div>
          <div className="hidden md:block md:col-span-1 text-center">{t('invoices.actions')}</div>
        </div>

        <div className="space-y-3">
          {items.map((item, index) => (
            <div
              key={item.id ? `existing-${item.id}` : `new-${itemKeyCounter}-${index}`}
              className="grid grid-cols-12 gap-4 p-4 items-start border border-border/50 rounded-2xl bg-muted/5 hover:bg-background hover:shadow-xl hover:shadow-primary/5 transition-all duration-300 group"
            >
              <div className="col-span-12 md:col-span-6">
                <FormField
                  control={form.control}
                  name={`items.${index}.description`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <div className="relative">
                          <Input
                            placeholder={t('invoices.item_description')}
                            {...field}
                            value={field.value || ''}
                            disabled={isInvoicePaid}
                            className="h-11 rounded-xl bg-background border-border/50 focus:ring-primary/20"
                          />
                          <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex items-center gap-1">
                            {!isInvoicePaid && (
                              <InventoryItemSelector
                                onItemSelect={(inventoryItem) => {
                                  const currentItems = form.getValues("items");
                                  const updatedItems = [...currentItems];
                                  updatedItems[index] = {
                                    ...updatedItems[index],
                                    description: inventoryItem.description,
                                    price: inventoryItem.price,
                                    unit_of_measure: inventoryItem.unit_of_measure,
                                    inventory_item_id: inventoryItem.inventory_item_id,
                                  };
                                  form.setValue("items", updatedItems);
                                }}
                                selectedItemId={item.inventory_item_id}
                                compact={true}
                              />
                            )}
                          </div>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="col-span-6 md:col-span-2">
                <div className="md:hidden text-center text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
                  {t('invoices.quantity')}
                </div>
                <FormField
                  control={form.control}
                  name={`items.${index}.quantity`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input
                          type="number"
                          min="0.01"
                          step="any"
                          placeholder={t('invoices.qty')}
                          {...field}
                          value={field.value ?? ''}
                          onChange={(e) => {
                            const value = e.target.value;
                            field.onChange(value === '' ? '' : parseFloat(value) || '');
                          }}
                          disabled={isInvoicePaid}
                          className="h-11 rounded-xl bg-background border-border/50 text-center font-medium"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="col-span-4 md:col-span-3">
                <div className="md:hidden text-right text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
                  {t('invoices.price')}
                </div>
                <FormField
                  control={form.control}
                  name={`items.${index}.price`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <div className="relative">
                          <Input
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder={t('invoices.price')}
                            {...field}
                            value={field.value ?? ''}
                            onChange={(e) => {
                              const value = e.target.value;
                              field.onChange(value === '' ? '' : parseFloat(value) || '');
                            }}
                            disabled={isInvoicePaid}
                            className="h-11 rounded-xl bg-background border-border/50 text-right font-bold pr-4"
                          />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="col-span-2 md:col-span-1 flex justify-center pt-2">
                <ProfessionalButton
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => removeItem(index)}
                  disabled={items.length === 1 || isInvoicePaid}
                  className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl"
                >
                  <Trash className="h-4 w-4" />
                </ProfessionalButton>
              </div>
            </div>
          ))}
        </div>

        {items.length === 0 && (
          <div className="text-center py-12 px-6 rounded-2xl border-2 border-dashed border-border/50 bg-muted/10">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
              <ShoppingCart className="h-8 w-8 text-muted-foreground/40" />
            </div>
            <h3 className="text-lg font-bold text-foreground mb-1">{t('invoices.no_items_yet')}</h3>
            <p className="text-sm text-muted-foreground">
              {t('invoices.click_add_to_start', 'Click "Add Item" to start adding products or services.')}
            </p>
          </div>
        )}
      </div>
    </ProfessionalCard>
  );
}
