import React, { useState, useEffect } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { Loader2, Save, X } from "lucide-react";
import { useTranslation } from 'react-i18next';

import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { ProfessionalInput } from "@/components/ui/professional-input";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalCard, ProfessionalCardHeader, ProfessionalCardTitle, ProfessionalCardContent, ProfessionalCardFooter } from "@/components/ui/professional-card";
import { toast } from "sonner";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { CurrencySelector } from "@/components/ui/currency-selector";

const formSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email address").optional().or(z.literal('')),
  phone: z.string().optional(),
  address: z.string().optional(),
  company: z.string().optional(),
  preferred_currency: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

interface ClientFormProps {
  client?: Client;
  isEdit?: boolean;
}

export function ClientForm({ client, isEdit = false }: ClientFormProps) {
  const { t } = useTranslation();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: client?.name || "",
      email: client?.email || "",
      phone: client?.phone || "",
      address: client?.address || "",
      company: client?.company || "",
      preferred_currency: client?.preferred_currency || "USD",
    },
  });



  // Reset form when client data changes (only for edit mode)
  useEffect(() => {
    if (isEdit && client) {
      form.reset({
        name: client.name || "",
        email: client.email || "",
        phone: client.phone || "",
        address: client.address || "",
        company: client.company || "",
        preferred_currency: client.preferred_currency || "USD",
      });
    }
  }, [client, form, isEdit]);

  const onSubmit = async (data: FormValues) => {
    setSubmitting(true);
    try {
      if (isEdit && client) {
        // Update existing client - include email in updates
        const updateData = {
          name: data.name,
          email: data.email,
          phone: data.phone,
          address: data.address,
          company: data.company,
          preferred_currency: data.preferred_currency
        };
        await clientApi.updateClient(client.id, updateData);
        toast.success(t('clientForm.updateSuccess'));
      } else {
        // Create new client with required fields including email
        const newClient = {
          name: data.name,
          email: data.email || "",
          phone: data.phone,
          address: data.address,
          company: data.company,
          balance: 0, // Set initial balance to 0 for new clients
          paid_amount: 0,
          preferred_currency: data.preferred_currency
        };
        await clientApi.createClient(newClient);
        toast.success(t('clientForm.createSuccess'));
      }
      navigate("/clients"); // Redirect to clients page
    } catch (error) {
      console.error("Failed to save client:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ProfessionalCard className="w-full max-w-4xl mx-auto backdrop-blur-sm bg-card/95 shadow-xl border-primary/10">
      <ProfessionalCardHeader className="pb-6 border-b border-border/50">
        <ProfessionalCardTitle className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
          {isEdit ? t('clientForm.editClient') : t('clientForm.createNewClient')}
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="pt-8">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <ProfessionalInput
                        {...field}
                        label={t('clientForm.name')}
                        placeholder={t('clientForm.namePlaceholder')}
                        variant="filled"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <ProfessionalInput
                        {...field}
                        label={t('clientForm.email')}
                        placeholder={t('clientForm.emailPlaceholder')}
                        type="email"
                        variant="filled"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <ProfessionalInput
                        {...field}
                        label={t('clientForm.phone')}
                        placeholder={t('clientForm.phonePlaceholder')}
                        variant="filled"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="company"
                render={({ field }) => (
                  <FormItem>
                    <FormControl>
                      <ProfessionalInput
                        {...field}
                        label={t('clientForm.company')}
                        placeholder={t('clientForm.companyPlaceholder')}
                        variant="filled"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="md:col-span-2">
                <FormField
                  control={form.control}
                  name="address"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <ProfessionalInput
                          {...field}
                          label={t('clientForm.address')}
                          placeholder={t('clientForm.addressPlaceholder')}
                          variant="filled"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="md:col-span-2">
                <FormField
                  control={form.control}
                  name="preferred_currency"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t('clientForm.preferredCurrency')}
                      </FormLabel>
                      <FormControl>
                        <CurrencySelector
                          key={client?.id || 'new'}
                          value={field.value || client?.preferred_currency || 'USD'}
                          onValueChange={field.onChange}
                          placeholder={t('clientForm.selectPreferredCurrency')}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-border/50">
              <ProfessionalButton
                variant="outline"
                type="button"
                onClick={() => navigate("/clients")}
                leftIcon={<X className="h-4 w-4" />}
              >
                {t('common.cancel')}
              </ProfessionalButton>
              <ProfessionalButton
                type="submit"
                disabled={submitting}
                variant="gradient"
                leftIcon={submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              >
                {isEdit ? t('clientForm.updateClient') : t('clientForm.createClient')}
              </ProfessionalButton>
            </div>
          </form>
        </Form>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
} 