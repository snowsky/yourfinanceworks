import React from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { InventoryInvoiceForm } from "@/components/inventory/InventoryInvoiceForm";
import { useTranslation } from "react-i18next";

const NewInventoryInvoice = () => {
  const { t } = useTranslation();

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
          <p className="text-muted-foreground">
            Create a new invoice with inventory integration - select items from your inventory catalog
          </p>
        </div>

        <div className="slide-in">
          <InventoryInvoiceForm />
        </div>
      </div>
    </AppLayout>
  );
};

export default NewInventoryInvoice;
