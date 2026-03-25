import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ClientForm } from "@/components/clients/ClientForm";
import { clientApi, Client, getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, ArrowLeft } from "lucide-react";
import { ClientNotes } from "@/components/clients/ClientNotes";
import { ClientTimeline } from "@/components/clients/ClientTimeline";
import { CrmContactsPanel } from "@/components/clients/CrmContactsPanel";
import { useTranslation } from 'react-i18next';
import { ProfessionalButton } from "@/components/ui/professional-button";
import { usePlugins } from "@/contexts/PluginContext";
import { ShareButton } from "@/components/sharing/ShareButton";

const BASE_TABS = ["Details", "Activity"] as const;
type TabValue = "Details" | "Activity" | "Contacts";

const EditClient = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isPluginEnabled } = usePlugins();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState<TabValue>("Details");

  const tabs: TabValue[] = [...BASE_TABS, ...(isPluginEnabled('crm') ? ['Contacts' as const] : [])];

  useEffect(() => {
    const fetchClient = async () => {
      if (!id) {
        navigate("/clients");
        return;
      }

      setLoading(true);
      try {
        const data = await clientApi.getClient(parseInt(id));
        setClient(data);
      } catch (error) {
        console.error("Failed to fetch client:", error);
        toast.error(getErrorMessage(error, t));
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchClient();
  }, [id, navigate, t]);

  if (loading) {
    return (
      <>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('editClient.loadingClientData')}</p>
        </div>
      </>
    );
  }

  if (error || !client) {
    return (
      <>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t('editClient.clientNotFound')}</h1>
            <p className="text-muted-foreground">{t('editClient.clientNotFoundDescription')}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <ProfessionalButton
                  variant="outline"
                  size="icon-sm"
                  onClick={() => navigate('/clients')}
                  className="rounded-full"
                >
                  <ArrowLeft className="h-4 w-4" />
                </ProfessionalButton>
              </div>
              <h1 className="text-4xl font-bold tracking-tight">{t('editClient.editClient')}</h1>
              <p className="text-lg text-muted-foreground">{t('editClient.updateClientInformation')}</p>
            </div>
            {client?.id && <ShareButton recordType="client" recordId={client.id} />}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-5 py-2.5 text-sm font-medium transition-all duration-200 -mb-px
                border-b-2
                ${
                  activeTab === tab
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
                }
              `}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "Details" && (
          <>
            <ClientForm client={client} isEdit={true} />
            {client && <ClientNotes clientId={client.id} />}
          </>
        )}

        {activeTab === "Activity" && client && (
          <ClientTimeline clientId={client.id} />
        )}

        {activeTab === "Contacts" && client && (
          <CrmContactsPanel clientId={client.id} />
        )}
      </div>
    </>
  );
};

export default EditClient; 