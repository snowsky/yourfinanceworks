import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { FormValues } from "@/hooks/useInvoiceForm";

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
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {t('invoices.payment_details', 'Payment Details')}
          {!canEditPayment && (
            <span className="text-sm text-muted-foreground">
              ({t('invoices.read_only', 'Read only')})
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              {t('invoices.total_amount', 'Total Amount')}
            </label>
            <div className="text-lg font-semibold">
              <CurrencyDisplay amount={totalAmount} currency={form.watch("currency")} />
            </div>
          </div>

          <div>
            <FormField
              control={form.control}
              name="paidAmount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('invoices.paid_amount', 'Paid Amount')}</FormLabel>
                  <FormControl>
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
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              {t('invoices.outstanding_amount', 'Outstanding Amount')}
            </label>
            <div className={`text-lg font-semibold ${outstandingAmount > 0 ? 'text-orange-600' : 'text-green-600'}`}>
              <CurrencyDisplay amount={outstandingAmount} currency={form.watch("currency")} />
            </div>
          </div>
        </div>

        {canEditPayment && (
          <div className="text-sm text-muted-foreground bg-blue-50 p-3 rounded-lg">
            {t('invoices.payment_update_note', 'You can update the paid amount for this approved invoice to record partial payments.')}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
