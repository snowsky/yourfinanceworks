import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { ClientForm } from "@/components/clients/ClientForm";
import { clientApi, Client } from "@/lib/api";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { ClientNotes } from "@/components/clients/ClientNotes";

const EditClient = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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
        toast.error("Failed to load client data");
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchClient();
  }, [id, navigate]);

  if (loading) {
    return (
      <AppLayout>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>Loading client data...</p>
        </div>
      </AppLayout>
    );
  }

  if (error || !client) {
    return (
      <AppLayout>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">Client Not Found</h1>
            <p className="text-muted-foreground">The client you're looking for doesn't exist or couldn't be loaded.</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">Edit Client</h1>
          <p className="text-muted-foreground">Update client information</p>
        </div>
        
        <ClientForm client={client} isEdit={true} />

        {client && <ClientNotes clientId={client.id} />}
      </div>
    </AppLayout>
  );
};

export default EditClient; 