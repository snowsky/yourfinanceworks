import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as Localization from 'expo-localization';

const resources = {
  en: {
    translation: {
      // Dashboard
      dashboard: {
        welcome: 'Welcome back, {{name}}!',
        overview: 'Overview of your invoicing activity',
        totalIncome: 'Total Income',
        pendingAmount: 'Pending Amount',
        totalClients: 'Total Clients',
        overdueInvoices: 'Overdue Invoices',
        quickActions: 'Quick Actions',
        recentInvoices: 'Recent Invoices',
        viewAll: 'View All',
        loading: 'Loading dashboard...'
      },
      // Invoices
      invoices: {
        title: 'Invoices',
        noInvoices: 'No invoices found',
        emptySubtext: 'Create your first invoice to get started',
        searchPlaceholder: 'Search invoices...',
        status: {
          all: 'All Statuses',
          paid: 'Paid',
          pending: 'Pending',
          overdue: 'Overdue',
          draft: 'Draft'
        },
        loading: 'Loading invoices...'
      },
      // Settings
      settings: {
        title: 'Settings',
        companyInfo: 'Company Information',
        chooseFile: 'Choose file',
        noFileSelected: 'No file selected',
        save: 'Save',
        signOut: 'Sign Out',
        loading: 'Loading settings...'
      },
      // General
      general: {
        loading: 'Loading...',
        error: 'Error',
        success: 'Success',
        cancel: 'Cancel',
        confirm: 'Confirm',
        update: 'Update',
        by: 'by {{user}}',
        amount: 'Amount',
        viewDetails: 'View Details',
        noUpdateHistory: 'No update history available',
        loadingHistory: 'Loading history...'
      }
    }
  },
  es: {
    translation: {
      dashboard: {
        welcome: '¡Bienvenido de nuevo, {{name}}!',
        overview: 'Resumen de tu actividad de facturación',
        totalIncome: 'Ingresos Totales',
        pendingAmount: 'Pendiente',
        totalClients: 'Clientes Totales',
        overdueInvoices: 'Facturas Vencidas',
        quickActions: 'Acciones Rápidas',
        recentInvoices: 'Facturas Recientes',
        viewAll: 'Ver Todo',
        loading: 'Cargando panel...'
      },
      invoices: {
        title: 'Facturas',
        noInvoices: 'No se encontraron facturas',
        emptySubtext: 'Crea tu primera factura para comenzar',
        searchPlaceholder: 'Buscar facturas...',
        status: {
          all: 'Todos los Estados',
          paid: 'Pagado',
          pending: 'Pendiente',
          overdue: 'Vencido',
          draft: 'Borrador'
        },
        loading: 'Cargando facturas...'
      },
      settings: {
        title: 'Configuración',
        companyInfo: 'Información de la Empresa',
        chooseFile: 'Elegir archivo',
        noFileSelected: 'Ningún archivo seleccionado',
        save: 'Guardar',
        signOut: 'Cerrar sesión',
        loading: 'Cargando configuración...'
      },
      general: {
        loading: 'Cargando...',
        error: 'Error',
        success: 'Éxito',
        cancel: 'Cancelar',
        confirm: 'Confirmar',
        update: 'Actualizar',
        by: 'por {{user}}',
        amount: 'Monto',
        viewDetails: 'Ver Detalles',
        noUpdateHistory: 'No hay historial de actualizaciones disponible',
        loadingHistory: 'Cargando historial...'
      }
    }
  },
  fr: {
    translation: {
      dashboard: {
        welcome: 'Bon retour, {{name}} !',
        overview: 'Aperçu de votre activité de facturation',
        totalIncome: 'Revenus Totaux',
        pendingAmount: 'Montant en Attente',
        totalClients: 'Clients Totaux',
        overdueInvoices: 'Factures en Retard',
        quickActions: 'Actions Rapides',
        recentInvoices: 'Factures Récentes',
        viewAll: 'Voir Tout',
        loading: 'Chargement du tableau de bord...'
      },
      invoices: {
        title: 'Factures',
        noInvoices: 'Aucune facture trouvée',
        emptySubtext: 'Créez votre première facture pour commencer',
        searchPlaceholder: 'Rechercher des factures...',
        status: {
          all: 'Tous les Statuts',
          paid: 'Payé',
          pending: 'En attente',
          overdue: 'En retard',
          draft: 'Brouillon'
        },
        loading: 'Chargement des factures...'
      },
      settings: {
        title: 'Paramètres',
        companyInfo: 'Informations sur l’entreprise',
        chooseFile: 'Choisir un fichier',
        noFileSelected: 'Aucun fichier sélectionné',
        save: 'Enregistrer',
        signOut: 'Déconnexion',
        loading: 'Chargement des paramètres...'
      },
      general: {
        loading: 'Chargement...',
        error: 'Erreur',
        success: 'Succès',
        cancel: 'Annuler',
        confirm: 'Confirmer',
        update: 'Mettre à jour',
        by: 'par {{user}}',
        amount: 'Montant',
        viewDetails: 'Voir les détails',
        noUpdateHistory: 'Aucun historique de mise à jour disponible',
        loadingHistory: 'Chargement de l’historique...'
      }
    }
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: Localization.locale.split('-')[0],
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n; 