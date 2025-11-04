import React, { useState, useEffect } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useTranslation } from 'react-i18next';

import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { CurrencySelector } from "@/components/ui/currency-selector";

const formSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email address").optional(),
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
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>{isEdit ? t('clientForm.editClient') : t('clientForm.createNewClient')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('clientForm.name')}</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder={t('clientForm.namePlaceholder')} />
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
                  <FormLabel>{t('clientForm.email')}</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder={t('clientForm.emailPlaceholder')}
                      type="email"
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
                  <FormLabel>{t('clientForm.phone')}</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder={t('clientForm.phonePlaceholder')} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="address"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('clientForm.address')}</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder={t('clientForm.addressPlaceholder')} />
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
                  <FormLabel>Company</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Enter company name (optional)" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="preferred_currency"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('clientForm.preferredCurrency')}</FormLabel>
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

            <div className="flex justify-end gap-3">
              <Button variant="outline" type="button" onClick={() => navigate("/clients")}> 
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isEdit ? t('clientForm.updateClient') : t('clientForm.createClient')}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
} 