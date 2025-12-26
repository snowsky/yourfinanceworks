import { ClientForm } from "@/components/clients/ClientForm";
import { useTranslation } from 'react-i18next';

const NewClient = () => {
  const { t } = useTranslation();
  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t('newClient.addNewClient')}</h1>
          <p className="text-muted-foreground">{t('newClient.createNewClientDescription')}</p>
        </div>

        <ClientForm />
      </div>
    </>
  );
};

export default NewClient; 