import React from "react";
import { UseFormReturn } from "react-hook-form";
import { Plus, Users, FileText as FileTextIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { SmartClientSelector } from "./SmartClientSelector";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { Badge } from "@/components/ui/badge";
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FormValues } from "@/hooks/useInvoiceForm";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

interface InvoiceClientSectionProps {
  form: UseFormReturn<FormValues>;
  clients: any[];
  isEdit: boolean;
  isInvoicePaid: boolean;
  tenantInfo: { default_currency: string } | null;

  // Client management
  showNewClientDialog: boolean;
  setShowNewClientDialog: (show: boolean) => void;
  newClientForm: {
    name: string;
    email: string;
    phone: string;
    address: string;
    preferred_currency: string;
  };
  setNewClientForm: (form: any) => void;
  resetNewClientForm: () => void;
  handleCreateClient: () => Promise<any>;
}

export function InvoiceClientSection({
  form,
  clients,
  isEdit,
  isInvoicePaid,
  tenantInfo,
  showNewClientDialog,
  setShowNewClientDialog,
  newClientForm,
  setNewClientForm,
  resetNewClientForm,
  handleCreateClient,
}: InvoiceClientSectionProps) {
  const { t } = useTranslation();

  return (
    <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
      <div className="pb-6 border-b border-border/50 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
            <Users className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.client_info', 'Client Information')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('invoices.client_section_description', 'Choose or create a client for this invoice.')}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        <FormField
          control={form.control}
          name="client"
          render={({ field }) => (
            <FormItem data-tour="client-selector">
              <div className="flex items-center gap-2 mb-2">
                <FormLabel className="text-sm font-bold text-muted-foreground uppercase tracking-wider">{t('invoices.client')}</FormLabel>
                <HelpTooltip
                  content={t('invoices.client_help_content', { defaultValue: 'Select an existing client or create a new one. Client information will be used for billing and contact details.' })}
                  title={t('invoices.client_help_title', { defaultValue: 'Client Selection' })}
                />
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <SmartClientSelector
                    clients={clients}
                    value={field.value}
                    onValueChange={(value) => {
                      field.onChange(value);
                      form.trigger("client");
                      if (value && value.trim() !== "") {
                        form.clearErrors("client");
                      }
                    }}
                    onCreateNew={() => setShowNewClientDialog(true)}
                    placeholder={t('invoices.select_a_client')}
                    disabled={isInvoicePaid}
                  />
                </div>
                {!isInvoicePaid && (
                  <ProfessionalButton
                    type="button"
                    variant="outline"
                    onClick={() => setShowNewClientDialog(true)}
                    className="h-11 rounded-xl"
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    {t('invoices.new_client')}
                  </ProfessionalButton>
                )}
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <FormField
            control={form.control}
            name="invoiceNumber"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center gap-2 mb-2">
                  <FormLabel className="text-sm font-bold text-muted-foreground uppercase tracking-wider">{t('invoices.invoice_number')}</FormLabel>
                  <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-widest bg-muted/50">
                    {t('common.optional', { defaultValue: 'Optional' })}
                  </Badge>
                </div>
                <FormControl>
                  <Input
                    {...field}
                    className="h-11 rounded-xl bg-muted/30 border-border/50 focus:bg-background transition-all"
                    placeholder={t('invoices.invoice_number_placeholder', { defaultValue: 'Leave empty to auto-generate' })}
                    disabled={isInvoicePaid}
                  />
                </FormControl>
                <FormDescription className="text-[11px] font-medium text-muted-foreground/70">
                  {t('invoices.invoice_number_auto_generate')}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="currency"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center gap-2 mb-2">
                  <FormLabel className="text-sm font-bold text-muted-foreground uppercase tracking-wider">{t('invoices.currency')}</FormLabel>
                </div>
                <FormControl>
                  <CurrencySelector
                    value={field.value || ""}
                    onValueChange={field.onChange}
                    placeholder="Select currency"
                    disabled={isInvoicePaid}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="payer"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center gap-2 mb-2">
                  <FormLabel className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                    {t('invoices.payer', { defaultValue: 'Payer' })}
                  </FormLabel>
                </div>
                <Select value={field.value || "Client"} onValueChange={field.onChange} disabled={isInvoicePaid}>
                  <FormControl>
                    <SelectTrigger className="h-11 rounded-xl bg-muted/30 border-border/50">
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent className="rounded-xl">
                    <SelectItem value="You" className="rounded-lg">{t('invoices.payer_you', { defaultValue: 'You' })}</SelectItem>
                    <SelectItem value="Client" className="rounded-lg">{t('invoices.payer_client', { defaultValue: 'Client' })}</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      </div>

      {/* Client Creation Dialog */}
      <Dialog open={showNewClientDialog} onOpenChange={(open) => {
        setShowNewClientDialog(open);
        if (!open) {
          resetNewClientForm();
        }
      }}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-2xl">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Plus className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              {t('invoices.add_new_client')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5 py-4">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{t('invoices.name')}</Label>
              <Input
                id="name"
                className="h-11 rounded-xl"
                value={newClientForm.name}
                onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{t('invoices.email')}</Label>
              <Input
                id="email"
                type="email"
                className="h-11 rounded-xl"
                value={newClientForm.email}
                onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="phone" className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{t('invoices.phone')}</Label>
                <Input
                  id="phone"
                  className="h-11 rounded-xl"
                  value={newClientForm.phone || ''}
                  onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="preferred_currency" className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{t('invoices.currency')}</Label>
                <CurrencySelector
                  value={newClientForm.preferred_currency || tenantInfo?.default_currency || 'USD'}
                  onValueChange={(val) => setNewClientForm({ ...newClientForm, preferred_currency: val })}
                  placeholder={t('invoices.select_preferred_currency')}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="address" className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{t('invoices.address')}</Label>
              <Input
                id="address"
                className="h-11 rounded-xl"
                value={newClientForm.address || ''}
                onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <ProfessionalButton variant="minimal" onClick={() => {
              setShowNewClientDialog(false);
              resetNewClientForm();
            }} className="rounded-xl">
              {t('invoices.cancel')}
            </ProfessionalButton>
            <ProfessionalButton variant="gradient" onClick={handleCreateClient} className="rounded-xl px-8 shadow-lg shadow-blue-500/20">
              {t('invoices.add_client')}
            </ProfessionalButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ProfessionalCard>
  );
}
