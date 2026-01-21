import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { FormValues } from "@/hooks/useInvoiceForm";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { Wallet, CheckCircle2, AlertCircle, Coins } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface InvoicePaymentSectionProps {
  form: UseFormReturn<FormValues>;
  canEditPayment: boolean;
}

export function InvoicePaymentSection({
  form,
  canEditPayment
}: InvoicePaymentSectionProps) {
  const { t } = useTranslation();

  // Calculate total amount after discount (same logic as in useInvoiceForm)
  const calculateTotalAmount = () => {
    const items = form.watch("items") || [];
    const discountType = form.watch("discountType");
    const discountValue = form.watch("discountValue") || 0;

    // Calculate subtotal
    const subtotal = items.reduce((sum: number, item: any) => {
      const quantity = Number(item.quantity) || 0;
      const price = Number(item.price) || 0;
      return sum + quantity * price;
    }, 0);

    // Calculate discount
    let discount = 0;
    if (discountType === "percentage") {
      discount = (subtotal * discountValue) / 100;
    } else if (discountType === "fixed") {
      discount = Math.min(discountValue, subtotal);
    }

    // Return total after discount
    return Math.max(0, subtotal - discount);
  };

  const totalAmount = calculateTotalAmount();
  const paidAmount = form.watch("paidAmount") || 0;
  const outstandingAmount = totalAmount - paidAmount;

  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-100 dark:bg-indigo-900/30 rounded-xl">
              <Wallet className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.payment_status', 'Payment Status')}</h2>
              <p className="text-sm text-muted-foreground">
                {t('invoices.payment_section_description', 'Track and record payments for this invoice.')}
              </p>
            </div>
          </div>
          {!canEditPayment && (
            <Badge variant="secondary" className="px-3 py-1 rounded-full bg-muted text-muted-foreground border-transparent">
              {t('invoices.read_only', 'Read Only')}
            </Badge>
          )}
        </div>
      </div>

      <div className="space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="p-6 rounded-3xl bg-muted/30 border border-border/50">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest leading-none mb-2">{t('invoices.total_amount')}</p>
            <div className="text-2xl font-black tracking-tight flex items-center gap-2">
              <Coins className="h-5 w-5 text-muted-foreground/50" />
              <CurrencyDisplay amount={totalAmount} currency={form.watch("currency")} />
            </div>
          </div>

          <FormField
            control={form.control}
            name="paidAmount"
            render={({ field }) => (
              <FormItem className="relative p-6 rounded-3xl bg-background border-2 border-primary/20 shadow-sm transition-all focus-within:border-primary/50">
                <FormLabel className="text-[10px] font-bold text-primary uppercase tracking-widest leading-none mb-2 block">{t('invoices.paid_amount')}</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      max={totalAmount}
                      placeholder="0.00"
                      disabled={!canEditPayment}
                      {...field}
                      onChange={(e) => {
                        const value = parseFloat(e.target.value) || 0;
                        field.onChange(value);
                      }}
                      className="h-10 text-xl font-bold bg-transparent border-0 p-0 focus-visible:ring-0 shadow-none appearance-none"
                    />
                    <div className="absolute right-0 top-1/2 -translate-y-1/2">
                      <Badge variant="outline" className="text-[10px] font-bold border-primary/20 text-primary uppercase py-0 px-2">
                        {form.watch("currency") || "USD"}
                      </Badge>
                    </div>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className={`p-6 rounded-3xl border-2 transition-all ${outstandingAmount > 0
            ? 'bg-amber-50/50 border-amber-100 dark:bg-amber-900/10 dark:border-amber-900/30'
            : 'bg-emerald-50/50 border-emerald-100 dark:bg-emerald-900/10 dark:border-emerald-900/30'}`}>
            <p className={`text-[10px] font-bold uppercase tracking-widest leading-none mb-2 ${outstandingAmount > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {t('invoices.outstanding')}
            </p>
            <div className={`text-2xl font-black tracking-tight flex items-center gap-2 ${outstandingAmount > 0 ? 'text-amber-700 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400'}`}>
              {outstandingAmount > 0 ? <AlertCircle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
              <CurrencyDisplay amount={outstandingAmount} currency={form.watch("currency")} />
            </div>
          </div>
        </div>

        {canEditPayment && (
          <div className="flex items-start gap-4 p-5 rounded-2xl bg-indigo-50/50 border border-indigo-100 dark:bg-indigo-900/10 dark:border-indigo-900/30 italic">
            <CheckCircle2 className="h-5 w-5 text-indigo-600 dark:text-indigo-400 shrink-0" />
            <p className="text-sm text-indigo-900/70 dark:text-indigo-400/70">
              {t('invoices.payment_update_note', 'You can update the paid amount for this approved invoice to record partial payments.')}
            </p>
          </div>
        )}
      </div>
    </ProfessionalCard>
  );
}
