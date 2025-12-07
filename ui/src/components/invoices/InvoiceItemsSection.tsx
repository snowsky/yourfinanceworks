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
      form.setValue("items", newItems);
      form.clearErrors("items");
    }
  };

  return (
    <div className="space-y-4" data-tour="invoice-items">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-medium">{t('invoices.items')}</h3>
          <HelpTooltip
            content="Add products or services to your invoice. Include detailed descriptions, quantities, and prices for accurate billing."
            title="Invoice Items"
          />
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
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
            title="Validate stock availability for all inventory items"
          >
            Validate Stock
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
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
            title="Quickly add available inventory items to invoice"
          >
            <Plus className="h-4 w-4 mr-2" />
            Quick Add
          </Button>

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
      </div>

      {/* Column headers for items */}
      <div className="grid grid-cols-12 gap-4 font-semibold text-sm text-gray-600 mb-2">
        <div className="col-span-6">{t('invoices.item_description')}</div>
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
                    <div className="relative">
                      <Input
                        placeholder={t('invoices.item_description')}
                        {...field}
                        value={field.value || ''}
                        disabled={isInvoicePaid}
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
          <div className="col-span-2">
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
                      value={field.value || ''}
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
                      min="0"
                      step="0.01"
                      placeholder={t('invoices.price')}
                      {...field}
                      value={field.value || ''}
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
  );
}
