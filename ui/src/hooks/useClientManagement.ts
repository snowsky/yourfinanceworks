import { useState, useCallback } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Client } from "@/lib/api";
import { clientApi, getErrorMessage } from "@/lib/api";

interface UseClientManagementProps {
  clients: Client[];
  setClients: (clients: Client[]) => void;
  tenantInfo: { default_currency: string } | null;
}

export function useClientManagement({ clients, setClients, tenantInfo }: UseClientManagementProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Client creation state
  const [showNewClientDialog, setShowNewClientDialog] = useState(false);
  const [newClientForm, setNewClientForm] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    preferred_currency: "",
  });

  // Reset client form
  const resetNewClientForm = useCallback(() => {
    setNewClientForm({
      name: "",
      email: "",
      phone: "",
      address: "",
      preferred_currency: tenantInfo?.default_currency || "USD",
    });
  }, [tenantInfo]);

  // Handle client creation
  const handleCreateClient = useCallback(async () => {
    try {
      if (!localStorage.getItem('user')) {
        toast.error("Please log in to create a client");
        return;
      }

      const clientData = {
        ...newClientForm,
        preferred_currency: newClientForm.preferred_currency || tenantInfo?.default_currency || "USD",
        balance: 0,
        paid_amount: 0,
      };

      console.log("Creating client with data:", clientData);
      const newClient = await clientApi.createClient(clientData);
      console.log("✅ Created client:", newClient);

      // Update clients list
      const updatedClients = [...clients, newClient];
      setClients(updatedClients);

      setShowNewClientDialog(false);
      resetNewClientForm();
      toast.success("Client created successfully!");

      return newClient;
    } catch (error) {
      console.error("Failed to create client:", error);
      if (error instanceof Error && error.message.includes('Authentication failed')) {
        toast.error(getErrorMessage(error, t));
        navigate('/login');
      } else {
        toast.error(getErrorMessage(error, t));
      }
      throw error;
    }
  }, [newClientForm, tenantInfo, clients, setClients, resetNewClientForm, t, navigate]);

  // Refresh client list
  const refreshClientList = useCallback(async () => {
    try {
      const clientsData = await clientApi.getClients();
      setClients(clientsData);
    } catch (error) {
      console.error("Failed to refresh client list:", error);
    }
  }, [setClients]);

  // Handle client selection change
  const handleClientChange = useCallback((clientId: string, onClientChange?: (client: Client | undefined) => void) => {
    const selectedClient = clients.find(c => c.id.toString() === clientId);
    if (selectedClient && onClientChange) {
      onClientChange(selectedClient);
    }
    return selectedClient;
  }, [clients]);

  return {
    // State
    showNewClientDialog,
    setShowNewClientDialog,
    newClientForm,
    setNewClientForm,

    // Actions
    resetNewClientForm,
    handleCreateClient,
    refreshClientList,
    handleClientChange,
  };
}
