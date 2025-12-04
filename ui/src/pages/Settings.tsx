import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { Loader2, Download, Database, Upload, Plus, Edit, Trash2, Calculator, CheckCircle, XCircle } from "lucide-react";
import { settingsApi, discountRulesApi, aiConfigApi, DiscountRule, DiscountRuleCreate, AIConfig, AIConfigCreate, AIProviderInfo } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { CurrencyManager } from "@/components/ui/currency-manager";
import { CurrencySelector } from "@/components/ui/currency-selector";
import { SearchStatus } from "@/components/search/SearchStatus";
import { api } from "@/lib/api";
import { getErrorMessage } from '@/lib/api';
import APIClientManagement from "@/components/APIClientManagement/APIClientManagement";
import CookieSettings from "@/components/settings/CookieSettings";
import ExportDestinationsTab from "@/components/settings/ExportDestinationsTab";
import EmailIntegrationSettings from "@/components/settings/EmailIntegrationSettings";
import { getCurrentUser } from "@/utils/auth";
import { useTaxIntegration } from "@/hooks/useTaxIntegration";
import LicenseManagement from "@/pages/LicenseManagement";
import { FeatureGate } from "@/components/FeatureGate";
import { useFeatures } from "@/contexts/FeatureContext";
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";

const Settings = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Get current user and check if admin
  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === 'admin';

  // Feature flags
  const { isFeatureEnabled } = useFeatures();

  // Tax integration status
  const { status: taxIntegrationStatus, isEnabled: taxIntegrationEnabled } = useTaxIntegration();

  // Backend hardcoded English defaults used for detection
  const BACKEND_DEFAULT_NOTES = t('settings.thank_you');
  const BACKEND_DEFAULT_TERMS = t('settings.payment_terms_net30');

  // Discount rules state
  const [discountRules, setDiscountRules] = useState<DiscountRule[]>([]);
  const [loadingDiscountRules, setLoadingDiscountRules] = useState(false);
  const [showDiscountRuleDialog, setShowDiscountRuleDialog] = useState(false);
  const [editingDiscountRule, setEditingDiscountRule] = useState<DiscountRule | null>(null);
  const [newDiscountRule, setNewDiscountRule] = useState<DiscountRuleCreate>({
    name: "",
    min_amount: 0,
    discount_type: "percentage",
    discount_value: 0,
    is_active: true,
    priority: 0,
    currency: "USD",
  });

  const [companyInfo, setCompanyInfo] = useState({
    name: "",
    email: "",
    phone: "",
    address: "",
    tax_id: "",
    logo: "",
  });

  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string>("");
  const [uploadingLogo, setUploadingLogo] = useState(false);

  const [aiAssistantEnabled, setAiAssistantEnabled] = useState(false);

  // AI Configuration state
  const [aiConfigs, setAiConfigs] = useState<AIConfig[]>([]);
  const [loadingAiConfigs, setLoadingAiConfigs] = useState(false);
  const [showAIConfigDialog, setShowAIConfigDialog] = useState(false);
  const [editingAIConfig, setEditingAIConfig] = useState<AIConfig | null>(null);
  const [supportedProviders, setSupportedProviders] = useState<Record<string, AIProviderInfo>>({});
  const [newAIConfig, setNewAIConfig] = useState<AIConfigCreate>({
    provider_name: "openai",
    provider_url: "",
    api_key: "",
    model_name: "gpt-4",
    is_active: true,
    is_default: false,
    ocr_enabled: false,
  });
  const [testingNewConfig, setTestingNewConfig] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean, message: string } | null>(null);

  // Helper function to check if a provider requires an API key
  const providerRequiresApiKey = (providerName: string): boolean => {
    const provider = supportedProviders[providerName];
    return provider ? provider.requires_api_key : true; // Default to requiring API key if unknown
  };

  const [invoiceSettings, setInvoiceSettings] = useState({
    prefix: "INV-",
    next_number: "0001",
    terms: t('settings.payment_terms_net30'),
    notes: t('settings.thank_you'),
    send_copy: true,
    auto_reminders: true,
  });

  const [timezone, setTimezone] = useState("UTC");

  const [taxSettings, setTaxSettings] = useState({
    enabled: taxIntegrationEnabled,
    base_url: "",
    api_key: "",
    timeout: 30,
    retry_attempts: 3,
  });
  const [testingTaxConnection, setTestingTaxConnection] = useState(false);
  const [taxTestResult, setTaxTestResult] = useState<{ success: boolean, message: string } | null>(null);
  const [taxConnectionTested, setTaxConnectionTested] = useState(false);
  const [taxEnabledSwitch, setTaxEnabledSwitch] = useState(taxIntegrationEnabled);

  const [emailSettings, setEmailSettings] = useState({
    provider: "aws_ses",
    from_name: "Your Company",
    from_email: "noreply@yourcompany.com",
    enabled: false,
    // AWS SES
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_region: "us-east-1",
    // Azure Email Services
    azure_connection_string: "",
    // Mailgun
    mailgun_api_key: "",
    mailgun_domain: "",
  });

  const [userProfile, setUserProfile] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('user') || '{}');
    } catch {
      return {};
    }
  });
  const [profileSaving, setProfileSaving] = useState(false);

  // Notification settings state
  const [notificationSettings, setNotificationSettings] = useState({
    user_created: false,
    user_updated: false,
    user_deleted: false,
    user_login: false,
    client_created: true,
    client_updated: false,
    client_deleted: true,
    invoice_created: true,
    invoice_updated: false,
    invoice_deleted: true,
    invoice_sent: true,
    invoice_paid: true,
    invoice_overdue: true,
    payment_created: true,
    payment_updated: false,
    payment_deleted: true,
    // Expense operations
    expense_created: true,
    expense_updated: false,
    expense_deleted: true,
    expense_approved: true,
    expense_rejected: true,
    expense_submitted: true,
    // Inventory operations
    inventory_created: true,
    inventory_updated: false,
    inventory_deleted: true,
    inventory_low_stock: true,
    inventory_out_of_stock: true,
    // Statement operations
    statement_generated: true,
    statement_sent: true,
    statement_overdue: true,
    // Reminder operations
    reminder_created: true,
    reminder_sent: true,
    reminder_overdue: true,
    settings_updated: false,
    notification_email: "",
    daily_summary: false,
    weekly_summary: false,
  });
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const [savingNotifications, setSavingNotifications] = useState(false);

  // Get tab from URL parameters, default to 'cookies' for non-admin users
  const [activeTab, setActiveTab] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const defaultTab = isAdmin ? 'company' : 'cookies';
    return urlParams.get('tab') || defaultTab;
  });

  // Update active tab when URL changes
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab && tab !== activeTab) {
      setActiveTab(tab);
    }
  }, []);

  // Update URL when active tab changes
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const currentTab = urlParams.get('tab');

    if (activeTab !== currentTab) {
      if (activeTab) {
        urlParams.set('tab', activeTab);
      } else {
        urlParams.delete('tab');
      }

      const newUrl = `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`;
      window.history.replaceState({}, '', newUrl);
    }
  }, [activeTab]);

  // Note: Tax settings are initialized from taxIntegrationEnabled in useState above
  // We don't sync continuously to avoid overriding user's manual toggle actions

  // Handle highlighting for AI Assistant toggle
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    const highlight = urlParams.get('highlight');

    console.log('Settings highlight check:', { tab, highlight, activeTab });

    if (tab === 'ai-config' && highlight === 'ai_assistant' && activeTab === 'ai-config') {
      console.log('Attempting to highlight AI Assistant toggle');
      // Wait for component to render and tab to switch, then highlight the AI Assistant toggle
      setTimeout(() => {
        const aiToggle = document.getElementById('ai_assistant');
        console.log('Found AI toggle:', aiToggle);
        if (aiToggle) {
          const toggleContainer = aiToggle.closest('.flex');
          console.log('Found toggle container:', toggleContainer);
          if (toggleContainer) {
            toggleContainer.classList.add('bg-yellow-100', 'dark:bg-yellow-900/30', 'border-2', 'border-yellow-400', 'dark:border-yellow-600', 'rounded-lg', 'p-3', 'transition-all', 'duration-300');
            console.log('Applied highlighting styles');

            // Remove highlighting after 3 seconds
            setTimeout(() => {
              toggleContainer.classList.remove('bg-yellow-100', 'dark:bg-yellow-900/30', 'border-2', 'border-yellow-400', 'dark:border-yellow-600', 'rounded-lg', 'p-3', 'transition-all', 'duration-300');
              console.log('Removed highlighting styles');
            }, 3000);
          }
        }
      }, 1500);
    }
  }, [activeTab]);

  // Fetch settings when component mounts
  useEffect(() => {
    const fetchSettings = async () => {
      setLoading(true);
      try {
        // Only fetch admin settings if user is admin
        if (!isAdmin) {
          setLoading(false);
          return;
        }

        const settings = await settingsApi.getSettings();

        // Update state with fetched settings
        if (settings.company_info) {
          setCompanyInfo({
            name: settings.company_info.name || companyInfo.name,
            email: settings.company_info.email || companyInfo.email,
            phone: settings.company_info.phone || companyInfo.phone,
            address: settings.company_info.address || companyInfo.address,
            tax_id: settings.company_info.tax_id || companyInfo.tax_id,
            logo: settings.company_info.logo || companyInfo.logo,
          });
        }

        // Set AI assistant enabled state
        setAiAssistantEnabled(settings.enable_ai_assistant ?? false);

        // Set timezone
        setTimezone(settings.timezone || "UTC");

        // Update user profile with any settings that might affect it
        const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
        if (currentUser) {
          const updatedUser = { ...currentUser };
          localStorage.setItem('user', JSON.stringify(updatedUser));
          setUserProfile(updatedUser);
        }

        if (settings.invoice_settings) {
          setInvoiceSettings({
            prefix: settings.invoice_settings.prefix || invoiceSettings.prefix,
            next_number: settings.invoice_settings.next_number || invoiceSettings.next_number,
            terms: (settings.invoice_settings.terms && settings.invoice_settings.terms !== BACKEND_DEFAULT_TERMS)
              ? settings.invoice_settings.terms
              : t('settings.payment_terms_net30'),
            notes: (settings.invoice_settings.notes && settings.invoice_settings.notes !== BACKEND_DEFAULT_NOTES)
              ? settings.invoice_settings.notes
              : t('settings.thank_you'),
            send_copy: settings.invoice_settings.send_copy ?? invoiceSettings.send_copy,
            auto_reminders: settings.invoice_settings.auto_reminders ?? invoiceSettings.auto_reminders,
          });
        }

        // Try to fetch email settings
        try {
          type EmailConfig = {
            provider: string;
            from_name: string;
            from_email: string;
            enabled: boolean;
            aws_access_key_id?: string;
            aws_secret_access_key?: string;
            aws_region?: string;
            azure_connection_string?: string;
            mailgun_api_key?: string;
            mailgun_domain?: string;
          };
          const emailData = await api.get<EmailConfig>('/email/config');
          setEmailSettings({
            provider: emailData.provider || emailSettings.provider,
            from_name: emailData.from_name || emailSettings.from_name,
            from_email: emailData.from_email || emailSettings.from_email,
            enabled: emailData.enabled ?? emailSettings.enabled,
            aws_access_key_id: emailData.aws_access_key_id || emailSettings.aws_access_key_id,
            aws_secret_access_key: emailData.aws_secret_access_key || emailSettings.aws_secret_access_key,
            aws_region: emailData.aws_region || emailSettings.aws_region,
            azure_connection_string: emailData.azure_connection_string || emailSettings.azure_connection_string,
            mailgun_api_key: emailData.mailgun_api_key || emailSettings.mailgun_api_key,
            mailgun_domain: emailData.mailgun_domain || emailSettings.mailgun_domain,
          });
        } catch (error) {
          console.log("Email settings not configured yet");
        }

        // Fetch discount rules
        try {
          setLoadingDiscountRules(true);
          const rules = await discountRulesApi.getDiscountRules();
          setDiscountRules(rules);
        } catch (error) {
          console.error("Failed to fetch discount rules:", error);
          toast.error(t('settings.failed_to_load_discount_rules'));
        } finally {
          setLoadingDiscountRules(false);
        }

        // Fetch AI configurations
        try {
          setLoadingAiConfigs(true);
          const configs = await aiConfigApi.getAIConfigs();
          setAiConfigs(configs);
        } catch (error) {
          console.error("Failed to fetch AI configs:", error);
          toast.error(t('settings.failed_to_load_ai_configurations'));
        } finally {
          setLoadingAiConfigs(false);
        }

        // Fetch supported providers
        try {
          const response = await aiConfigApi.getSupportedProviders();
          setSupportedProviders(response.providers);
        } catch (error) {
          console.error("Failed to fetch supported providers:", error);
        }

        // Fetch notification settings
        try {
          setLoadingNotifications(true);
          type NotificationSettingsResponse = {
            user_created?: boolean;
            user_updated?: boolean;
            user_deleted?: boolean;
            user_login?: boolean;
            client_created?: boolean;
            client_updated?: boolean;
            client_deleted?: boolean;
            invoice_created?: boolean;
            invoice_updated?: boolean;
            invoice_deleted?: boolean;
            invoice_sent?: boolean;
            invoice_paid?: boolean;
            invoice_overdue?: boolean;
            payment_created?: boolean;
            payment_updated?: boolean;
            payment_deleted?: boolean;
            // Expense operations
            expense_created?: boolean;
            expense_updated?: boolean;
            expense_deleted?: boolean;
            expense_approved?: boolean;
            expense_rejected?: boolean;
            expense_submitted?: boolean;
            // Inventory operations
            inventory_created?: boolean;
            inventory_updated?: boolean;
            inventory_deleted?: boolean;
            inventory_low_stock?: boolean;
            inventory_out_of_stock?: boolean;
            // Statement operations
            statement_generated?: boolean;
            statement_sent?: boolean;
            statement_overdue?: boolean;
            // Reminder operations
            reminder_created?: boolean;
            reminder_sent?: boolean;
            reminder_overdue?: boolean;
            settings_updated?: boolean;
            notification_email?: string;
            daily_summary?: boolean;
            weekly_summary?: boolean;
          };
          const notifData = await api.get<NotificationSettingsResponse>('/notifications/settings');
          setNotificationSettings({
            user_created: notifData.user_created ?? false,
            user_updated: notifData.user_updated ?? false,
            user_deleted: notifData.user_deleted ?? false,
            user_login: notifData.user_login ?? false,
            client_created: notifData.client_created ?? true,
            client_updated: notifData.client_updated ?? false,
            client_deleted: notifData.client_deleted ?? true,
            invoice_created: notifData.invoice_created ?? true,
            invoice_updated: notifData.invoice_updated ?? false,
            invoice_deleted: notifData.invoice_deleted ?? true,
            invoice_sent: notifData.invoice_sent ?? true,
            invoice_paid: notifData.invoice_paid ?? true,
            invoice_overdue: notifData.invoice_overdue ?? true,
            payment_created: notifData.payment_created ?? true,
            payment_updated: notifData.payment_updated ?? false,
            payment_deleted: notifData.payment_deleted ?? true,
            // Expense operations
            expense_created: notifData.expense_created ?? true,
            expense_updated: notifData.expense_updated ?? false,
            expense_deleted: notifData.expense_deleted ?? true,
            expense_approved: notifData.expense_approved ?? true,
            expense_rejected: notifData.expense_rejected ?? true,
            expense_submitted: notifData.expense_submitted ?? true,
            // Inventory operations
            inventory_created: notifData.inventory_created ?? true,
            inventory_updated: notifData.inventory_updated ?? false,
            inventory_deleted: notifData.inventory_deleted ?? true,
            inventory_low_stock: notifData.inventory_low_stock ?? true,
            inventory_out_of_stock: notifData.inventory_out_of_stock ?? true,
            // Statement operations
            statement_generated: notifData.statement_generated ?? true,
            statement_sent: notifData.statement_sent ?? true,
            statement_overdue: notifData.statement_overdue ?? true,
            // Reminder operations
            reminder_created: notifData.reminder_created ?? true,
            reminder_sent: notifData.reminder_sent ?? true,
            reminder_overdue: notifData.reminder_overdue ?? true,
            settings_updated: notifData.settings_updated ?? false,
            notification_email: notifData.notification_email ?? "",
            daily_summary: notifData.daily_summary ?? false,
            weekly_summary: notifData.weekly_summary ?? false,
          });
        } catch (error) {
          console.error("Failed to fetch notification settings:", error);
        } finally {
          setLoadingNotifications(false);
        }
      } catch (error) {
        console.error("Failed to fetch settings:", error);
        toast.error(t('settings.failed_to_load_settings'));
      } finally {
        setLoading(false);
      }
    };

    // Only fetch admin settings if user is admin
    if (isAdmin) {
      fetchSettings();
    } else {
      // For non-admin users, just set loading to false
      setLoading(false);
    }
  }, [isAdmin]);

  const handleCompanyChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name === 'email') return;
    setCompanyInfo((prev) => ({ ...prev, [name]: value }));
  };

  const handleInvoiceChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setInvoiceSettings((prev) => ({ ...prev, [name]: value }));
  };

  const handleToggleChange = (name: string, checked: boolean) => {
    setInvoiceSettings((prev) => ({ ...prev, [name]: checked }));
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setEmailSettings((prev) => ({ ...prev, [name]: value }));
  };

  const handleEmailProviderChange = (provider: string) => {
    setEmailSettings((prev) => ({ ...prev, provider }));
  };

  const handleEmailToggleChange = (name: string, checked: boolean) => {
    setEmailSettings((prev) => ({ ...prev, [name]: checked }));
  };

  const testEmailConfiguration = async () => {
    // Only allow admin to test email configuration
    if (!isAdmin) return;

    const testEmail = prompt("Enter email address to send test email to:");
    if (!testEmail) return;

    try {
      // Send current email settings along with the test request
      const result = await api.post<{ success: boolean; message: string }>('/email/test', {
        test_email: testEmail,
        config: emailSettings
      });
      if (result.success) {
        toast.success(t('settings.test_email_sent_successfully'));
      } else {
        toast.error(t('settings.failed_to_send_test_email', { message: result.message }));
      }
    } catch (error) {
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleSave = async () => {
    // Only allow admin to save settings
    if (!isAdmin) return;

    setSaving(true);
    try {
      // Upload logo first if there's a new file
      if (logoFile) {
        await uploadLogo();
      }

      // Format data for API
      const settingsData = {
        company_info: {
          name: companyInfo.name,
          email: companyInfo.email,
          phone: companyInfo.phone,
          address: companyInfo.address,
          tax_id: companyInfo.tax_id,
          logo: companyInfo.logo
        },
        invoice_settings: {
          prefix: invoiceSettings.prefix,
          next_number: invoiceSettings.next_number,
          terms: invoiceSettings.terms,
          notes: invoiceSettings.notes,
          send_copy: invoiceSettings.send_copy,
          auto_reminders: invoiceSettings.auto_reminders
        },
        enable_ai_assistant: aiAssistantEnabled,
        timezone: timezone
      };

      // console.log('Settings: Saving AI Assistant state', {
      //   currentState: aiAssistantEnabled,
      //   settingsData: settingsData.enable_ai_assistant
      // });

      // Send to API
      await settingsApi.updateSettings(settingsData);

      console.log('Settings: API update successful, invalidating cache');

      // Invalidate settings cache to refresh AI assistant immediately
      await queryClient.invalidateQueries({ queryKey: ['settings'] });

      // Force refetch of settings to ensure AI Assistant updates immediately
      await queryClient.refetchQueries({ queryKey: ['settings'] });

      // Also invalidate any settings queries with additional keys
      await queryClient.invalidateQueries({ queryKey: ['settings'], exact: false });

      // Trigger events to notify sidebar of settings update
      localStorage.setItem('settings_updated', Date.now().toString());
      window.dispatchEvent(new StorageEvent('storage', { key: 'settings_updated' }));
      window.dispatchEvent(new CustomEvent('settings-updated'));

      console.log('Settings: Events dispatched for sidebar update');
      console.log('Settings: Cache invalidated and refetched');

      // Handle AI assistant state changes
      if (aiAssistantEnabled) {
        // AI Assistant was enabled
        await queryClient.invalidateQueries({ queryKey: ['ai-configs'] });
        toast.success(t('settings.ai_assistant_enabled'));
      } else {
        // AI Assistant was disabled - more aggressive cache clearing
        console.log('Settings: AI Assistant disabled, clearing all related cache');
        await queryClient.invalidateQueries({ queryKey: ['ai-configs'] });
        await queryClient.removeQueries({ queryKey: ['ai-configs'] }); // Remove cached data completely
        await queryClient.resetQueries({ queryKey: ['settings'] }); // Reset settings cache
        toast.success(t('settings.ai_assistant_disabled'));
      }

      toast.success(t('settings.settings_saved_successfully'));

      // Save email settings separately
      try {
        await api.put('/email/config', emailSettings);
      } catch (error) {
        toast.error(getErrorMessage(error, t));
      }

    } catch (error) {
      console.error("Failed to save settings:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSaving(false);
    }
  };

  const handleTestTaxConnection = async () => {
    setTestingTaxConnection(true);
    setTaxTestResult(null);

    try {
      // Call the real API endpoint to test the tax service connection
      const result = await api.post<{ success: boolean; message: string }>('/tax-integration/test-connection');

      if (result.success) {
        console.log('Tax connection test PASSED - setting taxConnectionTested to true');
        setTaxTestResult({
          success: true,
          message: result.message || "Tax service connection successful!"
        });
        setTaxConnectionTested(true);
        toast.success("Tax service connection test passed!");
      } else {
        setTaxTestResult({
          success: false,
          message: result.message || "Tax service connection failed."
        });
        setTaxConnectionTested(false);
        toast.error("Tax service connection test failed!");
      }
    } catch (error) {
      console.error("Error testing tax connection:", error);
      setTaxTestResult({
        success: false,
        message: "Connection test failed due to network error or invalid configuration."
      });
      setTaxConnectionTested(false);
      toast.error("Tax service connection test failed!");
    } finally {
      setTestingTaxConnection(false);
    }
  };

  const handleSaveTaxSettings = async () => {
    // Only allow admin to save tax settings
    if (!isAdmin) return;

    // Validate that if enabled=true, connection must have been tested OR already enabled
    if (taxEnabledSwitch && !taxConnectionTested && !taxIntegrationEnabled) {
      toast.error("Tax service must be tested and connection verified before enabling.");
      return;
    }

    setSaving(true);
    try {
      // Call the tax integration settings API
      await api.put('/tax-integration/settings', taxSettings);

      toast.success("Tax settings saved successfully!");

      // Only reset test status if tax integration is being disabled
      // If enabled, keep the tested state so user can toggle on/off without re-testing
      if (!taxSettings.enabled) {
        setTaxConnectionTested(false);
        setTaxTestResult(null);
      }
      setTaxEnabledSwitch(taxSettings.enabled);

      // Refetch tax integration status to update the UI
      queryClient.invalidateQueries({ queryKey: ['tax-integration-status'] });
    } catch (error) {
      console.error("Failed to save tax settings:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSaving(false);
    }
  };

  const handleExportData = async () => {
    // Only allow admin to export data
    if (!isAdmin) return;

    setExporting(true);
    try {
      await settingsApi.exportData();
      toast.success(t('settings.data_exported_successfully'));
    } catch (error) {
      console.error("Failed to export data:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setExporting(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.sqlite')) {
        toast.error(t('settings.please_select_sqlite_file'));
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleImportData = async () => {
    // Only allow admin to import data
    if (!isAdmin) return;

    if (!selectedFile) {
      toast.error(t('settings.please_select_file_to_import'));
      return;
    }

    setImporting(true);
    try {
      const result = await settingsApi.importData(selectedFile);
      toast.success(t('settings.data_imported_successfully', { imported_counts: JSON.stringify(result.imported_counts) }));
      setSelectedFile(null);
      // Reset the file input
      const fileInput = document.getElementById('import-file') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    } catch (error) {
      console.error("Failed to import data:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setImporting(false);
    }
  };

  // Discount rules management functions
  const handleCreateDiscountRule = async () => {
    // Only allow admin to create discount rules
    if (!isAdmin) return;

    try {
      const rule = await discountRulesApi.createDiscountRule({ ...newDiscountRule, currency: newDiscountRule.currency || "USD" });
      setDiscountRules([...discountRules, rule]);
      setShowDiscountRuleDialog(false);
      setNewDiscountRule({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
      });
      toast.success(t('settings.discount_rule_created'));
    } catch (error) {
      console.error("Failed to create discount rule:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleUpdateDiscountRule = async () => {
    // Only allow admin to update discount rules
    if (!isAdmin) return;

    if (!editingDiscountRule) return;

    try {
      await discountRulesApi.updateDiscountRule(editingDiscountRule.id, {
        ...newDiscountRule,
        currency: newDiscountRule.currency || "USD",
      });
      // Re-fetch the full list of discount rules from the backend
      const rules = await discountRulesApi.getDiscountRules();
      setDiscountRules(rules);
      setShowDiscountRuleDialog(false);
      setEditingDiscountRule(null);
      setNewDiscountRule({
        name: "",
        min_amount: 0,
        discount_type: "percentage",
        discount_value: 0,
        is_active: true,
        priority: 0,
        currency: "USD",
      });
      toast.success(t('settings.discount_rule_updated'));
    } catch (error) {
      console.error("Failed to update discount rule:", error);
      toast.error(t('settings.failed_to_update_discount_rule'));
    }
  };

  const handleDeleteDiscountRule = async (id: number) => {
    // Only allow admin to delete discount rules
    if (!isAdmin) return;

    if (!confirm(t('settings.confirm_delete_discount_rule'))) return;

    try {
      await discountRulesApi.deleteDiscountRule(id);
      setDiscountRules((discountRules || []).filter(rule => rule.id !== id));
      toast.success(t('settings.discount_rule_deleted'));
    } catch (error) {
      console.error("Failed to delete discount rule:", error);
      toast.error(t('settings.failed_to_delete_discount_rule'));
    }
  };

  const openEditDialog = (rule: DiscountRule) => {
    setEditingDiscountRule(rule);
    setNewDiscountRule({
      name: rule.name,
      min_amount: rule.min_amount,
      discount_type: rule.discount_type,
      discount_value: rule.discount_value,
      is_active: rule.is_active,
      priority: rule.priority,
      currency: rule.currency || "USD",
    });
    setShowDiscountRuleDialog(true);
  };

  const openCreateDialog = () => {
    setEditingDiscountRule(null);
    setNewDiscountRule({
      name: "",
      min_amount: 0,
      discount_type: "percentage",
      discount_value: 0,
      is_active: true,
      priority: 0,
      currency: "USD",
    });
    setShowDiscountRuleDialog(true);
  };

  // AI Configuration handlers
  const handleAIConfigChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setNewAIConfig((prev) => ({ ...prev, [name]: value }));
  };

  const handleAIConfigToggleChange = (name: string, checked: boolean) => {
    setNewAIConfig((prev) => ({ ...prev, [name]: checked }));
  };

  // Handle AI Assistant toggle with immediate save
  const handleAIAssistantToggle = async (checked: boolean) => {
    // Only allow admin to toggle AI assistant
    if (!isAdmin) return;

    console.log('AI Assistant Toggle:', { from: aiAssistantEnabled, to: checked });

    // Update local state immediately for UI responsiveness
    setAiAssistantEnabled(checked);

    try {
      // Prepare settings data for API
      const settingsData = {
        company_info: {
          name: companyInfo.name,
          email: companyInfo.email,
          phone: companyInfo.phone,
          address: companyInfo.address,
          tax_id: companyInfo.tax_id,
          logo: companyInfo.logo
        },
        invoice_settings: {
          prefix: invoiceSettings.prefix,
          next_number: invoiceSettings.next_number,
          terms: invoiceSettings.terms,
          notes: invoiceSettings.notes,
          send_copy: invoiceSettings.send_copy,
          auto_reminders: invoiceSettings.auto_reminders
        },
        enable_ai_assistant: checked // Use the new toggle value
      };

      console.log('AI Assistant: Saving toggle state to API...', { enable_ai_assistant: checked });

      // Save to API
      await settingsApi.updateSettings(settingsData);

      console.log('AI Assistant: Toggle saved successfully, updating cache...');

      // Force immediate cache update
      await queryClient.resetQueries({ queryKey: ['settings'] });
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
      await queryClient.refetchQueries({ queryKey: ['settings'] });

      // Force re-render of all components using settings
      await queryClient.invalidateQueries();

      // Dispatch custom event to notify AI assistant component
      window.dispatchEvent(new CustomEvent('ai-assistant-toggle', { detail: { enabled: checked } }));
      window.dispatchEvent(new StorageEvent('storage', { key: 'ai_assistant_enabled', newValue: checked.toString() }));

      if (checked) {
        // AI Assistant was enabled
        await queryClient.invalidateQueries({ queryKey: ['ai-configs'] });
        toast.success(t('settings.ai_assistant_enabled'));
      } else {
        // AI Assistant was disabled - aggressive cache clearing
        console.log('AI Assistant: Disabled, clearing all related cache');
        await queryClient.invalidateQueries({ queryKey: ['ai-configs'] });
        await queryClient.removeQueries({ queryKey: ['ai-configs'] });
        await queryClient.resetQueries({ queryKey: ['settings'] });
        toast.success(t('settings.ai_assistant_disabled'));
      }

    } catch (error) {
      console.error('Failed to save AI Assistant toggle:', error);
      // Revert local state on error
      setAiAssistantEnabled(!checked);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleCreateAIConfig = async () => {
    // Only allow admin to create AI configs
    if (!isAdmin) return;

    try {
      await aiConfigApi.createAIConfig(newAIConfig);
      toast.success(t('settings.ai_config_created'));
      setShowAIConfigDialog(false);
      // Refresh AI configs
      const configs = await aiConfigApi.getAIConfigs();
      setAiConfigs(configs);
    } catch (error) {
      console.error("Failed to create AI config:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleUpdateAIConfig = async () => {
    // Only allow admin to update AI configs
    if (!isAdmin) return;

    if (!editingAIConfig) return;

    try {
      await aiConfigApi.updateAIConfig(editingAIConfig.id, newAIConfig);
      toast.success(t('settings.ai_config_updated'));
      setShowAIConfigDialog(false);
      // Refresh AI configs
      const configs = await aiConfigApi.getAIConfigs();
      setAiConfigs(configs);
    } catch (error) {
      console.error("Failed to update AI config:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleDeleteAIConfig = async (id: number) => {
    // Only allow admin to delete AI configs
    if (!isAdmin) return;

    if (!confirm(t('settings.confirm_delete_ai_config'))) return;

    try {
      await aiConfigApi.deleteAIConfig(id);
      toast.success(t('settings.ai_config_deleted'));
      // Refresh AI configs
      const configs = await aiConfigApi.getAIConfigs();
      setAiConfigs(configs);
    } catch (error) {
      console.error("Failed to delete AI config:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleTestAIConfig = async (id: number) => {
    // Only allow admin to test AI configs
    if (!isAdmin) return;

    try {
      console.log(`Testing AI config ${id}...`);
      const result = await aiConfigApi.testAIConfig(id);
      console.log('Test AI config result:', result);

      if (result.success) {
        toast.success(t('settings.ai_config_test_successful'));
        // Refresh AI configs to show updated tested status
        const configs = await aiConfigApi.getAIConfigs();
        setAiConfigs(configs);
      } else {
        console.log('Test failed with message:', result.message);
        toast.error(result.message || t('settings.ai_config_test_failed'));
      }
    } catch (error) {
      console.error("Failed to test AI config:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const handleTestNewAIConfig = async () => {
    // Only allow admin to test new AI configs
    if (!isAdmin) return;

    setTestingNewConfig(true);
    setTestResult(null);
    try {
      // Create a temporary config for testing
      const tempConfig = await aiConfigApi.createAIConfig(newAIConfig);
      const result = await aiConfigApi.testAIConfig(tempConfig.id);

      if (result.success) {
        setTestResult({ success: true, message: result.message || t('settings.ai_config_test_successful') });
        // Update the newAIConfig to mark it as tested
        setNewAIConfig(prev => ({ ...prev, tested: true }));

        // Check if this is the first tested provider and set as default
        const testedConfigs = aiConfigs.filter(c => c.tested);
        if (testedConfigs.length === 0) {
          setNewAIConfig(prev => ({ ...prev, tested: true, is_default: true }));
          setTestResult({ success: true, message: result.message + ' and set as default provider' });
        }
      } else {
        setTestResult({ success: false, message: result.message || t('settings.ai_config_test_failed') });
      }

      // Always delete the temporary config after testing
      await aiConfigApi.deleteAIConfig(tempConfig.id);

      // Refresh the AI configs list to reflect any changes
      const configs = await aiConfigApi.getAIConfigs();
      setAiConfigs(configs);

    } catch (error) {
      console.error("Failed to test new AI config:", error);
      setTestResult({ success: false, message: getErrorMessage(error, t) });
    } finally {
      setTestingNewConfig(false);
    }
  };

  const handleMarkAsTested = async (id: number) => {
    // Only allow admin to mark AI configs as tested
    if (!isAdmin) return;

    try {
      await aiConfigApi.markAsTested(id);
      toast.success(t('settings.ai_config_marked_as_tested'));
      // Refresh AI configs to show updated tested status
      const configs = await aiConfigApi.getAIConfigs();
      setAiConfigs(configs);
    } catch (error) {
      console.error("Failed to mark AI config as tested:", error);
      toast.error(getErrorMessage(error, t));
    }
  };

  const openEditAIConfigDialog = (config: AIConfig) => {
    setEditingAIConfig(config);
    setNewAIConfig({
      provider_name: config.provider_name,
      provider_url: config.provider_url || "",
      api_key: config.api_key || "",
      model_name: config.model_name,
      is_active: config.is_active,
      is_default: config.is_default,
      tested: config.tested,
      ocr_enabled: config.ocr_enabled || false,
    });
    setShowAIConfigDialog(true);
  };

  const openCreateAIConfigDialog = () => {
    setEditingAIConfig(null);
    setNewAIConfig({
      provider_name: "openai",
      provider_url: "",
      api_key: "",
      model_name: "gpt-4",
      is_active: true,
      is_default: false,
      tested: false,
      ocr_enabled: false,
    });
    setTestResult(null);
    setShowAIConfigDialog(true);
  };

  const handleProviderChange = (provider: string) => {
    // Get default model from supported providers if available
    const providerInfo = supportedProviders[provider];
    const defaultModel = providerInfo?.default_model ||
      (provider === "openai" ? "gpt-4" :
        provider === "openrouter" ? "openai/gpt-4" :
          provider === "ollama" ? "llama3.2-vision:11b" :
            provider === "anthropic" ? "claude-3-sonnet" :
              provider === "google" ? "gemini-pro" :
                "model-name");

    // Set default provider URLs
    const defaultProviderUrl =
      provider === "openrouter" ? "https://openrouter.ai/api/v1" :
        provider === "anthropic" ? "https://api.anthropic.com" :
          provider === "google" ? "https://generativelanguage.googleapis.com" :
            provider === "ollama" ? "http://localhost:11434" :
              provider === "openai" ? "" : // OpenAI uses default endpoint
                "";

    setNewAIConfig(prev => ({
      ...prev,
      provider_name: provider,
      model_name: defaultModel,
      provider_url: defaultProviderUrl
    }));
  };

  const handleLogoFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setLogoFile(file);
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setLogoPreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const uploadLogo = async () => {
    if (!logoFile) return;

    try {
      const formData = new FormData();
      formData.append('file', logoFile);

      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'}/settings/upload-logo`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload logo');
      }

      const result = await response.json();
      const logoUrl = result.url;

      // Update company info with the new logo URL
      setCompanyInfo(prev => ({ ...prev, logo: logoUrl }));

      // Clear the file input and preview
      setLogoFile(null);
      setLogoPreview("");

    } catch (error) {
      console.error('Failed to upload logo:', error);
      throw error; // Re-throw to be handled by handleSave
    }
  };

  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setUserProfile((prev: any) => ({ ...prev, [name]: value }));
  };

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const updated = await api.put('/auth/me', {
        first_name: userProfile.first_name,
        last_name: userProfile.last_name,
        show_analytics: userProfile.show_analytics ?? true,
      });
      // Update localStorage and state
      localStorage.setItem('user', JSON.stringify(updated));
      setUserProfile(updated);
      toast.success(t('settings.profile_updated_successfully'));
      // Optionally, trigger a storage event for other tabs/components
      window.dispatchEvent(new StorageEvent('storage', { key: 'user' }));
    } catch (error: any) {
      toast.error(getErrorMessage(error, t));
    } finally {
      setProfileSaving(false);
    }
  };

  // Notification settings handlers
  const handleNotificationToggle = (setting: string, checked: boolean) => {
    setNotificationSettings(prev => ({ ...prev, [setting]: checked }));
  };

  const handleNotificationEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNotificationSettings(prev => ({ ...prev, notification_email: e.target.value }));
  };

  const handleSaveNotifications = async () => {
    // Only allow admin to save notification settings
    if (!isAdmin) return;

    setSavingNotifications(true);
    try {
      const response = await api.put('/notifications/settings', notificationSettings);
      toast.success(t('settings.notification_settings_saved_successfully'));
    } catch (error) {
      console.error('Failed to save notification settings:', error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleTestNotification = async () => {
    // Only allow admin to test notifications
    if (!isAdmin) return;

    try {
      await api.post('/notifications/test');
      toast.success(t('settings.test_notification_sent_successfully'));
    } catch (error) {
      console.error('Failed to send test notification:', error);
      toast.error(getErrorMessage(error, t));
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('settings.loading_settings')}</p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={isAdmin ? t('settings.title') : t('settings.preferences_title', 'Preferences')}
          description={isAdmin ? t('settings.description') : t('settings.preferences_description', 'Manage your personal preferences and privacy settings.')}
        />

        <ContentSection className="w-full">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full tabs-professional">
            <TabsList className="flex w-full flex-wrap gap-2 h-auto justify-start max-w-full overflow-x-auto">
              {isAdmin && (
                <>
                  <TabsTrigger value="company" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.company')}</TabsTrigger>
                  <TabsTrigger value="invoices" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.invoices')}</TabsTrigger>
                  <TabsTrigger value="currencies" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.currencies')}</TabsTrigger>
                  <TabsTrigger value="discount-rules" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.discount_rules')}</TabsTrigger>
                  <TabsTrigger value="ai-config" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.ai_config')}</TabsTrigger>
                  <TabsTrigger value="api-keys" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.api_keys')}</TabsTrigger>
                  <TabsTrigger value="search" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.search')}</TabsTrigger>
                  <TabsTrigger value="email-notifications" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.email_notifications')}</TabsTrigger>
                  <TabsTrigger value="email-integration" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('emailIntegration.title')}</TabsTrigger>
                  {isFeatureEnabled('tax_integration') && (
                    <TabsTrigger value="tax-integration" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.tax_integration')}</TabsTrigger>
                  )}
                  {isFeatureEnabled('cloud_storage') && (
                    <TabsTrigger value="export-destinations" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.export_destinations')}</TabsTrigger>
                  )}
                  <TabsTrigger value="license" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('license.tabTitle')}</TabsTrigger>
                </>
              )}
              <TabsTrigger value="cookies" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.cookies')}</TabsTrigger>
              {isAdmin && (
                <TabsTrigger value="export" className="text-xs md:text-sm min-w-0 flex-shrink-0">{t('settings.tabs.export')}</TabsTrigger>
              )}
            </TabsList>

            {isAdmin && (
              <TabsContent value="company" className="mt-6">
                <ProfessionalCard className="mb-6">
                  <CardHeader>
                    <CardTitle>{t('settings.user_profile')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="first_name">{t('settings.first_name')}</Label>
                        <Input
                          id="first_name"
                          name="first_name"
                          value={userProfile.first_name || ''}
                          onChange={handleProfileChange}
                          autoComplete="given-name"
                        />
                      </div>
                      <div>
                        <Label htmlFor="last_name">{t('settings.last_name')}</Label>
                        <Input
                          id="last_name"
                          name="last_name"
                          value={userProfile.last_name || ''}
                          onChange={handleProfileChange}
                          autoComplete="family-name"
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-4">
                      <div className="space-y-0.5">
                        <Label htmlFor="show_analytics">Show Analytics Menu</Label>
                        <p className="text-sm text-muted-foreground">Show or hide the analytics menu in the sidebar</p>
                      </div>
                      <Switch
                        id="show_analytics"
                        checked={userProfile.show_analytics ?? true}
                        onCheckedChange={(checked) => setUserProfile((prev: any) => ({ ...prev, show_analytics: checked }))}
                      />
                    </div>
                    <div className="flex justify-end mt-4">
                      <Button onClick={handleProfileSave} disabled={profileSaving}>
                        {profileSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        {t('settings.save_profile')}
                      </Button>
                    </div>
                  </CardContent>
                </ProfessionalCard>
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>{t('settings.company_info')}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="name">{t('settings.company_name')}</Label>
                        <Input
                          id="name"
                          name="name"
                          value={companyInfo.name}
                          onChange={handleCompanyChange}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="tax_id">{t('settings.tax_id')}</Label>
                        <Input
                          id="tax_id"
                          name="tax_id"
                          value={companyInfo.tax_id}
                          onChange={handleCompanyChange}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="email">{t('settings.company_email')}</Label>
                        <Input
                          id="email"
                          name="email"
                          type="email"
                          value={companyInfo.email}
                          onChange={handleCompanyChange}
                          disabled
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="phone">{t('settings.company_phone')}</Label>
                        <Input
                          id="phone"
                          name="phone"
                          value={companyInfo.phone}
                          onChange={handleCompanyChange}
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="address">{t('settings.company_address')}</Label>
                      <Textarea
                        id="address"
                        name="address"
                        rows={3}
                        value={companyInfo.address}
                        onChange={handleCompanyChange}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="timezone">Timezone</Label>
                      <Select value={timezone} onValueChange={setTimezone}>
                        <SelectTrigger id="timezone">
                          <SelectValue placeholder="Select timezone" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="UTC">UTC (Coordinated Universal Time)</SelectItem>
                          <SelectItem value="America/New_York">Eastern Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Chicago">Central Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Denver">Mountain Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Los_Angeles">Pacific Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Phoenix">Arizona</SelectItem>
                          <SelectItem value="America/Anchorage">Alaska</SelectItem>
                          <SelectItem value="Pacific/Honolulu">Hawaii</SelectItem>
                          <SelectItem value="Europe/London">London</SelectItem>
                          <SelectItem value="Europe/Paris">Paris</SelectItem>
                          <SelectItem value="Europe/Berlin">Berlin</SelectItem>
                          <SelectItem value="Europe/Rome">Rome</SelectItem>
                          <SelectItem value="Europe/Madrid">Madrid</SelectItem>
                          <SelectItem value="Europe/Amsterdam">Amsterdam</SelectItem>
                          <SelectItem value="Europe/Stockholm">Stockholm</SelectItem>
                          <SelectItem value="Europe/Zurich">Zurich</SelectItem>
                          <SelectItem value="Asia/Tokyo">Tokyo</SelectItem>
                          <SelectItem value="Asia/Shanghai">Shanghai</SelectItem>
                          <SelectItem value="Asia/Hong_Kong">Hong Kong</SelectItem>
                          <SelectItem value="Asia/Singapore">Singapore</SelectItem>
                          <SelectItem value="Asia/Dubai">Dubai</SelectItem>
                          <SelectItem value="Asia/Kolkata">Mumbai, Kolkata, New Delhi</SelectItem>
                          <SelectItem value="Asia/Bangkok">Bangkok</SelectItem>
                          <SelectItem value="Australia/Sydney">Sydney</SelectItem>
                          <SelectItem value="Australia/Melbourne">Melbourne</SelectItem>
                          <SelectItem value="Australia/Brisbane">Brisbane</SelectItem>
                          <SelectItem value="Australia/Perth">Perth</SelectItem>
                          <SelectItem value="Pacific/Auckland">Auckland</SelectItem>
                          <SelectItem value="America/Toronto">Toronto</SelectItem>
                          <SelectItem value="America/Vancouver">Vancouver</SelectItem>
                          <SelectItem value="America/Mexico_City">Mexico City</SelectItem>
                          <SelectItem value="America/Sao_Paulo">Sao Paulo</SelectItem>
                          <SelectItem value="America/Buenos_Aires">Buenos Aires</SelectItem>
                          <SelectItem value="Africa/Johannesburg">Johannesburg</SelectItem>
                          <SelectItem value="Africa/Cairo">Cairo</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-sm text-muted-foreground">Select your organization's timezone for date and time display</p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="logo">{t('settings.company_logo')}</Label>
                      <div className="space-y-4">
                        {/* Custom File Picker */}
                        <div className="flex items-center space-x-4">
                          <input
                            id="logo-upload"
                            name="logo"
                            type="file"
                            accept="image/*"
                            style={{ display: 'none' }}
                            onChange={handleLogoFileChange}
                            disabled={uploadingLogo}
                          />
                          <Button
                            type="button"
                            onClick={() => document.getElementById('logo-upload')?.click()}
                            disabled={uploadingLogo}
                            size="sm"
                          >
                            {t('settings.choose_file')}
                          </Button>
                          <span className="text-sm text-muted-foreground">
                            {logoFile ? logoFile.name : t('settings.no_file_selected')}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{t('settings.recommended_size')}</p>

                        {/* Logo Preview */}
                        {(logoPreview || companyInfo.logo) && (
                          <div className="space-y-2">
                            <Label>{t('settings.logo_preview')}</Label>
                            <div className="flex items-center space-x-4">
                              <img
                                src={logoPreview || `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${companyInfo.logo}`}
                                alt="Company Logo"
                                className="w-16 h-16 object-contain border rounded"
                                onError={(e) => {
                                  console.error('Failed to load logo image:', e);
                                  e.currentTarget.style.display = 'none';
                                }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <Button onClick={handleSave} disabled={saving}>
                        {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {saving ? t('settings.saving') : t('settings.save_changes')}
                      </Button>
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="invoices" className="mt-6">
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>{t('settings.invoice_settings')}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="prefix">{t('settings.invoice_prefix')}</Label>
                        <Input
                          id="prefix"
                          name="prefix"
                          value={invoiceSettings.prefix}
                          onChange={handleInvoiceChange}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="next_number">{t('settings.next_invoice_number')}</Label>
                        <Input
                          id="next_number"
                          name="next_number"
                          value={invoiceSettings.next_number}
                          onChange={handleInvoiceChange}
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="terms">{t('settings.default_terms')}</Label>
                      <Textarea
                        id="terms"
                        name="terms"
                        rows={4}
                        value={invoiceSettings.terms}
                        onChange={handleInvoiceChange}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="notes">{t('settings.default_notes')}</Label>
                      <Textarea
                        id="notes"
                        name="notes"
                        rows={2}
                        value={invoiceSettings.notes}
                        onChange={handleInvoiceChange}
                      />
                    </div>

                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="send_copy">{t('settings.send_copy')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.send_copy_description')}</p>
                        </div>
                        <Switch
                          id="send_copy"
                          checked={invoiceSettings.send_copy}
                          onCheckedChange={(checked) => handleToggleChange('send_copy', checked)}
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="auto_reminders">{t('settings.auto_reminders')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.auto_reminders_description')}</p>
                        </div>
                        <Switch
                          id="auto_reminders"
                          checked={invoiceSettings.auto_reminders}
                          onCheckedChange={(checked) => handleToggleChange('auto_reminders', checked)}
                        />
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <Button onClick={handleSave} disabled={saving}>
                        {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {saving ? t('settings.saving') : t('settings.save_changes')}
                      </Button>
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="currencies" className="mt-6">
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>{t('settings.currency_management')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CurrencyManager />
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="discount-rules" className="mt-6">
                <ProfessionalCard>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>{t('settings.discount_rules')}</CardTitle>
                      <Button onClick={openCreateDialog} size="sm">
                        <Plus className="h-4 w-4 mr-2" />
                        {t('settings.tabs.add_rule')}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {loadingDiscountRules ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin mr-2" />
                        <span className="text-sm text-muted-foreground">{t('settings.loading_discount_rules')}</span>
                      </div>
                    ) : discountRules.length === 0 ? (
                      <div className="text-center py-8">
                        <p className="text-muted-foreground mb-4">{t('settings.no_discount_rules_configured')}</p>
                        <p className="text-sm text-muted-foreground">
                          {t('settings.create_discount_rules_to_apply_discounts')}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {discountRules.map((rule) => (
                          <div key={rule.id} className="flex items-center justify-between p-4 border rounded-lg">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <h4 className="font-medium">{rule.name}</h4>
                                <Badge variant={rule.is_active ? "default" : "secondary"}>
                                  {rule.is_active ? t('settings.rule_active') : t('settings.rule_inactive')}
                                </Badge>
                                <Badge variant="outline" className="font-semibold">
                                  {t('settings.priority')}: {rule.priority}
                                </Badge>
                                {/* Show currency badge */}
                                <Badge variant="secondary">{rule.currency || "USD"}</Badge>
                              </div>
                              <p className="text-sm text-muted-foreground">
                                {rule.discount_type === "percentage"
                                  ? `${rule.discount_value}% ${t('settings.discount')}`
                                  : `$${rule.discount_value} ${t('settings.discount')}`
                                } {t('settings.when_total')} ≥ ${rule.min_amount}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openEditDialog(rule)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDeleteDiscountRule(rule.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="ai-config" className="mt-6">
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle>{t('settings.ai_configuration')}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* AI Assistant Toggle */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="ai_assistant">{t('settings.ai_assistant')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.ai_assistant_description')}</p>
                          {!isFeatureEnabled('ai_chat') && (
                            <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                              {t('settings.ai_assistant_license_required', 'AI Assistant requires a valid license. Please upgrade your plan.')}
                            </p>
                          )}
                        </div>
                        <Switch
                          id="ai_assistant"
                          checked={aiAssistantEnabled}
                          onCheckedChange={handleAIAssistantToggle}
                          disabled={!isFeatureEnabled('ai_chat') && !aiAssistantEnabled}
                        />
                      </div>
                    </div>

                    {/* AI Provider Configurations */}
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <div>
                          <h3 className="text-lg font-semibold">{t('settings.ai_provider_configurations')}</h3>
                          <p className="text-sm text-muted-foreground">{t('settings.ai_provider_configurations_description')}</p>
                        </div>
                        <Button onClick={openCreateAIConfigDialog}>
                          <Plus className="h-4 w-4 mr-2" />
                          {t('settings.add_provider')}
                        </Button>
                      </div>

                      {loadingAiConfigs ? (
                        <div className="flex justify-center py-8">
                          <Loader2 className="h-8 w-8 animate-spin" />
                        </div>
                      ) : aiConfigs.length === 0 ? (
                        <div className="text-center py-8">
                          <p className="text-muted-foreground">{t('settings.no_ai_configurations')}</p>
                          <p className="text-sm text-muted-foreground mt-2">
                            {t('settings.add_ai_providers_hint')}
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {aiConfigs.map((config) => (
                            <div key={config.id} className="flex items-center justify-between p-4 border rounded-lg">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-medium">{config.provider_name}</h4>
                                  <Badge variant={config.is_active ? "default" : "secondary"}>
                                    {config.is_active ? t('settings.active') : t('settings.inactive')}
                                  </Badge>
                                  {config.is_default && (
                                    <Badge variant="outline">{t('settings.default')}</Badge>
                                  )}
                                  {config.tested && (
                                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                                      {t('settings.tested')}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground">
                                  {t('settings.model')}: {config.model_name}
                                  {config.provider_url && ` | ${t('settings.url')}: ${config.provider_url}`}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleTestAIConfig(config.id)}
                                >
                                  {t('settings.test')}
                                </Button>
                                {!config.tested && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleMarkAsTested(config.id)}
                                  >
                                    {t('settings.mark_tested')}
                                  </Button>
                                )}
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => openEditAIConfigDialog(config)}
                                >
                                  <Edit className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleDeleteAIConfig(config.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="search" className="mt-6">
                <SearchStatus />
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="email-notifications" className="mt-6">
                <div className="space-y-6">
                  {/* Email Configuration Section */}
                  <ProfessionalCard>
                    <CardHeader>
                      <CardTitle>{t('settings.email_configuration')}</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Configure your email service provider and settings
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                          <Label htmlFor="email_enabled">{t('settings.enable_email_service')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.enable_email_service_description')}</p>
                        </div>
                        <Switch
                          id="email_enabled"
                          checked={emailSettings.enabled}
                          onCheckedChange={(checked) => handleEmailToggleChange('enabled', checked)}
                        />
                      </div>

                      {emailSettings.enabled && (
                        <>
                          <div className="space-y-2">
                            <Label htmlFor="provider">{t('settings.email_provider')}</Label>
                            <Select value={emailSettings.provider} onValueChange={handleEmailProviderChange}>
                              <SelectTrigger>
                                <SelectValue placeholder={t('settings.select_email_provider')} />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="aws_ses">{t('settings.aws_ses')}</SelectItem>
                                <SelectItem value="azure_email">{t('settings.azure_email_services')}</SelectItem>
                                <SelectItem value="mailgun">{t('settings.mailgun')}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                              <Label htmlFor="from_name">{t('settings.from_name')}</Label>
                              <Input
                                id="from_name"
                                name="from_name"
                                value={emailSettings.from_name}
                                onChange={handleEmailChange}
                              />
                            </div>

                            <div className="space-y-2">
                              <Label htmlFor="from_email">{t('settings.from_email')}</Label>
                              <Input
                                id="from_email"
                                name="from_email"
                                type="email"
                                value={emailSettings.from_email}
                                onChange={handleEmailChange}
                              />
                            </div>
                          </div>

                          {emailSettings.provider === "aws_ses" && (
                            <div className="space-y-4 p-4 border rounded-lg">
                              <h4 className="font-medium">{t('settings.aws_ses_configuration')}</h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                  <Label htmlFor="aws_access_key_id">{t('settings.aws_access_key_id')}</Label>
                                  <Input
                                    id="aws_access_key_id"
                                    name="aws_access_key_id"
                                    type="password"
                                    value={emailSettings.aws_access_key_id}
                                    onChange={handleEmailChange}
                                  />
                                </div>
                                <div className="space-y-2">
                                  <Label htmlFor="aws_secret_access_key">{t('settings.aws_secret_access_key')}</Label>
                                  <Input
                                    id="aws_secret_access_key"
                                    name="aws_secret_access_key"
                                    type="password"
                                    value={emailSettings.aws_secret_access_key}
                                    onChange={handleEmailChange}
                                  />
                                </div>
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="aws_region">{t('settings.aws_region')}</Label>
                                <Select value={emailSettings.aws_region} onValueChange={(value) => setEmailSettings(prev => ({ ...prev, aws_region: value }))}>
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="us-east-1">{t('settings.us_east_virginia')}</SelectItem>
                                    <SelectItem value="us-west-2">{t('settings.us_west_oregon')}</SelectItem>
                                    <SelectItem value="eu-west-1">{t('settings.eu_ireland')}</SelectItem>
                                    <SelectItem value="ap-southeast-1">{t('settings.asia_pacific_singapore')}</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                          )}

                          {emailSettings.provider === "azure_email" && (
                            <div className="space-y-4 p-4 border rounded-lg">
                              <h4 className="font-medium">{t('settings.azure_email_services_configuration')}</h4>
                              <div className="space-y-2">
                                <Label htmlFor="azure_connection_string">{t('settings.azure_connection_string')}</Label>
                                <Input
                                  id="azure_connection_string"
                                  name="azure_connection_string"
                                  type="password"
                                  value={emailSettings.azure_connection_string}
                                  onChange={handleEmailChange}
                                />
                              </div>
                            </div>
                          )}

                          {emailSettings.provider === "mailgun" && (
                            <div className="space-y-4 p-4 border rounded-lg">
                              <h4 className="font-medium">{t('settings.mailgun_configuration')}</h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                  <Label htmlFor="mailgun_api_key">{t('settings.mailgun_api_key')}</Label>
                                  <Input
                                    id="mailgun_api_key"
                                    name="mailgun_api_key"
                                    type="password"
                                    value={emailSettings.mailgun_api_key}
                                    onChange={handleEmailChange}
                                  />
                                </div>
                                <div className="space-y-2">
                                  <Label htmlFor="mailgun_domain">{t('settings.mailgun_domain')}</Label>
                                  <Input
                                    id="mailgun_domain"
                                    name="mailgun_domain"
                                    value={emailSettings.mailgun_domain}
                                    onChange={handleEmailChange}
                                  />
                                </div>
                              </div>
                            </div>
                          )}

                          <div className="flex justify-between pt-4 border-t">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={testEmailConfiguration}
                            >
                              {t('settings.test_configuration')}
                            </Button>
                            <Button onClick={handleSave} disabled={saving}>
                              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                              {t('settings.save_email_settings')}
                            </Button>
                          </div>
                        </>
                      )}
                    </CardContent>
                  </ProfessionalCard>

                  {/* Notification Settings Section */}
                  <ProfessionalCard>
                    <CardHeader>
                      <CardTitle>{t('settings.notification_settings_title')}</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {t('settings.notification_settings_description')}
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {loadingNotifications ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          <span className="text-sm text-muted-foreground">{t('settings.loading_notification_settings')}</span>
                        </div>
                      ) : (
                        <>
                          {/* Custom notification email */}
                          <div className="space-y-2">
                            <Label htmlFor="notification_email">Notification Email (Optional)</Label>
                            <Input
                              id="notification_email"
                              type="email"
                              value={notificationSettings.notification_email}
                              onChange={handleNotificationEmailChange}
                              placeholder="Leave empty to use your account email"
                            />
                            <p className="text-sm text-muted-foreground">
                              If specified, notifications will be sent to this email instead of your account email
                            </p>
                          </div>

                          {/* User Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">User Operations</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>User Created</Label>
                                  <p className="text-sm text-muted-foreground">When a new user is added</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.user_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('user_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>User Updated</Label>
                                  <p className="text-sm text-muted-foreground">When user info is modified</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.user_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('user_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>User Deleted</Label>
                                  <p className="text-sm text-muted-foreground">When a user is removed</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.user_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('user_deleted', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>User Login</Label>
                                  <p className="text-sm text-muted-foreground">When a user logs in</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.user_login}
                                  onCheckedChange={(checked) => handleNotificationToggle('user_login', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Client Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">Client Operations</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Client Created</Label>
                                  <p className="text-sm text-muted-foreground">When a new client is added</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.client_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('client_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Client Updated</Label>
                                  <p className="text-sm text-muted-foreground">When client info is modified</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.client_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('client_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Client Deleted</Label>
                                  <p className="text-sm text-muted-foreground">When a client is removed</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.client_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('client_deleted', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Invoice Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">Invoice Operations</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Created</Label>
                                  <p className="text-sm text-muted-foreground">When a new invoice is created</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Updated</Label>
                                  <p className="text-sm text-muted-foreground">When invoice is modified</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Deleted</Label>
                                  <p className="text-sm text-muted-foreground">When an invoice is deleted</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_deleted', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Sent</Label>
                                  <p className="text-sm text-muted-foreground">When invoice is sent to client</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_sent}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_sent', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Paid</Label>
                                  <p className="text-sm text-muted-foreground">When invoice is marked as paid</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_paid}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_paid', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Invoice Overdue</Label>
                                  <p className="text-sm text-muted-foreground">When invoice becomes overdue</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.invoice_overdue}
                                  onCheckedChange={(checked) => handleNotificationToggle('invoice_overdue', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Payment Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">Payment Operations</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Payment Created</Label>
                                  <p className="text-sm text-muted-foreground">When a payment is recorded</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.payment_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('payment_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Payment Updated</Label>
                                  <p className="text-sm text-muted-foreground">When payment is modified</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.payment_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('payment_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>Payment Deleted</Label>
                                  <p className="text-sm text-muted-foreground">When a payment is removed</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.payment_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('payment_deleted', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Expense Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">{t('settings.expense_operations')}</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_created')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_created_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_updated')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_updated_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_deleted')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_deleted_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_deleted', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_approved')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_approved_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_approved}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_approved', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_rejected')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_rejected_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_rejected}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_rejected', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.expense_submitted')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.expense_submitted_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.expense_submitted}
                                  onCheckedChange={(checked) => handleNotificationToggle('expense_submitted', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Inventory Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">{t('settings.inventory_operations')}</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.inventory_created')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.inventory_created_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.inventory_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('inventory_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.inventory_updated')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.inventory_updated_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.inventory_updated}
                                  onCheckedChange={(checked) => handleNotificationToggle('inventory_updated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.inventory_deleted')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.inventory_deleted_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.inventory_deleted}
                                  onCheckedChange={(checked) => handleNotificationToggle('inventory_deleted', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.inventory_low_stock')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.inventory_low_stock_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.inventory_low_stock}
                                  onCheckedChange={(checked) => handleNotificationToggle('inventory_low_stock', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.inventory_out_of_stock')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.inventory_out_of_stock_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.inventory_out_of_stock}
                                  onCheckedChange={(checked) => handleNotificationToggle('inventory_out_of_stock', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Statement Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">{t('settings.statement_operations')}</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.statement_generated')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.statement_generated_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.statement_generated}
                                  onCheckedChange={(checked) => handleNotificationToggle('statement_generated', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.statement_sent')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.statement_sent_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.statement_sent}
                                  onCheckedChange={(checked) => handleNotificationToggle('statement_sent', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.statement_overdue')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.statement_overdue_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.statement_overdue}
                                  onCheckedChange={(checked) => handleNotificationToggle('statement_overdue', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Reminder Operations */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">{t('settings.reminder_operations')}</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.reminder_created')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.reminder_created_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.reminder_created}
                                  onCheckedChange={(checked) => handleNotificationToggle('reminder_created', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.reminder_sent')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.reminder_sent_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.reminder_sent}
                                  onCheckedChange={(checked) => handleNotificationToggle('reminder_sent', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.reminder_overdue')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.reminder_overdue_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.reminder_overdue}
                                  onCheckedChange={(checked) => handleNotificationToggle('reminder_overdue', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Summary Notifications */}
                          <div className="space-y-4">
                            <h3 className="text-lg font-semibold">Summary Notifications</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.daily_summary')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.daily_summary_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.daily_summary}
                                  onCheckedChange={(checked) => handleNotificationToggle('daily_summary', checked)}
                                />
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="space-y-0.5">
                                  <Label>{t('settings.weekly_summary')}</Label>
                                  <p className="text-sm text-muted-foreground">{t('settings.weekly_summary_description')}</p>
                                </div>
                                <Switch
                                  checked={notificationSettings.weekly_summary}
                                  onCheckedChange={(checked) => handleNotificationToggle('weekly_summary', checked)}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Action buttons */}
                          <div className="flex justify-between pt-4 border-t">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={handleTestNotification}
                            >
                              {t('settings.send_test_notification')}
                            </Button>
                            <Button
                              onClick={handleSaveNotifications}
                              disabled={savingNotifications}
                            >
                              {savingNotifications && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                              {t('settings.save_notification_settings')}
                            </Button>
                          </div>
                        </>
                      )}
                    </CardContent>
                  </ProfessionalCard>
                </div>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="email-integration" className="mt-6">
                <EmailIntegrationSettings />
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="tax-integration" className="mt-6">
                <div className="space-y-6">
                  {/* Tax Service Configuration Section */}
                  <ProfessionalCard>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Calculator className="h-5 w-5" />
                        {t('taxIntegration.configuration.title')}
                      </CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {t('taxIntegration.configuration.description')}
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Always show configuration fields so users can test before enabling */}
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="space-y-2">
                            <Label htmlFor="tax_base_url">{t('taxIntegration.configuration.baseUrl')}</Label>
                            <Input
                              id="tax_base_url"
                              type="url"
                              value={taxSettings.base_url}
                              onChange={(e) => setTaxSettings(prev => ({ ...prev, base_url: e.target.value }))}
                              placeholder="https://api.tax-service.com"
                            />
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="tax_api_key">{t('taxIntegration.configuration.apiKey')}</Label>
                            <Input
                              id="tax_api_key"
                              type="password"
                              value={taxSettings.api_key}
                              onChange={(e) => setTaxSettings(prev => ({ ...prev, api_key: e.target.value }))}
                              placeholder={t('taxIntegration.configuration.apiKeyPlaceholder')}
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div className="space-y-2">
                            <Label htmlFor="tax_timeout">{t('taxIntegration.configuration.timeout')}</Label>
                            <Input
                              id="tax_timeout"
                              type="number"
                              min="1"
                              max="300"
                              value={taxSettings.timeout}
                              onChange={(e) => setTaxSettings(prev => ({ ...prev, timeout: parseInt(e.target.value) || 30 }))}
                            />
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="tax_retry_attempts">{t('taxIntegration.configuration.retryAttempts')}</Label>
                            <Input
                              id="tax_retry_attempts"
                              type="number"
                              min="0"
                              max="10"
                              value={taxSettings.retry_attempts}
                              onChange={(e) => setTaxSettings(prev => ({ ...prev, retry_attempts: parseInt(e.target.value) || 3 }))}
                            />
                          </div>
                        </div>

                        {/* Test Results */}
                        {taxTestResult && (
                          <div className={`p-3 rounded-md text-sm ${taxTestResult.success
                            ? 'bg-green-50 text-green-800 border border-green-200'
                            : 'bg-red-50 text-red-800 border border-red-200'
                            }`}>
                            <div className="flex items-center gap-2">
                              {taxTestResult.success ? (
                                <CheckCircle className="h-4 w-4" />
                              ) : (
                                <XCircle className="h-4 w-4" />
                              )}
                              <span>{taxTestResult.message}</span>
                            </div>
                          </div>
                        )}

                        {taxConnectionTested && (
                          <div className="p-3 rounded-md text-sm bg-green-50 text-green-800 border border-green-200">
                            <div className="flex items-center gap-2">
                              <CheckCircle className="h-4 w-4" />
                              <span>{t('taxIntegration.configuration.connectionTestedSuccess')}</span>
                            </div>
                          </div>
                        )}

                        {/* Action Buttons */}
                        <div className="flex justify-end gap-3 pt-4">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => handleTestTaxConnection()}
                            disabled={testingTaxConnection || !taxSettings.base_url}
                          >
                            {testingTaxConnection && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {t('taxIntegration.configuration.testConnection')}
                          </Button>
                          <Button
                            onClick={handleSaveTaxSettings}
                            disabled={saving}
                          >
                            {saving ? (
                              <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                {t('taxIntegration.configuration.saving')}
                              </>
                            ) : (
                              t('taxIntegration.configuration.saveTaxSettings')
                            )}
                          </Button>
                        </div>

                      </>
                    </CardContent>
                  </ProfessionalCard>

                  {/* Tax Integration Status Section */}
                  <ProfessionalCard>
                    <CardHeader>
                      <CardTitle>{t('taxIntegration.configuration.integrationStatus')}</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        {t('taxIntegration.configuration.integrationStatusDescription')}
                      </p>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
                          <div className="text-2xl font-bold text-blue-600">
                            {taxSettings.enabled ? '✅' : '❌'}
                          </div>
                          <h3 className="font-medium text-blue-900 mt-2">{t('taxIntegration.configuration.serviceStatus')}</h3>
                          <p className="text-sm text-blue-700 mt-1">
                            {taxSettings.enabled ? t('taxIntegration.configuration.enabled') : t('taxIntegration.configuration.disabled')}
                          </p>
                        </div>
                        <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                          <div className="text-2xl font-bold text-green-600">🔗</div>
                          <h3 className="font-medium text-green-900 mt-2">{t('taxIntegration.configuration.apiConnection')}</h3>
                          <p className="text-sm text-green-700 mt-1">
                            {taxTestResult?.success ? t('taxIntegration.configuration.connected') : t('taxIntegration.configuration.notTested')}
                          </p>
                        </div>
                        <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
                          <div className="text-2xl font-bold text-purple-600">⚙️</div>
                          <h3 className="font-medium text-purple-900 mt-2">{t('taxIntegration.configuration.configuration')}</h3>
                          <p className="text-sm text-purple-700 mt-1">
                            {taxSettings.base_url ? t('taxIntegration.configuration.configured') : t('taxIntegration.configuration.notConfigured')}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </ProfessionalCard>
                </div>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="export-destinations" className="mt-6">
                <ExportDestinationsTab isAdmin={isAdmin} />
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="license" className="mt-6">
                <LicenseManagement />
              </TabsContent>
            )}

            <TabsContent value="cookies" className="space-y-6">
              <CookieSettings />
            </TabsContent>

            {isAdmin && (
              <TabsContent value="export" className="space-y-6">
                {/* Data Overview Section */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Database className="h-5 w-5" />
                      {t('settings.data_management')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.data_management_description')}
                    </p>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="text-2xl font-bold text-blue-600">📊</div>
                        <h3 className="font-medium text-blue-900 mt-2">{t('settings.complete_backup')}</h3>
                        <p className="text-sm text-blue-700 mt-1">{t('settings.complete_backup_description')}</p>
                      </div>
                      <div className="text-center p-4 bg-green-50 rounded-lg border border-green-200">
                        <div className="text-2xl font-bold text-green-600">🔄</div>
                        <h3 className="font-medium text-green-900 mt-2">{t('settings.easy_restore')}</h3>
                        <p className="text-sm text-green-700 mt-1">{t('settings.easy_restore_description')}</p>
                      </div>
                      <div className="text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
                        <div className="text-2xl font-bold text-purple-600">🔒</div>
                        <h3 className="font-medium text-purple-900 mt-2">{t('settings.data_control')}</h3>
                        <p className="text-sm text-purple-700 mt-1">{t('settings.data_control_description')}</p>
                      </div>
                    </div>
                  </CardContent>
                </ProfessionalCard>

                {/* Export Section */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Download className="h-5 w-5" />
                      {t('settings.export_data')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.export_data_description')}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-3">{t('settings.what_will_be_exported')}</h4>
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                              <span>{t('settings.client_information')}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                              <span>{t('settings.complete_invoice_history')}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                              <span>{t('settings.payment_records')}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                              <span>{t('settings.client_notes')}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-gray-500 rounded-full"></div>
                              <span>{t('settings.company_settings')}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                              <span>Expenses & Receipts</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
                              <span>Statements & Transactions</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>
                              <span>Audit Logs & Activity History</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <div className="w-2 h-2 bg-pink-500 rounded-full"></div>
                              <span>AI Chat History</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-3">{t('settings.export_details')}</h4>
                          <div className="space-y-2 text-sm text-muted-foreground">
                            <p><strong>{t('settings.format')}:</strong> {t('settings.sqlite_database')}</p>
                            <p><strong>{t('settings.compatibility')}:</strong> {t('settings.works_with_database_tools')}</p>
                            <p><strong>{t('settings.security')}:</strong> {t('settings.no_sensitive_authentication_data')}</p>
                            <p><strong>{t('settings.size')}:</strong> {t('settings.size_description')}</p>
                            <p><strong>Note:</strong> Attachment files (receipts, bank statements, invoice attachments) are not included in the export. Only database records are exported.</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="border-t pt-4">
                      <Button
                        onClick={handleExportData}
                        disabled={exporting}
                        size="lg"
                        className="w-full sm:w-auto"
                      >
                        {exporting ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            {t('settings.creating_export')}
                          </>
                        ) : (
                          <>
                            <Download className="mr-2 h-4 w-4" />
                            {t('settings.download_complete_backup')}
                          </>
                        )}
                      </Button>
                      <p className="text-xs text-muted-foreground mt-2">
                        {t('settings.export_includes_all_data')}
                      </p>
                    </div>
                  </CardContent>
                </ProfessionalCard>

                {/* Import Section */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Upload className="h-5 w-5" />
                      {t('settings.import_data')}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.import_data_description')}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                      <div className="flex items-start gap-3">
                        <div className="text-amber-600 text-lg">⚠️</div>
                        <div>
                          <h4 className="font-medium text-amber-900 mb-1">{t('settings.important_warning')}</h4>
                          <p className="text-sm text-amber-800">
                            {t('settings.importing_data_warning_strong')}
                            {t('settings.importing_data_warning_cannot_be_undone')}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div className="space-y-4">
                        <div>
                          <Label htmlFor="import-file" className="text-base font-medium">{t('settings.select_backup_file')}</Label>
                          <p className="text-sm text-muted-foreground mb-3">
                            {t('settings.choose_sqlite_file')}
                          </p>
                          <Input
                            id="import-file"
                            type="file"
                            accept=".sqlite"
                            onChange={handleFileSelect}
                            disabled={importing}
                            className="cursor-pointer"
                          />
                          {selectedFile && (
                            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                              <div className="flex items-center gap-2 text-sm">
                                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                <span className="font-medium">{t('settings.file_selected')}:</span>
                              </div>
                              <p className="text-sm text-green-700 mt-1">
                                {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} {t('settings.mb')})
                              </p>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <h4 className="font-medium mb-3">{t('settings.import_process')}</h4>
                          <div className="space-y-2 text-sm text-muted-foreground">
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                              <span>{t('settings.file_validation_and_structure_check')}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                              <span>{t('settings.current_data_backup_and_removal')}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                              <span>{t('settings.import_new_data_with_id_mapping')}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full"></div>
                              <span>{t('settings.data_integrity_verification')}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="border-t pt-4">
                      <div className="flex flex-col sm:flex-row gap-3">
                        <Button
                          onClick={handleExportData}
                          disabled={exporting || importing}
                          variant="outline"
                          size="lg"
                        >
                          {exporting ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              {t('settings.creating_backup')}
                            </>
                          ) : (
                            <>
                              <Download className="mr-2 h-4 w-4" />
                              {t('settings.backup_current_data_first')}
                            </>
                          )}
                        </Button>

                        <Button
                          onClick={handleImportData}
                          disabled={importing || !selectedFile}
                          variant="destructive"
                          size="lg"
                        >
                          {importing ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              {t('settings.importing_data')}
                            </>
                          ) : (
                            <>
                              <Upload className="mr-2 h-4 w-4" />
                              {t('settings.import_and_replace_data')}
                            </>
                          )}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground mt-2">
                        {t('settings.recommended_backup_hint')}
                      </p>
                    </div>
                  </CardContent>
                </ProfessionalCard>

                {/* Best Practices Section */}
                <ProfessionalCard>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <span className="text-lg">💡</span>
                      {t('settings.best_practices_and_tips')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div>
                        <h4 className="font-medium mb-3 text-green-700">{t('settings.recommended_practices')}</h4>
                        <ul className="space-y-2 text-sm text-muted-foreground">
                          <li className="flex items-start gap-2">
                            <span className="text-green-500 mt-0.5">•</span>
                            <span>{t('settings.create_regular_backups')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-green-500 mt-0.5">•</span>
                            <span>{t('settings.always_backup_before_importing')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-green-500 mt-0.5">•</span>
                            <span>{t('settings.store_backup_files_in_multiple_safe_locations')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-green-500 mt-0.5">•</span>
                            <span>{t('settings.test_imports_in_a_separate_environment_first')}</span>
                          </li>
                        </ul>
                      </div>

                      <div>
                        <h4 className="font-medium mb-3 text-blue-700">{t('settings.technical_information')}</h4>
                        <ul className="space-y-2 text-sm text-muted-foreground">
                          <li className="flex items-start gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            <span>{t('settings.sqlite_files_can_be_opened_with_db_browser')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            <span>{t('settings.data_can_be_used_programmatically_in_custom_applications')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            <span>{t('settings.import_validates_file_structure_before_processing')}</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="text-blue-500 mt-0.5">•</span>
                            <span>{t('settings.new_invoice_numbers_are_generated_to_avoid_conflicts')}</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </ProfessionalCard>
              </TabsContent>
            )}

            {isAdmin && (
              <TabsContent value="api-keys" className="mt-6">
                <APIClientManagement />
              </TabsContent>
            )}
          </Tabs>
        </ContentSection>

        {/* AI Configuration Dialog */}
        <Dialog open={showAIConfigDialog} onOpenChange={setShowAIConfigDialog}>
          <DialogContent className="sm:max-w-[650px]">
            <DialogHeader>
              <DialogTitle>
                {editingAIConfig ? t('settings.edit_ai_configuration') : t('settings.add_ai_configuration')}
              </DialogTitle>
              <DialogDescription>
                {t('settings.configure_ai_provider_for_enhanced_features')}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="provider_name">{t('settings.provider')}</Label>
                  <Select
                    value={newAIConfig.provider_name}
                    onValueChange={handleProviderChange}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('settings.select_provider')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">{t('settings.openai')}</SelectItem>
                      <SelectItem value="openrouter">OpenRouter</SelectItem>
                      <SelectItem value="ollama">{t('settings.ollama')}</SelectItem>
                      <SelectItem value="anthropic">{t('settings.anthropic')}</SelectItem>
                      <SelectItem value="google">{t('settings.google')}</SelectItem>
                      <SelectItem value="custom">{t('settings.custom')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="model_name">{t('settings.model')}</Label>
                  <Input
                    id="model_name"
                    name="model_name"
                    value={newAIConfig.model_name}
                    onChange={handleAIConfigChange}
                    placeholder={
                      newAIConfig.provider_name === "openai" ? t('settings.openai_model_example') :
                        newAIConfig.provider_name === "openrouter" ? "openai/gpt-4, anthropic/claude-3-sonnet" :
                          newAIConfig.provider_name === "ollama" ? t('settings.ollama_model_example') :
                            newAIConfig.provider_name === "anthropic" ? t('settings.anthropic_model_example') :
                              newAIConfig.provider_name === "google" ? t('settings.google_model_example') :
                                t('settings.model_name_example')
                    }
                  />
                  <p className="text-sm text-muted-foreground">
                    {newAIConfig.provider_name === "openai" && t('settings.openai_model_hint')}
                    {newAIConfig.provider_name === "openrouter" && "Access 100+ models via OpenRouter. Use format: provider/model (e.g., openai/gpt-4, anthropic/claude-3-sonnet)"}
                    {newAIConfig.provider_name === "ollama" && t('settings.ollama_model_hint')}
                    {newAIConfig.provider_name === "anthropic" && t('settings.anthropic_model_hint')}
                    {newAIConfig.provider_name === "google" && t('settings.google_model_hint')}
                    {newAIConfig.provider_name === "custom" && t('settings.custom_model_hint')}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="provider_url">{t('settings.provider_url_optional')}</Label>
                <Input
                  id="provider_url"
                  name="provider_url"
                  value={newAIConfig.provider_url}
                  onChange={handleAIConfigChange}
                  placeholder={t('settings.provider_url_placeholder')}
                />
                <p className="text-sm text-muted-foreground">
                  {t('settings.leave_empty_for_default_endpoints')}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="api_key">
                  {t('settings.api_key')}
                  {!providerRequiresApiKey(newAIConfig.provider_name) && (
                    <span className="text-sm text-muted-foreground ml-1">(Optional)</span>
                  )}
                </Label>
                <Input
                  id="api_key"
                  name="api_key"
                  type="password"
                  value={newAIConfig.api_key}
                  onChange={handleAIConfigChange}
                  placeholder={
                    providerRequiresApiKey(newAIConfig.provider_name)
                      ? t('settings.enter_api_key')
                      : "Optional - leave empty for local providers"
                  }
                />
              </div>

              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="is_active"
                    checked={newAIConfig.is_active}
                    onCheckedChange={(checked) => handleAIConfigToggleChange('is_active', checked)}
                  />
                  <Label htmlFor="is_active">{t('settings.active')}</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Switch
                    id="is_default"
                    checked={newAIConfig.is_default}
                    onCheckedChange={(checked) => handleAIConfigToggleChange('is_default', checked)}
                  />
                  <Label htmlFor="is_default">{t('settings.default_provider')}</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Switch
                    id="tested"
                    checked={newAIConfig.tested}
                    onCheckedChange={(checked) => handleAIConfigToggleChange('tested', checked)}
                  />
                  <Label htmlFor="tested">{t('settings.mark_as_tested')}</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Switch
                    id="ocr_enabled"
                    checked={newAIConfig.ocr_enabled || false}
                    onCheckedChange={(checked) => handleAIConfigToggleChange('ocr_enabled', checked)}
                  />
                  <Label htmlFor="ocr_enabled">OCR Enabled</Label>
                </div>
              </div>

              {/* Test Result Display */}
              {testResult && (
                <div className={`p-3 rounded-lg border ${testResult.success
                  ? 'bg-green-50 border-green-200 text-green-800'
                  : 'bg-red-50 border-red-200 text-red-800'
                  }`}>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${testResult.success ? 'bg-green-500' : 'bg-red-500'
                      }`}></div>
                    <span className="font-medium">
                      {testResult.success ? 'Test Successful' : 'Test Failed'}
                    </span>
                  </div>
                  <p className="text-sm mt-1">{testResult.message}</p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setShowAIConfigDialog(false)}>
                {t('settings.cancel')}
              </Button>
              <Button
                variant="outline"
                onClick={handleTestNewAIConfig}
                disabled={testingNewConfig || !newAIConfig.model_name || (providerRequiresApiKey(newAIConfig.provider_name) && !newAIConfig.api_key)}
              >
                {testingNewConfig ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('common.loading')}
                  </>
                ) : (
                  t('settings.test')
                )}
              </Button>
              <Button
                onClick={editingAIConfig ? handleUpdateAIConfig : handleCreateAIConfig}
              >
                {editingAIConfig ? t('settings.update') : t('settings.create')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Discount Rule Dialog */}
        <Dialog open={showDiscountRuleDialog} onOpenChange={setShowDiscountRuleDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {editingDiscountRule ? t('settings.edit_discount_rule') : t('settings.create_discount_rule')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="rule-name">{t('settings.rule_name')}</Label>
                <Input
                  id="rule-name"
                  value={newDiscountRule.name}
                  onChange={(e) => setNewDiscountRule(prev => ({ ...prev, name: e.target.value }))}
                  placeholder={t('settings.rule_name_placeholder')}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="min-amount">{t('settings.min_amount')}</Label>
                  <Input
                    id="min-amount"
                    type="number"
                    min="0"
                    step="0.01"
                    value={newDiscountRule.min_amount}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, min_amount: parseFloat(e.target.value) || 0 }))}
                    placeholder={t('settings.min_amount_placeholder')}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="priority">{t('settings.priority')}</Label>
                  <Input
                    id="priority"
                    type="number"
                    min="0"
                    value={newDiscountRule.priority}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, priority: parseInt(e.target.value) || 0 }))}
                    placeholder={t('settings.priority_placeholder')}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="discount-type">{t('settings.discount_type')}</Label>
                  <Select
                    value={newDiscountRule.discount_type}
                    onValueChange={(value: 'percentage' | 'fixed') =>
                      setNewDiscountRule(prev => ({ ...prev, discount_type: value }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percentage">{t('settings.percentage_discount')}</SelectItem>
                      <SelectItem value="fixed">{t('settings.fixed_amount_discount')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="discount-value">{t('settings.discount_value')}</Label>
                  <Input
                    id="discount-value"
                    type="number"
                    min="0"
                    step={newDiscountRule.discount_type === "percentage" ? "0.01" : "0.01"}
                    value={newDiscountRule.discount_value}
                    onChange={(e) => setNewDiscountRule(prev => ({ ...prev, discount_value: parseFloat(e.target.value) || 0 }))}
                    placeholder={newDiscountRule.discount_type === "percentage" ? t('settings.percentage_discount_value_placeholder') : t('settings.fixed_amount_discount_value_placeholder')}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="currency">{t('settings.currency')}</Label>
                <CurrencySelector
                  value={newDiscountRule.currency || "USD"}
                  onValueChange={(value) => setNewDiscountRule(prev => ({ ...prev, currency: value }))}
                />
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="is-active"
                  checked={newDiscountRule.is_active}
                  onCheckedChange={(checked) => setNewDiscountRule(prev => ({ ...prev, is_active: checked }))}
                />
                <Label htmlFor="is-active">{t('settings.active')}</Label>
              </div>

              <div className="flex justify-end space-x-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowDiscountRuleDialog(false)}
                >
                  {t('settings.cancel')}
                </Button>
                <Button
                  onClick={editingDiscountRule ? handleUpdateDiscountRule : handleCreateDiscountRule}
                >
                  {editingDiscountRule ? t('settings.update_rule') : t('settings.create_rule')}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
};

export default Settings;
