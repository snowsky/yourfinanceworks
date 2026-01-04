import React from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import { FormValues } from "@/hooks/useInvoiceForm";

interface InvoiceNotesSectionProps {
  form: ReturnType<typeof useForm<FormValues>>;
  isEdit?: boolean;
}

export function InvoiceNotesSection({ form, isEdit = false }: InvoiceNotesSectionProps) {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">
          {t('invoices.notes', 'Notes')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                {t('invoices.notes_label', 'Additional Notes')}
              </FormLabel>
              <FormControl>
                <Textarea
                  placeholder={t('invoices.notes_placeholder', 'Add any additional notes or comments for this invoice...')}
                  className="min-h-[100px] resize-y"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </CardContent>
    </Card>
  );
}
