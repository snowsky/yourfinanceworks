import React from "react";
import { InventoryInvoiceForm } from "@/components/inventory/InventoryInvoiceForm";
import { useTranslation } from "react-i18next";
import { PageHeader } from '@/components/ui/professional-layout';

const NewInventoryInvoice = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader title={t("invoices.new_invoice")} description={t("invoices.inventory_invoice_description")} />

        <div className="slide-in">
          <InventoryInvoiceForm />
        </div>
      </div>
    </>
  );
};

export default NewInventoryInvoice;
