import { ClientForm } from "@/components/clients/ClientForm";
import { useTranslation } from 'react-i18next';
import { PageHeader } from '@/components/ui/professional-layout';

const NewClient = () => {
  const { t } = useTranslation();
  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader title={t('newClient.addNewClient')} description={t('newClient.createNewClientDescription')} />

        <ClientForm />
      </div>
    </>
  );
};

export default NewClient; 