import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FormField, FormItem, FormLabel, FormControl } from "@/components/ui/form";
import { Plus, X, Bookmark } from "lucide-react";
import { FormValues } from "@/hooks/useInvoiceForm";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

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
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
            <Bookmark className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.labels', 'Labels')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('invoices.labels_description', 'Add up to 10 labels to organize your invoices')}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <div className="flex flex-wrap gap-2 min-h-[40px] p-4 rounded-2xl bg-muted/30 border border-dashed border-border/50">
          {labels.length > 0 ? (
            labels.map((label: string, index: number) => (
              <Badge
                key={index}
                className="flex items-center gap-2 pl-3 pr-1 py-1.5 rounded-full bg-background border-border/50 text-foreground hover:border-destructive/30 hover:bg-destructive/5 transition-all group"
              >
                <span className="text-sm font-medium">{label}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    removeLabel(label);
                  }}
                  className="p-1 rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))
          ) : (
            <div className="w-full text-center py-2 text-sm text-muted-foreground/60 italic">
              {t('invoices.no_labels_yet', 'No labels added yet...')}
            </div>
          )}
        </div>

        {labels.length < 10 && (
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Input
                placeholder={t('invoices.add_label_placeholder', 'Add a label...')}
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                onKeyDown={handleKeyPress}
                className="h-12 rounded-xl bg-background border-border/50 shadow-sm focus:ring-primary/20 pl-4 pr-10"
                maxLength={50}
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/40">
                <Plus className="h-4 w-4" />
              </div>
            </div>
            <ProfessionalButton
              type="button"
              onClick={addLabel}
              disabled={!newLabel.trim() || labels.length >= 10}
              variant="gradient"
              className="rounded-xl px-6"
            >
              {t('common.add', 'Add')}
            </ProfessionalButton>
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
    </ProfessionalCard>
  );
}
