import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { DiscountRule } from "@/lib/api";
import { FormValues } from "@/hooks/useInvoiceForm";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { Tag, Percent, Receipt, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface InvoiceDiscountSectionProps {
  form: UseFormReturn<FormValues>;
  isEdit: boolean;
  isInvoicePaid: boolean;
  availableDiscountRules: DiscountRule[];
  appliedDiscountRule: {
    id: number;
    name: string;
    min_amount: number;
    discount_type: 'percentage' | 'fixed';
    discount_value: number;
  } | null;
  calculateSubtotal: () => number;
  calculateDiscount: () => number;
  calculateTotal: () => number;
  applyDiscountRule: (rule: DiscountRule) => void;
}

export function InvoiceDiscountSection({
  form,
  isEdit,
  isInvoicePaid,
  availableDiscountRules,
  appliedDiscountRule,
  calculateSubtotal,
  calculateDiscount,
  calculateTotal,
  applyDiscountRule,
}: InvoiceDiscountSectionProps) {
  const { t } = useTranslation();
  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-rose-100 dark:bg-rose-900/30 rounded-xl">
            <Tag className="h-6 w-6 text-rose-600 dark:text-rose-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.discount_and_summary')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('invoices.discount_section_description', 'Apply discounts and review the final totals.')}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <FormField
            control={form.control}
            name="discountType"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-sm font-semibold text-foreground/70">{t('invoices.discount_type')}</FormLabel>
                <Select
                  onValueChange={(value) => {
                    field.onChange(value);
                    if (value !== "rule") {
                      // Note: setAppliedDiscountRule would need to be passed down
                    } else {
                      if (availableDiscountRules.length > 0) {
                        const currentCurrency = form.watch("currency") || "USD";
                        const subtotal = calculateSubtotal();

                        const availableRule = availableDiscountRules
                          .filter(rule =>
                            rule.is_active &&
                            (rule.currency || '').trim().toUpperCase() === currentCurrency.trim().toUpperCase() &&
                            subtotal >= rule.min_amount
                          )
                          .sort((a, b) => b.priority - a.priority || b.min_amount - a.min_amount)[0];

                        if (availableRule) {
                          applyDiscountRule(availableRule);
                          form.setValue("discountValue", availableRule.discount_value);
                        } else {
                          form.setValue("discountValue", 0);
                        }
                      } else {
                        form.setValue("discountValue", 0);
                      }
                    }
                  }}
                  value={field.value}
                  disabled={isInvoicePaid}
                >
                  <FormControl>
                    <SelectTrigger className="h-12 rounded-xl bg-background border-border/50 shadow-sm focus:ring-primary/20">
                      <SelectValue placeholder={t('invoices.select_discount_type')} />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent className="rounded-xl border-border/50 shadow-2xl">
                    <SelectItem value="percentage" className="rounded-lg">{t('invoices.percentage')}</SelectItem>
                    <SelectItem value="fixed" className="rounded-lg">{t('invoices.fixed_amount')}</SelectItem>
                    <SelectItem value="rule" className="rounded-lg">{t('invoices.discount_rule')}</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="discountValue"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-sm font-semibold text-foreground/70">{t('invoices.discount_value')}</FormLabel>
                <FormControl>
                  {form.watch("discountType") === "rule" ? (
                    <Select
                      value={appliedDiscountRule?.id?.toString() || ""}
                      onValueChange={(value) => {
                        const selectedRule = availableDiscountRules.find(
                          rule => rule.id.toString() === value
                        );
                        if (
                          selectedRule &&
                          (selectedRule.currency || '').trim().toUpperCase() === (form.watch("currency") || '').trim().toUpperCase()
                        ) {
                          field.onChange(selectedRule.discount_value);
                          applyDiscountRule(selectedRule);
                        } else {
                          field.onChange(0);
                        }
                      }}
                      disabled={isInvoicePaid}
                    >
                      <SelectTrigger className="h-12 rounded-xl bg-background border-border/50 shadow-sm focus:ring-primary/20">
                        <SelectValue placeholder={t('invoices.select_a_discount_rule')} />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border-border/50 shadow-2xl">
                        {availableDiscountRules
                          .sort((a, b) => b.priority - a.priority || b.min_amount - a.min_amount)
                          .map((rule) => {
                            const dropdownCurrency = form.watch("currency");
                            return (
                              <SelectItem
                                key={rule.id}
                                value={rule.id.toString()}
                                disabled={(rule.currency || '').trim().toUpperCase() !== (dropdownCurrency || '').trim().toUpperCase()}
                                className="rounded-lg"
                              >
                                {rule.name} - {rule.discount_value}{rule.discount_type === 'percentage' ? '%' : '$'} ({t('invoices.min', { amount: rule.min_amount })})
                              </SelectItem>
                            );
                          })}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="relative">
                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        placeholder="0.00"
                        {...field}
                        onChange={(e) => {
                          const value = parseFloat(e.target.value) || 0;
                          const discountType = form.watch("discountType");

                          if (discountType === "percentage" && value > 100) {
                            field.onChange(100);
                          } else {
                            field.onChange(value);
                          }
                        }}
                        disabled={isInvoicePaid}
                        className="h-12 rounded-xl bg-background border-border/50 shadow-sm focus:ring-primary/20 pr-10"
                      />
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none">
                        {form.watch("discountType") === "percentage" ? <Percent className="h-4 w-4" /> : <Receipt className="h-4 w-4" />}
                      </div>
                    </div>
                  )}
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Discount Rule Indicator */}
        {form.watch("discountType") === "rule" && appliedDiscountRule && (
          <div className={`p-6 rounded-3xl border-2 transition-all duration-300 ${calculateSubtotal() >= appliedDiscountRule.min_amount
            ? "bg-emerald-50/50 border-emerald-100 dark:bg-emerald-900/10 dark:border-emerald-900/30"
            : "bg-amber-50/50 border-amber-100 dark:bg-amber-900/10 dark:border-amber-900/30"
            }`}>
            <div className="flex items-start gap-4">
              <div className={`p-2 rounded-xl ${calculateSubtotal() >= appliedDiscountRule.min_amount
                ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-800 dark:text-emerald-400"
                : "bg-amber-100 text-amber-600 dark:bg-amber-800 dark:text-amber-400"
                }`}>
                <Info className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className={`font-bold ${calculateSubtotal() >= appliedDiscountRule.min_amount ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
                    {calculateSubtotal() >= appliedDiscountRule.min_amount ? t('invoices.applied_discount_rule') : t('invoices.discount_rule_not_applied')}
                  </h4>
                  <Badge variant={calculateSubtotal() >= appliedDiscountRule.min_amount ? "success" : "warning"} className="rounded-lg px-2 py-0.5">
                    {calculateSubtotal() >= appliedDiscountRule.min_amount ? "Applied" : "Pending"}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-none tracking-widest">{t('invoices.rule')}</p>
                    <p className="text-sm font-semibold">{appliedDiscountRule.name}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-none tracking-widest">{t('invoices.minimum')}</p>
                    <p className="text-sm font-semibold">${appliedDiscountRule.min_amount.toFixed(2)}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-none tracking-widest">{t('invoices.discount')}</p>
                    <p className="text-sm font-bold text-rose-600">
                      {appliedDiscountRule.discount_value}{appliedDiscountRule.discount_type === 'percentage' ? '%' : '$'}
                    </p>
                  </div>
                  <div className="space-y-1 text-right">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase leading-none tracking-widest">{t('invoices.amount')}</p>
                    <p className="text-sm font-bold text-rose-600">-${calculateDiscount().toFixed(2)}</p>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-border/30 text-xs text-muted-foreground">
                  {calculateSubtotal() >= appliedDiscountRule.min_amount
                    ? t('invoices.rule_applied_desc', 'This discount rule was automatically applied based on the subtotal.')
                    : t('invoices.rule_pending_desc', 'Requires a minimum subtotal of {{amount}} to apply.', { amount: appliedDiscountRule.min_amount.toFixed(2) })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Summary Card */}
        <div className="bg-muted/30 rounded-3xl p-8 border border-border/50">
          <div className="space-y-4">
            <div className="flex justify-between items-center text-muted-foreground">
              <span className="text-sm font-medium">{t('invoices.subtotal')}</span>
              <span className="text-lg font-semibold text-foreground">${calculateSubtotal().toFixed(2)}</span>
            </div>

            {(form.watch("discountValue") > 0 || appliedDiscountRule) && (
              <div className="flex justify-between items-center text-rose-600">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{t('invoices.discount')}</span>
                  {form.watch("discountType") !== "rule" && (
                    <Badge variant="outline" className="text-[10px] border-rose-200 text-rose-600 bg-rose-50/50">
                      {form.watch("discountValue")}{form.watch("discountType") === "percentage" ? "%" : "$"} Off
                    </Badge>
                  )}
                </div>
                <span className="text-lg font-bold">-${calculateDiscount().toFixed(2)}</span>
              </div>
            )}

            <div className="pt-4 border-t border-border/50 flex justify-between items-end">
              <div>
                <span className="text-sm font-bold text-muted-foreground uppercase tracking-widest leading-none block mb-1">{t('invoices.total_amount')}</span>
                <span className="text-4xl font-black tracking-tight bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
                  ${calculateTotal().toFixed(2)}
                </span>
              </div>
              <Badge className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold px-3 py-1 rounded-full animate-pulse shadow-lg shadow-primary/20">
                Final Total
              </Badge>
            </div>
          </div>
        </div>

        <FormField
          control={form.control}
          name="showDiscountInPdf"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center space-x-3 space-y-0 p-6 rounded-2xl border border-border/50 hover:bg-muted/5 transition-colors cursor-pointer group">
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  className="rounded-md border-border/50 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                />
              </FormControl>
              <div className="space-y-0.5 leading-none flex-1">
                <FormLabel className="text-sm font-bold text-foreground/80 group-hover:text-foreground transition-colors cursor-pointer">
                  {t('invoices.show_discount_in_pdf')}
                </FormLabel>
                <p className="text-xs text-muted-foreground">
                  {t('invoices.pdf_discount_description', 'Visible in the PDF preview and download.')}
                </p>
              </div>
            </FormItem>
          )}
        />
      </div>
    </ProfessionalCard>
  );
}
