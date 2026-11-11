import React from "react";
import { InvoiceFormWithApproval } from "@/components/invoices/InvoiceFormWithApproval";
import { useTranslation } from "react-i18next";
import { PageHeader } from '@/components/ui/professional-layout';

const NewInvoiceManual = () => {
  const { t } = useTranslation();

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader title={t("invoices.new_invoice")} description={t("invoices.enter_invoice_details_manually")} />

        <div className="slide-in">
          <InvoiceFormWithApproval />
        </div>
      </div>
    </>
  );
};

export default NewInvoiceManual;