import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FormField, FormItem, FormLabel, FormControl } from "@/components/ui/form";
import { X } from "lucide-react";
import { FormValues } from "@/hooks/useInvoiceForm";

interface InvoiceLabelsSectionProps {
  form: UseFormReturn<FormValues>;
}

export function InvoiceLabelsSection({ form }: InvoiceLabelsSectionProps) {
  const { t } = useTranslation();
  const [newLabel, setNewLabel] = React.useState("");
  const labels = form.watch("labels") || [];
  
  console.log("InvoiceLabelsSection rendering with labels:", labels);

  const addLabel = () => {
    const trimmed = newLabel.trim();
    if (trimmed && !labels.includes(trimmed) && labels.length < 10) {
      const updatedLabels = [...labels, trimmed];
      form.setValue("labels", updatedLabels);
      setNewLabel("");
    }
  };

  const removeLabel = (labelToRemove: string) => {
    const updatedLabels = labels.filter((label: string) => label !== labelToRemove);
    form.setValue("labels", updatedLabels);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addLabel();
    }
  };

  return (
    <div className="space-y-4 p-4 border-2 border-blue-500 rounded-lg bg-card">
      <div>
        <h3 className="text-lg font-medium text-blue-600">{t('invoices.labels', 'Labels')}</h3>
        <p className="text-sm text-muted-foreground">
          {t('invoices.labels_description', 'Add up to 10 labels to organize your invoices')}
        </p>
      </div>

      {/* Debug info */}
      <div className="text-xs text-gray-500">
        Debug: Component is rendering! Labels count: {labels.length}
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {labels.map((label: string, index: number) => (
            <Badge
              key={index}
              variant="secondary"
              className="flex items-center gap-1 pr-1"
            >
              {label}
              <X
                className="h-3 w-3 cursor-pointer hover:text-destructive"
                onClick={() => removeLabel(label)}
              />
            </Badge>
          ))}
        </div>

        {labels.length < 10 && (
          <div className="flex gap-2">
            <Input
              placeholder={t('invoices.add_label_placeholder', 'Add a label...')}
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyPress={handleKeyPress}
              className="flex-1"
              maxLength={50}
            />
            <button
              type="button"
              onClick={addLabel}
              disabled={!newLabel.trim() || labels.length >= 10}
              className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t('common.add', 'Add')}
            </button>
          </div>
        )}

        <FormField
          control={form.control}
          name="labels"
          render={() => (
            <FormItem className="hidden">
              <FormControl>
                <Input />
              </FormControl>
            </FormItem>
          )}
        />
      </div>
    </div>
  );
}
