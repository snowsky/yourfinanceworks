import React from "react";
import { UseFormReturn } from "react-hook-form";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { SmartClientSelector } from "./SmartClientSelector";
import { HelpTooltip } from "@/components/onboarding/HelpTooltip";
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FormValues } from "@/hooks/useInvoiceForm";

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
    <div className="grid grid-cols-1 gap-6">
      <FormField
        control={form.control}
        name="client"
        render={({ field }) => (
          <FormItem data-tour="client-selector">
            <div className="flex items-center gap-2">
              <FormLabel>{t('invoices.client')}</FormLabel>
              <HelpTooltip
                content="Select an existing client or create a new one. Client information will be used for billing and contact details."
                title="Client Selection"
              />
            </div>
            <div className="space-y-2">
              <SmartClientSelector
                clients={clients}
                value={field.value}
                onValueChange={(value) => {
                  console.log("🔍 Client selection changed:", value);
                  field.onChange(value);
                  form.trigger("client");
                  // Clear any existing client error when a client is selected
                  if (value && value.trim() !== "") {
                    form.clearErrors("client");
                  }
                }}
                onCreateNew={() => setShowNewClientDialog(true)}
                placeholder={t('invoices.select_a_client')}
                disabled={isInvoicePaid}
              />
              {!isInvoicePaid && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowNewClientDialog(true)}
                  className="w-full sm:w-auto"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  {t('invoices.new_client')}
                </Button>
              )}
            </div>
            <FormMessage />
            {form.formState.errors.client && (
              <div className="text-red-500 text-sm mt-1 font-medium bg-red-50 border border-red-200 rounded p-2">
                ⚠️ {form.formState.errors.client.message}
              </div>
            )}
          </FormItem>
        )}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <FormField
          control={form.control}
          name="invoiceNumber"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('invoices.invoice_number')} (Optional)</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  placeholder="Leave empty to auto-generate"
                  disabled={isInvoicePaid}
                />
              </FormControl>
              <FormDescription>
                If left empty, an invoice number will be generated automatically
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
              <FormLabel>{t('invoices.currency')}</FormLabel>
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
              <FormLabel>Payer</FormLabel>
              <Select value={field.value || "Client"} onValueChange={field.onChange} disabled={isInvoicePaid}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="You">You</SelectItem>
                  <SelectItem value="Client">Client</SelectItem>
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      {/* Client Creation Dialog */}
      <Dialog open={showNewClientDialog} onOpenChange={(open) => {
        setShowNewClientDialog(open);
        if (!open) {
          resetNewClientForm();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('invoices.add_new_client')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">{t('invoices.name')}</Label>
              <Input
                id="name"
                value={newClientForm.name}
                onChange={(e) => setNewClientForm({ ...newClientForm, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="email">{t('invoices.email')}</Label>
              <Input
                id="email"
                type="email"
                value={newClientForm.email}
                onChange={(e) => setNewClientForm({ ...newClientForm, email: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="phone">{t('invoices.phone')}</Label>
              <Input
                id="phone"
                value={newClientForm.phone || ''}
                onChange={(e) => setNewClientForm({ ...newClientForm, phone: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="address">{t('invoices.address')}</Label>
              <Input
                id="address"
                value={newClientForm.address || ''}
                onChange={(e) => setNewClientForm({ ...newClientForm, address: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="preferred_currency">{t('invoices.preferred_currency')}</Label>
              <CurrencySelector
                value={newClientForm.preferred_currency || tenantInfo?.default_currency || 'USD'}
                onValueChange={(val) => setNewClientForm({ ...newClientForm, preferred_currency: val })}
                placeholder={t('invoices.select_preferred_currency')}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowNewClientDialog(false);
              resetNewClientForm();
            }}>
              {t('invoices.cancel')}
            </Button>
            <Button onClick={handleCreateClient}>{t('invoices.add_client')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
