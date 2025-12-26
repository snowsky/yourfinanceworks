import React from "react";
import { InventoryInvoiceForm } from "@/components/inventory/InventoryInvoiceForm";
import { useTranslation } from "react-i18next";

const NewInventoryInvoice = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
          <p className="text-muted-foreground">
            {t("invoices.inventory_invoice_description")}
          </p>
        </div>

        <div className="slide-in">
          <InventoryInvoiceForm />
        </div>
      </div>
    </>
  );
};

export default NewInventoryInvoice;
