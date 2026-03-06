import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Plus, Trash2, ReceiptText } from "lucide-react";

import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { FormValues } from "@/hooks/useInvoiceForm";

interface InvoiceTaxSectionProps {
  form: UseFormReturn<FormValues>;
}

export function InvoiceTaxSection({ form }: InvoiceTaxSectionProps) {
  const { t } = useTranslation();
  const customFields = form.watch("customFields") || [];

  const addCustomField = () => {
    form.setValue("customFields", [...customFields, { key: "", value: "" }], {
      shouldDirty: true,
      shouldValidate: true,
    });
  };

  const updateCustomField = (index: number, key: "key" | "value", value: string) => {
    const next = [...customFields];
    next[index] = { ...next[index], [key]: value };
    form.setValue("customFields", next, { shouldDirty: true, shouldValidate: true });
  };

  const removeCustomField = (index: number) => {
    form.setValue(
      "customFields",
      customFields.filter((_, i) => i !== index),
      { shouldDirty: true, shouldValidate: true }
    );
  };

  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-amber-100 dark:bg-amber-900/30 rounded-xl">
            <ReceiptText className="h-6 w-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              {t("invoices.tax_and_custom_fields", "Tax & Custom Fields")}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t(
                "invoices.tax_and_custom_fields_desc",
                "Set explicit tax values for export and add any additional key-value fields."
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <FormField
            control={form.control}
            name="taxAmount"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("invoices.tax_amount", "Tax Amount")}</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={field.value ?? ""}
                    onChange={(e) => {
                      const value = e.target.value;
                      field.onChange(value === "" ? undefined : Number(value));
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="taxRate"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("invoices.tax_rate_percent", "Tax Rate (%)")}</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={field.value ?? ""}
                    onChange={(e) => {
                      const value = e.target.value;
                      field.onChange(value === "" ? undefined : Number(value));
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-foreground">
              {t("invoices.custom_fields", "Custom Fields")}
            </h3>
            <Button type="button" variant="outline" size="sm" onClick={addCustomField}>
              <Plus className="h-4 w-4 mr-2" />
              {t("invoices.add_custom_field", "Add Field")}
            </Button>
          </div>

          {customFields.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("invoices.no_custom_fields", "No custom fields yet.")}
            </p>
          )}

          <div className="space-y-3">
            {customFields.map((customField, index) => (
              <div key={index} className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3">
                <Input
                  placeholder={t("invoices.custom_field_key", "Field key")}
                  value={customField.key}
                  onChange={(e) => updateCustomField(index, "key", e.target.value)}
                />
                <Input
                  placeholder={t("invoices.custom_field_value", "Field value")}
                  value={customField.value || ""}
                  onChange={(e) => updateCustomField(index, "value", e.target.value)}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeCustomField(index)}
                  aria-label={t("invoices.remove_custom_field", "Remove custom field")}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </ProfessionalCard>
  );
}
