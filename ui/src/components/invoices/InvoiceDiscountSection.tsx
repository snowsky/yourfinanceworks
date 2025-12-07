import React from "react";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { DiscountRule } from "@/lib/api";
import { FormValues } from "@/hooks/useInvoiceForm";

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
    <div className="space-y-4">
      <h3 className="text-lg font-medium">{t('invoices.discount')}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <FormField
          control={form.control}
          name="discountType"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('invoices.discount_type')}</FormLabel>
              <Select
                onValueChange={(value) => {
                  field.onChange(value);
                  // Clear applied rule when switching away from rule type
                  if (value !== "rule") {
                    // Note: setAppliedDiscountRule would need to be passed down
                  } else {
                    // When switching TO rule type, automatically select the first available rule
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
                  <SelectTrigger>
                    <SelectValue placeholder={t('invoices.select_discount_type')} />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="percentage">{t('invoices.percentage')}</SelectItem>
                  <SelectItem value="fixed">{t('invoices.fixed_amount')}</SelectItem>
                  <SelectItem value="rule">{t('invoices.discount_rule')}</SelectItem>
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
              <FormLabel>{t('invoices.discount_value')}</FormLabel>
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
                        // Note: setAppliedDiscountRule(null) would need to be passed down
                      }
                    }}
                    disabled={isInvoicePaid}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('invoices.select_a_discount_rule')} />
                    </SelectTrigger>
                    <SelectContent>
                      {availableDiscountRules
                        .sort((a, b) => b.priority - a.priority || b.min_amount - a.min_amount)
                        .map((rule) => {
                          const dropdownCurrency = form.watch("currency");
                          return (
                            <SelectItem
                              key={rule.id}
                              value={rule.id.toString()}
                              disabled={(rule.currency || '').trim().toUpperCase() !== (dropdownCurrency || '').trim().toUpperCase()}
                            >
                              {rule.name} - {rule.discount_value}{rule.discount_type === 'percentage' ? '%' : '$'} ({t('invoices.min', { amount: rule.min_amount })})
                              {(rule.currency || '').trim().toUpperCase() !== (dropdownCurrency || '').trim().toUpperCase() && (
                                <span style={{ color: '#888', fontSize: '0.85em', marginLeft: 8 }}>
                                  ({t('invoices.not_available_for', { currency: dropdownCurrency })})
                                </span>
                              )}
                            </SelectItem>
                          );
                        })}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder={form.watch("discountType") === "percentage" ? "0.00" : "0.00"}
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
                  />
                )}
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      {/* Discount Rule Indicator */}
      {form.watch("discountType") === "rule" && appliedDiscountRule && (
        <div className={`text-sm p-4 rounded-md border ${calculateSubtotal() >= appliedDiscountRule.min_amount
          ? "text-blue-600 bg-blue-50 border-blue-200"
          : "text-orange-600 bg-orange-50 border-orange-200"
          }`}>
          <div className="font-medium mb-2">
            {calculateSubtotal() >= appliedDiscountRule.min_amount ? t('invoices.applied_discount_rule') : t('invoices.discount_rule_not_applied')}
          </div>
          <div className="space-y-1">
            <div><span className="font-medium">{t('invoices.rule')}:</span> {appliedDiscountRule.name}</div>
            <div><span className="font-medium">{t('invoices.minimum_amount')}:</span> ${appliedDiscountRule.min_amount.toFixed(2)}</div>
            <div><span className="font-medium">{t('invoices.current_subtotal')}:</span> ${calculateSubtotal().toFixed(2)}</div>
            <div><span className="font-medium">{t('invoices.discount')}:</span> {appliedDiscountRule.discount_value}{appliedDiscountRule.discount_type === 'percentage' ? '%' : '$'}</div>
            <div><span className="font-medium">{t('invoices.discount_amount')}:</span> -${calculateDiscount().toFixed(2)}</div>
          </div>
          <div className={`text-xs mt-2 pt-2 border-t ${calculateSubtotal() >= appliedDiscountRule.min_amount
            ? "text-blue-500 border-blue-200"
            : "text-orange-500 border-orange-200"
            }`}>
            {calculateSubtotal() >= appliedDiscountRule.min_amount ? t('invoices.this_discount_rule_was_automatically_applied_based_on_your_invoice_subtotal') : t('invoices.this_discount_rule_requires_a_minimum_subtotal_of', { amount: appliedDiscountRule.min_amount.toFixed(2) })}
          </div>
        </div>
      )}

      {/* Legacy discount indicator for non-rule discounts */}
      {form.watch("discountValue") > 0 && form.watch("discountType") !== "rule" && (
        <div className="text-sm text-blue-600 bg-blue-50 p-2 rounded-md border border-blue-200">
          <span className="font-medium">{t('invoices.discount_applied')}:</span> {form.watch("discountValue")}{form.watch("discountType") === "percentage" ? "%" : "$"} {t('invoices.discount')}
        </div>
      )}

      {/* Summary Section */}
      <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg space-y-2">
        <div className="flex justify-between">
          <span className="text-sm text-gray-600">{t('invoices.subtotal')}:</span>
          <span className="font-medium">${calculateSubtotal().toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-gray-600">
            {t('invoices.discount')}: {t('invoices.discount_type')} {t('invoices.discount_value')}
          </span>
          <span className="font-medium text-red-600">-${calculateDiscount().toFixed(2)}</span>
        </div>
        <div className="border-t pt-2 flex justify-between">
          <span className="font-semibold">{t('invoices.total')}:</span>
          <span className="font-bold text-lg">${calculateTotal().toFixed(2)}</span>
        </div>
      </div>

      <FormField
        control={form.control}
        name="showDiscountInPdf"
        render={({ field }) => (
          <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4 shadow">
            <FormControl>
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            </FormControl>
            <div className="space-y-1 leading-none">
              <FormLabel>
                {t('invoices.show_discount_in_pdf')}
              </FormLabel>
              <FormDescription>
                {t('invoices.if_checked_discount_details_will_be_visible_in_the_pdf_preview_and_download')}
              </FormDescription>
            </div>
          </FormItem>
        )}
      />
    </div>
  );
}
