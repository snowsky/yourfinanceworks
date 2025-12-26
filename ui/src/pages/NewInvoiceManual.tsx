import React from "react";
import { InvoiceFormWithApproval } from "@/components/invoices/InvoiceFormWithApproval";
import { useTranslation } from "react-i18next";

const NewInvoiceManual = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t("invoices.new_invoice")}</h1>
          <p className="text-muted-foreground">Enter invoice details manually</p>
        </div>

        <div className="slide-in">
          <InvoiceFormWithApproval />
        </div>
      </div>
    </>
  );
};

export default NewInvoiceManual;